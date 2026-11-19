# Flood reduction against density: 64 routers, random regular graphs

FRR pull request 24128 (`flood-reduction` under `router isis`, draft-ietf-lsr-distoptflood) at commit e263c441,
measured on 64-router random regular graphs of degree 3 to 48. Every router in a random regular graph has the same
degree, so in this sweep the degree is the only thing that changes. Each topology ran with flood reduction off and on,
twice each. In each run, 3 links were taken down and brought back up, one at a time, with a 30 s window after each
change.

Runs of 2026-11-19, 07:10 to 10:57 UTC. Data: `measurements.jsonl.gz` (one JSON line per run, with per-router figures).
The tables below are the output of `topology-builders report measurements.jsonl.gz`, rounded.

## Link changes: LSPs sent fall from 7% fewer at degree 3 to 94% fewer at degree 32

Each degree has 12 link windows per variant (2 runs x 3 links x down and up). LSPs are Level-2 LSPs sent, summed over
the 64 routers; the figure is the mean per window. "Pairs" compares the same link and direction, averaged over the
2 runs, with flood reduction off and on: 6 pairs per degree.

| Degree | Links | LSPs sent, off | on | Fewer | Pairs with fewer on |
|---:|---:|---:|---:|---:|---:|
| 3 | 96 | 269 | 250 | 7% | 6 of 6 |
| 4 | 128 | 372 | 328 | 12% | 6 of 6 |
| 6 | 192 | 595 | 460 | 23% | 6 of 6 |
| 8 | 256 | 799 | 513 | 36% | 6 of 6 |
| 12 | 384 | 1,289 | 531 | 59% | 6 of 6 |
| 16 | 512 | 1,749 | 436 | 75% | 6 of 6 |
| 24 | 768 | 2,803 | 267 | 90% | 6 of 6 |
| 32 | 1,024 | 3,808 | 223 | 94% | 6 of 6 |

- With flood reduction off, sends grow roughly in proportion to the degree. At degree 32, 3,808 sends is about 60 per router,
  close to each of the two new LSPs (one from each end of the link) going out on every link of every router.
- With it on, sends stop growing at degree 12 and then fall: 531, 436, 267 and 223 at degree 12, 16, 24 and 32.
  We have not looked at why.
- In every one of the 384 link windows up to degree 32 (both variants), every router ended the window with the same
  LSPs as every other router, including a newer LSP from each end of the link.

## Link changes: isisd CPU is a median 14% to 23% lower from degree 8, and not measurably lower below it

CPU is isisd's CPU time summed over the 64 routers, net of a quiet window of the same length with no event in the
same run. The quiet window takes out the work that goes on without any event: hellos every second on every link,
and timers.

| Degree | Net isisd ms, off | on | Lower, means | Pairs lower on | Median saving over pairs |
|---:|---:|---:|---:|---:|---:|
| 3 | 865 | 832 | 4% | 4 of 6 | 11% |
| 4 | 976 | 1,064 | -9% | 0 of 6 | -6% |
| 6 | 1,268 | 1,293 | -2% | 2 of 6 | -5% |
| 8 | 1,826 | 1,558 | 15% | 6 of 6 | 14% |
| 12 | 2,607 | 2,138 | 18% | 5 of 6 | 18% |
| 16 | 3,382 | 2,749 | 19% | 6 of 6 | 19% |
| 24 | 5,296 | 3,938 | 26% | 6 of 6 | 23% |
| 32 | 6,667 | 5,096 | 24% | 6 of 6 | 17% |

- These CPU figures depend on the setup. Degree 16 was run again the same day in a different one, with the routers
  in an LXD container with its own Docker, pinned to 20 CPUs: LSPs sent for a link change were within 4% of the
  figures here (1,684 and 435), but net isisd CPU was 10% lower with flood reduction on instead of 19%, still lower
  in 6 of 6 pairs. Bring-up savings matched (48% fewer LSPs, 26% less CPU).
- Up to degree 6 the difference is smaller than the spread between windows: at degree 6, single windows ranged from
  680 to 1,990 ms off and 740 to 2,000 ms on.
- At degree 32, flood reduction removed 94% of the LSPs sent but about a fifth of the CPU, so most of the CPU a
  link change costs in these runs is not in sending LSPs. We have not measured where it goes; route computation and
  receiving LSPs are the obvious candidates.
- An earlier run on 32 routers at degree 6 (in the main README) showed 46% less net CPU for link down and 47% less for
  link up, with the repeats not overlapping. At 64 routers and degree 6 there is no difference. The graphs, the
  number of routers and the load on the host all differ between the two, and we do not know which of these
  explains it.

