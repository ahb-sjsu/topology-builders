# Why flooding was slow after router and multi-link failures, with flood reduction on

The [timing results](../timing-n64/README.md) found that when a router failed, or three links failed together,
flooding with flood reduction on (FRR pull request 24128 at e263c441) often took one to eight seconds to reach the
last router, against well under half a second without it. This lab replays those same failures with more of isisd's
logging, to see how the last routers got the new LSPs and why they got them late.

**Answer.** The late routers got the new LSPs through the periodic CSNP exchange (complete sequence-number PDUs,
which neighbors exchange to repair their databases), not through flooding: 242 of the
250 router-LSP pairs that arrived more than 1 s late. In 244 of the 250, a neighbor that already held the LSP did not
send it on because it decided with a topology that still held some of the failed links: it counted on a router that
had just lost its links to cover the late router. That topology was the one isisd built at the neighbor's first
flooding decision after the failure, when it had received only the first one to five of the failure's new LSPs, and
kept until its next route computation (see [when the topology is built](#when-the-topology-is-built); an earlier
version of this README said it was the topology from before the failure, which was wrong). Without flood reduction, on
the same butterfly and the same failures, every router had every new LSP within 236 ms.

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
- **Event times.** `events.json` gives, for each event, the earliest time at which one router had finished setting
  its links down or up (`NetnsLab.apply`: each router runs its `ip link set` commands, then reads the clock). A failed
  router sets all its own links, 9 on the butterfly and 48 on a spine, so the failure starts before that time: the
  first new LSPs were built up to 1.33 s before it. The analysis therefore looks for each failure's new LSPs from 5 s
  before the recorded time, and takes the "frozen" snapshot at the neighbor's first decision after the failure's
  first new LSP. Until 2026-11-25 it looked from 0.5 s before the recorded time. After router r25 failed, that left
  out two of the nine new LSPs and timed a third from the recovery LSP its router built 25 s later, and after spine
  r1 failed it did the same for one leaf's LSP. It also took the "frozen" snapshot at the neighbor's first decision
  after the recorded time, which can be later than its first decision after the failure.
- **Setup:** 2026-11-20, 09:06 to 09:58 UTC, in the container shaped like Colab ([colab-shaped](../colab-shaped/README.md):
  Ubuntu 24.04, FRR from the same commit built by `tools/colab/setup.sh`), namespace backend, 64 routers on 4 CPUs.
  Those 4 CPUs share physical cores with 4 of the CPUs a measurement campaign was using at the same time, so
  absolute times here are not comparable with the timing runs' (some delays here are longer, some shorter). A
  console demo engine of ours (running since 2026-09-28) used about 60% of one CPU throughout, not pinned, and the
  host's own Docker daemons also ran; neither changes which LSPs are sent.

## Results: arrivals more than 1 s after the LSP was built

| Lab | Event | Router-LSP pairs | Later than 1 s | Via CSNP | Stale relay | Unmatched relay | Neither | Slowest, ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Butterfly 4x4x4, on | router r25 fails | 558 | 2 | 2 | 2 | 0 | 0 | 1,802 |
| Butterfly 4x4x4, on | router r45 fails | 558 | 12 | 8 | 8 | 1 | 3 | 6,873 |
| Butterfly 4x4x4, on | links r0-r2, r19-r31, r32-r40 fail | 378 | 7 | 6 | 7 | 0 | 0 | 2,981 |
| Butterfly 4x4x4, on | links r48-r50, r52-r55, r52-r56 fail | 315 | 1 | 1 | 1 | 0 | 0 | 4,897 |
| Leaf-spine 48 x 16, on | spine r6 fails | 2,976 | 153 | 153 | 116 | 37 | 0 | 8,787 |
| Leaf-spine 48 x 16, on | spine r1 fails | 2,976 | 70 | 70 | 37 | 33 | 0 | 1,710 |
| Leaf-spine 48 x 16, on | links r2-r49, r7-r40, r10-r46 fail | 378 | 2 | 2 | 2 | 0 | 0 | 2,414 |
| Leaf-spine 48 x 16, on | links r4-r36, r4-r37, r13-r29 fail | 315 | 3 | 0 | 0 | 0 | 3 | 1,166 |
| **All, flood reduction on** | | **8,454** | **250** | **242** | **173** | **71** | **6** | |
| Butterfly 4x4x4, off | the same four events | 1,809 | 0 | | | | | 175, 179, 236, 163 |

"Unmatched relay": a neighbor that, on the fresh topology, would have sent the LSP to the late router, but whose
logged decision none of the four snapshots reproduces. Until 2026-11-25 the analysis looked for the new LSPs from
0.5 s before each event's recorded time (see Event times above); this table then read 434 pairs, 1 late pair and
1,056 ms for router r25, and 8,330, 249, 241 and 172 in all.

- **Late routers were rescued by CSNPs.** 242 of the 250 late pairs got the LSP through the CSNP exchange: 1 to
  8.8 s after it was built (median 2.8 s), within one CSNP interval.
- **The relay decided with a topology that still held failed links.** In 173 pairs a stale relay is found. Counting
  each such relay once per pair, there are 175 relay decisions: 174 are reproduced by the "frozen" snapshot (the
  failed links of the new LSPs the relay held at its first decision after the failure removed), 173 of them also by
  the snapshot with no failed link removed, and one only by "rebuilt". The neighbor had received the new LSP, but
  decided as if the failed router or links were still there: it left the late router to a router that could no
  longer reach it. [When the topology is built](#when-the-topology-is-built) shows which topology each one used.
- **Leaf-spine, spine failure:** with flood reduction on, each leaf's new LSP is sent on to the other leaves by a few
  spines. After spine r6 failed, spines that decided as if r6 were still up left some leaves to r6. Those leaves got
  four leaves' LSPs from CSNPs, staggered from 0.5 to 8.8 s.
- **The 71 unmatched pairs** have the same cause. None of the four snapshots reproduces the relay's decision, but
  the topology the relay held when isisd built its decision topology does, in all 71 (next section). For 6 pairs no
  relay explanation is found.
- **The control.** Without flood reduction, on the same butterfly and the same four failures, no router got a new LSP
  later than 236 ms. The leaf-spine lab without flood reduction never converged on 4 CPUs with this much logging, so
  leaf-spine has no control here. In the timing runs, on 20 CPUs, three links failing together on leaf-spine flooded
  in 0.28 to 0.43 s without flood reduction; a spine failure took 1.5 to 1.9 s without it and 1.5 to 2.6 s with
  it.
- **Below 1 s.** After spine r1 failed, a further 399 pairs arrived between 0.5 and 1 s, most of them by flooding. On
  leaf-spine, router failures were slow with flood reduction off as well, so these are not counted as late.

## When the topology is built

- **From FRR's code at e263c441** (`isisd/isis_lsp.c`, `isisd/isis_spf.c`): the topology a router decides with is
  built from its LSP database at the first flooding decision after a route computation starts, and dropped only when
  the next route computation starts; a comment there says this limits rebuilds to one per route computation instead
  of one per received LSP. Every LSP received schedules a route computation, at most one per `spf-interval` (1 s by
  default, counted in whole seconds). Between two route computations, decisions therefore use a topology without the
  LSPs that arrived after it was built.
- **What the logs show** (`tools/model/check_builds.py`, on the full logs; `analysis-builds.txt`). `debug isis
  spf-events` logs each route computation's start ("SPF needed"). For each of the 246 relay decisions behind the 244
  late pairs with a stale or unmatched relay, the check takes the relay's last route-computation start before the
  decision and its first flood-reduction decision after that start, when isisd built the topology the relay decided
  with.
  - Every topology was built after the failure had begun, when the relay had received 1 to 5 of the failure's new
    LSPs. None was built before the failure.
  - No route computation started between the build and the decision.
  - On the topology held at the build (the failed links removed where the relay had received an end's new LSP), the
    model reproduces 245 of the 246 logged decisions exactly. The other is reproduced by the topology the relay held
    0.2 ms later, at the decision itself. The topology held at the decision reproduces none of the other 245.
  - Most decisions came in the burst of LSPs that follows a failure: 99 within 1 ms of the build, 107 more than
    100 ms after it (up to 0.96 s).

  So a relay decides with the topology isisd built on the first of the failure's new LSPs it received, and its
  decisions on the later ones still count on links those LSPs report down. An earlier version of this README said
  the topology was built before the failure. That came from the analysis window (see Event times), not from isisd.
- **Why the wait is seconds.** The draft (section 1.2.4) recommends that a router which does not reflood an LSP send
  every neighbor a PSNP listing it after a short timer, much shorter than the CSNP interval, so that a neighbor
  missing it asks for it. The pull request leaves this out and relies on periodic CSNPs, so the late routers waited
  up to a CSNP interval.
- Whether this can leave a router without an LSP for good. Here no router was: every router got every new LSP
  within the window, by CSNP if not by flooding, as in the timing runs. That relies on the periodic CSNPs.

One way to avoid the misses would be to drop the cached topology whenever a newer LSP changes a router's adjacencies,
or to remove from it the adjacencies that LSP no longer reports. [results/cache-experiment](../cache-experiment/README.md)
tests the first, with the topology rebuilt at every decision: no router got a new LSP more than 1 s late, and the
LSPs sent rose by 1.5% to 4.5%. The draft's short-timer PSNP would shorten the wait whatever the cause; it is not
tested.

## Files

- `analysis-fb444-on.txt`, `analysis-fb444-off.txt`, `analysis-ls16-on.txt`: `analyze_events.py --verbose`, with
  every late pair and every relay's snapshot matches.
- `classify.py`: the table above, from those files: `python classify.py analysis-*-on.txt`.
- `analysis-builds.txt`: `check_builds.py` on the two labs with flood reduction on: when each relay's decision
  topology was built, and which topologies reproduce its decision, per relay decision.
- `logs.tar.gz`: for each lab, the lab (`lab/lab.json`), the events with their times (`events.json`), and every
  router's log reduced by `tools/model/filter_logs.py` to the lines the two analyses read (LSPs built and received,
  flood-reduction decisions, route-computation starts, CSNPs received and the CSNP comparisons that found a newer or
  older copy), from 6 s before the first event's recorded time to 30 s after the last. Both analyses print exactly
  the same on these reduced logs as on the full logs (2.2 GB).

```
mkdir mech && tar -xzf results/mechanism/logs.tar.gz -C mech
python tools/model/analyze_events.py --verbose mech/fb444-on mech/fb444-off mech/ls16-on
python tools/model/check_builds.py mech/fb444-on mech/ls16-on
```

Run the lab again (Linux, root or `unshare -Urnm`, FRR with the pull request installed, as `tools/colab/setup.sh`
builds it):

```
unshare -Urnm python3 tools/model/collect_events.py --out mech --topology fb444.json --events fb444-events.json \
    --reduction both
```

where `fb444.json` is the topology file and `fb444-events.json` the `node` and `multi` events of the butterfly's
record with flood reduction on in `results/timing-n64/measurements.jsonl.gz`.
