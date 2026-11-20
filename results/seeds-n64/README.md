# Three graphs per degree: 64 routers, with isisd's CPU per event handler

FRR pull request 24128 (`flood-reduction` under `router isis`, draft-ietf-lsr-distoptflood) at commit e263c441. The
[random-regular sweep](../random-regular-n64/README.md) used one graph per degree. This run takes three (seeds 1, 2
and 3) at degree 4, 8, 16 and 32, three runs of each variant per graph, and adds isisd's own CPU accounting per event
handler (`show event cpu`, cleared at the start of every window). The 4x4x4 flattened butterfly and the leaf-spine
fabric with 16 spines from the [families results](../families-n64/README.md) ran again, two runs each. In each run,
3 links were taken down and brought back up, one at a time, with a 30 s window after each change.

Runs of 2026-11-20, 04:28 to 13:00 UTC. Data: `measurements.jsonl.gz`; `report.txt` and `report-pooled.txt` are the
output of `topology-builders report` and `topology-builders report --pool-seeds` on it; `model.txt` is the flooding
model's count for the same links; `topologies.tar.gz` holds the 14 topology files the labs were written from.

## Link changes: the LSP saving depends on the degree, hardly on the graph

LSPs are Level-2 LSPs sent, summed over the 64 routers, mean per window. CPU is isisd's CPU time summed over the
routers, net of a quiet window with no event in the same run. Pairs compare the same link and direction, averaged over
the runs, off against on: 6 per graph, 18 per degree.

| Degree | LSPs sent, off | on | Fewer | Fewer, per graph | Net isisd ms, off | on | Lower, means | Lower, per graph | Pairs lower on | Median saving over pairs |
|---:|---:|---:|---:|---|---:|---:|---:|---|---:|---:|
| 4 | 366 | 320 | 13% | 9%, 15%, 14% | 857 | 898 | -5% | 5%, -16%, -4% | 9 of 18 | -4% |
| 8 | 789 | 512 | 35% | 36%, 35%, 34% | 1,516 | 1,422 | 5% | 16%, 13%, -13% | 11 of 18 | 10% |
| 16 | 1,696 | 428 | 75% | 75%, 75%, 74% | 2,987 | 2,687 | 10% | 10%, 13%, 7% | 16 of 18 | 10% |
| 32 | did not converge | 238 | | | | | | | | |

| Topology | LSPs sent, off | on | Fewer | Net isisd ms, off | on | Lower, means | Pairs lower on | Median saving over pairs |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Flattened butterfly 4x4x4 | 922 | 274 | 70% | 1,675 | 1,591 | 5% | 3 of 6 | 5% |
| Leaf-spine, 48 leaves x 16 spines | 2,686 | 178 | 93% | 4,037 | 2,717 | 33% | 6 of 6 | 31% |

- **LSPs:** the three graphs of one degree save within 1 point of each other at degree 8 and 16, and within 6 points
  at degree 4. Seed 1 agrees with the random-regular sweep, which ran in a different setup (12%, 36% and 75% there),
  and the butterfly and leaf-spine agree with the families sweep (68% and 93% there). In all 66 pairs (random
  graphs up to degree 16, butterfly, leaf-spine), flood reduction sent fewer LSPs.
- **CPU:** small and not consistent below degree 16. At degree 16 it is lower in 16 of 18 pairs, by a median of
  10%, as in the families sweep's rerun in this setup (10%) and against 19% in the random-regular sweep's setup.
- **CPU does not repeat as well as LSPs.** On the butterfly, the families sweep found a median 22% saving, lower in 6
  of 6 pairs; this run finds 5%, lower in 3 of 6, with the same graph, links, configuration and setup. On leaf-spine,
  40% then and 31% now. Two runs per variant are not enough to pin CPU savings of this size down.
- Every window ended with every router holding the same LSPs as every other router: 372 of 372 on the random graphs
  up to degree 16, the butterfly and leaf-spine, and 54 of 54 with flood reduction on at degree 32.

## Where isisd's CPU goes: route computation, which flood reduction does not change

