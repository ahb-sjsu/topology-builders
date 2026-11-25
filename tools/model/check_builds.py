"""When did each stale relay build the topology it decided with? Reads the FULL logs that collect_events.py saved; the
reduced logs in results/mechanism/logs.tar.gz leave out the route-computation lines this needs.

isisd (FRR pull request 24128 at e263c441) builds the topology its flood-reduction decisions use at the first decision
after a route computation starts, and frees it when the next route computation starts, which `debug isis spf-events`
logs as "SPF needed". For every stale relay decision that analyze_events.py finds in pairs later than 1 s (a relay
whose logged decision only topologies holding failed links reproduce, and which would have sent the LSP to the late
router on the topology without them), and every unmatched one (a relay that would have sent it, in a pair without a
stale relay, whose decision none of analyze_events.py's snapshots reproduces), this reports:
- the build: the relay's first flood-reduction decision after its last "SPF needed" before the stale decision, and
  whether a route computation started between the build and the stale decision;
- how many of the failure's new LSPs the relay held at the build. A failure's new LSPs are each originator's first
  build of its own LSP from 5 s before the event's recorded time, because that time is taken after the links are down;
- which topologies reproduce the logged decision with the model: the one held at the build (failed links removed
  where the relay had received an end's new LSP, or was that end; with and without the LSP decided at the build), the
  one held at the stale decision, and the one with no failed link removed.

    python tools/model/check_builds.py mech/fb444-on mech/ls16-on
"""
import argparse
import bisect
import json
import os
import re

import analyze_events as AE

M = AE.M
SPF_START = re.compile(AE.TIME + r".*ISIS-SPF \(\d+\) L2 SPF needed")
BEFORE = AE.BEFORE  # seconds before the recorded event time in which a failure's first LSP builds are looked for


def read_full(path):
    """One router's whole log: SPF start times, decisions (time, LSP ID), LSPs received and built (time, ID, seq)."""
    spf, dec, rcvd, own = [], [], [], []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "SPF needed" in line:
                m = SPF_START.match(line)
                if m:
                    spf.append(AE.seconds(m))
            elif "with reduction" in line:
                m = AE.DECISION.match(line)
                if m:
                    dec.append((AE.seconds(m), m.group(8)))
            elif "Rcvd L2 LSP" in line:
                m = AE.RCVD.match(line)
                if m:
                    rcvd.append((AE.seconds(m), m.group(8), int(m.group(9), 16)))
            elif "L2 LSP" in line and ("Building" in line or "Refreshed our" in line):
                m = AE.OWN.match(line)
                if m and m.group(8).endswith(".00-00"):
                    own.append((AE.seconds(m), m.group(8), int(m.group(9), 16)))
    return {"spf": spf, "dec": dec, "rcvd": rcvd, "own": own}


def held(first, rcvd, n, t, strict):
    """The originators whose new LSP router n had received by time t (before t if strict), and n itself if it is
    one and had built its own by t. `first` maps each originator to (time, LSP ID, seq) of its first new LSP."""
    out = {n} if n in first and first[n][0] <= t else set()
    for o, (_, lsp, seq) in first.items():
        if o != n and any(li == lsp and si >= seq and (ti < t if strict else ti <= t) for ti, li, si in rcvd):
            out.add(o)
    return out


def reproduces(topo, failed, holding, n, tn, o, neighbors, logged):
    """Whether the model's decision of n, on the topology without the failed links that touch `holding`, is the
    logged one."""
    x = M.decide(topo.without([y for y in failed if set(y) & holding]), n, tn, o, neighbors)
    return x.applied and (x.selected, x.thl, x.rnl, x.start, x.suppressed) == logged


