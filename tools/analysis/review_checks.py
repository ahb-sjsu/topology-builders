"""Further checks on the published data in `results/` and on the model; measures nothing.

    python review_checks.py <topology-builders results dir> <scratch dir>

A. A counterexample to "a two-hop rule can drop a copy only where routers two hops apart share more than one
   neighbour": two triangles sharing one router, the outer edge of one failing.
B. How well degree and two-hop multiplicity each order the link-change saving across the Figure 2 graphs: Spearman
   rank correlation, and R^2 of a least-squares line in log(x).
C. isisd CPU per link change, paired by run: per campaign, graph and repeat, the mean net CPU of the run's satisfied
   link windows off and on, and the saving 1 - on/off of each pair. Windows within a run are not independent; runs
   (and Colab sessions) are the replication unit.
"""
import gzip
import json
import math
import os
import sys
from statistics import mean

import data
import networkx as nx

from topology_builders import flood_model as FM
from topology_builders import output as O
from topology_builders.measure import net_isisd_ms


def part_a():
    adj = {"c": {"a1", "a2", "b1", "b2"}, "a1": {"c", "a2"}, "a2": {"c", "a1"}, "b1": {"c", "b2"}, "b2": {"c", "b1"}}
    topo = FM.Topology(adj, {"c": 1, "a1": 2, "a2": 3, "b1": 4, "b2": 5})
    g = nx.Graph([(u, v) for u in adj for v in adj[u]])
    print("A. Two triangles sharing router c; link a1-a2 fails")
    print(f"   two-hop multiplicity {O.two_hop_multiplicity(g)}, four-cycles {sum(1 for c in nx.simple_cycles(g, length_bound=4) if len(c) == 4)}, "
          f"triangles {sum(nx.triangles(g).values()) // 3}")
    for red in (False, True):
        res = FM.flood_link_change(topo, ("a1", "a2"), "down", red)
        print(f"   reduction {'on ' if red else 'off'}: sent {res['sent']}; result keys {sorted(res)}")
    print(f"   floor 2(n-1) = {2 * (len(adj) - 1)}")


def ranks(xs):
    order = sorted(range(len(xs)), key=xs.__getitem__)
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def pearson(x, y):
    mx, my = mean(x), mean(y)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    return sxy / math.sqrt(sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y))


def part_b(results, scratch):
    index = data.topology_index(results, scratch)
    rows = [r for r in data.rows(data.records(results, data.STUDY), index)
            if r["timers"] == "topotest" and r["multiplicity"] and all(r[k]["satisfied"] >= 6 for k in ("off", "on"))]
    s = [data.saving(r, "link") for r in rows]
    print(f"\nB. Link-change saving across the {len(rows)} Figure 2 graphs")
    for name, key in (("degree", "degree"), ("two-hop multiplicity", "multiplicity")):
        x = [r[key] for r in rows]
        rho = pearson(ranks(x), ranks(s))
        r2 = pearson([math.log(v) for v in x], s) ** 2
        print(f"   {name:<22} Spearman {rho:.3f}; R^2 of saving on log({key}) {r2:.3f}")
    for fam in sorted({r["family"] for r in rows}):
        mine = [r for r in rows if r["family"] == fam]
        if len(mine) >= 4:
            sv = [data.saving(r, "link") for r in mine]
            out = []
            for key in ("degree", "multiplicity"):
                x = [r[key] for r in mine]
                out.append(f"{key} {pearson(ranks(x), ranks(sv)):.2f}" if len(set(x)) > 1 else f"{key} constant")
            print(f"   within {fam} ({len(mine)} graphs): Spearman " + ", ".join(out))
    big = [r for r in rows if r["routers"] != 64 and r["family"] == "random-regular"]
    print("   size at fixed degree (random regular):", ", ".join(
        f"n{r['routers']} d{r['degree']:g}: mult {r['multiplicity']:.2f} saving {100 * data.saving(r, 'link'):.0f}%"
        for r in sorted(big, key=lambda r: (r["degree"], r["routers"]))))


