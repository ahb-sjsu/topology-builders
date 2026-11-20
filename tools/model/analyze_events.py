"""How did each router get each new LSP after a router or several links failed? Reads what collect_events.py saved.

For every down event, and every router and new LSP (the failed links' ends, or the failed router's neighbors,
rebuild their LSPs):
- when the router first held the new LSP, measured from when its originator built it;
- how: "csnp" if, before the LSP arrived, the router's log shows a neighbor's CSNP listing the newer copy (FRR logs
  "Compare LSP ... is newer than ours"), so the router asked for it with a PSNP or the neighbor sent it after the
  CSNP; otherwise "flood";
- for late arrivals, the neighbors that held the LSP first: each one's logged flood-reduction decision on it, and
  which topology snapshot reproduces that decision with the model (fresh: every failed link removed; stale: only the
  failed links touching the originators whose new LSPs it held when it decided; old: none removed), and whether the
  reproducing decision sends the LSP to the late router.

    python analyze_events.py mech/fb444-on [--late-ms 500]
"""
import argparse
import calendar
import json
import os
import re

from topology_builders import flood_model as M

TIME = r"(\d{4})/(\d\d)/(\d\d) (\d\d):(\d\d):(\d\d)\.(\d{6})"
LSPID = r"([0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{2}-[0-9a-f]{2})"
RCVD = re.compile(TIME + r".*ISIS-Upd .*: Rcvd L2 LSP " + LSPID + r", seq 0x([0-9a-f]+),.* on (\S+)$")
OWN = re.compile(TIME + r".*ISIS-Upd .*: (?:Building|Refreshed our) L2 LSP " + LSPID + r", len \d+, seq 0x([0-9a-f]+)")
DECISION = re.compile(TIME + r".*Flooding LSP " + LSPID + r" with reduction: (selected|not selected), THL (\d+), "
                      r"RNL (\d+), start (\d+), suppressed (\d+)")
COMPARE = re.compile(TIME + r".*ISIS-Snp .*: Compare LSP " + LSPID + r" seq 0x([0-9a-f]+)")
NEWER = re.compile(r".*ISIS-Snp .*:\s+is newer than ours")
OLDER = re.compile(r".*ISIS-Snp .*:\s+is older than ours")
CSNP_IN = re.compile(r".*ISIS-Snp .*: Rcvd L2 CSNP (?:from \S+ )?on (\S+?)[,\s]")


def seconds(m):
    y, mo, d, h, mi, s, us = (int(x) for x in m.groups()[:7])
    return calendar.timegm((y, mo, d, h, mi, s)) + us / 1e6


def parse(path, t0, t1):
    """The lines of one router's log between t0 and t1 that the analysis needs."""
    out = {"rcvd": [], "own": [], "decisions": [], "csnp_newer": [], "csnp_older": []}
    pending, csnp_iface = None, None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "ISIS-Snp" in line:
                m = CSNP_IN.match(line)
                if m:
                    csnp_iface = m.group(1)
                    continue
                m = COMPARE.match(line)
                if m:
                    pending = m
                    continue
                if pending is not None:
                    t = seconds(pending)
                    if t0 <= t <= t1 and NEWER.match(line):  # a neighbor's CSNP lists a newer copy than ours
                        out["csnp_newer"].append((t, pending.group(8), int(pending.group(9), 16)))
                    elif t0 <= t <= t1 and OLDER.match(line):  # the neighbor on csnp_iface holds an older copy
                        out["csnp_older"].append((t, pending.group(8), int(pending.group(9), 16), csnp_iface))
                pending = None
                continue
            for key, rx in (("rcvd", RCVD), ("own", OWN), ("decisions", DECISION)):
                m = rx.match(line)
                if m:
                    t = seconds(m)
                    if t0 <= t <= t1:
                        out[key].append((t, *m.groups()[7:]))
                    break
    return out