isisd's CPU per event handler, mean ms per link window net of the quiet window, off -> on, averaged over the graphs of
one degree (the per-graph figures are in `report.txt`):

| Topology | Route computation (`isis_run_spf_cb`) | Receiving (`isis_receive`) | Sending (`tx_queue_send_event`) | Route computation's share of the net CPU, off |
|---|---|---|---|---:|
| Random regular, degree 4 | 737 -> 736 | 84 -> 108 | 6.9 -> 6.5 | 86% |
| Random regular, degree 8 | 1,320 -> 1,306 | 174 -> 124 | 11.8 -> 8.7 | 87% |
| Random regular, degree 16 | 2,702 -> 2,601 | 349 -> 230 | 23.4 -> 7.4 | 90% |
| Flattened butterfly 4x4x4 | 1,586 -> 1,356 | 125 -> 158 | 14.4 -> 5.7 | 95% |
| Leaf-spine, 48 x 16 | 3,296 -> 2,854 | 877 -> 117 | 38.3 -> 3.1 | 82% |

- For a single link change, route computation is 82% to 95% of isisd's net CPU, and costs about the same with flood
  reduction on: every router still recomputes its routes. Receiving is where the LSP saving shows (877 to 117 ms on
  leaf-spine), and sending costs little either way.
- This is why the CPU saving is so much smaller than the LSP saving. It answers the question left open in the
  random-regular sweep, which saw 94% fewer LSPs but about a fifth less CPU at degree 32.
- With ten links failing at once ([flap10-n64](../flap10-n64/README.md)) receiving costs more than route computation
  without flood reduction, and the CPU saving is much larger.
- On the butterfly and leaf-spine, route computation also cost 13% to 15% less with flood reduction on, because the
  routers ran fewer route computations, each costing the same: on leaf-spine 100 instead of 131 per link-down window
  (summed over the 64 routers) and 191 instead of 217 per link-up window; on the butterfly 121 instead of 128 and 201
  instead of 239. On the random graphs the counts are within 2% (about 2 per router when a link goes down and 3.5
  when it comes up), except link-up at degree 16: 221 against 236. We have not looked at why fewer run; the counts are in the data (`event_cpu`, milliseconds and
  calls per handler).

## Degree 32: without flood reduction, none of the 9 runs converged

| Degree 32 (1,024 links), 3 graphs x 3 runs | off | on |
|---|---:|---:|
| Runs that converged | 0 of 9 | 9 of 9 |
| Bring-up LSPs sent, mean | 12.7 million | 262,921 |
| Bring-up isisd CPU, mean | 3,208 s | 196 s |
| Link windows satisfied | 0 of 54 | 54 of 54 |

In the random-regular sweep, degree 32 without flood reduction converged in both runs, with the routers unpinned on
the host's 25 CPUs; here they share 20, and the families sweep found the same at 960 and 1,024 links. Where the
routers without flood reduction stop converging depends on the CPU they share, so this is a statement about the
total work, not about routers with CPUs of their own. The link-change rows for degree 32 compare a network that never
converged with one that did, so the table above leaves out their saving.

## Bring-up: from 3% fewer LSPs at degree 4 to 47% at degree 16

From the routers' start to the check that finds every router with all its adjacencies and the same LSPs as every
other router; mean of the runs, isisd CPU in seconds summed over the routers.

| Topology | LSPs sent, off | on | Fewer | isisd s, off | on | Lower | Converged, off / on |
|---|---:|---:|---:|---:|---:|---:|---|
| Random regular, degree 4 | 22,102 | 21,370 | 3% | 12.0 | 12.2 | -2% | 9 of 9 / 9 of 9 |
| Random regular, degree 8 | 73,403 | 59,780 | 19% | 31.4 | 29.0 | 8% | 9 of 9 / 9 of 9 |
| Random regular, degree 16 | 246,783 | 131,774 | 47% | 95.5 | 71.0 | 26% | 9 of 9 / 9 of 9 |
| Flattened butterfly 4x4x4 | 90,346 | 62,496 | 31% | 37.6 | 32.8 | 13% | 2 of 2 / 2 of 2 |
| Leaf-spine, 48 x 16 | 448,622 | 171,922 | 62% | 181.8 | 112.3 | 38% | 2 of 2 / 2 of 2 |

