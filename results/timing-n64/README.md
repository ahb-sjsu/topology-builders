# Flooding and convergence times after failures: 64 routers

FRR pull request 24128 (`flood-reduction` under `router isis`, draft-ietf-lsr-distoptflood) at commit e263c441, on
four 64-router topologies: random regular graphs of degree 8 and 16, the flattened butterfly 4x4x4 (degree 9) and a
leaf-spine fabric of 48 leaves and 16 spines. Each run takes, one after another: two single links down and up
(`link`), two routers down and up, each with all its links at once, as when a router fails (`node`), and two sets of
three links down and up at once, chosen so that the graph stays connected (`multi`). Every window is 20 s. Two runs
of each variant, flood reduction off and on. Runs of 2026-11-20 00:38 to 03:53 UTC, and one run again on 2026-11-21
(see Limits).

Times come from the routers' own logs: every router logs each LSP it builds or receives (`debug isis
update-packets`, `log timestamp precision 6`), and all routers share the host's clock. For each window:

- **flooding time:** for each LSP the event changed, from the moment its router built it to the moment the last
  router held it; the largest over those LSPs;
- **convergence time:** from the event to the moment the last router held every changed LSP. It includes the time
  the routers take to notice the change and build their new LSPs (`lsp-gen-interval 2`), which flood reduction does
  not change.

Data: `measurements.jsonl.gz`; the table is from `python3 timing_tables.py measurements.jsonl.gz`.

## Single link changes: flooding takes the same tens of milliseconds either way

With one link down or up, flooding took 21 to 206 ms with flood reduction off and 22 to 183 ms with it on, across
the four topologies. Convergence after a link went down, from 0.4 to 1 s, is set by when the two routers build their new LSPs.

## Several links at once: with flood reduction on, flooding was often seconds slower

| Down windows | Flooding, off (ms) | Flooding, on (ms) |
|---|---|---|
| Butterfly 4x4x4, a router fails | 70, 73, 76, 90 | 1,143, 3,107, 3,437, 6,281 |
| Random regular, degree 8, a router fails | 61, 71, 72, 80 | 59, 1,299, 1,755, 2,978 |
| Leaf-spine 48 x 16, three links fail | 275, 284, 329, 427 | 1,606, 1,855, 7,566, 8,082 |
| Butterfly 4x4x4, three links fail | 58, 71, 75, 97 | 53, 335, 3,037, 3,305 |
| Random regular, degree 8, three links fail | 62, 69, 70, 83 | 66, 74, 406, 446 |
| Random regular, degree 16, a router fails | 231, 242, 254, 315 | 103, 115, 295, 527 |
| Random regular, degree 16, three links fail | 122, 130, 133, 161 | 94, 100, 553, 812 |

- With flood reduction on, a router failure took over a second to flood in all 4 windows on the butterfly and in 3
  of 4 on the random graph of degree 8; three links failing together took over a second in all 4 windows on
  leaf-spine and in 2 of 4 on the butterfly. On the random graph of degree 16 the slowest window took 0.8 s.
- Without flood reduction there was no such tail: every window in which links went down flooded in at most 0.43 s,
  except router failures on leaf-spine, which took 1.5 to 1.9 s with flood reduction on or off.
- Every window still ended with every router holding the same LSPs. This is about speed, not correctness.
- The mechanism, from a lab that replays these failures with flooding, CSNP and PSNP logs
  ([mechanism](../mechanism/README.md)): 241 of the 249 router-LSP pairs that arrived more than 1 s late came
  through the periodic CSNP exchange (complete sequence-number PDUs, which neighbors exchange to repair their
  databases), not through flooding. In 172 of them, a neighbor that held the LSP decided with the topology from
  before the failure and left the late router to a router that had just lost its links. Why that topology
  predates the failure is still open.

## Recoveries were not slower

When the links or the router came back up, flooding with flood reduction on took about the same time or less: on
leaf-spine, a router coming back flooded in 165 to 429 ms against 671 to 2,887 ms without it. The exceptions were one
router recovery each on the butterfly (5.2 s) and on the random graph of degree 8 (2.9 s).

## All windows

| Topology | Window | Flooding, off (ms) | Flooding, on (ms) | Convergence, off -> on (median, s) | Consistent, off / on |
|---|---|---|---|---|---|
| flattened butterfly 4x4x4 | link-down | 56, 58, 62, 76 | 45, 46, 51, 58 | 0.59 -> 0.92 | 4 of 4 / 4 of 4 |
| flattened butterfly 4x4x4 | link-up | 22, 29, 32, 32 | 23, 24, 29, 35 | 2.61 -> 2.70 | 4 of 4 / 4 of 4 |
| flattened butterfly 4x4x4 | node-down | 70, 73, 76, 90 | 1,143, 3,107, 3,437, 6,281 | 0.56 -> 3.67 | 4 of 4 / 4 of 4 |
| flattened butterfly 4x4x4 | node-up | 24, 33, 39, 99 | 25, 36, 130, 5,237 | 2.92 -> 3.22 | 4 of 4 / 4 of 4 |
| flattened butterfly 4x4x4 | multi-down | 58, 71, 75, 97 | 53, 335, 3,037, 3,305 | 0.66 -> 2.19 | 4 of 4 / 4 of 4 |
| flattened butterfly 4x4x4 | multi-up | 29, 45, 84, 92 | 17, 38, 46, 60 | 2.92 -> 2.86 | 4 of 4 / 4 of 4 |
| leaf-spine, 48 x 16 | link-down | 158, 163, 178 (+1 missing) | 154, 165, 173, 183 | 0.96 -> 0.70 | 4 of 4 / 4 of 4 |
| leaf-spine, 48 x 16 | link-up | 53, 92, 131, 206 | 40, 80, 80, 101 | 3.25 -> 2.67 | 4 of 4 / 4 of 4 |
| leaf-spine, 48 x 16 | node-down | 1,490, 1,527, 1,806, 1,929 | 1,491, 1,842, 1,879, 2,571 | 2.01 -> 2.44 | 4 of 4 / 4 of 4 |
| leaf-spine, 48 x 16 | node-up | 671, 834, 2,132, 2,887 | 165, 230, 272, 429 | 4.89 -> 3.09 | 4 of 4 / 4 of 4 |
| leaf-spine, 48 x 16 | multi-down | 275, 284, 329, 427 | 1,606, 1,855, 7,566, 8,082 | 1.00 -> 5.21 | 4 of 4 / 4 of 4 |
| leaf-spine, 48 x 16 | multi-up | 181, 248, 292, 296 | 108, 119, 142, 172 | 3.17 -> 3.39 | 4 of 4 / 4 of 4 |
| random regular, degree 8 | link-down | 21, 33, 45, 53 | 46, 50, 56, 57 | 0.38 -> 0.68 | 4 of 4 / 4 of 4 |
| random regular, degree 8 | link-up | 25, 29, 33, 40 | 22, 27, 28, 29 | 3.04 -> 2.41 | 4 of 4 / 4 of 4 |
| random regular, degree 8 | node-down | 61, 71, 72, 80 | 59, 1,299, 1,755, 2,978 | 0.80 -> 2.45 | 4 of 4 / 4 of 4 |
| random regular, degree 8 | node-up | 19, 31, 38, 40 | 30, 32, 52, 2,883 | 2.91 -> 3.06 | 4 of 4 / 4 of 4 |
| random regular, degree 8 | multi-down | 62, 69, 70, 83 | 66, 74, 406, 446 | 0.46 -> 0.90 | 4 of 4 / 4 of 4 |
| random regular, degree 8 | multi-up | 26, 40, 44, 102 | 27, 40, 44, 56 | 2.77 -> 2.95 | 4 of 4 / 4 of 4 |
| random regular, degree 16 | link-down | 91, 100, 114, 117 | 78, 81, 106, 110 | 0.73 -> 0.95 | 4 of 4 / 4 of 4 |
| random regular, degree 16 | link-up | 44, 57, 77, 88 | 27, 27, 32, 38 | 2.71 -> 2.68 | 4 of 4 / 4 of 4 |
| random regular, degree 16 | node-down | 231, 242, 254, 315 | 103, 115, 295, 527 | 1.00 -> 0.88 | 4 of 4 / 4 of 4 |
| random regular, degree 16 | node-up | 170, 175, 217, 221 | 47, 62, 71, 116 | 3.92 -> 2.80 | 4 of 4 / 4 of 4 |
| random regular, degree 16 | multi-down | 122, 130, 133, 161 | 94, 100, 553, 812 | 0.65 -> 0.87 | 4 of 4 / 4 of 4 |
| random regular, degree 16 | multi-up | 79, 126, 132, 137 | 59, 85, 89, 91 | 3.76 -> 2.91 | 4 of 4 / 4 of 4 |

"Missing": one window in which a router's log did not show every changed LSP, so no flooding time; the window was
still consistent. Convergence after a link or router comes back up includes forming the adjacency again (hello
interval 1 s), so it is longer.

## Limits of these runs

- Two to four windows per cell, one graph per topology.
- Debug logging, needed for the times, costs CPU, in both variants alike. The times are comparable between off and
  on; CPU figures from these runs are not used anywhere.
- Degree 32 is missing: with the logging, the routers without flood reduction never converged on the 20 CPUs they
  shared, and the run was stopped. No records were written.
- Other load on the host's CPUs: while leaf-spine ran (03:19 to 03:53 UTC), other jobs of ours ran pinned to CPUs
  44-47 (building and then running a QEMU guest), which share physical cores with CPUs 20-23, four of the routers'
  20. That slows the routers on those four CPUs, in both variants alike since they took turns; the other three
  topologies ran without it.
- Background load throughout: a console demo engine of ours (running since 2026-09-28) used about 60% of one CPU on
  average, allowed to run on any of CPUs 12-23 and 36-47, the routers' among them, and the host's own Docker
  daemons, outside the lab container, three to five CPUs. Both variants ran under it alike. An earlier version of
  this README did not mention it.
- One run is set aside, in `excluded.jsonl.gz`: the butterfly's first run without flood reduction, which started
  while the stopped degree-32 lab was still being taken down and shared the CPUs with it. That run was made again on
  2026-11-21, 04:08 to 04:14 UTC, with the same lab directory, events, options and place in the order (first run,
  first lab), after the other sweeps had ended; it is in `measurements.jsonl.gz` and in the tables above. It began 47
  s after a 180-router lab had been taken down, while the host's one-minute load average was still falling from that
  (118 at the start, under 13 one to two minutes later); a database backup used about one CPU on the host at the
  time. Its flooding
  times are in line with the other run's (router failure 73 and 76 ms against 70 and 90; three links 58 and 71 ms
  against 75 and 97).

## How it was run

```
topology-builders clab topos64/random-regular-n64-d8-s1.json --out labs/t-rr64-d8 --name t-rr64-d8 \
    --image frr-distoptflood:e263c441 --cpu-set 12-23,36-43 --timing-logs
topology-builders measure labs/t-rr64-d8/off labs/t-rr64-d8/on --timing --event link,node,multi --links 2 \
    --fail 3 --repeat 2 --window 20 --max-wait 300 --out timing.jsonl
```

Same configuration, image and container setup as the [families results](../families-n64/README.md), with
topology-builders 0.2.0.dev0. The links, routers and sets of links are chosen from the topology file and seed 1, the
same for off and on; the labs take turns and the order alternates between the two runs.
