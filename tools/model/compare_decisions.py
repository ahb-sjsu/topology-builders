"""Compare FRR's logged flood-reduction decisions with the flooding model's, decision by decision.

Reads what collect_decisions.py saved. For every "Flooding LSP ... with reduction" line in a router's log, the
transmitting neighbor is the one on the interface of the router's last "Rcvd" line for that LSP, and the topology
state is the one after the last link change before it. The model's `decide` is run for that router, neighbor and
LSP under three snapshots: the topology without the changed link (the model's assumption), with it, and the routers'
actual adjacencies. A decision matches when selected, THL, RNL, start index and suppressed count all agree.

    python compare_decisions.py decisions/*/
"""
import calendar
import collections
import json
import os
import re
import sys

from topology_builders import flood_model as M

TIME = r"(\d{4})/(\d\d)/(\d\d) (\d\d):(\d\d):(\d\d)\.(\d{6})"
RCVD = re.compile(TIME + r".*Rcvd L2 LSP (\S+), seq 0x([0-9a-f]+),.* on (\S+)")
DECISION = re.compile(TIME + r".*Flooding LSP (\S+) with reduction: (selected|not selected), THL (\d+), RNL (\d+), "
                      r"start (\d+), suppressed (\d+)")
FALLBACK = re.compile(TIME + r".*Flooding reduction not applicable to LSP (\S+)")


def seconds(m):
    y, mo, d, h, mi, s, us = (int(x) for x in m.groups()[:7])
    return calendar.timegm((y, mo, d, h, mi, s)) + us / 1e6


def load(d):
    with open(os.path.join(d, "lab", "lab.json"), encoding="utf-8") as fh:
        lab = json.load(fh)
    topo = M.Topology.from_lab(lab["routers"], lab["links"])
    by_id = {f"{s:012x}": r for r, s in topo.sysid.items()}
    port = {}
    for x in lab["links"]:
        port[(x["a"], x["a_port"])] = x["b"]
        port[(x["b"], x["b_port"])] = x["a"]
    events = []
    with open(os.path.join(d, "events.txt"), encoding="utf-8") as fh:
        for line in fh:
            t, state, a, b, _ = line.split()
            events.append((float(t), state, a, b))
    return topo, by_id, port, events


def router_of(lsp_id, by_id):
    return by_id.get(lsp_id.split(".00-")[0].replace(".", "").lower())


def decisions(d, by_id, port):
    out = []
    for f in sorted(os.listdir(os.path.join(d, "logs"))):
        r = f[:-4]
        last = {}
        with open(os.path.join(d, "logs", f), encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = RCVD.match(line)
                if m:
                    last[m.group(8)] = port.get((r, m.group(10)))
                    continue
                m = DECISION.match(line) or FALLBACK.match(line)
                if m:
                    lsp = m.group(8)
                    rec = {"router": r, "time": seconds(m), "lsp": lsp, "origin": router_of(lsp, by_id),
                           "tn": last.get(lsp)}
                    if m.re is DECISION:
                        rec.update(selected=m.group(9) == "selected", thl=int(m.group(10)), rnl=int(m.group(11)),
                                   start=int(m.group(12)), suppressed=int(m.group(13)))
                    else:
                        rec["fallback"] = True
                    out.append(rec)
    return out


def model_decision(snap, actual, local, tn, origin):
    """decide() plus the statistics FRR logs: (selected, THL, RNL, start, suppressed) or None for a fallback."""
    dec = M.decide(snap, local, tn, origin, actual[local])
    if not dec.applied:
        return None
    return dec.selected, dec.thl, dec.rnl, dec.start, dec.suppressed


def compare(d):
    topo, by_id, port, events = load(d)
    recs = [x for x in decisions(d, by_id, port) if x["time"] >= events[0][0]]
    tally = collections.defaultdict(collections.Counter)
    misses = []
    for x in recs:
        before = [e for e in events if e[0] <= x["time"]]
        if not before or x["tn"] is None or x["origin"] is None or "fallback" in x:
            tally["all"]["skipped"] += 1
            continue
        _, state, a, b = before[-1]
        without = topo.without([(a, b)])
        actual = (topo if state == "up" else without).adj
        logged = (x["selected"], x["thl"], x["rnl"], x["start"], x["suppressed"])
        snaps = {"without-link": without, "with-link": topo, "actual": M.Topology(actual, topo.sysid)}
        for name, snap in snaps.items():
            got = model_decision(snap, actual, x["router"], x["tn"], x["origin"])
            tally[name]["match" if got == logged else "differ"] += 1
        # Any combination of snapshot (with or without the changed link) and neighbor list (with or without it: at
        # the link's ends the adjacency may not be up yet when the router decides).
        combos = {(s, n): model_decision(sv, nv, x["router"], x["tn"], x["origin"])
                  for s, sv in (("without", without), ("with", topo))
                  for n, nv in (("without", without.adj), ("with", topo.adj))}
        hit = [k for k, v in combos.items() if v == logged]
        tally[f"any-{state}"]["match" if hit else "differ"] += 1
        snaps_hit = {s for s, _ in hit}
        which = "either" if snaps_hit == {"without", "with"} else next(iter(snaps_hit), "none")
        tally[f"snapshot-{state}"][which] += 1
        if not hit and len(misses) < 12:
            misses.append((x["router"], x["lsp"], f"TN {x['tn']}", state, f"{a}-{b}", "FRR", logged,
                           "model (snapshot without, with)", combos[("without", "without")], combos[("with", "with")]))
    print(f"{os.path.basename(os.path.normpath(d))}: {len(recs)} decisions after the first change, "
          f"skipped {tally['all']['skipped']}")
    for name in ("without-link", "with-link", "actual", "any-down", "any-up"):
        t = tally[name]
        n = t["match"] + t["differ"]
        label = {"any-down": "any, link down", "any-up": "any, link up"}.get(name, f"snapshot {name}")
        print(f"  {label:<22} {t['match']:>5}/{n} match" + (f" ({100 * t['match'] / n:.1f}%)" if n else ""))
    for state in ("down", "up"):
        t = tally[f"snapshot-{state}"]
        print(f"  link {state:<4} decisions whose snapshot was: without the link {t['without']}, with it {t['with']}, "
              f"either (same decision) {t['either']}, neither {t['none']}")
    for m in misses:
        print("   matches no combination:", *m)


if __name__ == "__main__":
    for d in sys.argv[1:]:
        if os.path.exists(os.path.join(d, "lab", "lab.json")):  # skip folders that hold no lab, such as topos/
            compare(d)
