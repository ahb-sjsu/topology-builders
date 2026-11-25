# Without the cached decision topology, flooding after failures is not slow

The [mechanism lab](../mechanism/README.md) found that after a router or several links fail, a relay running FRR pull
request 24128 (draft-ietf-lsr-distoptflood, at e263c441) decides with the topology isisd built at its first flooding
decision after the failure, and keeps it until its next route computation. Decisions on the LSPs that arrive later
still count on links those LSPs report down, so some routers are skipped and wait for the periodic CSNP exchange,
up to a CSNP interval. This experiment removes the cache and replays the same failures.

**Answer.** With the topology rebuilt at every decision, no router got a new LSP more than 1 s after it was built, in
either run: every new LSP reached every router within 68 ms on the butterfly and 210 ms on leaf-spine, against up to
8.9 s with the pull request as it is. The LSPs sent per failure rose by 1.5% on the butterfly and 4.5% on
leaf-spine.

## Method

- **The change.** In `lsp_flood_reduced()` (`isisd/isis_lsp.c`), the pull request builds the decision topology only
  when none is cached (`if (!*graph) *graph = isis_fr_graph_build(...)`), and `isis_run_spf_cb()` frees it when the
  next route computation starts. The changed isisd frees and rebuilds it at every call instead: two lines, nothing
  else. In these failure windows only adjacency changes alter that topology, so this gives the same decisions as a
  cache dropped whenever a newer LSP changes a router's adjacencies. FRR's code is GPL, so the patched source is not
  in this MIT-licensed repository. The image (`tb-colab-nocache`) was built from `tb-colab-test` (FRR at e263c441
  built by `tools/colab/setup.sh`, which keeps the build tree in `/opt/frr-src`) by changing those two lines and
  running `make` and `make install`: only `isisd/isis_lsp.o` was recompiled and `isisd` relinked. The two isisd
  binaries' SHA-256 begin 2e8633debf187 (as it is) and 768f0f8a826fa (changed); every lab log records which ran.
- **The labs.** `tools/model/collect_events.py`, as in the mechanism lab: the 4x4x4 flattened butterfly and the
  leaf-spine fabric of 48 leaves and 16 spines, with the same events (two routers failing, two sets of three links
  failing together, each followed by recovery), every router logging its flooding decisions, LSPs, CSNPs, PSNPs and
  route-computation starts. Flood reduction on. The butterfly also once without flood reduction, as the control.
- **Where.** KVM guests through `tools/overlay/run_vm.sh` (no network device, 16 vCPUs on the host's CPUs 12-23 and
  36-43, 32 GiB), the namespace backend inside the `tb-colab-*` images, 2026-11-25. Guest 1 (01:24 to 01:42 UTC) ran
  the pull request as it is on both topologies and the control; its runs of the changed isisd failed to start (its
  image was not readable through the share). Guest 2 (02:13 to 02:49 UTC) ran, per topology, changed, as it is,
  changed. So each variant has two runs per topology. The host's other heavy job, a Lean build in a container on the
  same CPUs, was paused while each guest ran.
