# The flooding model against FRR, decision by decision

Does `topology_builders.flood_model`, written from draft-ietf-lsr-distoptflood-14, decide what FRR's isisd decides?
With `debug isis flooding`, isisd logs every flood-reduction decision: whether the router was selected, the size of
the two-hop list (THL) and of the remote neighbor list (RNL), the start index of the walk (from the LSP ID's hash),
and how many neighbors the LSP was not sent to. This run compares all five with the model's `decide`.

**Method.** `tools/model/collect_decisions.py` on 2026-11-20, in the container shaped like Colab (Ubuntu 24.04,
Colab's capabilities, no network, 2 CPUs of a two-socket Xeon workstation; FRR from pull request 24128 at e263c441,
built by `tools/colab/setup.sh`), netns backend: five topologies of 16 to 20 routers with flood reduction on, three
links taken down and up one at a time, 12 s apart. `tools/model/compare_decisions.py` finds each decision's
transmitting neighbor from the router's last "Rcvd" line for that LSP, and runs the model's `decide` for the same
router, neighbor and LSP, with the topology snapshot with and without the changed link, and the router's neighbor
list with and without it (at the link's ends the adjacency may not be up yet when the router decides).

**Result: every decision matches.** All 1,186 decisions compared match the model exactly, on all five fields, for one
of those combinations. Three decisions per topology were skipped (no transmitting neighbor found in the log, or
isisd fell back to normal flooding).

| Topology | Decisions | Match, any snapshot | Match, snapshot without the changed link | Link down: snapshot without / with / either | Link up: snapshot without / with / either |
|---|---|---|---|---|---|
| fat-tree, k = 4 | 282 | 282 | 226 (80%) | 57 / 0 / 57 | 30 / 56 / 82 |
| flattened butterfly 4×4 | 222 | 222 | 151 (68%) | 71 / 0 / 19 | 35 / 71 / 26 |
| flattened butterfly 8×2 | 237 | 237 | 173 (73%) | 73 / 0 / 17 | 57 / 64 / 26 |
| leaf-spine, 12 leaves, 4 spines | 222 | 222 | 132 (59%) | 84 / 0 / 6 | 42 / 90 / 0 |
| random, degree 4 | 223 | 223 | 178 (80%) | 52 / 0 / 38 | 24 / 45 / 64 |
| **All** | **1,186** | **1,186** | **860 (73%)** | **337 / 0 / 137** | **188 / 326 / 198** |

"Either": the decision is the same with either snapshot.

**What it shows.**

- **The rule is FRR's.** Given the topology a router decides with, the model reproduces isisd's decision exactly,
  including the start index, so the LSP ID hash is right as well.
- **Which topology a router decides with depends on timing.** When a link goes down, no decision used a snapshot
  that still held the link: the first new LSP a router receives already removes it in the two-way check. When a link
  comes up, 326 of the 514 decisions that depend on it used a snapshot that already held the new link, and 188 one
  that did not: the model's `flood_link_change` assumes the snapshot without the link, which is right for link-down
  windows and wrong for most decisions after a link comes up.
- **Scope.** Single link changes on topologies of 16 to 20 routers, 2 CPUs, one run per topology. Router and
  multi-link failures, where stale snapshots are the suspected cause of the slow flooding in
  [timing-n64](../timing-n64/README.md), are the next check.

Files: [compare.txt](compare.txt) (the comparison as printed); [decisions.tar.gz](decisions.tar.gz) (every router's
log from just before the first change, the lab and the times of the changes, per topology). Rerun the comparison:

```
tar -xzf results/model-decisions/decisions.tar.gz -C /tmp/decisions
python tools/model/compare_decisions.py /tmp/decisions/*/
```