def analyze(d, late_ms, verbose=False):
    with open(os.path.join(d, "lab", "lab.json"), encoding="utf-8") as fh:
        lab = json.load(fh)
    with open(os.path.join(d, "events.json"), encoding="utf-8") as fh:
        events = json.load(fh)
    topo = M.Topology.from_lab(lab["routers"], lab["links"])
    port = {}
    for x in lab["links"]:
        port[(x["a"], x["a_port"])] = x["b"]
        port[(x["b"], x["b_port"])] = x["a"]
    name = os.path.basename(os.path.normpath(d))
    for i, ev in enumerate(events):
        if ev["state"] != "down":
            continue
        t0 = ev["time"]
        t1 = events[i + 1]["time"] if i + 1 < len(events) else t0 + 25
        failed = [(x["a"], x["b"]) for x in ev["links"]]
        dead = ev.get("router")
        origins = sorted({r for x in failed for r in x} - {dead})
        logs = {r: parse(os.path.join(d, "logs", f"{r}.log"), t0 - 0.5, t1) for r in topo.adj}
        built = {}
        for o in origins:
            mine = [x for x in logs[o]["own"] if x[1].endswith(".00-00")]  # a router's own LSP, fragment 0
            if mine:
                built[o] = (mine[0][0], mine[0][1], int(mine[0][2], 16))
        new = topo.without(failed)
        rows, lates = [], []
        for o, (tb, lsp, seq) in built.items():
            for r in sorted(new.hops(o)):
                if r == o:
                    continue
                got = [(t, iface, int(s, 16)) for t, i, s, iface in logs[r]["rcvd"] if i == lsp and int(s, 16) >= seq]
                if not got:
                    rows.append((r, o, None, "missing"))
                    continue
                t, iface, s_got = got[0]
                asked = [c for c in logs[r]["csnp_newer"] if c[1] == lsp and c[2] >= seq and c[0] <= t]
                frm = port.get((r, iface))
                sent = [c for c in (logs[frm]["csnp_older"] if frm in logs else [])
                        if c[1] == lsp and c[2] < seq and c[0] <= t and port.get((frm, c[3])) == r]
                how = ("csnp-asked" if asked else "csnp-sent" if sent else "flood") + (f", a later copy (+{s_got - seq})" if s_got > seq else "")
                ms = round(1000 * (t - tb), 1)
                rows.append((r, o, ms, how))
                if ms > late_ms:
                    lates.append((r, o, lsp, ms, how, port.get((r, iface))))
        n_late = sum(1 for x in rows if x[2] is None or x[2] > late_ms)
        print(f"{name}: {ev['kind']} down {dead or [a + '-' + b for a, b in failed]}: {len(built)}/{len(origins)} new "
              f"LSPs, {len(rows)} router-LSP pairs, late (> {late_ms:.0f} ms) or missing {n_late}, of which via CSNP "
              f"{sum(1 for x in lates if x[4].startswith('csnp'))} (by flooding {sum(1 for x in lates if x[4].startswith('flood'))}); slowest {max((x[2] for x in rows if x[2]), default=0):.0f} ms")
        stale = 0
        for r, o, lsp, ms, how, frm in lates:
            relays = explain(r, o, lsp, logs, topo, failed, built, port, t0)
            # a relay skipped r because of a stale snapshot: its decision is reproduced only by snapshots that still
            # hold failed links, and with the fresh topology it would have sent the LSP to r
            culprits = [n for n, fits, fresh_sends in relays if fresh_sends and fits and "fresh" not in fits]
            stale += bool(culprits)
            print(f"   late: {r} got {o}'s LSP after {ms:.0f} ms via {how}, from {frm}; "
                  + (f"stale relay: {', '.join(culprits)}" if culprits else "no stale relay found"))
            if verbose:
                for n, fits, fresh_sends in relays:
                    print(f"      {n}: reproduced by {', '.join(sorted(fits)) or 'none'}; fresh topology sends to {r}: "
                          f"{fresh_sends}")
        if lates:
            print(f"   late pairs with a stale relay: {stale} of {len(lates)}")


def explain(r, o, lsp, logs, topo, failed, built, port, t0):
    """For each neighbor n of r that held o's new LSP before r: which snapshots reproduce n's logged decision on it
    (fresh: every failed link removed; rebuilt: the failed links of the new LSPs n held at this decision; frozen:
    those n held at its first flood-reduction decision after the failure, a snapshot FRR keeps until its next SPF
    run; old: none removed), and whether the decision on the fresh topology sends the LSP to r. Returns
    [(n, set of snapshot names, fresh sends to r)]."""
    new = topo.without(failed)
    seq = built[o][2]
    t_r = min(t for t, i, s, _ in logs[r]["rcvd"] if i == lsp and int(s, 16) >= seq)
    relays = []
    for n in sorted(new.adj[r]):
        got = [(t, iface) for t, i, s, iface in logs[n]["rcvd"] if i == lsp and int(s, 16) >= seq]
        if not got or got[0][0] >= t_r:
            continue
        t_n, iface = got[0]
        tn = port.get((n, iface))
        dec = [d for d in logs[n]["decisions"] if d[1] == lsp and d[0] >= t_n]
        if not dec:
            continue  # n is the originator, or fell back to normal flooding
        _, _, sel, thl, rnl, start, sup = dec[0]
        logged = (sel == "selected", int(thl), int(rnl), int(start), int(sup))
        def held(t, n=n):
            out = {oo for oo, (tb, ll, ss) in built.items()
                   if any(i == ll and int(s, 16) >= ss and tt <= t for tt, i, s, _ in logs[n]["rcvd"])}
            return out | ({n} if n in built and built[n][0] <= t else set())

        t_first = min(dd[0] for dd in logs[n]["decisions"] if dd[0] >= t0)
        snaps = {"fresh": new, "rebuilt": topo.without([x for x in failed if set(x) & (held(t_n) | {o})]),
                 "frozen": topo.without([x for x in failed if set(x) & held(t_first)]), "old": topo}
        fits = set()
        for k, s in snaps.items():
            dd = M.decide(s, n, tn, o, new.adj[n])
            if dd.applied and (dd.selected, dd.thl, dd.rnl, dd.start, dd.suppressed) == logged:
                fits.add(k)
        relays.append((n, fits, r in M.decide(new, n, tn, o, new.adj[n]).send))
    return relays


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("labs", nargs="+")
    p.add_argument("--late-ms", type=float, default=500)
    p.add_argument("--verbose", action="store_true", help="every relay of every late pair")
    a = p.parse_args(argv)
    for d in a.labs:
        analyze(d, a.late_ms, a.verbose)


if __name__ == "__main__":
    main()