def run_cpu(rec, phases):
    vals = [net_isisd_ms(p) for p in rec["phases"] if p["phase"] in phases and p["outcome"] == "satisfied"]
    vals = [v for v in vals if v is not None]
    return mean(vals) if vals else None


T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
       11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086}


def interval(xs):
    """Mean and two-sided 95% t-interval of independent values (None when fewer than 2)."""
    m = mean(xs)
    if len(xs) < 2:
        return m, None, None
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))
    h = T95[len(xs) - 1] * sd / math.sqrt(len(xs))
    return m, m - h, m + h


def part_c(results):
    print("\nC. isisd CPU per window, net of the idle window, paired by run (saving = 1 - on/off per pair)")
    folders = data.STUDY + data.TIMERS + ["flap10-n64", "colab-sessions"]
    pooled_groups = {}
    for folder in folders:
        path = os.path.join(results, folder, "measurements.jsonl.gz")
        if not os.path.exists(path):
            continue
        phases = ("multi-down", "multi-up") if folder == "flap10-n64" else ("link-down", "link-up")
        groups = {}
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                r = json.loads(line)
                if r.get("timing") or not r.get("converged"):
                    continue
                t = r["topology"]
                unit = r.get("session", "")
                key = (t["family"], json.dumps(t.get("parameters"), sort_keys=True), t["routers"], data.timers(r), unit)
                v = run_cpu(r, phases)
                if v is not None:
                    groups.setdefault(key, {}).setdefault(r["repeat"], {})["on" if r["settings"]["flood_reduction"] else "off"] = v
        print(f"  {folder}")
        for key in sorted(groups, key=lambda k: (k[0], k[2], k[1], k[3], k[4])):
            pairs = [(v["off"], v["on"]) for _, v in sorted(groups[key].items()) if "off" in v and "on" in v]
            if not pairs:
                continue
            sav = [1 - on / off for off, on in pairs]
            fam, params, n, tm, unit = key
            p = json.loads(params) or {}
            # a run pair is the replication unit, except on Colab, where a session's pooled saving is one value
            unit_vals = ([1 - mean(on for _, on in pairs) / mean(off for off, _ in pairs)]
                         if folder == "colab-sessions" else sav)
            gkey = (folder, fam, p.get("degree") if fam == "random-regular" else None, n, tm)
            pooled_groups.setdefault(gkey, []).extend(unit_vals)
            name = fam + " " + ",".join(f"{k}={p[k]}" for k in sorted(p) if k not in ("routers",)) + f" n={n}"
            pooled = 1 - mean(on for _, on in pairs) / mean(off for off, _ in pairs)
            print(f"    {name:<52} {tm:<12} {unit:<6} pairs {len(pairs)}: per pair "
                  + ", ".join(f"{100 * x:+.0f}%" for x in sav)
                  + f"; mean {100 * mean(sav):+.0f}%, range {100 * min(sav):+.0f}% to {100 * max(sav):+.0f}%; "
                  f"pooled {100 * pooled:+.0f}%")
    print("\nD. Pooled over the graphs of one family and degree (and size, timers): one value per run pair, or per "
          "Colab session; mean and 95% t-interval")
    for gkey in sorted(pooled_groups, key=str):
        folder, fam, deg, n, tm = gkey
        xs = pooled_groups[gkey]
        m, lo, hi = interval(xs)
        ci = "-" if lo is None else f"{100 * lo:+.0f}% to {100 * hi:+.0f}%"
        print(f"  {folder:<20} {fam:<20} degree {deg if deg is not None else '-':<4} n={n:<4} {tm:<12} units {len(xs):>2}: "
              f"mean {100 * m:+.1f}%, 95% CI {ci}; range {100 * min(xs):+.0f}% to {100 * max(xs):+.0f}%; "
              f"lower with reduction in {sum(x > 0 for x in xs)} of {len(xs)}")


if __name__ == "__main__":
    part_a()
    part_b(sys.argv[1], sys.argv[2])
    part_c(sys.argv[1])
