"""Distance from the tree bound, per graph: LSPs sent per link-down window against the spanning-tree floor.

    python tree_bound.py <topology-builders checkout> <scratch dir> > tree_bound.txt

Also writes tree_bound.json beside the output directory given as a third argument (default: this folder).

Columns (link-down windows only; see data.tree_bound for the two reference counts):
- off, on: mean LSPs sent per satisfied link-down window.
- floor: 2(n - 1), the fewest sends that deliver both changed LSPs to every router.
- full: full flooding without duplicate suppression.
- off/full: how much duplicate suppression already saves without flood reduction.
- saving: 1 - on/off, measured.  bound: 1 - floor/off, the most any rule could save against this baseline.
- removed: (off - on)/(off - floor), the share of the removable copies flood reduction removed.
- on/floor: copies sent per copy needed."""
import json
import os
import sys
from statistics import mean

import data


def main(results, scratch, out_dir):
    index = data.topology_index(results, scratch)
    table = []
    for group in (data.STUDY, data.TIMERS):
        for row in data.rows(data.records(results, group), index):
            if group is data.TIMERS and row["timers"] == "topotest":
                continue  # the topotest-timer guests repeat graphs of the study; keep only the default-timer runs
            floor, full = data.tree_bound(row)
            off, on = row["off"]["down"], row["on"]["down"]
            r = {k: row[k] for k in ("label", "family", "seed", "routers", "links", "degree", "multiplicity",
                                     "timers", "folders", "sha")}
            r.update(floor=floor, full=full, off=mean(off) if off else None, on=mean(on) if on else None,
                     windows_off=len(off), windows_on=len(on),
                     left_out_off=row["off"]["windows"] - row["off"]["satisfied"],
                     left_out_on=row["on"]["windows"] - row["on"]["satisfied"],
                     link_saving=data.saving(row, "link"))
            if off and on:
                r.update(saving=1 - r["on"] / r["off"], bound=1 - floor / r["off"],
                         removed=(r["off"] - r["on"]) / (r["off"] - floor), on_per_floor=r["on"] / floor,
                         off_per_full=r["off"] / full)
            table.append(r)
    with open(os.path.join(out_dir, "tree_bound.json"), "w", encoding="utf-8") as fh:
        json.dump(table, fh, indent=1)

    def p(x):
        return "-" if x is None else f"{100 * x:.0f}%"

    def f(x):
        return "-" if x is None else f"{x:,.0f}"
    print("LSPs sent per link-down window (satisfied windows only) against the spanning-tree floor 2(n-1)")
    print(f"{'graph':<52} {'timers':<12} {'n':>4} {'m':>5} {'deg':>5} {'2hop':>5} {'off':>7} {'on':>6} {'floor':>5} "
          f"{'full':>6} {'off/full':>8} {'saving':>6} {'bound':>5} {'removed':>7} {'on/floor':>8} {'left out':>8}")
    for r in table:
        name = r["label"] + (f", seed {r['seed']}" if r["seed"] is not None and r["family"] == "random-regular" else "")
        if r["family"] == "random-regular":
            name += f", {r['routers']} routers"
        if r["off"] is not None and r["off"] > r["full"]:
            name = "* " + name
        print(f"{name[:52]:<52} {r['timers']:<12} {r['routers']:>4} {r['links']:>5} {r['degree']:>5.1f} "
              f"{(r['multiplicity'] or 0):>5.2f} {f(r['off']):>7} {f(r['on']):>6} {r['floor']:>5} {r['full']:>6} "
              f"{p(r.get('off_per_full')):>8} {p(r.get('saving')):>6} {p(r.get('bound')):>5} {p(r.get('removed')):>7} "
              f"{(r.get('on_per_floor') or 0):>8.2f} {r['left_out_off']:>3} {r['left_out_on']:>4}")
    print("\n* off sent more than full flooding of two LSPs allows: the window carried more than two new LSP instances "
          "(or retransmissions), so the floor 2(n-1) is not a bound there.")
    print("left out: windows not satisfied, off and on. A graph's runs from several result folders are pooled.")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else os.path.dirname(os.path.abspath(__file__)))
