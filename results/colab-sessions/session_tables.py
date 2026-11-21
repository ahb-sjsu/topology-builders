"""Tables for the Colab sessions: per session, the rows of `topology-builders report`; the spread across sessions;
the pairs pooled over sessions; the quiet windows; the Atlas runs of the same graphs in the other results folders;
and the flooding model's count for the links each setup took down.

    python results/colab-sessions/session_tables.py results/colab-sessions/measurements.jsonl.gz \
        results/colab-sessions/sessions.json results
"""
import glob
import json
import os
import sys
from statistics import mean, median

from topology_builders import clab, families, report
from topology_builders import flood_model as fm


def pct(x):
    return "" if x is None else f"{100 * x:.0f}%"


def name(row):
    return f"{row['topology']}, {row['routers']} routers"


def rname(r):
    return f"{report.label(r['topology'])}, {r['topology']['routers']} routers"


def pairs(records, sha):
    """(lsp_off, lsp_on, ms_off, ms_on) per link and direction, averaged over the runs, as report.rows pairs them."""
    out = {}
    for r in records:
        if r.get("timing") or r["source_sha256"] != sha:
            continue
        side = "on" if r["settings"]["flood_reduction"] else "off"
        for p in r["phases"]:
            if p["phase"] in report.LINK_PHASES and p.get("net_of_quiet"):
                out.setdefault((p.get("event", p.get("link")), p["phase"]), {"off": [], "on": []})[side].append(
                    (p["counters"].get("tx_l2_lsp", 0), p["net_of_quiet"]["cpu_ms"].get("isisd", 0)))
    return [tuple(mean(x[i] for x in v[s]) for i in (0, 1) for s in ("off", "on"))
            for v in out.values() if v["off"] and v["on"]]


def quiet(records, row):
    """isisd ms of the quiet window of every run of this topology, off and on."""
    return {s: [p["cpu_ms"].get("isisd", 0) for r in records
                if report.label(r["topology"]) == row["topology"] and r["topology"]["routers"] == row["routers"]
                and bool(r["settings"]["flood_reduction"]) == (s == "on")
                for p in r["phases"] if p["phase"] == "quiet"] for s in ("off", "on")}


def graph(topology):
    """The graph a record's topology was built from, rebuilt with the same generator and parameters."""
    p = topology["parameters"]
    if topology["family"] == "random-regular":
        return families.random_regular(p["routers"], p["degree"], p["seed"])
    if topology["family"] == "leaf-spine":
        return families.leaf_spine(p["leaves"], p["spines"])
    if topology["family"] == "flattened-butterfly":
        return families.flattened_butterfly(p["radices"])
    return None


