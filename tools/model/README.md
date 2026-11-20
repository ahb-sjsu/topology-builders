# Checking the flooding model against FRR, decision by decision

`topology_builders.flood_model` reproduces the reflood decision of draft-ietf-lsr-distoptflood-14. These two scripts
check it against the decisions FRR's isisd actually makes.

1. `collect_decisions.py` (root, or inside `unshare -Urnm`): for each topology file, writes a lab with flood
   reduction on, `debug isis flooding` and timing logs, deploys it with the netns backend, waits for convergence,
   takes links down and up one at a time, and saves every router's log and the lab.
2. `compare_decisions.py`: for every "Flooding LSP ... with reduction" line, finds the transmitting neighbor from
   the router's last "Rcvd" line for that LSP, runs the model's `decide` for the same router, neighbor and LSP, and
   compares what FRR logged (selected, THL, RNL, start index, suppressed) under three snapshots: the topology
   without the changed link (the model's assumption), with it, and the routers' actual adjacencies.

```
unshare -Urnm python3 tools/model/collect_decisions.py --out decisions topos/*.json
python tools/model/compare_decisions.py decisions/*/
```

**Status (2026-11-20):** not yet run.
