# Four Colab sessions: three Atlas graphs on other machines

FRR pull request 24128 (`flood-reduction` under `router isis`, draft-ietf-lsr-distoptflood) at commit e263c441,
built on each runtime by [`tools/colab/setup.sh`](../../tools/colab/setup.sh), on Google Colab Pro runtimes of the
type "CPU with high memory" (8 vCPUs, 51 GB). The labs ran on the namespace backend (`measure --backend netns` inside
`unshare -Urnm`): every router is a network namespace of the runtime and every link a veth pair. No containers were
involved.

Three sessions ran at the same time on 2026-11-21, from 05:17 to 06:27 UTC. Each measured the same three 64-router
graphs as the runs on Atlas (the HP Z840 workstation the other results folders ran on) in
[seeds-n64](../seeds-n64/README.md) and [families-n64](../families-n64/README.md):

- the 4x4x4 flattened butterfly;
- the random regular graph of degree 16 (seed 1);
- leaf-spine with 48 leaves and 16 spines.

In each session, each graph ran with flood reduction off and on, two runs each. In each run, 3 links were taken down
and brought back up, one at a time, with a 30 s window after each change, and isisd's CPU was recorded per event
handler.

A fourth session, from 03:33 to 04:48 UTC, ran the notebook's probe ladder with 2 links per run. The ladder was
random graphs of 16, 32 and 64 routers, then the degree-16 graph and leaf-spine.

Data:

- `measurements.jsonl.gz`: all four sessions. Every record has a `session` and a `runtime` field.
- `sessions.json`: each runtime (CPU model, CPUs, memory, kernel, capabilities, setup time) and each lab's duration
  and steal time.