- **The analysis.** `tools/model/analyze_events.py` and `results/mechanism/classify.py` (late pairs, how they got
  the LSP, stale and unmatched relays), `tools/model/check_builds.py` (which topology each relay decided with) and
  `tools/model/count_sends.py` (LSPs sent from 5 s before each failure's recorded time to its recovery), all on the
  full logs. The reduced logs here reproduce every one of these outputs byte for byte.

These guests are not the container of the mechanism lab (64 routers on 4 shared CPUs), so absolute times differ from
its results; compare the variants with each other. The changed isisd's CPU was not measured: the debug logging these
runs need distorts it.

## Results

Slowest new LSP of each failure, from its build to the last router holding it, in ms:

| Failure | As it is, run 1 | As it is, run 2 | Changed, run 1 | Changed, run 2 | Without flood reduction |
|---|---:|---:|---:|---:|---:|
| Butterfly, router r25 | 3,970 | 2,954 | 56 | 57 | 62 |
| Butterfly, router r45 | 2,469 | 4,246 | 68 | 63 | 67 |
| Butterfly, links r0-r2, r19-r31, r32-r40 | 3,337 | 1,497 | 67 | 58 | 92 |
| Butterfly, links r48-r50, r52-r55, r52-r56 | 5,126 | 5,856 | 66 | 66 | 60 |
| Leaf-spine, spine r6 | 8,884 | 8,898 | 210 | 170 | |
| Leaf-spine, spine r1 | 2,470 | 2,361 | 177 | 159 | |
| Leaf-spine, links r2-r49, r7-r40, r10-r46 | 2,251 | 4,281 | 174 | 128 | |
| Leaf-spine, links r4-r36, r4-r37, r13-r29 | 5,494 | 238 | 121 | 176 | |

- **Late arrivals.** Of the 8,454 router-LSP pairs per run, 342 and 221 arrived more than 1 s late with the pull
  request as it is, 341 and 217 of them through the CSNP exchange. With the change, none in either run.
- **Why they were late.** Every late pair of the runs as they are has a relay that skipped the late router (262 and
  140 stale relay pairs, 80 and 81 unmatched, none unexplained). On the topology each such relay held when isisd
  built it, the model reproduces every one of their 572 logged decisions; on the topology it held at the decision
  itself, 1 of them. As in the mechanism lab, every topology was built after the failure began.
- **LSPs sent** from 5 s before each failure to its recovery, the four failures of a topology summed:

  | Topology | As it is, run 1 | As it is, run 2 | Changed, run 1 | Changed, run 2 | Without flood reduction |
  |---|---:|---:|---:|---:|---:|
  | Butterfly 4x4x4 | 3,870 | 3,922 | 3,982 | 3,930 | 12,375 |
  | Leaf-spine 48 x 16 | 14,100 | 14,656 | 14,831 | 15,220 | |

  The change sends 1.5% more on the butterfly and 4.5% more on leaf-spine, means of the two runs. The counts include
  LSPs sent on request after a CSNP or PSNP, which the runs as they are needed to repair the skipped routers. On the
  butterfly, flood reduction sends 68% fewer LSPs than the control with the change, and 69% fewer without it.
- **Not tested.** The draft (section 1.2.4) recommends that a router which does not reflood an LSP send every
  neighbor a PSNP listing it after a short timer, much shorter than the CSNP interval; the pull request leaves this
  out. With the cache removed no router was left late in these failures, so there was nothing for it to repair.

## Files

- `analysis-<run>-<lab>.txt`: `analyze_events.py --verbose`, for runs `stock-r1`, `stock-r2` (the pull request as it
  is), `nocache-r1`, `nocache-r2` (changed), labs `fb444-on`, `ls16-on`, and `stock-r1` `fb444-off` (the control).
- `classify-<run>.txt`: `classify.py` on a run's two labs: the per-failure table of late pairs.
- `analysis-<run>-builds.txt`: `check_builds.py` on a run's two labs.
- `sends-<run>.txt`: `count_sends.py` on a run's labs.
- `logs.tar.gz`: per run and lab, the lab, the events with their times and every router's log reduced by
  `tools/model/filter_logs.py --sends` (the lines the analyses read, plus every LSP sent), from 6 s before the first
  failure to 30 s after the last.
- `job/`: the guest jobs (`job1.sh`, `job2.sh`, `inner.sh`).

```
mkdir cache && tar -xzf results/cache-experiment/logs.tar.gz -C cache
cd cache/nocache-r1 && python ../../tools/model/analyze_events.py --verbose fb444-on ls16-on
python ../../tools/model/check_builds.py fb444-on ls16-on && python ../../tools/model/count_sends.py fb444-on ls16-on
```
