"""Replay measured failures in a lab with FRR's flooding, CSNP/PSNP and SPF debug logs, to see how each router got
each new LSP after a router or several links fail.

For one topology file and a list of events (as `measure` stores them: {"kind", "links": [{a, a_port, b, b_port}],
"router"}), and for flood reduction off and/or on: write the lab with `debug isis flooding`, update-packet timing
logs, `debug isis snp-packets` and `debug isis spf-events`; deploy it with the netns backend (run as root, or inside
`unshare -Urnm`); wait for convergence; for each event take its links down, wait `--window` seconds, bring them up
and wait for convergence; then save every router's log from just before the first event, events.txt and the lab.

    unshare -Urnm python3 collect_events.py --out mech --topology t.json --events events.json --reduction both
"""
import argparse
import json
import os
import sys
import time

from collect_decisions import wait_converged

from topology_builders import clab as C
from topology_builders import measure as M

EXTRA_DEBUG = ["debug isis snp-packets", "debug isis spf-events"]


def add_debug(lab_dir, routers):
    """Insert the extra debug lines after the timing-log lines of every router's frr.conf."""
    for r in routers:
        p = os.path.join(lab_dir, r, "frr.conf")
        with open(p, encoding="utf-8") as fh:
            conf = fh.read()
        anchor = "debug isis update-packets\n"
        if anchor not in conf:
            raise ValueError(f"{p}: no timing-log lines (write the lab with timing_logs)")
        conf = conf.replace(anchor, anchor + "".join(line + "\n" for line in EXTRA_DEBUG), 1)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(conf)


def run(topology, events, out, reduction, window, settle):
    name = f"{os.path.splitext(os.path.basename(topology))[0]}-{'on' if reduction else 'off'}"
    d = os.path.join(out, name)
    lab_dir = os.path.join(d, "lab")
    C.write_lab(topology, lab_dir, name=name, flood_reduction=reduction, debug_flooding=True, timing_logs=True)
    lab = M.NetnsLab(lab_dir)
    add_debug(lab_dir, lab.routers)
    lab.containerlab("deploy")
    try:
        time.sleep(settle)
        conv = wait_converged(lab, 900)
        print(f"{name}: {len(lab.routers)} routers converged after {conv} s more", flush=True)
        if conv is None:
            return False
        offsets = {r: os.path.getsize(lab.log_path(r)) for r in lab.routers}
        done = []
        for e in events:
            for state in ("down", "up"):
                t = lab.apply(e, state)
                done.append({"state": state, "time": t, **e})
                time.sleep(window)
            back = wait_converged(lab, 300)
            print(f"{name}: {e['kind']} event {e.get('router') or [x['a'] + '-' + x['b'] for x in e['links']]}: "
                  f"converged {back} s after the up window", flush=True)
        os.makedirs(os.path.join(d, "logs"), exist_ok=True)
        for r in lab.routers:
            with open(lab.log_path(r), "rb") as fh:
                fh.seek(offsets[r])
                data = fh.read().replace(b"\0", b"")
            with open(os.path.join(d, "logs", f"{r}.log"), "wb") as fh:
                fh.write(data)
        with open(os.path.join(d, "events.json"), "w", encoding="utf-8") as fh:
            json.dump(done, fh, indent=1)
        return True
    finally:
        lab.containerlab("destroy")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--topology", required=True)
    p.add_argument("--events", required=True, help="JSON list of events as measure stores them")
    p.add_argument("--out", required=True)
    p.add_argument("--reduction", choices=("on", "off", "both"), default="both")
    p.add_argument("--window", type=int, default=25, help="seconds after each change (default 25: > the 10 s CSNP "
                                                          "interval)")
    p.add_argument("--settle", type=int, default=30)
    a = p.parse_args(argv)
    with open(a.events, encoding="utf-8") as fh:
        events = json.load(fh)
    settings = {"on": [True], "off": [False], "both": [True, False]}[a.reduction]  # on first: the case
    # under study; off is the control
    ok = [run(a.topology, events, a.out, on, a.window, a.settle) for on in settings]
    sys.exit(0 if all(ok) else 1)


if __name__ == "__main__":
    main()
