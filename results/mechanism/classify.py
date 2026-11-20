"""Summarize analyze_events.py --verbose output: for each down event, the router-LSP pairs that got their LSP more
than 1 s after it was built, by how they got it (CSNP exchange or flooding) and what their relays did.

    python results/mechanism/classify.py results/mechanism/analysis-*-on.txt

A pair's relays are the late router's neighbors that held the LSP before it. Classes:
- stale relay: a relay whose logged decision the model reproduces only with a snapshot that still holds failed links,
  and which, deciding on the topology without them, would have sent the LSP to the late router;
- unmatched relay: a relay that would have sent it on the topology without the failed links, but whose logged
  decision none of the tested snapshots reproduces;
- neither.
Also counts, over the stale relays of these pairs, which snapshots reproduce the relay's decision.
"""
import collections
import re
import sys

EVENT = re.compile(r"^(\S+): (.*?): (\d+)/(\d+) new LSPs, (\d+) router-LSP pairs, .*slowest (\d+) ms$")
LATE = re.compile(r"^   late: (\S+) got (\S+)'s LSP after (\d+) ms via (\S+?)[,;] .*?; "
                  r"(?:stale relay: (.*)|no stale relay found)$")
RELAY = re.compile(r"^      (\S+): reproduced by (.*); fresh topology sends to \S+: (True|False)$")
LATE_MS = 1000


def read(path):
    events, cur = [], None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            m = EVENT.match(line)
            if m:
                events.append({"lab": m[1], "event": m[2], "pairs": int(m[5]), "slowest": int(m[6]), "late": []})
                continue
            m = LATE.match(line)
            if m:
                cur = {"ms": int(m[3]), "how": m[4], "culprits": [x.strip() for x in (m[5] or "").split(",") if x.strip()],
                       "relays": {}}
                events[-1]["late"].append(cur)
                continue
            m = RELAY.match(line)
            if m:
                fits = frozenset(x.strip() for x in m[2].split(",")) - {"none"}
                cur["relays"][m[1]] = (fits, m[3] == "True")
    return events


def main(paths):
    total = collections.Counter()
    snapshots = collections.Counter()
    print("| Lab | Event | Router-LSP pairs | Later than 1 s | Via CSNP | Stale relay | Unmatched relay | Neither "
          "| Slowest, ms |")
    print("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for p in paths:
        for ev in read(p):
            late = [x for x in ev["late"] if x["ms"] > LATE_MS]
            c = collections.Counter()
            for x in late:
                c["late"] += 1
                c["csnp"] += x["how"].startswith("csnp")
                if x["culprits"]:
                    c["stale"] += 1
                    for n in x["culprits"]:
                        snapshots[" and ".join(sorted(x["relays"][n][0]))] += 1
                elif any(sends and not fits for fits, sends in x["relays"].values()):
                    c["unmatched"] += 1
                else:
                    c["neither"] += 1
            total.update(c)
            total["pairs"] += ev["pairs"]
            print(f"| {ev['lab']} | {ev['event']} | {ev['pairs']:,} | {c['late']} | {c['csnp']} | {c['stale']} "
                  f"| {c['unmatched']} | {c['neither']} | {ev['slowest']:,} |")
    print(f"| **All** | | **{total['pairs']:,}** | **{total['late']}** | **{total['csnp']}** | **{total['stale']}** "
          f"| **{total['unmatched']}** | **{total['neither']}** | |")
    print()
    print("Snapshots reproducing the stale relays' decisions (one count per late pair and relay):",
          ", ".join(f"{k}: {v}" for k, v in snapshots.most_common()))


if __name__ == "__main__":
    main(sys.argv[1:])