- `report.txt`: the output of `topology-builders report` on all the records.
- `report-<session>.txt`: the same output, on one session's records.
- `atlas-colab-links.jsonl.gz`: the same three graphs and the same links, run on Atlas afterwards
  ([below](#the-colab-links-on-atlas)); `report-atlas-colab-links.txt` is `topology-builders report` on it.
- `tables.txt`: the output of `session_tables.py`. It has, per session, the spread across sessions, the pairs pooled
  over sessions, the quiet windows, the Atlas runs of the same graphs, the Atlas run with the Colab links, and the
  flooding model's count for each setup's links.

| Session | CPU | Started (UTC) | Setup | Labs |
|---|---|---|---:|---|
| 2c3f | AMD EPYC 7B12 | 05:17 | 105 s | butterfly, degree 16, leaf-spine |
| a057 | Intel Xeon, 2.20 GHz | 05:17 | 158 s | the same |
| cd61 | Intel Xeon, 2.20 GHz | 05:27 | 46 s (FRR from the copy on Drive) | the same |
| ff2f | Intel Xeon, 2.20 GHz | 03:33 | 153 s | the ladder: 16 routers degree 4, 32 degree 8, 64 degree 8, 64 degree 16, leaf-spine |

All four sessions had 8 vCPUs (2 threads per core), 51 GB, Ubuntu 24.04 and kernel 6.6. In the batch sessions,
each lab took 18 to 21 minutes, both variants included. Steal time over each lab, from /proc/stat, was at most 0.35%. 2c3f
ran on a different processor model from the others, so on a different physical machine. We cannot tell whether
a057, cd61 and ff2f shared one.

## LSPs: the same saving on every machine

LSPs are the Level-2 LSPs sent, summed over the 64 routers, as a mean per link window (down and up).

| Topology | Links | LSPs sent, off -> on, per session | Fewer, per session | Atlas, same graph, other links |
|---|---:|---|---|---|
| Flattened butterfly 4x4x4 | 288 | 827-842 -> 328-337 | 60%, 60%, 60% | 70% (seeds-n64), 68% (families-n64) |
| Random regular, degree 16 | 512 | 1,508-1,574 -> 436-443 | 71%, 72%, 72%, 71% | 75% (seeds-n64, random-regular-n64), 74% (families-n64) |
| Leaf-spine, 48 x 16 | 768 | 2,378-2,611 -> 180-191 | 93%, 93%, 92%, 92% | 93%, 93% |

- **Machine to machine, the LSP saving moved by at most 1 point.** In all 62 pairs on these three graphs (same link
  and direction, off against on), and in all 12 pairs of the ladder's three other labs, flood reduction sent fewer
  LSPs. Every run converged. All 296 link windows ended with every router
  holding the same LSPs as every other router: 24 per lab and session, and 16 per lab in the ladder.
- **Against Atlas, the saving is the same on leaf-spine, 3 points lower at degree 16, and 8 to 10 points lower on
  the butterfly.** The graphs are the same: rebuilt with the notebook's commands, their edge sets equal those of the
  Atlas topology files. The links taken down differ, though. `measure` picks the links from the topology file's
  hash, and the Colab files carry other builder metadata (Python 3.13 and topology-builders 0.2.0, against Python
  3.12 and topology-builders 0.1.0 or 0.2.0.dev0 in the Atlas files).
- **The model puts part of the butterfly's gap down to the link choice.** The flooding model (lockstep) gives a 65%
  saving for the Colab links and 70% for the Atlas links, because with flood reduction on the Colab links flood more
  (304 against 261.5 LSPs per window). On the degree-16 graph the model gives 77% for the Colab links and 76% to 78%
  for the Atlas ones, so link choice does not explain that 3-point gap. The rest is the setup, as the Atlas run with
  the Colab links shows ([below](#the-colab-links-on-atlas)).

## The Colab links on Atlas

The same three topology files and so the same links, run on Atlas on 2026-11-21 from 16:59 to 18:01 UTC, in the
setup of [seeds-n64](../seeds-n64/README.md). They were Docker labs in the LXD container, with every router pinned to
the same 20 CPUs, image `frr-distoptflood:e263c441`, and the same protocol: 2 runs of each variant, 3 links,
`--profile`. The files were rebuilt on Atlas with the builder's Python version set to Colab's, and their sha256
equals the one in the Colab records. In all 72 windows every router ended with the same LSPs.

LSPs sent per link window, off -> on, and the saving:

| Topology | Colab, Colab links | Atlas, Colab links | Atlas, Atlas links |
|---|---|---|---|
| Flattened butterfly 4x4x4 | 827-842 -> 328-337 (60%) | 922 -> 343 (63%) | 881-922 -> 274-280 (68%, 70%) |
| Random regular, degree 16 | 1,508-1,574 -> 436-443 (71-72%) | 1,728 -> 440 (75%) | 1,684-1,749 -> 422-436 (74-75%) |
| Leaf-spine, 48 x 16 | 2,378-2,611 -> 180-191 (92-93%) | 2,730 -> 192 (93%) | 2,686-2,795 -> 178-183 (93%) |

- **With flood reduction on, the links set the count.** The same links sent nearly the same number of LSPs in both
  setups: 343 against 328 to 337 on the butterfly, 440 against 436 to 443 at degree 16, 192 against 180 to 191 on
  leaf-spine. As the model predicted, the Colab links flood more on the butterfly than the Atlas links (343 against
  274 to 280).
- **Without flood reduction, the setup sets the count.** Atlas's container labs sent 5% to 15% more LSPs than
  Colab's namespace labs: 922 against 827 to 842 on the butterfly, and 1,728 against 1,508 to 1,574 at degree 16.
  Without flood reduction, how many copies a router sends depends on timing.
- **So the butterfly's 8 to 10 points split into 5 to 7 from the links and 3 from the setup.** Degree 16's 3 points
  are all setup.
- **CPU per link change, median over pairs:** 9% on the butterfly (5 of 6 pairs lower), 16% at degree 16 (5 of 6) and
  27% on leaf-spine (6 of 6). Those are close to the medians pooled over the Colab sessions (11%, 10%, 28%) and to
  the earlier Atlas runs (5% and 22%, 10% and 19%, 31% and 40%). isisd's CPU per link change on Atlas was 1.7
  to 2 times Colab's (net 1,897 against 937 ms on the butterfly, without flood reduction).
- **Bring-up saved nearly as much as in the earlier Atlas runs:** 32%, 48% and 59% fewer LSPs, against 31% to 33%, 46% to
  48% and 62% to 66% with Atlas's links and 15% to 32% on Colab. The smaller bring-up saving on Colab comes from the
  setup, not the links.
- During the run, the host's own Docker daemons (containerd about 2.4 CPUs, dockerd about 1.9) and libvirtd (about
  1 CPU, serving a virtual machine) ran on CPUs among the routers'. So did postgres, netdata and other Python jobs of
  ours: the console demo engine, and for part of the run a job of another project. The 1-minute load average was
  6 to 46, the labs included, and the CPU packages reached 74 °C. Both variants ran under the same load, taking turns.

## CPU per link change: about the Atlas median, with a wide spread

isisd's CPU time summed over the routers, net of the run's quiet window. Per session: the median saving over the
pairs, with the number of pairs lower with flood reduction on. Pooled: every session's pairs together.

| Topology | 2c3f | a057 | cd61 | ff2f | Pooled over sessions | Atlas, same graph |
|---|---:|---:|---:|---:|---|---|
| Flattened butterfly 4x4x4 | 12% (6 of 6) | 12% (4 of 6) | -4% (2 of 6) | | 11%, 12 of 18 lower, quartiles -5% to 13% | 5% (3 of 6, seeds-n64), 22% (6 of 6, families-n64) |
| Random regular, degree 16 | 11% (6 of 6) | -56% (0 of 6) | 13% (6 of 6) | 15% (3 of 4) | 10%, 15 of 22 lower, quartiles -6% to 16% | 10% (6 of 6, seeds-n64 and families-n64), 19% (6 of 6, random-regular-n64) |
| Leaf-spine, 48 x 16 | 17% (6 of 6) | 2% (3 of 6) | 35% (6 of 6) | 32% (4 of 4) | 28%, 19 of 22 lower, quartiles 13% to 32% | 31% (6 of 6, seeds-n64), 40% (6 of 6, families-n64) |

- **Pooled over the sessions, the median savings are close to the Atlas runs':** 11% on the butterfly against 5% and
  22%, 10% at degree 16 against 10% and 19%, and 28% on leaf-spine against 31% and 40%.
- **One session pins the CPU saving down no better than one Atlas run.** On the same graph and links, single sessions
  gave anything from -56% to 15% at degree 16, and 2% to 35% on leaf-spine.
- **The quiet window is why.** Each run subtracts one quiet window (30 s with no event) from every event window in
  it. Hellos and timers alone cost isisd 3.6 to 15 s summed over the routers in those 30 s, while a link change adds
  0.7 to 3.7 s. Within a session, the two quiet windows of one lab and variant differed by up to 2.2 s (leaf-spine on
  2c3f, off: 8.2 and 10.4 s), as much as a link change costs.
- **The outlier is a057's degree-16 lab.** Its quiet windows were 10.4 and 9.6 s off and 9.3 s twice on. Net of
  them, a link change cost more with flood reduction on (2,108 against 1,426 ms), and no pair was lower.
- On Atlas, the quiet windows of one lab and variant differed by at most 6% on these three graphs (for example
  14.1 to 14.5 s at degree 16 in seeds-n64, and 15.4 to 16.3 s in the run with the Colab links), and by up to 9% on
  the degree-8 graph. On Colab they differed by up to 27%.
- On the AMD session, isisd cost a quarter to a third less than on the Intel ones. On the butterfly, its quiet
  windows took 3.6 to 3.8 s against 5.2 to 5.7 s, and route computation 714 against 959 to 982 ms per link
  window.

## Where isisd's CPU goes

Mean ms per link window net of the quiet window, off -> on, over every window of every session (`report.txt`):

| Topology | Route computation (`isis_run_spf_cb`) | Receiving (`isis_receive`) | Sending (`tx_queue_send_event`) |
|---|---|---|---|
| Flattened butterfly 4x4x4 | 885 -> 836 | 114 -> 96 | 7.5 -> 3.9 |
| Random regular, degree 16 | 1,829 -> 1,748 | 223 -> 179 | 13.2 -> 4.7 |
| Leaf-spine, 48 x 16 | 2,447 -> 1,885 | 567 -> 206 | 21.1 -> 1.9 |

- As on Atlas, route computation is most of isisd's CPU for a link change. Without flood reduction it is 94% of the
  net CPU on the butterfly and 92% on leaf-spine. At degree 16 it is slightly more than the net total, because other
  handlers' net figures are negative. In seeds-n64, on these graphs, the share was 82% to 95%.
- On leaf-spine, route computation cost 23% less with flood reduction on (13% to 15% less on Atlas, where the routers
  ran fewer route computations). Receiving fell from 567 to 206 ms.

## Bring-up: smaller savings than on Atlas

From the routers' start to the check that finds every router with all its adjacencies and the same LSPs:

| Topology | LSPs fewer, per session | Atlas | isisd CPU lower, per session | Atlas |
|---|---|---|---|---|
| Flattened butterfly 4x4x4 | 15%, 25%, 25% | 31%, 33% | 4%, 10%, 10% | 13%, 14% |
| Random regular, degree 16 | 27%, 32%, 30%, 28% | 46%, 47%, 48% | 12%, 16%, 16%, 14% | 25%, 25%, 26% |
| Leaf-spine, 48 x 16 | 22%, 28%, 25%, 27% | 62%, 66% | 16%, 21%, 16%, 18% | 38%, 43% |

- On Atlas, without flood reduction, bring-up sent 1.4 to 3.7 times as many LSPs as on Colab. On leaf-spine it was
  449,000 to 515,000 against 138,000 to 156,000. With flood reduction on, the difference is smaller.
- The deploy step took about as long in both setups: 23 to 69 s on Atlas and 28 to 66 s on Colab for the 64-router
  labs. With the Colab links on Atlas, bring-up saved nearly as much as in the other Atlas runs, so the difference comes
  from the setup (backend and machine), not the links. We have not looked further into why.

## The probe ladder (ff2f)

Two links per run, two runs of each variant:

| Lab | Routers | Links | LSPs sent, off -> on | Fewer | Windows satisfied | Runs converged | Minutes |
|---|---:|---:|---|---:|---:|---:|---:|
| Random regular, degree 4 | 16 | 32 | 97 -> 69 | 29% | 16 of 16 | 4 of 4 | 12.6 |
| Random regular, degree 8 | 32 | 128 | 391 -> 189 | 52% | 16 of 16 | 4 of 4 | 13.3 |
| Random regular, degree 8 | 64 | 256 | 726 -> 501 | 31% | 16 of 16 | 4 of 4 | 14.5 |
| Random regular, degree 16 | 64 | 512 | 1,537 -> 443 | 71% | 16 of 16 | 4 of 4 | 15.5 |
| Leaf-spine, 48 x 16 | 64 | 768 | 2,378 -> 187 | 92% | 16 of 16 | 4 of 4 | 16.5 |

- The ladder stops at the first lab that does not converge. All five converged, so on 8 vCPUs it found no limit up to
  64 routers and 768 links.
- At degree 8 and 64 routers, the saving was 31% against 36% on Atlas (random-regular-n64 and seeds-n64), with other
  links. The model gives 35% for these links and 35% to 36% for Atlas's.
- In the smaller labs, the CPU a link change causes is within the noise (45 ms net at 16 routers).

## Limits of these runs

- Four sessions, three of them at the same time. Two runs per variant per session, 3 links per run (2 in the ladder).
- The Colab links differ from those of the earlier Atlas runs; the Atlas run with the Colab links separates the two
  (above). It is one more run of two repeats, under the load described there.
- The Atlas run's labs were written by the lab container's copy of topology-builders, an earlier 0.2.0.dev0 build
  that did not copy the diameter and two-hop multiplicity into the lab, so `report-atlas-colab-links.txt` shows
  them as `-`. The topology files hold them.
- Colab does not say what else ran on the physical machines. Low steal time means the hypervisor gave the vCPUs
  their time. It does not mean the caches and memory bandwidth were not shared.
- The records' `image` field is the default of `topology-builders clab` (quay.io/frrouting/frr:10.7.1); the
  namespace backend does not use it. It runs the FRR in
  `/usr/lib/frr` that `setup.sh` built (riw777/frr at e263c441). Every one of the 148 link windows with flood reduction on
  counted suppressed sends.
- The probe ladder has graphs of degree 8 at 32 and 64 routers. `report` now adds the number of routers to a name
  that covers graphs of more than one size, so `report.txt` and `report-ff2f.txt` keep them apart in every table
  (an earlier version merged them in the per-handler table).

## How it was run

`tools/colab/topology_builders_sessions.ipynb`, one copy per session.

- For a057, 2c3f and cd61: `PLAN = 'batch'`, `LINKS = 3`, `REPEAT = 2` and `USE_DRIVE = True`, with these labs:

  ```
  ('fb64-444', 'flattened-butterfly', '--radices 4,4,4'),
  ('rr64-d16', 'random-regular', '--routers 64 --degree 16 --seed 1'),
  ('ls64-s16', 'leaf-spine', '--leaves 48 --spines 16'),
  ```

- For ff2f: `PLAN = 'probe'`, `LINKS = 2`, `REPEAT = 2`.

For each lab, the notebook runs:

```
topology-builders build <family> <arguments> --out <name>.json
topology-builders clab <name>.json --out labs/<name> --name <name>
unshare -Urnm topology-builders measure labs/<name>/off labs/<name>/on --backend netns --profile --links 3 \
    --repeat 2 --max-wait 300 --out <session>.jsonl
```

The FRR configuration is the same topotest configuration as on Atlas: level-2-only, point-to-point, hello 1 s x 3,
lsp-gen-interval 2.

On Atlas, for the Colab links, each of the three topology files was rebuilt with the same `build` command and its
builder field `"python": "3.12.3"` replaced by `"3.13.18"`. That gives the sha256 of the Colab records, and so the
same links. Then, in the lab container:

```
topology-builders clab <name>.json --out labs/c-<name> --name c-<name> --image frr-distoptflood:e263c441 \
    --cpu-set 12-23,36-43
topology-builders measure labs/c-<name>/off labs/c-<name>/on --profile --links 3 --repeat 2 --max-wait 300 \
    --out colab-links.jsonl
```

The tables come from:

```
topology-builders report results/colab-sessions/measurements.jsonl.gz
topology-builders report results/colab-sessions/atlas-colab-links.jsonl.gz
python results/colab-sessions/session_tables.py results/colab-sessions/measurements.jsonl.gz \
    results/colab-sessions/sessions.json results
```
