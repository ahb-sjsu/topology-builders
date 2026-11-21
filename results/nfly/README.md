# Flood reduction on multistage butterflies (k-ary n-fly): FRR

FRR pull request 24128 (`flood-reduction` under `router isis`, draft-ietf-lsr-distoptflood) at commit e263c441, on
four k-ary n-flies: n stages of k^(n-1) switches, each linked to the k switches of the next stage whose position
differs from its own in one base-k digit, switches only. Flood reduction off and on, two runs each; in each run 3
links were taken down and brought back up, one at a time, with a 30 s window after each change, and isisd's CPU per
event handler was recorded. The [model-only tables](../model-nfly/README.md) cover the same family up to 2,304
switches.

Runs of 2026-11-21, 01:10 to 02:21 UTC, and 04:15 to 04:32 UTC for the 3-ary 3-fly again (see Limits). Data:
`measurements.jsonl.gz`; `report.txt` is `topology-builders report` on it; `model.txt` is the flooding model's count
for the same links (`tools/model/validate.py`); `topologies.tar.gz` holds the four topology files the labs were
written from.

## Link changes: 25% to 57% fewer LSPs, following the two-hop multiplicity

LSPs are Level-2 LSPs sent, summed over the routers, mean per window; each topology has 12 link windows per variant
(2 runs x 3 links x down and up). CPU is isisd's CPU summed over the routers, net of a quiet window of the same length
in the same run; pairs compare the same link and direction, off against on (6 per topology).

| n-fly | Switches | Links | Degree | Two-hop multiplicity | LSPs sent, off | on | Fewer | CPU lower, mean (pairs lower) | median |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2-ary 5-fly | 80 | 128 | 3.2 | 1.25 | 357 | 269 | 25% | -8% (1 of 6) | -9% |
| 2-ary 4-fly | 32 | 48 | 3.0 | 1.27 | 141 | 96 | 32% | 20% (5 of 6) | 16% |
| 3-ary 3-fly | 27 | 54 | 4.0 | 1.62 | 168 | 82 | 51% | -25% (2 of 6) | -19% |
| 4-ary 3-fly | 48 | 128 | 5.3 | 1.82 | 402 | 171 | 57% | 18% (4 of 6) | 11% |

- **LSPs:** lower with flood reduction on in all 24 pairs. The saving follows the two-hop multiplicity (the mean
  number of common neighbors of two routers two hops apart) more than the size: the two 2-ary flies, with about 1.25,
  save 25% and 32%; the 3- and 4-ary 3-flies, with 1.62 and 1.82, save 51% and 57%. In the
  [random-regular sweep](../random-regular-n64/README.md) random graphs of 64 routers saved 12% at degree 4 (13%
  over three graphs in [seeds-n64](../seeds-n64/README.md)) and 23% at degree 6.
- **CPU:** no consistent difference. A link change costs these small networks about 150 to 1,200 ms of isisd CPU in
  total, and from 64% to all of it is route computation (`isis_run_spf_cb`, 147 to 1,043 ms without flood
  reduction), which costs the same with flood reduction on. The difference flood reduction makes, in receiving and sending LSPs, is a few to a few tens of
  milliseconds, below the run-to-run spread.
- Every window ended with every router holding the same LSPs as every other router: 96 of 96.

## Bring-up: 4% to 19% fewer LSPs

| n-fly | LSPs sent, off | on | Fewer | isisd s, off | on | Lower |
|---|---:|---:|---:|---:|---:|---:|
| 2-ary 4-fly | 3,856 | 3,721 | 4% | 3.30 | 3.35 | -2% |
| 2-ary 5-fly | 24,486 | 23,224 | 5% | 14.1 | 14.1 | 1% |
| 3-ary 3-fly | 3,990 | 3,633 | 9% | 3.59 | 3.46 | 4% |
| 4-ary 3-fly | 20,162 | 16,262 | 19% | 11.7 | 11.0 | 6% |