## Bring-up: from 3% fewer LSPs and no CPU saving at degree 3 to 77% fewer LSPs and 57% less CPU at degree 32

From the routers' start to the check that finds every router with all its adjacencies and the same LSPs as every
other router. The first check is 30 s after deployment, and they repeat every 5 s. Mean of 2 runs per variant; isisd
CPU in seconds, summed over the routers.

| Degree | LSPs sent, off | on | Fewer | isisd s, off | on | Lower |
|---:|---:|---:|---:|---:|---:|---:|
| 3 | 14,999 | 14,546 | 3% | 8.6 | 8.8 | -2% |
| 4 | 25,106 | 23,012 | 8% | 13.0 | 12.9 | 1% |
| 6 | 50,074 | 43,019 | 14% | 22.5 | 21.4 | 5% |
| 8 | 82,344 | 65,098 | 21% | 33.5 | 31.0 | 8% |
| 12 | 159,676 | 106,988 | 33% | 63.1 | 55.0 | 13% |
| 16 | 280,158 | 147,176 | 47% | 104.4 | 78.1 | 25% |
| 24 | 700,813 | 228,070 | 67% | 264.3 | 144.7 | 45% |
| 32 | 1,360,316 | 311,184 | 77% | 536.6 | 229.4 | 57% |

From degree 6 up, the two runs of one variant do not overlap the two runs of the other, for LSPs or for CPU. Every
run up to degree 32 converged.

## Degree 48: without flood reduction the 64 routers did not converge on this host; with it they did

| Degree 48 (1,536 links) | off | on |
|---|---:|---:|
| Runs that converged | 0 of 2 | 2 of 2 |
| Bring-up LSPs sent | 17.9 million | 434,206 |
| Bring-up isisd CPU | 4,677 s | 442 s |
| LSPs sent per link window | 1.28 million | 232 |
| Link windows satisfied | 0 of 12 | 12 of 12 |

- With flood reduction off, the routers' LSP databases still differed 330 s after deployment (30 s settle and 300 s
  more of checking), in both runs. They then kept sending about 1.2 million LSPs per 30 s window even in the quiet
  windows, with no event, and isisd used about 10 CPUs. We did not record why the routers never agreed.
  Adjacencies timing out while isisd waits for CPU (the hold time is 3 s) is one possibility we have not checked.
- With flood reduction on, both runs passed the first check, 30 s after deployment, and every window was satisfied.
- The 64 routers share the host's CPUs. This shows that without flood reduction the total work exceeded what the
  host could give, not that a router with CPUs of its own would fail to converge. The off runs also made the host's
  load average rise above 250, so we stopped there and did not run degree 63, the full mesh.

## How it was run

```
topology-builders sweep --routers 64 --families random-regular --seeds 1 --out topos
topology-builders clab topos/random-regular-n64-d$D-s1.json --out labs/d$D --name tb-rr64-d$D \
    --image frr-distoptflood:e263c441
topology-builders measure labs/d$D/off labs/d$D/on --repeat 2 --links 3 --max-wait 300 --out sweep.jsonl
topology-builders report sweep.jsonl
```

- One graph per degree (seed 1). The 3 links are chosen from the topology file and seed 1, so the off and on runs
  use the same links. The off and on labs take turns, and the order alternates between the 2 runs.
- Configuration as in the pull request's topotest (isis_flood_reduction_topo1): level-2-only, point-to-point links,
  hello interval 1 s, hello multiplier 3, lsp-gen-interval 2. The off and on labs differ only in the
  `flood-reduction` line.
- Image: FRR built from riw777/frr at e263c441 with `tools/frr-image/build.sh` (FRR 10.9.0-dev_git972336414998). Its
  `make check` passed, including `isisd/test_isis_flood_reduction.py`.
- Host: HP Z840 with two Xeon E5-2690 v3, of which 25 logical CPUs were online (the 12 cores of one socket with
  their hyperthreads, and one core of the other). Ubuntu 24.04, Docker 29, containerlab 0.78.2. The routers were
  not pinned to CPUs. Docker's own daemons used about 5 CPUs throughout. The host's load average and hottest CPU
  sensor at the start and end of each run are in the data.
- Before each run the harness waited until the hottest CPU sensor was below 80 C.
- How a run is measured, window by window: the main README, "Measuring flooding and CPU".

## Not covered by these runs

- One graph per degree, 64 routers, 2 runs and 3 links per degree.
- The time to converge. The harness checks 30 s after deployment, then every 5 s, and once at the end of each
  link change's 30 s window, so it cannot see differences of a few seconds.
- Other families. Flattened butterflies and leaf-spine fabrics of 64 routers are next, with every router pinned to
  a fixed set of CPUs.
