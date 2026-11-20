"""Tables for results/timing-n64 from measurements.jsonl.gz: per topology and window kind, flood reduction off and
on, the flooding time of every window (ms, sorted), the median convergence time, and the windows in which every
router ended with the same LSPs. Run: python3 timing_tables.py measurements.jsonl.gz"""
import gzip
import json
import sys
from statistics import median

KINDS = ("link-down", "link-up", "node-down", "node-up", "multi-down", "multi-up")


def label(t):
    p = t["parameters"]
    if t["family"] == "random-regular":
        return f"random regular, degree {p['degree']}"
    if t["family"] == "leaf-spine":
        return f"leaf-spine, {p['leaves']} x {p['spines']}"
    return "flattened butterfly " + "x".join(map(str, p["radices"]))


cells = {}
with gzip.open(sys.argv[1], "rt", encoding="utf-8") as fh:
    for line in fh:
        rec = json.loads(line)
        side = "on" if rec["settings"]["flood_reduction"] else "off"
        key = (rec["topology"]["average_degree"], label(rec["topology"]))
        for p in rec["phases"]:
            t = p.get("timing")
            if p["phase"] not in KINDS or not t:
                continue
            c = cells.setdefault((key, p["phase"]), {}).setdefault(
                side, {"flood": [], "conv": [], "missing": 0, "ok": 0, "n": 0})
            c["n"] += 1
            c["ok"] += p["outcome"] == "satisfied"
            if t.get("flood_ms") is None:
                c["missing"] += 1
            else:
                c["flood"].append(round(t["flood_ms"]))
                c["conv"].append(t["max_ms"])


def fmt(c):
    if not c:
        return "-", "-", "-"
    fl = ", ".join(f"{x:,}" for x in sorted(c["flood"])) + (f" (+{c['missing']} missing)" if c["missing"] else "")
    cv = f"{median(c['conv']) / 1000:.2f}" if c["conv"] else "-"
    return fl, cv, f"{c['ok']} of {c['n']}"


print("| Topology | Window | Flooding, off (ms) | Flooding, on (ms) | Convergence, off -> on (median, s) "
      "| Consistent, off / on |")
print("|---|---|---|---|---|---|")
for (key, kind) in sorted(cells, key=lambda k: (k[0][1].split(",")[0], k[0][0], KINDS.index(k[1]))):
    v = cells[(key, kind)]
    off, on = fmt(v.get("off")), fmt(v.get("on"))
    print(f"| {key[1]} | {kind} | {off[0]} | {on[0]} | {off[1]} -> {on[1]} | {off[2]} / {on[2]} |")
