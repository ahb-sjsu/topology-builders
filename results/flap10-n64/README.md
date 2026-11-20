# Ten links failing at once: flood reduction halves isisd's CPU in FRR

FRR pull request 24128 (`flood-reduction` under `router isis`, draft-ietf-lsr-distoptflood) at commit e263c441, on
the same 64-router random regular graphs (seed 1) as the [random-regular sweep](../random-regular-n64/README.md), at
degree 16 and 24. Each event takes ten links down at once, chosen at random so that the graph stays connected, waits
30 s, then brings them back up and waits 30 s more. This follows the link-flap test in the measurements presented at
the LSR working group at IETF 125 (95 routers, about 1,000 links, ten random flaps), which reported about 20% more CPU
with flood reduction in that implementation.

Two events per run, two runs of each variant, flood reduction off and on: 8 windows per variant. Runs of 2026-11-20
03:53 to 04:28 UTC. Data: `measurements.jsonl.gz`; the tables are from
`topology-builders report measurements.jsonl.gz --event multi`, rounded.

## Results

| Ten links down, then up (per event) | Degree 16 (512 links) | Degree 24 (768 links) |
|---|---|---|
| LSPs sent, flood reduction off -> on | 20,938 -> 4,703 (78% fewer) | 33,304 -> 3,622 (89% fewer) |
| isisd CPU, net of the quiet window | 8.0 s -> 4.2 s (48% less) | 17.2 s -> 7.1 s (59% less) |
| Pairs (same event, same direction) lower with it on | 4 of 4 | 4 of 4 |
| Windows in which every router ended with the same LSPs | 16 of 16 | 16 of 16 |

Where the CPU goes, from isisd's own accounting per event handler (`show event cpu`), mean per window, net of the
quiet window:

| isisd handler | Degree 16, off -> on | Degree 24, off -> on |
|---|---|---|
| `isis_receive` (receiving and processing PDUs) | 4.7 s -> 1.2 s | 10.8 s -> 1.5 s |
| `isis_run_spf_cb` (route computation) | 2.9 s -> 2.9 s | 5.8 s -> 5.8 s |
| `tx_queue_send_event` (sending) | 0.24 s -> 0.07 s | 0.40 s -> 0.06 s |

- The saving is in receiving LSPs: with flood reduction off, every router processes many copies of each changed
  LSP. Route computation costs the same either way, since every router still has to recompute its routes.
- The saving grows with density, from 48% at degree 16 to 59% at degree 24, as the LSPs do.
- No LSP was retransmitted in any window. With flood reduction on, the fallback counter rose only in the windows
  where the links came back up (51 to 86 per window), not when they went down.
- Bring-up: 50% and 77% fewer LSPs, and 29% and 60% less isisd CPU, at degree 16 and 24.

## How this differs from the IETF 125 measurement

The sign is the opposite of the 20% increase reported at IETF 125, but the experiments differ in more than the
implementation:

- **Implementation:** FRR's, from pull request 24128; the IETF 125 figure is from another implementation, whose
  presenter put the extra CPU down to cache thrashing.
- **Graph:** 64 routers at degree 16 and 24 here; about 95 routers and about 1,000 links there.
- **Database synchronization:** FRR's periodic CSNPs were left on here.
- **Event:** ten links down at once, then up at once, with 30 s windows, and the graph kept connected; how the flaps
  were timed there is not known to us.
- **Setup:** all 64 routers share 20 CPUs here (an LXD container on one host, every router pinned to CPUs 12-23 and
  36-43); CPU figures depend on the setup, as the [families results](../families-n64/README.md) show. During all of
  these runs, a QEMU guest of ours ran pinned to CPUs 44-47, which share physical cores with CPUs 20-23, four of the
  routers' 20. That slows the routers on those four CPUs and can raise their CPU times, in both variants alike: the
  off and on labs took turns under the same load. It does not change which LSPs are sent.

So this measures FRR's behaviour under this protocol; it does not contradict the other implementation's figure.

## How it was run

```
topology-builders clab topos64/random-regular-n64-d16-s1.json --out labs/p-rr64-d16-flap10 \
    --name p-rr64-d16-flap10 --image frr-distoptflood:e263c441 --cpu-set 12-23,36-43
topology-builders measure labs/p-rr64-d16-flap10/off labs/p-rr64-d16-flap10/on --profile --event multi \
    --fail 10 --links 2 --repeat 2 --max-wait 300 --out flap10.jsonl
```

Same configuration, image and container setup as the families results (topotest configuration: level-2-only,
point-to-point, hello 1 s x 3, lsp-gen-interval 2), with topology-builders 0.2.0.dev0. The ten links of each event
are chosen from the topology file and seed 1, the same for off and on; the labs take turns and the order alternates
between the two runs.