def check(d):
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
    full, rows, starts = {}, [], []

    def log(r):
        if r not in full:
            full[r] = read_full(os.path.join(d, "logs", f"{r}.log"))
        return full[r]

    for i, ev in enumerate(events):
        if ev["state"] != "down":
            continue
        t0 = ev["time"]
        t1 = events[i + 1]["time"] if i + 1 < len(events) else t0 + 25
        failed = [(x["a"], x["b"]) for x in ev["links"]]
        dead = ev.get("router")
        origins = sorted({r for x in failed for r in x} - {dead})
        label = f"{ev['kind']} down {dead or ', '.join(a + '-' + b for a, b in failed)}"
        first = {}
        for o in origins:
            b = [x for x in log(o)["own"] if t0 - BEFORE <= x[0] <= t1]
            if b:
                first[o] = b[0]
        offs = sorted(v[0] - t0 for v in first.values())
        starts.append((label, len(first), len(origins), offs[0], offs[-1],
                       sum(1 for v in first.values() if v[0] < t0 - 0.5)))
        # the late pairs and stale relays exactly as analyze_events.py finds them
        logs = {r: AE.parse(os.path.join(d, "logs", f"{r}.log"), t0 - BEFORE, t1) for r in topo.adj}
        built = {}
        for o in origins:
            mine = [x for x in logs[o]["own"] if x[1].endswith(".00-00")]
            if mine:
                built[o] = (mine[0][0], mine[0][1], int(mine[0][2], 16))
        new = topo.without(failed)
        t_start = min((b[0] for b in built.values()), default=t0)
        for o, (tb, lsp, seq) in built.items():
            for r in sorted(new.hops(o)):
                if r == o:
                    continue
                got = [t for t, ii, s, _ in logs[r]["rcvd"] if ii == lsp and int(s, 16) >= seq]
                if not got or float(f"{round(1000 * (got[0] - tb), 1):.0f}") <= 1000:  # as classify.py counts
                    continue
                relays = AE.explain(r, o, lsp, logs, topo, failed, built, port, t_start)
                # as classify.py: a pair's stale relays if it has any, else its unmatched ones (would have sent the
                # LSP on the fresh topology, but no snapshot analyze_events.py tries reproduces the decision)
                chosen = [x for x in relays if x[2] and x[1] and "fresh" not in x[1]]
                kind = "stale"
                if not chosen:
                    chosen, kind = [x for x in relays if x[2] and not x[1]], "unmatched"
                for n, fits, _ in chosen:
                    t_n, iface = min((t, f) for t, ii, s, f in logs[n]["rcvd"] if ii == lsp and int(s, 16) >= seq)
                    dd = min(x for x in logs[n]["decisions"] if x[1] == lsp and x[0] >= t_n)
                    logged = (dd[2] == "selected", int(dd[3]), int(dd[4]), int(dd[5]), int(dd[6]))
                    t_dec, tn, g = dd[0], port.get((n, iface)), log(n)
                    k = bisect.bisect_left(g["spf"], t_dec) - 1
                    s = g["spf"][k] if k >= 0 else float("-inf")
                    j = bisect.bisect_left([x[0] for x in g["dec"]], s)
                    t_b = g["dec"][j][0]
                    h_b = held(first, g["rcvd"], n, t_b, False)
                    fit = {key: reproduces(topo, failed, h, n, tn, o, new.adj[n], logged) for key, h in (
                        ("fit_build", h_b), ("fit_build_without", held(first, g["rcvd"], n, t_b, True)),
                        ("fit_decision", held(first, g["rcvd"], n, t_dec, False)), ("fit_old", set()))}
                    rows.append({
                        "kind": kind, "lab": name, "event": label, "late": r, "origin": o, "relay": n,
                        "published": sorted(fits),
                        "gap": t_dec - t_b, "build": t_b - t0, "decision": t_dec - t0,
                        "spf_between": sum(1 for x in g["spf"] if t_b <= x < t_dec),
                        "held_at_build": len(h_b - {n}), "before_any": t_b < min(v[0] for v in first.values()),
                        **fit})
    return starts, rows


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("labs", nargs="+")
    a = p.parse_args(argv)
    starts, rows = [], []
    for d in a.labs:
        s, r = check(d)
        starts += [(os.path.basename(os.path.normpath(d)), *x) for x in s]
        rows += r
    print("Failures: each originator's first new LSP, from the event's recorded time")
    for lab, label, nb, no, lo, hi, early in starts:
        print(f"  {lab} {label}: {nb}/{no} originators built, first builds {lo:+.3f} to {hi:+.3f} s; "
              f"more than 0.5 s before the recorded time: {early}")
    for kind in ("stale", "unmatched"):
        rs = [r for r in rows if r["kind"] == kind]
        n = len(rs)
        pairs = len({(r["lab"], r["event"], r["late"], r["origin"]) for r in rs})
        print(f"\n{kind.capitalize()} relay decisions (a relay counted once per late pair): {n}, in {pairs} pairs; "
              f"reproduced only by the topology with no failed link removed among analyze_events.py's snapshots: "
              f"{sum(1 for r in rs if r['published'] == ['old'])}")
        if not rs:
            continue
        print(f"  topology built before any of the failure's new LSPs existed: {sum(r['before_any'] for r in rs)}")
        hist = {}
        for r in rs:
            hist[r["held_at_build"]] = hist.get(r["held_at_build"], 0) + 1
        print(f"  the failure's new LSPs the relay had received at the build: {dict(sorted(hist.items()))}")
        print(f"  a route computation started between the build and the decision: "
              f"{sum(1 for r in rs if r['spf_between'])}")
        for key, what in (("fit_build", "the topology held at the build"),
                          ("fit_build_without", "the same, without the LSP decided at the build"),
                          ("fit_decision", "the topology held at the decision"),
                          ("fit_old", "no failed link removed")):
            print(f"  reproduced by {what}: {sum(r[key] for r in rs)} of {n}")
        gaps = sorted(r["gap"] for r in rs)
        print(f"  decision after the build: under 1 ms {sum(g < 0.001 for g in gaps)}, 1 to 10 ms "
              f"{sum(0.001 <= g < 0.01 for g in gaps)}, 10 to 100 ms {sum(0.01 <= g < 0.1 for g in gaps)}, over "
              f"100 ms {sum(g >= 0.1 for g in gaps)}; longest {gaps[-1]:.3f} s")
    print("\nkind | lab | event | late router | originator | relay | published snapshots | held at build | build, "
          "decision (s from the recorded time) | reproduced by build / build without / decision / old")
    for r in rows:
        print(f"{r['kind']} | {r['lab']} | {r['event']} | {r['late']} | {r['origin']} | {r['relay']} | "
              f"{','.join(r['published'])} | "
              f"{r['held_at_build']} | {r['build']:+.4f}, {r['decision']:+.4f} | {r['fit_build']} / "
              f"{r['fit_build_without']} / {r['fit_decision']} / {r['fit_old']}")


if __name__ == "__main__":
    main()
