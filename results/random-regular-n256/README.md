# 256 routers: random regular graphs of degree 4, 8 and 16, on the namespace backend

FRR pull request 24128 (`flood-reduction` under `router isis`, draft-ietf-lsr-distoptflood) at commit e263c441, on
256-router random regular graphs (seed 1) of degree 4, 8 and 16: twice the routers of the
[128-router results](../random-regular-n128/README.md), at the same degrees. containerlab could not deploy labs of
this size on Atlas (the 128-router README), so these ran on the namespace backend: every router a network namespace
running FRR's daemons, every link a veth pair, inside one Docker container per degree with no network
(`--network none`), the routers' 20 CPUs (12-23,36-43) and Colab's capabilities, the labs inside `unshare -Urnm`.
Same protocol as at 128 routers: two runs of each variant, 3 links per run taken down and brought back up one at a
time, a 30 s window after each change, isisd's CPU per event handler.

Runs of 2026-11-21, 18:02 to 23:44 UTC. Data: `measurements.jsonl.gz`; `report.txt` is the output of
`topology-builders report` on it; `model.txt` is the flooding model's count for the same links; `topologies.tar.gz`
holds the three topology files the labs were written from.

## Degree 4 and 8: small savings, no CPU saving at degree 8

LSPs are Level-2 LSPs sent, summed over the 256 routers, mean per link window (12 windows per variant). CPU is
isisd's CPU time summed over the routers, net of a quiet window. Pairs compare the same link and direction, averaged
over the 2 runs: 6 per degree.

| Degree | Links | Two-hop multiplicity | LSPs sent, off | on | Fewer | Same degree at 128 / 64 routers | Net isisd ms, off | on | Lower, means | Pairs lower on | Median saving over pairs |
|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| 4 | 512 | 1.012 | 1,452 | 1,328 | 9% | 8% / 13% | 9,282 | 8,418 | 9% | 5 of 6 | 11% |
| 8 | 1,024 | 1.089 | 3,133 | 2,678 | 15% | 19% / 35% | 16,697 | 17,428 | -4% | 2 of 6 | -2% |

- In all 12 pairs flood reduction sent fewer LSPs, and all 48 link windows ended with every router holding the same
  LSPs as every other router.
- **The saving keeps falling with size at a fixed degree, as the two-hop multiplicity falls.** At degree 8 the
  multiplicity is 1.42, 1.18 and 1.09 at 64, 128 and 256 routers, and the saving 35%, 19% and 15%.
- **No CPU saving at degree 8.** Route computation is nearly all of isisd's CPU for a link change (next section).

## Where isisd's CPU goes: route computation, and receiving costs more with flood reduction on

Mean ms per link window net of the quiet window, off -> on (`report.txt`):

| Degree | Route computation (`isis_run_spf_cb`) | Receiving (`isis_receive`) | Sending (`tx_queue_send_event`) |
|---:|---|---|---|
| 4 | 10,154 -> 8,672 | 118 -> 435 | 27.0 -> 24.9 |
| 8 | 16,540 -> 16,768 | 401 -> 1,014 | 44.1 -> 40.6 |

- Route computation is 10 to 17 s of isisd CPU per link window summed over the routers: 12.5 times the 64-router
  figure at degree 8 (1,320 ms in [seeds-n64](../seeds-n64/README.md)), for four times the routers.
- **Receiving costs more with flood reduction on** at this size: 3.7 times at degree 4 and 2.5 times at degree 8. At
  degree 4 it also rose at 64 and 128 routers (84 -> 108 and 27 -> 115 ms); at degree 8 it fell there (174 -> 124
  and 395 -> 309 ms) and rises here. One candidate is the work of building the two-hop view a flooding decision reads,
  which FRR does at the first decision after a route computation starts (see [mechanism](../mechanism/README.md)); we
  have not profiled inside `isis_receive` to check it.

## Degree 16: neither variant converged

With 2,048 links, the lab did not converge in any of its four runs, **with or without flood reduction**:

| Degree 16, 2 runs of each | off | on |
|---|---:|---:|
| Runs that converged within 600 s | 0 of 2 | 0 of 2 |
| Bring-up LSPs sent, mean | 49.2 million | 39.8 million |
| LSPs suppressed by flood reduction at bring-up | | 2.35 million |
| Bring-up isisd CPU, mean | 9,333 s | 8,777 s |
| LSPs sent in a quiet window (30 s, no event), mean | 6.5 million | 6.6 million |
| Windows satisfied | 0 of 14 | 0 of 14 |

