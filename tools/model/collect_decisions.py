"""Collect FRR's flood-reduction decisions around link changes, for checking the flooding model decision by decision.

For each topology file: write a lab with flood reduction on, `debug isis flooding` and timing logs; deploy it with
the netns backend (run as root, or inside `unshare -Urnm`); wait for convergence; take `--links` links down and up
one at a time, `--window` seconds apart; then save every router's log from just before the first change, and the
lab's lab.json, under <out>/<topology name>/.

    unshare -Urnm python3 collect_decisions.py --out decisions topos/*.json
"""
import argparse
import os
import random
import shutil
import sys
import time

import networkx as nx

from topology_builders import clab as C
from topology_builders import measure as M


def pick(lab, n, seed):
    """n links whose removal, one at a time, leaves the graph connected."""
    g = nx.Graph((x["a"], x["b"]) for x in lab.lab["links"])
    links = list(lab.lab["links"])
    random.Random(seed).shuffle(links)
    out = []
    for x in links:
        h = g.copy()
        h.remove_edge(x["a"], x["b"])
        if nx.is_connected(h):
            out.append(x)
        if len(out) == n:
            break
    return out


def wait_converged(lab, limit):
    t0 = time.time()
    while time.time() - t0 < limit:
        if lab.converged()[0]:
            return round(time.time() - t0, 1)
        time.sleep(3)
    return None


def collect(src, out, links, window, settle, seed):
    name = os.path.splitext(os.path.basename(src))[0]
    d = os.path.join(out, name)
    C.write_lab(src, os.path.join(d, "lab"), name=name, flood_reduction=True, debug_flooding=True, timing_logs=True)
    lab = M.NetnsLab(os.path.join(d, "lab"))
    lab.containerlab("deploy")
    try:
        time.sleep(settle)
        conv = wait_converged(lab, 300)
        print(f"{name}: {len(lab.routers)} routers converged after {conv} s more", flush=True)
        if conv is None:
            return False
        offsets = {r: os.path.getsize(lab.log_path(r)) for r in lab.routers}
        chosen = pick(lab, links, seed)
        events = []
        for x in chosen:
            for state in ("down", "up"):
                t = time.time()
                lab.link(x["a"], x["a_port"], state)
                events.append({"a": x["a"], "b": x["b"], "a_port": x["a_port"], "state": state, "time": t})
                time.sleep(window)
        ok = wait_converged(lab, 120) is not None
        os.makedirs(os.path.join(d, "logs"), exist_ok=True)
        for r in lab.routers:
            with open(lab.log_path(r), "rb") as fh:
                fh.seek(offsets[r])
                data = fh.read().replace(b"\0", b"")
            with open(os.path.join(d, "logs", f"{r}.log"), "wb") as fh:
                fh.write(data)
        with open(os.path.join(d, "events.txt"), "w", encoding="utf-8") as fh:
            fh.writelines(f"{e['time']:.6f} {e['state']} {e['a']} {e['b']} {e['a_port']}\n" for e in events)
        print(f"{name}: {len(events)} changes, converged at the end: {ok}", flush=True)
        return ok
    finally:
        lab.containerlab("destroy")
        shutil.rmtree(os.path.join(d, "lab", "etc"), ignore_errors=True)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("topologies", nargs="+")
    p.add_argument("--out", required=True)
    p.add_argument("--links", type=int, default=3)
    p.add_argument("--window", type=int, default=12, help="seconds after each change (default 12)")
    p.add_argument("--settle", type=int, default=20)
    p.add_argument("--seed", type=int, default=1)
    a = p.parse_args(argv)
    ok = [collect(t, a.out, a.links, a.window, a.settle, a.seed) for t in a.topologies]
    sys.exit(0 if all(ok) else 1)


if __name__ == "__main__":
    main()
