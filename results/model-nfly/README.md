# Multistage butterflies (k-ary n-fly): the model only

The flooding model's LSP counts for one link going down, flood reduction off and on, on k-ary n-flies from 16 to
2,304 switches, each beside a random regular graph of the same number of routers and (rounded) average degree.
**These are model results, not measurements.** Four of these topologies (27 to 80 switches) were since measured with
FRR: [results/nfly](../nfly/README.md).

`topology_builders.flood_model` implements the reflood decision of draft-ietf-lsr-distoptflood-14 (sections 1.2.2
and 1.2.3); see [the README](../../README.md#a-model-of-flooding). Twenty links per topology, chosen by seed. With
flood reduction on, the count barely depends on timing. Without it, the count depends on how many copies a router
receives before it sends, so it is given twice: in lockstep (every link takes one unit, no processing delay) and
with link delays drawn from 1 to 2 units. The saving column runs from the lockstep figure to the jittered one.

**Which end to believe.** On the 24 topologies of 64 routers measured with FRR both ways (random graphs, flattened
butterflies, leaf-spine), FRR's saving fell inside this range on 17 and at most 5 points below its lockstep end on
the other 7. On the four n-flies measured since, and on fat-trees, FRR's saving fell inside the range but 7 to 14
points above its lockstep end ([nfly](../nfly/README.md), [fat-tree](../fat-tree/README.md)). Read the lockstep
figure as a lower estimate for these families, about 10 points under FRR, and the jittered one as an upper bound.

Two-hop paths: the mean number of common neighbors of two routers two hops apart.

| Topology | Routers | Links | Average degree | Two-hop paths | LSPs off, lockstep | LSPs off, jittered | LSPs on | Saving |
|---|---|---|---|---|---|---|---|---|
| 8-ary 2-fly | 16 | 64 | 8.00 | 8.00 | 126 | 222 | 30 | 76% to 86% |
| random graph, degree 8 | 16 | 64 | 8.00 | 4.09 | 181 | 222 | 39 | 78% to 82% |
| 3-ary 3-fly | 27 | 54 | 4.00 | 1.62 | 106 | 160 | 64 | 40% to 60% |
| random graph, degree 4 | 27 | 54 | 4.00 | 1.12 | 137 | 160 | 114 | 16% to 29% |
| 2-ary 4-fly | 32 | 48 | 3.00 | 1.27 | 94 | 126 | 75 | 20% to 40% |
| random graph, degree 3 | 32 | 48 | 3.00 | 1.07 | 110 | 126 | 103 | 6% to 18% |
| 4-ary 3-fly | 48 | 128 | 5.33 | 1.82 | 254 | 414 | 130 | 49% to 69% |
| random graph, degree 5 | 48 | 120 | 5.00 | 1.17 | 314 | 382 | 257 | 18% to 33% |
| 2-ary 5-fly | 80 | 128 | 3.20 | 1.25 | 254 | 350 | 209 | 18% to 40% |
| random graph, degree 3 | 80 | 120 | 3.00 | 1.03 | 281 | 318 | 274 | 3% to 14% |
| 3-ary 4-fly | 108 | 243 | 4.50 | 1.50 | 484 | 754 | 328 | 32% to 56% |
| random graph, degree 4 | 108 | 216 | 4.00 | 1.05 | 543 | 646 | 510 | 6% to 21% |
| 2-ary 6-fly | 192 | 320 | 3.33 | 1.24 | 638 | 894 | 538 | 16% to 40% |
| random graph, degree 3 | 192 | 288 | 3.00 | 1.00 | 674 | 766 | 666 | 1% to 13% |
| 8-ary 3-fly | 192 | 1,024 | 10.67 | 2.26 | 2,046 | 3,710 | 774 | 62% to 79% |
| random graph, degree 11 | 192 | 1,056 | 11.00 | 1.27 | 3,084 | 3,838 | 2,386 | 23% to 38% |
| 4-ary 4-fly | 256 | 768 | 6.00 | 1.66 | 1,534 | 2,558 | 951 | 38% to 63% |
| random graph, degree 6 | 256 | 768 | 6.00 | 1.04 | 2,117 | 2,558 | 2,015 | 5% to 21% |
| 3-ary 5-fly | 405 | 972 | 4.80 | 1.45 | 1,942 | 3,076 | 1,406 | 28% to 54% |
| random graph, degree 6 | 405 | 1,215 | 6.00 | 1.03 | 3,316 | 4,048 | 3,210 | 3% to 21% |
| 2-ary 7-fly | 448 | 768 | 3.43 | 1.23 | 1,534 | 2,174 | 1,328 | 13% to 39% |
| random graph, degree 3 | 448 | 672 | 3.00 | 1.00 | 1,579 | 1,790 | 1,569 | 1% to 12% |
| 2-ary 8-fly | 1,024 | 1,792 | 3.50 | 1.22 | 3,582 | 5,118 | 3,154 | 12% to 38% |
| random graph, degree 4 | 1,024 | 2,048 | 4.00 | 1.00 | 5,174 | 6,142 | 5,142 | 1% to 16% |
| 4-ary 5-fly | 1,280 | 4,096 | 6.40 | 1.60 | 8,190 | 13,822 | 5,690 | 31% to 59% |
| random graph, degree 6 | 1,280 | 3,840 | 6.00 | 1.01 | 10,558 | 12,798 | 10,442 | 1% to 18% |
| 2-ary 9-fly | 2,304 | 4,096 | 3.56 | 1.22 | 8,190 | 11,774 | 7,270 | 11% to 38% |
| random graph, degree 4 | 2,304 | 4,608 | 4.00 | 1.00 | 11,622 | 13,822 | 11,604 | 0% to 16% |

**What the model shows.**

- **Structure beats degree.** At the same size and degree, a k-ary n-fly saves far more than a random graph: 49%
  against 18% at 48 switches (4-ary 3-fly), 38% against 5% at 256 (4-ary 4-fly), 31% against 1% at 1,280 (4-ary
  5-fly), lockstep figures.
- **Radix and stages.** The saving rises with the radix k and falls slowly as stages are added: 2-ary, 20% at 4
  stages and 11% at 9; 3-ary 3-fly 40%; 4-ary 3-fly 49%; 8-ary 3-fly 62%.
- **Two-hop paths again.** The saving follows the number of two-hop paths, as on the 64-router graphs measured with
  FRR: about 1.2 for the 2-ary flies, 1.45 to 1.82 for the 3- and 4-ary, 2.3 for the 8-ary 3-fly. A random graph of
  fixed degree has fewer as it grows, towards 1, and its lockstep saving falls towards nothing.
- **The 8-ary 2-fly** is the complete bipartite graph K8,8, a leaf-spine fabric with 8 leaves and 8 spines.

Regenerate (about 30 s on one core):

```
python results/model-nfly/nfly_model.py > results/model-nfly/model.txt
```

`model.txt` is the table above as the script printed it.
