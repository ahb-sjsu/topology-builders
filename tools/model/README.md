# Checking the flooding model against FRR, decision by decision

`topology_builders.flood_model` reproduces the reflood decision of draft-ietf-lsr-distoptflood-14. These scripts
check it against the decisions FRR's isisd actually makes, use it to explain FRR's logs, and compare its LSP counts
with measured ones.

1. `collect_decisions.py` (root, or inside `unshare -Urnm`): for each topology file, writes a lab with flood
   reduction on, `debug isis flooding` and timing logs, deploys it with the namespace backend, waits for convergence,
   takes links down and up one at a time, and saves every router's log and the lab.
2. `compare_decisions.py`: for every "Flooding LSP ... with reduction" line, finds the transmitting neighbor from
   the router's last "Rcvd" line for that LSP, runs the model's `decide` for the same router, neighbor and LSP, and
   compares what FRR logged (selected, THL, RNL, start index, suppressed) under three snapshots (the topology
   without the changed link, the model's assumption; with it; the routers' actual adjacencies) and under every
   combination of snapshot and neighbor list with and without the changed link, and lists any decision that
   matches none.

```
unshare -Urnm python3 tools/model/collect_decisions.py --out decisions topos/*.json
python tools/model/compare_decisions.py decisions/*/
```

**Status (2026-11-20):** run on five topologies of 16 to 20 routers: all 1,186 decisions match the model, given
the snapshot each router decided with ([results/model-decisions](../../results/model-decisions/README.md)).
`compare_decisions.py` also prints, per window, how many decisions used a snapshot with or without the changed link.

## After router and multi-link failures

3. `collect_events.py`: replays measured failures (`node` and `multi` events, as `measure` stores them) in a
   namespace lab, flood reduction off and/or on, with `debug isis flooding`, timing logs, `debug isis snp-packets`
   and `debug isis spf-events`, and saves every router's log, the lab and the events' times.
4. `analyze_events.py`: for each failure, when each router first held each new LSP and how it got it (flooding, or
   CSNP exchange: asked for with a PSNP, or sent by a neighbor that saw an older copy in its CSNP); for late
   arrivals, which topology snapshot reproduces each relaying neighbor's logged decision, and whether the decision on
   the topology without the failed links would have sent the LSP to the late router.

5. `check_builds.py`: for every relay `analyze_events.py` finds behind a late pair, when isisd built the topology
   the relay decided with (its first flood-reduction decision after its last route-computation start, "SPF needed"
   in `debug isis spf-events`), how many of the failure's new LSPs it had received by then, and whether the model
   reproduces the relay's logged decision on that topology, on the one it held at the decision, and with no failed
   link removed.
6. `filter_logs.py`: copies a lab's output keeping only the log lines the two analyses read, so that they can be
   published and rerun (`results/mechanism/logs.tar.gz`); with `--sends` also every LSP sent
   (`results/cache-experiment/logs.tar.gz`).
7. `count_sends.py`: LSPs sent per failure window (by flooding or on request after a CSNP or PSNP), from the logs'
   "Sending L2 LSP" lines.

```
unshare -Urnm python3 tools/model/collect_events.py --out mech --topology t.json --events events.json --reduction both
python tools/model/analyze_events.py --verbose mech/*/
python tools/model/check_builds.py mech/*-on
```

An event's recorded time (`events.json`) is taken after its links are down, and a router that fails with many links
starts the failure up to about 1.3 s earlier. The analyses therefore look for each failure's new LSPs from
`analyze_events.BEFORE` (5 s) before it. Until 2026-11-25 they looked from 0.5 s before it, which left out two of
the new LSPs after one router failure and replaced two others with the recovery LSPs built 25 s later.

**Status (2026-11-25):** on the 4x4x4 butterfly and leaf-spine with 16 spines, 242 of the 250 router-LSP pairs that
arrived more than 1 s late got the LSP by CSNP. For 244 of them a relay skipped the late router because it decided
with the topology isisd built at its first decision after the failure, which reproduces 245 of the 246 relays'
logged decisions ([results/mechanism](../../results/mechanism/README.md)). With that topology rebuilt at every
decision, no pair arrived more than 1 s late ([results/cache-experiment](../../results/cache-experiment/README.md)).

## The model against measured LSP counts

8. `validate.py`: for every run in a measurements file, finds the topology file the lab was written from (by sha256,
   under the folders in `TOPOLOGY_DIRS`) and prints, per topology, variant and window kind, the LSPs FRR sent against
   the model's count for the same links, in lockstep and with jittered link delays.

```
mkdir topos && tar -xzf results/seeds-n64/topologies.tar.gz -C topos
TOPOLOGY_DIRS=topos python tools/model/validate.py results/seeds-n64/measurements.jsonl.gz
```

**Status (2026-11-22):** it gives the `model.txt` of every FRR results folder with topology files:
[seeds-n64](../../results/seeds-n64/README.md), [random-regular-n128](../../results/random-regular-n128/README.md),
[nfly](../../results/nfly/README.md), [fat-tree](../../results/fat-tree/README.md), and the first two 64-router
sweeps, [random-regular-n64](../../results/random-regular-n64/README.md) and
[families-n64](../../results/families-n64/README.md) (28 topologies; their topology files were added on
2026-11-22).
