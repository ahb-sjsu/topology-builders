"""Read the measurements in `results/` and reduce them to one row per graph and timer setting, for the tree-bound
table (tree_bound.py), the figures (figures.py) and the further checks (review_checks.py).

Everything here reads the published data in `results/`; nothing is measured. The topology archives are extracted to a
scratch directory given on the command line.

Window rules, used by every table and figure:
- A link change is one link-down or link-up window; LSPs are the Level-2 LSPs sent, summed over all routers.
- Only windows whose outcome is "satisfied" count (every router ended with the same new LSPs). Rows say how many
  windows were left out. A variant with no satisfied window has no figure (for example 64 routers at degree 48 with
  flood reduction off, which never converged).
- Timing runs (`measure --timing`) are left out of counts and CPU: their debug logging costs CPU and they are read
  only for flooding times."""
import glob
import gzip
import hashlib
import json
import os
import tarfile
from statistics import mean

from topology_builders import output as O
from topology_builders.measure import net_isisd_ms
from topology_builders.report import label

# The folders measured on the workstation with the topotest timers, one graph per lab: the study's main data.
STUDY = ["random-regular-n64", "seeds-n64", "families-n64", "random-regular-n128", "random-regular-n256", "nfly",
         "fat-tree", "topology-zoo"]
TIMERS = ["operator-timers"]  # topotest and FRR default timers, in KVM guests


def records(results, folders):
    out = []
    for f in folders:
        with gzip.open(os.path.join(results, f, "measurements.jsonl.gz"), "rt", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    r = json.loads(line)
                    r["_folder"] = f
                    out.append(r)
    return out


def topology_index(results, workdir):
    """sha256 -> path of every topology file in the results' topologies.tar.gz archives."""
    index = {}
    for tar in sorted(glob.glob(os.path.join(results, "*", "topologies.tar.gz"))):
        d = os.path.join(workdir, os.path.basename(os.path.dirname(tar)))
        os.makedirs(d, exist_ok=True)
        with tarfile.open(tar) as t:
            t.extractall(d, filter="data")
        for root, _, names in os.walk(d):
            for n in names:
                if n.endswith(".json") and n not in ("manifest.json", "lab.json"):
                    p = os.path.join(root, n)
                    with open(p, "rb") as fh:
                        index.setdefault(hashlib.sha256(fh.read()).hexdigest(), p)
    return index


def multiplicity(rec, index, cache):
    """The graph's two-hop multiplicity: from the record if it carries it, else computed from the topology file."""
    t = rec["topology"]
    if t.get("two_hop_multiplicity") is not None:
        return t["two_hop_multiplicity"]
    sha = rec["source_sha256"]
    if sha not in cache:
        cache[sha] = O.two_hop_multiplicity(O.read(index[sha])) if sha in index else None
    return cache[sha]


def timers(rec):
    s = rec["settings"]
    return "topotest" if (s.get("hello_interval"), s.get("lsp_gen_interval")) == (1, 2) else "FRR defaults"


def rows(recs, index):
    """One dict per (graph, timer setting): sizes, multiplicity, and per variant the satisfied link windows.

    A graph is its family, parameters and router count, not its file's sha256: the same graph written by two builder
    versions has two hashes (the metadata differs), and its runs belong together."""
    groups, cache = {}, {}
    for r in recs:
        if r.get("timing"):
            continue
        t = r["topology"]
        key = (t["family"], json.dumps(t.get("parameters"), sort_keys=True), t["routers"], timers(r))
        groups.setdefault(key, []).append(r)
    out = []
    for (_, _, _, tm), rs in groups.items():
        sha = rs[0]["source_sha256"]
        t = rs[0]["topology"]
        row = {"sha": sha, "timers": tm, "label": label(t, seed=False), "family": t["family"],
               "seed": (t.get("parameters") or {}).get("seed"), "routers": t["routers"], "links": t["links"],
               "degree": t["average_degree"], "multiplicity": multiplicity(rs[0], index, cache),
               "folders": sorted({r["_folder"] for r in rs})}
        for fr, key in ((False, "off"), (True, "on")):
            mine = [r for r in rs if bool(r["settings"]["flood_reduction"]) == fr]
            win = [p for r in mine for p in r["phases"] if p["phase"] in ("link-down", "link-up")]
            ok = [p for p in win if p["outcome"] == "satisfied"]
            row[key] = {"runs": len(mine), "converged": sum(bool(r.get("converged")) for r in mine),
                        "windows": len(win), "satisfied": len(ok),
                        "down": [p["counters"].get("tx_l2_lsp", 0) for p in ok if p["phase"] == "link-down"],
                        "link": [p["counters"].get("tx_l2_lsp", 0) for p in ok],
                        "net_ms": [x for x in map(net_isisd_ms, ok) if x is not None]}
        out.append(row)
    return sorted(out, key=lambda r: (r["timers"], r["family"], r["routers"], r["degree"], r["label"]))


def saving(row, key):
    off, on = row["off"][key], row["on"][key]
    return 1 - mean(on) / mean(off) if off and on else None


def tree_bound(row):
    """Copies per link-down window: the spanning-tree floor and full flooding without duplicate suppression.

    A link-down changes two LSPs, one from each end of the link (the timing runs' targets show exactly two). Each
    must reach the other n - 1 routers, one send per reception at best: 2(n - 1). Full flooding sends each LSP on
    every adjacency but the one it arrived on: 2(m - 1) - (n - 1) per LSP on the m - 1 links left, assuming the graph
    stays connected."""
    n, m = row["routers"], row["links"]
    return 2 * (n - 1), 2 * (2 * (m - 1) - (n - 1))
