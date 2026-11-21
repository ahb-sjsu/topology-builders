# Flood reduction on three-tier fat-trees: FRR, 20 to 180 switches

FRR pull request 24128 (`flood-reduction` under `router isis`, draft-ietf-lsr-distoptflood) at commit e263c441, on
k-ary fat-trees (Al-Fares, Loukissas and Vahdat, SIGCOMM 2008) for k = 4 to 12: k pods of k/2 edge and k/2
aggregation switches and (k/2)^2 core switches, switches only. Flood reduction off and on, two runs each; in each run
3 links were taken down and brought back up, one at a time, with a 30 s window after each change, and isisd's CPU per
event handler was recorded. The [model-only tables](../model-fat-tree/README.md) cover the same family up to k = 24.

Runs of 2026-11-21, 02:23 to 04:07 UTC. Data: `measurements.jsonl.gz`; `report.txt` is `topology-builders report`
on it; `model.txt` is the flooding model's count for the same links (`tools/model/validate.py`);
`topologies.tar.gz` holds the five topology files the labs were written from.

## Link changes: 40% fewer LSPs at k = 4, 68% at k = 12

LSPs are Level-2 LSPs sent, summed over the routers, mean per window; each topology has 12 link windows per variant
(2 runs x 3 links x down and up). CPU is isisd's CPU summed over the routers, net of a quiet window of the same length
in the same run; pairs compare the same link and direction, off against on (6 per topology).

| Fat-tree | Switches | Links | Degree | Two-hop paths | LSPs sent, off | on | Fewer | CPU lower, mean (pairs lower) | median |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| k = 4 | 20 | 32 | 3.2 | 1.48 | 97 | 58 | 40% | 26% (4 of 6) | 29% |
| k = 6 | 45 | 108 | 4.8 | 1.82 | 337 | 158 | 53% | 4% (3 of 6) | 2% |
| k = 8 | 80 | 256 | 6.4 | 2.06 | 765 | 313 | 59% | 18% (6 of 6) | 18% |
| k = 10 | 125 | 500 | 8.0 | 2.25 | 1,470 | 556 | 62% | 4% (4 of 6) | 4% |
| k = 12 | 180 | 864 | 9.6 | 2.39 | 2,661 | 847 | 68% | 10% (6 of 6) | 9% |

- **LSPs:** lower with flood reduction on in all 30 pairs; the saving rises with the radix and with the number of
  two-hop paths (the mean number of common neighbors of two routers two hops apart), from 1.48 at k = 4 to 2.39 at
  k = 12. Random graphs of 64 routers at similar degrees saved 11% to 13% (degree 4), 23% (degree 6) and 36% (degree
  8) in the [random-regular sweep](../random-regular-n64/README.md).
- **CPU:** lower in 23 of 30 pairs, by a median of 2% to 29%, with no trend in k. Without flood reduction, route
  computation (`isis_run_spf_cb`) is 75% of isisd's CPU for a link change at k = 4 and all of it at k = 10 and 12
  (12.3 of 12.3 s summed over 180 routers at k = 12), and it costs about the same with flood reduction on. Receiving
  LSPs falls by about a third at k = 8 and 12 (168 to 108 ms, 381 to 242 ms), a small part of the total.
- Every window ended with every router holding the same LSPs as every other router: 120 of 120.

## Bring-up: up to 55% fewer LSPs and 34% less CPU

| Fat-tree | LSPs sent, off | on | Fewer | isisd s, off | on | Lower |
|---|---:|---:|---:|---:|---:|---:|
| k = 4 | 1,592 | 1,520 | 4% | 1.91 | 1.90 | 0% |
| k = 6 | 14,488 | 12,396 | 14% | 9.20 | 9.16 | 0% |
| k = 8 | 83,046 | 59,286 | 29% | 34.9 | 30.9 | 12% |
| k = 10 | 350,582 | 218,262 | 38% | 128 | 105 | 19% |
| k = 12 | 1,386,100 | 629,588 | 55% | 528 | 351 | 34% |

Every run converged, with flood reduction off and on, at k = 12 (180 routers, 864 links) as well. In the
[families results](../families-n64/README.md), 64-router networks with 960 and 1,024 links never converged on the same
20 CPUs without flood reduction (15 to 18 million LSPs at bring-up), while 768 links did; 864 links here fall between,
at 1.4 million LSPs.

## The flooding model on the same links

`model.txt`: the model's count for the same links, flood reduction on and off, beside FRR's. Link-down windows:

| Fat-tree | FRR, off -> on | Model on | Saving, FRR | Model, lockstep | Model, jittered |
|---|---|---:|---:|---:|---:|
| k = 4 | 76 -> 45.3 | 45.3 | 41% | 27% | 47% |
| k = 6 | 266 -> 122 | 122 | 54% | 43% | 64% |
| k = 8 | 606 -> 249 | 246 | 59% | 52% | 71% |
| k = 10 | 1,194 -> 442 | 435 | 63% | 56% | 75% |
| k = 12 | 2,168 -> 719 | 688 | 67% | 60% | 78% |

- With flood reduction on, the model's count is within 5% of FRR's, and exact at k = 4 and 6.
- FRR's saving falls inside the model's range, 7 to 14 points above its lockstep end: without flood reduction, FRR
  sent more LSPs than the lockstep count, as on the [n-flies](../nfly/README.md). On the 64-router random graphs,
  butterflies and leaf-spine fabrics FRR's saving was within 5 points of the lockstep figure, so the
  [model-only tables](../model-fat-tree/README.md) understate the saving of fat-trees by about 7 to 14 points.
- When a link comes up, FRR sends 22 to 275 more LSPs with flood reduction on than the model counts: the model leaves
  out the database exchange over the new adjacency.

## Limits of these runs

- Two runs per variant, 3 links per run, one topology per radix.
- **Other load on the host.** Throughout, a long-running service of ours used about 60% of one CPU, not pinned, and
  the host's own Docker daemons, outside the lab container, used about four CPUs. Neither changes which LSPs are sent;
  the off and on labs took turns, so both variants ran under the same conditions within a run.

## How it was run

```
topology-builders build fat-tree --k 8 --out topos/fat-tree-k8.json
topology-builders clab topos/fat-tree-k8.json --out labs/ft-k8 --name ft-k8 --image frr-distoptflood:e263c441 \
    --cpu-set 12-23,36-43
topology-builders measure labs/ft-k8/off labs/ft-k8/on --profile --links 3 --repeat 2 --max-wait 300 --out fattree.jsonl
topology-builders report fattree.jsonl
mkdir topos && tar -xzf topologies.tar.gz -C topos && TOPOLOGY_DIRS=topos python tools/model/validate.py measurements.jsonl.gz
```

Same configuration, image and container setup as the [families results](../families-n64/README.md) (topotest
configuration: level-2-only, point-to-point, hello 1 s x 3, lsp-gen-interval 2; an LXD container with its own Docker,
every router pinned to the same 20 CPUs; CPUs 44-47, which share physical cores with four of them, ran no job of ours
during these runs), with topology-builders 0.2.0.dev0. The links are chosen from the topology file and seed 1, the
same for off and on; the labs take turns and the order alternates between the two runs.