- The network flooded itself continuously: even the quiet windows sent about 6.5 million LSPs, and adjacencies kept
  expiring (`isis_adj_expire` took 2.4 s of CPU per link window without flood reduction, 0.6 s with it), so routers
  kept regenerating their LSPs. The host's load average stayed near 790 for most of the lab's 4 h 50 min, against 7
  to 68 at degree 4 and 8; the lab container's memory reached 39.6 GiB.
- **Flood reduction did not rescue it.** It suppressed about 6% of the sends at bring-up (2.35 million of 42.2
  million). At 64 routers and degree 32 ([seeds-n64](../seeds-n64/README.md)), where the two-hop multiplicity is
  16.3, flood reduction turned non-convergence into convergence; here the multiplicity is 1.50, the decision a router
  makes from two hops can drop few copies, and the churn regenerates them faster than they settle.
- The link-change figures of this degree (in `report.txt`) compare windows of a network that never settled and are
  not read as savings.

## Bring-up

From the routers' start to the check that finds every router with all its adjacencies and the same LSPs; mean of 2
runs, isisd CPU summed over the routers.

| Degree | LSPs sent, off | on | Fewer | isisd s, off | on | Lower | Converged, off / on |
|---:|---:|---:|---:|---:|---:|---:|---|
| 4 | 338,477 | 327,995 | 3% | 114.6 | 99.6 | 13% | 2 of 2 / 2 of 2 |
| 8 | 1,135,831 | 1,018,720 | 10% | 345.7 | 346.4 | 0% | 2 of 2 / 2 of 2 |
| 16 | 49,204,294 | 39,815,684 | 19% | 9,333 | 8,777 | 6% | 0 of 2 / 0 of 2 |

## The flooding model on these graphs

The model's count for the same links, flood reduction on, pooled over the link-down and link-up windows: 1,246 LSPs
per window in lockstep at degree 4 against 1,328 measured (+7%), and 2,607 at degree 8 against 2,678 (+3%). Its
lockstep saving is 3% and 11%, below FRR's 9% and 15%, as on the fat-trees and n-flies, where FRR saved 7 to 14 points
more than the lockstep figure. Degree 16 has no satisfied window and is not in `model.txt`.

## Memory

The lab container's memory, sampled each minute: at most 8.8 GiB at degree 4 (about 35 MiB per router, four FRR
daemons each), 12.0 GiB at degree 8 (48 MiB), and 39.6 GiB at degree 16, growing through the storm.

## Limits of these runs

- One graph per degree, two runs per variant, 3 links per run.
- The namespace backend, where the 64- and 128-router results used Docker labs. On the same links, namespace labs on
  Colab sent 5% to 15% fewer LSPs without flood reduction than Docker labs on Atlas, and nearly the same with it
  ([colab-sessions](../colab-sessions/README.md)); a saving measured here may run a few points below a Docker lab's.
- Other load on the host's CPUs, sampled each minute (`hostload.log` on Atlas): the host's own Docker daemons
  (containerd and dockerd, about 2.8 CPUs together), libvirtd (about 1 CPU, serving a virtual machine), a console
  demo engine of ours and other Python jobs, postgres, netdata and clickhouse, and for short spells jobs of other
  projects; all could run on the routers' CPUs. Between 18:02 and 18:07 UTC, while the degree-4 lab deployed and
  started measuring, we ran table and lint jobs of our own on CPUs 44-47 (which share cores with four of the routers'
  CPUs) and unpinned, about a minute of CPU in all. The off and on variants took turns throughout.
- The degree-16 lab was to stop at 4 h; the queue's time cap did not fire (corrected for the larger runs), and the
  lab ran all four runs in 4 h 50 min.

## How it was run

```
topology-builders sweep --routers 256 --families random-regular --seeds 1 --out topos256
topology-builders clab topos256/random-regular-n256-d$D-s1.json --out labs/p-rr256-d$D --name p-rr256-d$D
# in a container from an Ubuntu 24.04 image with FRR built by tools/colab/setup.sh (pr24128-e263c441):
docker run --rm --network none --cpuset-cpus 12-23,36-43 --memory 120g --cap-add SYS_ADMIN --cap-add SYS_PTRACE ...
unshare -Urnm topology-builders measure labs/p-rr256-d$D/off labs/p-rr256-d$D/on --backend netns --profile \
    --links 3 --repeat 2 --max-wait 600 --out n256-d$D.jsonl
topology-builders report measurements.jsonl.gz
mkdir topos && tar -xzf topologies.tar.gz -C topos && TOPOLOGY_DIRS=topos python tools/model/validate.py measurements.jsonl.gz
```

Configuration as in the other results: level-2-only, point-to-point, hello 1 s x 3, lsp-gen-interval 2;
topology-builders 0.2.0. The records' `image` field is `clab`'s default and is not used by the namespace backend.
