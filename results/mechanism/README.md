# Why flooding was slow after router and multi-link failures, with flood reduction on

The [timing results](../timing-n64/README.md) found that when a router failed, or three links failed together,
flooding with flood reduction on (FRR pull request 24128 at e263c441) often took one to eight seconds to reach the
last router, against well under half a second without it. This lab replays those same failures with more of isisd's
logging, to see how the last routers got the new LSPs and why they got them late.

**Answer.** The late routers got the new LSPs through the periodic CSNP exchange, not through flooding: 241 of the
249 router-LSP pairs that arrived more than 1 s late. In 172 of the 249, a neighbor that already held the LSP did not
send it on because it decided with the topology from before the failure: it counted on a router that had just lost
its links to cover the late router. Without flood reduction, on the same butterfly and the same failures, every
router had every new LSP within 236 ms.

## Method

- **The lab** (`tools/model/collect_events.py`): the 4x4x4 flattened butterfly and the leaf-spine fabric of 48 leaves
  and 16 spines from the timing runs, with the same events, taken from those runs' records: two routers failing
  (each with all its links at once) and two sets of three links failing together, each followed by recovery. Flood
  reduction on, then off. Every router logs each flood-reduction decision (`debug isis flooding`: selected or not,
  the sizes of the two-hop and remote neighbor lists, start index, number of neighbors skipped), each LSP it builds
  or receives (`debug isis update-packets`, microsecond timestamps), every CSNP and PSNP (`debug isis
  snp-packets`) and its route-computation scheduling (`debug isis spf-events`). 25 s windows after each change,
  longer than the interval between CSNPs (about 9 s on each interface in these logs; the configuration leaves FRR's
  default).