The three graphs of one degree are within 4 points of each other, for LSPs and for CPU (per graph in `report.txt`).

## The flooding model on these graphs

The model's count for the same links ([main README](../../README.md#a-model-of-flooding)), as the saving over the
link-down and link-up windows of each graph. "Lockstep": every link takes one unit and no processing delay;
"jittered": link delays drawn from 1 to 2 units, which raises the count without flood reduction.

| Topology | FRR | Model, lockstep | Model, jittered |
|---|---:|---:|---:|
| Random regular, degree 4, seeds 1, 2, 3 | 9%, 15%, 14% | 9%, 10%, 10% | 21%, 24%, 23% |
| Random regular, degree 8, seeds 1, 2, 3 | 36%, 35%, 34% | 36%, 35%, 33% | 48%, 48%, 46% |
| Random regular, degree 16, seeds 1, 2, 3 | 75%, 75%, 74% | 78%, 78%, 77% | 81%, 81%, 80% |
| Flattened butterfly 4x4x4 | 70% | 70% | 75% |
| Leaf-spine, 48 x 16 | 93% | 90% | 95% |

The lockstep saving is within 5 points of FRR's on all 11 topologies. With flood reduction on, FRR sent 5% to 15%
more LSPs than the model counts (`model.txt`).

## Limits of these runs

- Three runs per variant per graph (two for the butterfly and leaf-spine), 3 links per run.
- **Other load on the host's CPUs.** The routers were pinned to CPUs 12-23 and 36-43. During some of these runs, other
  jobs of ours (a QEMU guest, an FRR build, small namespace labs) ran pinned to CPUs 44-47, which share physical
  cores with CPUs 20-23, four of the routers' 20. That load overlapped degree 4 (seeds 1, partly, 2 and 3), degree 8
  (seeds 1 and 2), degree 16 (seeds 2 and 3) and degree 32 (seed 1); degree 8 seed 3, degree 16 seed 1, degree 32
  seeds 2 and 3, the butterfly and leaf-spine ran without it. It slows the routers that run on those four CPUs and
  can raise their CPU times; it does not change which LSPs are sent. The off and on labs took turns throughout, so
  both variants ran under the same conditions in a run. At degree 16 the graph that ran without it (10%) falls
  between the two that ran with it (13% and 7%); at degree 8 the graph without it gave -13% against 16% and 13% with
  it. We cannot tell that apart from the spread between graphs, and cannot rule out an effect on CPU.
- Single link changes only; the [timing results](../timing-n64/README.md) cover router and multi-link failures.

## How it was run

```
topology-builders sweep --routers 64 --families random-regular --seeds 1,2,3 --out topos64
topology-builders clab topos64/random-regular-n64-d$D-s$S.json --out labs/p-rr64-d$D-s$S --name p-rr64-d$D-s$S \
    --image frr-distoptflood:e263c441 --cpu-set 12-23,36-43
topology-builders measure labs/p-rr64-d$D-s$S/off labs/p-rr64-d$D-s$S/on --profile --links 3 --repeat 3 \
    --max-wait 300 --out seeds.jsonl
topology-builders report --pool-seeds seeds.jsonl
```

The butterfly and leaf-spine the same way with `--repeat 2`. Same configuration, image and container setup as the
[families results](../families-n64/README.md) (topotest configuration: level-2-only, point-to-point, hello 1 s x 3,
lsp-gen-interval 2; an LXD container with its own Docker, every router pinned to the same 20 CPUs), with
topology-builders 0.2.0.dev0. The links are chosen from the topology file and seed 1, the same for off and on; the
labs take turns and the order alternates between runs. The model's counts, from the topology files the labs were written from
(`topologies.tar.gz`, matched by sha256): `mkdir topos && tar -xzf topologies.tar.gz -C topos &&
TOPOLOGY_DIRS=topos python tools/model/validate.py measurements.jsonl.gz`.
