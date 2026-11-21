# Fat-trees (three-tier Clos): the model only

The flooding model's LSP counts for one link going down, flood reduction off and on, on k-ary fat-trees from k = 4
(20 switches) to k = 24 (720 switches), each beside a random regular graph of the same number of routers and
(rounded) average degree. **These are model results, not measurements.** The fat-trees from k = 4 to k = 12 (20 to
180 switches) were since measured with FRR: [results/fat-tree](../fat-tree/README.md).

The method is that of [the n-fly tables](../model-nfly/README.md), whose script this one uses: twenty links per
topology chosen by seed, flood reduction on counted in lockstep, and flood reduction off counted both in lockstep and
with link delays drawn from 1 to 2 units. The saving column runs from the lockstep figure to the jittered one. On the
24 topologies of 64 routers measured with FRR both ways, FRR's saving fell inside this range on 17 and at most 5
points below its lockstep end on the other 7. On the five fat-trees measured since, FRR's saving fell inside the
range but 7 to 14 points above its lockstep end (41% against 27% at k = 4, 59% against 52% at k = 8, 67% against
60% at k = 12, link-down windows; [fat-tree](../fat-tree/README.md)): for fat-trees read the lockstep figure as a
lower estimate and the jittered one as an upper bound.

The fat-tree is `families.fat_tree(k)`: k pods of k/2 edge and k/2 aggregation switches and (k/2)² core switches,
switches only, so edge switches have degree k/2 and the others k. Two-hop multiplicity: the mean number of common neighbors
of two routers two hops apart.

| Topology | Routers | Links | Average degree | Two-hop multiplicity | LSPs off, lockstep | LSPs off, jittered | LSPs on | Saving |
|---|---|---|---|---|---|---|---|---|
| fat-tree, k = 4 | 20 | 32 | 3.20 | 1.48 | 62 | 86 | 45 | 27% to 47% |
| random graph, degree 3 | 20 | 30 | 3.00 | 1.09 | 70 | 78 | 60 | 14% to 23% |
| fat-tree, k = 6 | 45 | 108 | 4.80 | 1.82 | 214 | 340 | 121 | 43% to 64% |
| random graph, degree 6 | 45 | 135 | 6.00 | 1.32 | 364 | 448 | 268 | 26% to 40% |
| fat-tree, k = 8 | 80 | 256 | 6.40 | 2.06 | 510 | 862 | 250 | 51% to 71% |
| random graph, degree 6 | 80 | 240 | 6.00 | 1.15 | 662 | 798 | 562 | 15% to 30% |
| fat-tree, k = 10 | 125 | 500 | 8.00 | 2.25 | 998 | 1,748 | 438 | 56% to 75% |
| random graph, degree 8 | 125 | 500 | 8.00 | 1.18 | 1,448 | 1,748 | 1,215 | 16% to 30% |
| fat-tree, k = 12 | 180 | 864 | 9.60 | 2.39 | 1,726 | 3,094 | 697 | 60% to 77% |
| random graph, degree 10 | 180 | 900 | 10.00 | 1.22 | 2,656 | 3,238 | 2,129 | 20% to 34% |
| fat-tree, k = 16 | 320 | 2,048 | 12.80 | 2.60 | 4,094 | 7,550 | 1,506 | 63% to 80% |
| random graph, degree 13 | 320 | 2,080 | 13.00 | 1.23 | 6,238 | 7,678 | 4,974 | 20% to 35% |
| fat-tree, k = 20 | 500 | 4,000 | 16.00 | 2.63 | 7,998 | 14,998 | 2,748 | 66% to 82% |
| random graph, degree 16 | 500 | 4,000 | 16.00 | 1.23 | 12,074 | 14,998 | 9,633 | 20% to 36% |
| fat-tree, k = 24 | 720 | 6,912 | 19.20 | 2.74 | 13,822 | 26,206 | 4,547 | 67% to 83% |
| random graph, degree 19 | 720 | 6,840 | 19.00 | 1.23 | 20,719 | 25,918 | 16,624 | 20% to 36% |

**What the model shows.**

- **The saving rises with the radix,** towards two-thirds: 27% at k = 4, 43% at 6, 51% at 8, 60% at 12, 63% at 16
  and 67% at 24 (lockstep figures).
- **A random graph of the same size and degree stays near 20%** from 80 routers up (15 to 20%; 14% and 26% at 20
  and 45 routers).
- **Two-hop multiplicity again.** A fat-tree's multiplicity goes from 1.48 at k = 4 to 2.74 at k = 24, while the random
  graphs stay between 1.09 and 1.32; the saving follows them, as on the 64-router graphs measured with FRR and on
  the multistage butterflies.

Regenerate (about 35 s on one core):

```
python results/model-fat-tree/fat_tree_model.py > results/model-fat-tree/model.txt
```

`model.txt` is the table above as the script printed it.
