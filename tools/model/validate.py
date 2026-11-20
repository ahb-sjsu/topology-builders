"""Check the flooding model against measured link changes: for every run in the given measurements files, find the
topology file the lab was written from (by the sha256 stored in the record, among the files under the folders in
TOPOLOGY_DIRS, separated by ":"), and compare LSPs sent per link-down and link-up window with the model's count for
the same link, flood reduction off and on, under three timing settings: lockstep, link delays jittered by up to one
unit, and that plus processing delay. Runs whose topology file is not found are skipped and reported.

    mkdir topos && tar -xzf results/seeds-n64/topologies.tar.gz -C topos
    TOPOLOGY_DIRS=topos python tools/model/validate.py results/seeds-n64/measurements.jsonl.gz
"""
import gzip
import hashlib
import json
import os
import random
import statistics as st
import sys
from collections import defaultdict

from topology_builders import clab as C
from topology_builders import flood_model as M
from topology_builders import output as O

TIMINGS = {"lockstep": dict(jitter=0.0, proc=0.0), "jitter1": dict(jitter=1.0, proc=0.0),
           "jitter1-proc0.5": dict(jitter=1.0, proc=0.5)}
SEEDS = 10


def topology(g):
    return M.Topology.from_lab(*C.plan(g))


def model(topo, link, state, reduction, timing):
    if timing["jitter"] == 0:
        return M.flood_link_change(topo, link, state, reduction, **timing)["sent"]
    rng = random.Random(1)
    return st.mean(M.flood_link_change(topo, link, state, reduction, rng=rng, **timing)["sent"] for _ in range(SEEDS))


ORIGINALS = {}


def index(dirs):
    """sha256 -> path of every topology file under dirs: the files the measured labs were written from."""
    for d in dirs:
        for root, _, names in os.walk(d):
            for n in names:
                if n.endswith(".json") and n not in ("manifest.json", "lab.json"):
                    p = os.path.join(root, n)
                    with open(p, "rb") as fh:
                        ORIGINALS.setdefault(hashlib.sha256(fh.read()).hexdigest(), p)


def main(files):
    cache, rows = {}, defaultdict(lambda: defaultdict(list))
    index(os.environ.get("TOPOLOGY_DIRS", "").split(":"))
    for path in files:
        for line in gzip.open(path, "rt"):
            r = json.loads(line)
            if [e.get("kind", "link") for e in r.get("events", [])] not in ([], ["link"] * len(r.get("events", []))):
                continue
            t = r["topology"]
            key = json.dumps([t["family"], t["parameters"]], sort_keys=True)
            if key not in cache:
                src = ORIGINALS.get(r["source_sha256"])
                cache[key] = topology(O.read(src)) if src else None
            topo = cache[key]
            if topo is None:
                print("sha256 mismatch, skipped:", key)
                continue
            on = bool(r["settings"]["flood_reduction"])
            windows = [p for p in r["phases"] if p["phase"] in ("link-down", "link-up")]
            for i, x in enumerate(r["links"]):
                for p in windows[2 * i:2 * i + 2]:
                    if p["outcome"] != "satisfied":
                        continue
                    state = "down" if p["phase"] == "link-down" else "up"
                    row = rows[(key, on, state)]
                    row["measured"].append(p["counters"]["tx_l2_lsp"])
                    for name, timing in TIMINGS.items():
                        row[name].append(model(topo, (x["a"], x["b"]), state, on, timing))
    print(f"{'topology':<44} {'red':<3} {'win':<4} {'n':>3} {'measured':>9} " +
          " ".join(f"{k:>16}" for k in TIMINGS) + "   measured-minus-model (" + list(TIMINGS)[1] + ")")
    for (key, on, state), row in sorted(rows.items()):
        fam, par = json.loads(key)
        name = fam + " " + ",".join(f"{k}={v}" for k, v in sorted(par.items()) if k != "routers")
        m = st.mean(row["measured"])
        cols = " ".join(f"{st.mean(row[k]):>16.1f}" for k in TIMINGS)
        print(f"{name[:44]:<44} {'on' if on else 'off':<3} {state:<4} {len(row['measured']):>3} {m:>9.1f} {cols}   "
              f"{m - st.mean(row[list(TIMINGS)[1]]):>8.1f}")


if __name__ == "__main__":
    main(sys.argv[1:])