Every run converged, with flood reduction off and on.

## The flooding model on the same links

`model.txt`: the model's count for the same links, flood reduction on and off, beside FRR's. Link-down windows:

| n-fly | FRR, off -> on | Model on | Saving, FRR | Model, lockstep | Model, jittered |
|---|---|---:|---:|---:|---:|
| 2-ary 5-fly | 278 -> 213 | 212 | 24% | 17% | 39% |
| 2-ary 4-fly | 109 -> 75.3 | 75.3 | 31% | 20% | 40% |
| 3-ary 3-fly | 130 -> 64 | 64 | 51% | 40% | 60% |
| 4-ary 3-fly | 316 -> 130 | 130 | 59% | 49% | 69% |

- With flood reduction on, the model's count is FRR's to within 1%, and exactly FRR's on three of the four.
- FRR's saving falls inside the model's range, 7 to 11 points above its lockstep end: without flood reduction, FRR
  sent more LSPs than the lockstep count. On the 64-router random graphs, butterflies and leaf-spine fabrics, FRR's
  saving was within 5 points of the lockstep figure, so the [model-only tables](../model-nfly/README.md) understate
  the saving of n-flies by about 10 points.
- When a link comes up, FRR sends 30 to 111 more LSPs with flood reduction on than the model counts: the model leaves
  out the database exchange over the new adjacency.

## Limits of these runs

- Two runs per variant, 3 links per run, one topology per size.
- **The 3-ary 3-fly was measured twice.** Its first measurement (01:10 to 01:27 UTC) overlapped a desktop application
  on the host that used several of the routers' CPUs until 01:26, unevenly between its runs; it is kept apart in
  `k3-n3-first-run.jsonl.gz` (`report-k3-n3-first-run.txt`) and the tables above use the second one. The two agree on
  LSPs (172 and 168 off, 82 and 82 on) and disagree on CPU (25% lower with flood reduction on in the first, 25% higher
  in the second), which is a measure of how little the CPU figures for networks this small say.
- **Other load on the host.** Around 02:08 UTC, for a few minutes, during the 2-ary 5-fly's first runs, a database
  job on the host ran a burst of queries on several CPUs, the routers' among them. At 04:09 UTC, before the 3-ary
  3-fly's second measurement, a database backup was using about one CPU, not pinned; we did not check whether it was
  still running during that measurement. Throughout, a console demo engine of ours (running since 2026-09-28) used
  about 60% of one CPU, not pinned (it ran during every Atlas run in `results/`), and the host's own Docker daemons,
  outside the lab container, used about four CPUs.
  None of this changes which LSPs are sent; the off and on labs took turns, so both variants ran under the same
  conditions within a run.

## How it was run

```
topology-builders build k-ary-n-fly --k 4 --stages 3 --out topos/nfly-k4-n3.json
topology-builders clab topos/nfly-k4-n3.json --out labs/nfly-k4-n3 --name nfly-k4-n3 \
    --image frr-distoptflood:e263c441 --cpu-set 12-23,36-43
topology-builders measure labs/nfly-k4-n3/off labs/nfly-k4-n3/on --profile --links 3 --repeat 2 --max-wait 300 \
    --out nfly.jsonl
topology-builders report nfly.jsonl
mkdir topos && tar -xzf topologies.tar.gz -C topos && TOPOLOGY_DIRS=topos python tools/model/validate.py measurements.jsonl.gz
```

Same configuration, image and container setup as the [families results](../families-n64/README.md) (topotest
configuration: level-2-only, point-to-point, hello 1 s x 3, lsp-gen-interval 2; an LXD container with its own Docker,
every router pinned to the same 20 CPUs; CPUs 44-47, which share physical cores with four of them, ran no job of ours
during these runs), with topology-builders 0.2.0.dev0. The links are chosen from the topology file and seed 1, the same for off and
on; the labs take turns and the order alternates between the two runs.
