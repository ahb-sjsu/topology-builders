"""Tables for the Topology Zoo labs: one row per network, density and timer set.

    python results/topology-zoo/zoo_tables.py results/topology-zoo/measurements.jsonl.gz

Per row, as `topology-builders report` defines them: mean LSPs sent per link window (link-down and link-up pooled),
flood reduction off and on, and the saving; mean isisd ms per link window net of the run's quiet window; bring-up
LSPs; runs converged. The report's own topology labels do not yet name Zoo graphs, hence this script."""
import gzip
import json
import sys
from statistics import mean

LINK = ("link-down", "link-up")


def rows(path):
    groups = {}
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        records = [json.loads(line) for line in fh]
    for r in records:
        t, s = r["topology"], r["settings"]
        p = t["parameters"]
        timers = "FRR defaults" if s.get("lsp_gen_interval") == 30 else "study"
        key = (p["name"], p["added_links"], timers)
        g = groups.setdefault(key, {"t": t, "window": r.get("window_s"), "runs": {False: [], True: []}})
        g["runs"][bool(s["flood_reduction"])].append(r)
    for (name, added, timers), g in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][2] != "study", kv[0][1])):
        t, out = g["t"], {}
        for on, recs in g["runs"].items():
            quiet = {id(r): next(p for p in r["phases"] if p["phase"] == "quiet")["cpu_ms"]["isisd"] for r in recs}
            win = [(r, p) for r in recs for p in r["phases"] if p["phase"] in LINK]
            out[on] = {
                "lsps": mean(p["counters"]["tx_l2_lsp"] for _, p in win),
                "cpu": mean(p["cpu_ms"]["isisd"] - quiet[id(r)] for r, p in win),
                "bring": mean(r["phases"][0]["counters"]["tx_l2_lsp"] for r in recs),
                "conv": sum(bool(r["converged"]) for r in recs), "n": len(recs), "windows": len(win),
            }
        yield name, added, timers, t, g["window"], out


def pct(off, on):
    return f"{100 * (1 - on / off):.0f}%"


def main(path):
    print("network      routers links (added) degree diam 2-hop timers        window | LSPs per link window off -> on"
          "        | bring-up LSPs off -> on        | isisd ms per window off -> on | converged")
    for name, added, timers, t, window, o in rows(path):
        a, b = o[False], o[True]
        links = t["parameters"]["original_links"] + added
        print(f"{name:12} {t['routers']:7} {links:5} ({added:3}) {t['average_degree']:6.2f} {t['diameter']:4} "
              f"{t['two_hop_multiplicity']:5.2f} {timers:13} {window:4} s | {a['lsps']:8,.0f} {b['lsps']:7,.0f} "
              f"{pct(a['lsps'], b['lsps']):>4} ({a['windows']}+{b['windows']}) | {a['bring']:9,.0f} {b['bring']:9,.0f} "
              f"{pct(a['bring'], b['bring']):>4} | {a['cpu']:8,.0f} {b['cpu']:7,.0f} {pct(a['cpu'], b['cpu']):>5} | "
              f"{a['conv']}/{a['n']} {b['conv']}/{b['n']}")


if __name__ == "__main__":
    main(sys.argv[1])