- **The analysis** (`tools/model/analyze_events.py`): for each failure, each new LSP (from the routers that lost
  links) and each other router: the time from the LSP's build to the router's first copy, and how it came:
  - **flooding;**
  - **CSNP, asked:** before the LSP arrived, the router's log shows a neighbor's CSNP listing a newer copy than its
    own ("is newer than ours"), so the router asked for it with a PSNP;
  - **CSNP, sent:** the neighbor's log shows the router's CSNP listing an older copy, so the neighbor sent the new one.

  For each pair later than the threshold, it takes the late router's neighbors that held the LSP before it and, for
  each, the flood-reduction decision the neighbor logged on that LSP. It runs the [flooding model](../../README.md#a-model-of-flooding)'s
  decision for the same router, LSP and transmitting neighbor on four topology snapshots: the topology with every
  failed link removed ("fresh"), with none removed ("old", as before the failure), and two partial ones (the failed
  links of the new LSPs the neighbor held when it decided, or held at its first decision after the failure), and
  notes which snapshots reproduce the logged decision exactly. The model's decision matches FRR's exactly, given the
  snapshot ([model-decisions](../model-decisions/README.md)), so this tells which topology the neighbor decided with.
  A **stale relay** is a neighbor whose decision only snapshots holding failed links reproduce, and which, deciding
  on the fresh topology, would have sent the LSP to the late router.
- **Setup:** 2026-11-20, 09:06 to 09:58 UTC, in the container shaped like Colab ([colab-shaped](../colab-shaped/README.md):
  Ubuntu 24.04, FRR from the same commit built by `tools/colab/setup.sh`), namespace backend, 64 routers on 4 CPUs.
  Those 4 CPUs share physical cores with 4 of the CPUs a measurement campaign was using at the same time, so
  absolute times here are not comparable with the timing runs' (some delays here are longer, some shorter).

## Results: arrivals more than 1 s after the LSP was built

| Lab | Event | Router-LSP pairs | Later than 1 s | Via CSNP | Stale relay | Unmatched relay | Neither | Slowest, ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Butterfly 4x4x4, on | router r25 fails | 434 | 1 | 1 | 1 | 0 | 0 | 1,056 |
| Butterfly 4x4x4, on | router r45 fails | 558 | 12 | 8 | 8 | 1 | 3 | 6,873 |
| Butterfly 4x4x4, on | links r0-r2, r19-r31, r32-r40 fail | 378 | 7 | 6 | 7 | 0 | 0 | 2,981 |
| Butterfly 4x4x4, on | links r48-r50, r52-r55, r52-r56 fail | 315 | 1 | 1 | 1 | 0 | 0 | 4,897 |
| Leaf-spine 48 x 16, on | spine r6 fails | 2,976 | 153 | 153 | 116 | 37 | 0 | 8,787 |
| Leaf-spine 48 x 16, on | spine r1 fails | 2,976 | 70 | 70 | 37 | 33 | 0 | 1,710 |
| Leaf-spine 48 x 16, on | links r2-r49, r7-r40, r10-r46 fail | 378 | 2 | 2 | 2 | 0 | 0 | 2,414 |
| Leaf-spine 48 x 16, on | links r4-r36, r4-r37, r13-r29 fail | 315 | 3 | 0 | 0 | 0 | 3 | 1,166 |
| **All, flood reduction on** | | **8,330** | **249** | **241** | **172** | **71** | **6** | |
| Butterfly 4x4x4, off | the same four events | 1,809 | 0 | | | | | 175, 179, 236, 163 |

"Unmatched relay": a neighbor that, on the fresh topology, would have sent the LSP to the late router, but whose
logged decision none of the four snapshots reproduces. "Router-LSP pairs" counts the new LSPs the analysis found
being built in the window: after router r25 failed with flood reduction on, it found 7 of the 9.

- **Late routers were rescued by CSNPs.** 241 of the 249 late pairs got the LSP through the CSNP exchange: 1 to
  8.8 s after it was built (median 2.8 s), within one CSNP interval.
- **The relay decided with the topology from before the failure.** In 172 pairs a stale relay is found. Counting
  each such relay once per pair, 173 of the 174 relay decisions are reproduced by the snapshot with none of the
  failed links removed (in 19 of them a partial snapshot gives the same decision), and one only by a partial one. The
  neighbor received the new LSP, but decided as if the failed router or links were still there: it left the late
  router to a router that could no longer reach it.
- **Leaf-spine, spine failure:** with flood reduction on, each leaf's new LSP is sent on to the other leaves by a few
  spines. After spine r6 failed, spines that decided as if r6 were still up left some leaves to r6. Those leaves got
  four leaves' LSPs from CSNPs, staggered from 0.5 to 8.8 s.
- **The 71 unmatched pairs** fit the same picture but are not shown by it: the neighbor that should have sent the
  LSP decided with some topology other than the four tried, for example one holding only some of the failed links.
  For 6 pairs no relay explanation is found.
- **The control.** Without flood reduction, on the same butterfly and the same four failures, no router got a new LSP
  later than 236 ms. The leaf-spine lab without flood reduction never converged on 4 CPUs with this much logging, so
  leaf-spine has no control here. In the timing runs, on 20 CPUs, three links failing together on leaf-spine flooded
  in 0.28 to 0.43 s without flood reduction; a spine failure took 1.5 to 1.9 s without it and 1.5 to 2.6 s with
  it.
- **Below 1 s.** After spine r1 failed, a further 395 pairs arrived between 0.5 and 1 s, most of them by flooding. On
  leaf-spine, router failures were slow with flood reduction off as well, so these are not counted as late.

## What the logs do not show

- Why the relays' snapshots were from before the failure. `debug isis spf-events` logs when a route computation is
  scheduled, not when it ends, so these logs cannot say whether the snapshot is refreshed with the route computation.
- Whether this can leave a router without an LSP for good. Here no router was: every router got every new LSP
  within the window, by CSNP if not by flooding, as in the timing runs. That relies on the periodic CSNPs.

One way to avoid the delay would be to remove from the snapshot, before deciding, the adjacencies that the new LSPs
in the database no longer report, so that a router never counts on a neighbor that has lost its links. We have not
tested this.

## Files

- `analysis-fb444-on.txt`, `analysis-fb444-off.txt`, `analysis-ls16-on.txt`: `analyze_events.py --verbose`, with
  every late pair and every relay's snapshot matches.
- `classify.py`: the table above, from those files: `python classify.py analysis-*-on.txt`.
- `logs.tar.gz`: for each lab, the lab (`lab/lab.json`), the events with their times (`events.json`), and every
  router's log reduced to the lines the analysis reads (LSPs built and received, flood-reduction decisions, CSNPs
  received and the CSNP comparisons that found a newer or older copy), from 1 s before the first failure to 30 s
  after the last. The analysis on these reduced logs prints exactly what it printed on the full logs (2.2 GB).

```
mkdir mech && tar -xzf results/mechanism/logs.tar.gz -C mech
python tools/model/analyze_events.py --verbose mech/fb444-on mech/fb444-off mech/ls16-on
```

Run the lab again (Linux, root or `unshare -Urnm`, FRR with the pull request installed, as `tools/colab/setup.sh`
builds it):

```
unshare -Urnm python3 tools/model/collect_events.py --out mech --topology fb444.json --events fb444-events.json \
    --reduction both
```

where `fb444.json` is the topology file and `fb444-events.json` the `node` and `multi` events of the butterfly's
record with flood reduction on in `results/timing-n64/measurements.jsonl.gz`.
