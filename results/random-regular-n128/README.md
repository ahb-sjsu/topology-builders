# 128 routers: random regular graphs of degree 4, 8 and 16

FRR pull request 24128 (`flood-reduction` under `router isis`, draft-ietf-lsr-distoptflood) at commit e263c441, on
128-router random regular graphs (seed 1) of degree 4, 8 and 16: twice the routers of the
[64-router results](../seeds-n64/README.md), at the same degrees. Two runs of each variant, flood reduction off and
on; in each run, 3 links were taken down and brought back up, one at a time, with a 30 s window after each change;
isisd's CPU per event handler (`show event cpu`) in every window.

Runs of 2026-11-20, 13:00 to 14:13 UTC. Data: `measurements.jsonl.gz`; `report.txt` is the output of
`topology-builders report` on it; `model.txt` is the flooding model's count for the same links; `topologies.tar.gz`
holds the three topology files the labs were written from.

## Link changes: at the same degree, the saving is smaller than at 64 routers

LSPs are Level-2 LSPs sent, summed over the 128 routers, mean per window (12 windows per variant). CPU is isisd's
CPU time summed over the routers, net of a quiet window. Pairs compare the same link and direction, averaged over the
2 runs: 6 per degree.

| Degree | Links | LSPs sent, off | on | Fewer | Same degree, 64 routers | Net isisd ms, off | on | Lower, means | Pairs lower on | Median saving over pairs |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 256 | 708 | 650 | 8% | 13% | 2,964 | 2,937 | 1% | 4 of 6 | 2% |
| 8 | 512 | 1,536 | 1,236 | 19% | 35% | 5,745 | 5,304 | 8% | 5 of 6 | 9% |
| 16 | 1,024 | 3,390 | 1,599 | 53% | 75% | 10,939 | 10,447 | 5% | 5 of 6 | 5% |

- In all 18 pairs flood reduction sent fewer LSPs, and every one of the 72 windows ended with every router holding
  the same LSPs as every other router.
- **The saving follows the two-hop paths, not the degree.** At a fixed degree, a larger random graph has fewer
  routers joined by two or more two-hop paths. The mean number of common neighbors of routers two hops apart is 1.03,
  1.18 and 2.15 at degree 4, 8 and 16 here, against 1.06, 1.41 and 3.95 at 64 routers. Matched by that number
  instead of degree, the two sizes agree: degree 8 here (1.18, 19% fewer) against degree 6 at 64 routers (1.18, 23%
  in the [random-regular sweep](../random-regular-n64/README.md)); degree 16 here (2.15, 53%) against degree 12 at
  64 routers (2.35, 59%).
- **CPU falls by 1% to 8%,** less than at 64 routers, because route computation is an even larger share (next
  section).

## Where isisd's CPU goes: nearly all of it to route computation

isisd's CPU per event handler, mean ms per link window net of the quiet window, off -> on:

| Degree | Route computation (`isis_run_spf_cb`) | Receiving (`isis_receive`) | Sending (`tx_queue_send_event`) | Route computations per link-down window, off / on | ms per route computation |
|---:|---|---|---|---|---:|
| 4 | 2,995 -> 2,972 | 27 -> 115 | 14 -> 13 | 255 / 249 | 9.1 |
| 8 | 5,526 -> 5,475 | 395 -> 309 | 24 -> 21 | 258 / 254 | 15.6 |
| 16 | 10,768 -> 10,537 | 563 -> 608 | 49 -> 26 | 259 / 255 | 29.5 |

- Each router runs about two route computations when a link goes down (and three to four when it comes up), with
  flood reduction on or off. Each costs about twice what it costs at 64 routers of the same degree (29.5 against
  14.9 ms at degree 16), so a link change's route computation grows with the network while the LSPs saved shrink.