def main(measurements, sessions_file, results):
    records = report.read([measurements])
    with open(sessions_file, encoding="utf-8") as fh:
        sessions = json.load(fh)
    recs = {s: [r for r in records if r.get("session") == s] for s in sorted(sessions)}

    print("SESSIONS")
    for s, info in sorted(sessions.items()):
        e = info["runtime"]
        print(f"  {s}: {e['cpu_model']}, {e['cpus']} CPUs, {e['mem_mb'] // 1024} GB, started {e['started']}, setup "
              f"{e['setup_s']} s (FRR from the Drive cache: {e['frr_from_cache']}); labs "
              + ", ".join(f"{x['lab']} {x['minutes']} min, steal {x['steal_pct']}%" for x in info["labs"]))

    by_sha = {}
    print("\nPER SESSION: link windows (LSPs sent, isisd ms net of the quiet window), pairs, bring-up")
    for s, rs in recs.items():
        for row in report.rows(rs):
            w, b, pr = row["windows"], row["bring_up"], row["pairs"]
            sha = next(r["source_sha256"] for r in rs if rname(r) == name(row))
            by_sha.setdefault(sha, {})[s] = row
            print(f"  {name(row)} | {s} | LSPs {w['off']['lsps']['mean']:.0f} -> {w['on']['lsps']['mean']:.0f} "
                  f"({pct(row['lsp_saving'])} fewer) | net ms {w['off']['net_ms']['mean']:.0f} -> "
                  f"{w['on']['net_ms']['mean']:.0f} ({pct(row['net_saving'])} lower) | CPU lower in "
                  f"{pr['net_lower_on']} of {pr['n']} pairs, median {pct(pr['median_net_saving'])}; LSPs lower in "
                  f"{pr['lsps_lower_on']} of {pr['n']} | bring-up LSPs {pct(row['bring_up_lsp_saving'])} fewer, CPU "
                  f"{pct(row['bring_up_ms_saving'])} lower | windows satisfied "
                  f"{w['off']['satisfied'] + w['on']['satisfied']} of {w['off']['windows'] + w['on']['windows']} | "
                  f"converged {b['off']['converged']} of {row['runs']['off']} off, "
                  f"{b['on']['converged']} of {row['runs']['on']} on")

    print("\nACROSS SESSIONS (same topology file, so the same links)")
    for sha, d in by_sha.items():
        if len(d) < 2:
            continue
        nm = name(next(iter(d.values())))
        for key in ("lsp_saving", "net_saving", "bring_up_lsp_saving", "bring_up_ms_saving"):
            vals = [d[s][key] for s in d if d[s][key] is not None]
            print(f"  {nm} {key}: " + ", ".join(f"{s[-4:]} {pct(d[s][key])}" for s in d)
                  + f"; range {pct(min(vals))} to {pct(max(vals))}")
        print(f"  {nm} median pair CPU saving: "
              + ", ".join(f"{s[-4:]} {pct(d[s]['pairs']['median_net_saving'])}" for s in d))
        allp = [v for s in d for v in pairs(recs[s], sha)]
        sav = sorted(1 - v[3] / v[2] for v in allp if v[2] > 0)
        print(f"  {nm} pairs of all {len(d)} sessions: CPU lower in {sum(v[3] < v[2] for v in allp)} of {len(allp)}, "
              f"median {pct(median(sav))}, quartiles {pct(sav[len(sav) // 4])} to {pct(sav[3 * len(sav) // 4])}; "
              f"LSPs lower in {sum(v[1] < v[0] for v in allp)} of {len(allp)}")

    print("\nQUIET WINDOWS: isisd ms summed over the routers in the 30 s with no event, one per run")
    for s, rs in recs.items():
        for row in report.rows(rs):
            q = quiet(rs, row)
            print(f"  {s[-4:]} {name(row)}: off {q['off']}, on {q['on']}; net link window off "
                  f"{row['windows']['off']['net_ms']['mean']:.0f}, on {row['windows']['on']['net_ms']['mean']:.0f}")

    print("\nATLAS RUNS OF THE SAME GRAPHS (same family, parameters and routers; other links)")
    names = {name(row) for d in by_sha.values() for row in d.values()}
    atlas_links = {}
    for f in sorted(glob.glob(os.path.join(results, "*", "measurements.jsonl.gz"))):
        folder = os.path.basename(os.path.dirname(f))
        if os.path.samefile(f, measurements):
            continue
        rs = [r for r in report.read([f]) if not r.get("timing")]
        for row in report.rows(rs):
            if name(row) in names and row["pairs"]["n"]:
                pr, q = row["pairs"], quiet(rs, row)
                print(f"  {folder}: {name(row)}, runs {row['runs']}: LSPs {row['windows']['off']['lsps']['mean']:.0f} "
                      f"-> {row['windows']['on']['lsps']['mean']:.0f} ({pct(row['lsp_saving'])} fewer); net ms "
                      f"{row['windows']['off']['net_ms']['mean']:.0f} -> {row['windows']['on']['net_ms']['mean']:.0f};"
                      f" CPU lower in {pr['net_lower_on']} of {pr['n']} pairs, median {pct(pr['median_net_saving'])};"
                      f" bring-up LSPs {pct(row['bring_up_lsp_saving'])} fewer, CPU {pct(row['bring_up_ms_saving'])}"
                      f" lower; quiet isisd ms off {q['off']}, on {q['on']}; deploy "
                      f"{mean(r['deploy_s'] for r in rs if rname(r) == name(row)):.0f} s; bring-up LSPs "
                      f"{row['bring_up']['off']['lsps']['mean']:.0f} -> {row['bring_up']['on']['lsps']['mean']:.0f}")
                atlas_links.setdefault(name(row), {})[folder] = next(r for r in rs if rname(r) == name(row))

    print("\nTHE MODEL FOR EACH SETUP'S LINKS: LSPs per window, lockstep, off -> on (saving)")
    for nm, folders in sorted(atlas_links.items()):
        colab = next(r for rs in recs.values() for r in rs if rname(r) == nm)
        g = graph(colab["topology"])
        if g is None:
            continue
        topo = fm.Topology.from_lab(*clab.plan(g))
        for where, r in [("Colab", colab)] + sorted(folders.items()):
            sent = {on: mean(fm.flood_link_change(topo, (x["a"], x["b"]), state, on)["sent"]
                             for x in r["links"] for state in ("down", "up")) for on in (False, True)}
            links = ", ".join(f"{x['a']}-{x['b']}" for x in r["links"])
            print(f"  {nm} {where} ({links}): {sent[False]:.1f} -> {sent[True]:.1f} "
                  f"({pct(1 - sent[True] / sent[False])})")

    print("\nDEPLOY AND BRING-UP: seconds the deploy step took, LSPs sent at bring-up, off -> on")
    for s, rs in recs.items():
        for row in report.rows(rs):
            sel = [r for r in rs if rname(r) == name(row)]
            b = row["bring_up"]
            print(f"  {s[-4:]} {name(row)}: deploy {mean(r['deploy_s'] for r in sel):.0f} s; bring-up LSPs "
                  f"{b['off']['lsps']['mean']:.0f} -> {b['on']['lsps']['mean']:.0f}")

    print("\nCPU PER EVENT HANDLER, per session")
    for s, rs in recs.items():
        print(f"== {s}")
        print(report.profile_text(rs))


if __name__ == "__main__":
    main(*sys.argv[1:4])