- Without flood reduction, route computation is 96% and 98% of the net CPU at degree 8 and 16, and slightly more
  than the net total at degree 4, where other handlers' net figures (vtysh's) are slightly negative. Receiving changed little and in no consistent direction: at this size and
  these degrees, there is not much receiving CPU to save.

## Bring-up

From the routers' start to the check that finds every router with all its adjacencies and the same LSPs as every
other router; mean of 2 runs, isisd CPU in seconds summed over the routers.

| Degree | LSPs sent, off | on | Fewer | isisd s, off | on | Lower | Converged, off / on |
|---:|---:|---:|---:|---:|---:|---:|---|
| 4 | 101,257 | 95,888 | 5% | 45.4 | 45.6 | -1% | 2 of 2 / 2 of 2 |
| 8 | 420,542 | 323,870 | 23% | 152.9 | 134.8 | 12% | 2 of 2 / 2 of 2 |
| 16 | 2,255,776 | 1,059,692 | 53% | 822.9 | 522.1 | 37% | 2 of 2 / 2 of 2 |

## The flooding model on these graphs

The model's saving for the same links, over the link-down and link-up windows ("lockstep": every link takes one unit
and no processing delay; "jittered": link delays drawn from 1 to 2 units):

| Degree | FRR | Model, lockstep | Model, jittered |
|---:|---:|---:|---:|
| 4 | 8% | 5% | 21% |
| 8 | 19% | 18% | 32% |
| 16 | 53% | 57% | 64% |

The lockstep figure is within 5 points of FRR's, as at 64 routers, and it predicted the smaller saving at this size.
With flood reduction on, FRR sent 2% to 15% more LSPs than the model counts (`model.txt`).

## 256 routers: the labs could not be deployed

The same runs at 256 routers (degree 4 and 8) never started: containerlab failed while deploying the 256 containers
("cannot attach link, container network namespace is not available", and Docker API calls cancelled), at degree 4
after 1.5 minutes and at degree 8 after 5. No records were written. The host's load average rose to about 775 during
the second attempt. 256 routers need a different setup, for example the namespace backend (`measure --backend
netns`), which creates no containers, or more than one host.

## Limits of these runs

- One graph per degree, two runs per variant, 3 links per run.
- No job of ours ran pinned to CPUs 44-47, which share physical cores with four of the routers' CPUs, during these
  runs. Throughout, though, a console demo engine of ours (running since 2026-09-28) used about 60% of one CPU on
  average, allowed to run on any of CPUs 12-23 and 36-47, the routers' among them, and the host's own Docker daemons,
  outside the lab container, three to five CPUs. Both variants ran under it alike, and it does not change which LSPs
  are sent. An earlier version of this README said no other job of ours shared these routers' CPUs; that was wrong.

## How it was run

```
topology-builders sweep --routers 128 --families random-regular --seeds 1 --out topos128
topology-builders clab topos128/random-regular-n128-d$D-s1.json --out labs/p-rr128-d$D --name p-rr128-d$D \
    --image frr-distoptflood:e263c441 --cpu-set 12-23,36-43
topology-builders measure labs/p-rr128-d$D/off labs/p-rr128-d$D/on --profile --links 3 --repeat 2 \
    --max-wait 600 --out large.jsonl
topology-builders report large.jsonl
```

Same configuration, image and container setup as the [families results](../families-n64/README.md) (topotest
configuration: level-2-only, point-to-point, hello 1 s x 3, lsp-gen-interval 2; an LXD container with its own
Docker, every router pinned to the same 20 CPUs, so 128 routers share 20 CPUs here), with topology-builders
0.2.0.dev0. The links are chosen from the topology file and seed 1, the same for off and on; the labs take turns and
the order alternates between the two runs. The model's counts, from the topology files the labs were written from
(`topologies.tar.gz`, matched by sha256): `mkdir topos && tar -xzf topologies.tar.gz -C topos &&
TOPOLOGY_DIRS=topos python tools/model/validate.py measurements.jsonl.gz`.
