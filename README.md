# Topology builders

Generators for network topologies whose density can be stepped while the number of routers stays fixed, so that
an experiment can tell the effect of density from the effect of size. The first use is testing an IS-IS flooding
reduction on denser and denser topologies.

## Families

| Family | What it is | Density knob at N routers |
|---|---|---|
| `random-regular` | Every router has exactly d links, chosen at random. networkx `random_regular_graph`; above d = (N - 1)/2, the complement of a random (N - 1 - d)-regular graph. A disconnected draw is drawn again. | d = 3, 4, 6, 8, 12, ... up to N - 1 (with N odd, even d only) |
| `leaf-spine` | Two-tier Clos: every leaf is linked to every spine | 2, 3, 4, 6, 8, ... spines up to N/2, the rest leaves |
| `flattened-butterfly` | Routers on a grid of radices k1 x k2 x ...; each is linked to every router that differs from it in one coordinate (Kim, Dally and Abts, ISCA 2007). One radix N is the full mesh; all radices 2 is the hypercube. | every factorization of N (a prime N has only the full mesh) |
| `zoo` | A Topology Zoo graph, in TopoHub's packaging, made denser by adding links: at random, or shortest great-circle distance first | target average degree, up to N - 1 |
| `k-ary-n-fly` | The butterfly: n stages of k^(n-1) switches, each linked to the k switches of the next stage whose position differs from its own in one base-k digit. Switches only, no hosts. | none: the size grows with k and n, so it is not in the sweep |

Random-regular and flattened-butterfly both end at the full mesh. Leaf-spine is densest at N/2 spines, where the
average degree is N/2.

The two ways of adding links to a Zoo graph give very different networks. On TataNld (143 routers, 181 links), at
an average degree of 8 the diameter is 16 hops with nearest-first and 4 with random links. Added links are nested:
with the same method and seed, every link added for a lower target is also there at a higher one, so a denser graph
differs from a sparser one only by the extra links.

## Output

Each topology is one JSON file in NetworkX node-link form, with keys `nodes` and `edges`, the shape TopoHub uses.
It can be read with `networkx.node_link_graph(data, edges="edges")`. Routers are named `r0`, `r1`, .... The graph
attributes record:

- the family, its parameters and how it was built;
- routers, links, average degree, density, minimum and maximum degree, whether it is connected, and the diameter in
  hops (left out, as null, when routers x links is over 20 million);
- the versions of this package, Python and networkx.

The `sweep` and `zoo` commands also write `manifest.json`, with each file's SHA-256 and summary. Nodes, edges and
keys are sorted, so the same versions and parameters give byte-identical files.

## Use

```
python -m topology_builders sweep --routers 64 --seeds 1,2,3 --out out/n64
python -m topology_builders zoo <topohub>/data/topozoo/TataNld.json --method nearest --degrees 4,8,16 --out out/tata
python -m topology_builders build flattened-butterfly --radices 8,8 --out ff-8x8.json
python -m topology_builders build k-ary-n-fly --k 4 --stages 3 --out fly-4x3.json
```

Without `--degrees`, `zoo` steps from just above the graph's own average degree to the full mesh. The Zoo data is
not included, because TopoHub's packaging states no licence: point `zoo` at a local copy.

Tests: `python -m pytest`. They check each family against its definition: degrees and connectivity; that the
flattened butterfly equals networkx's Cartesian product of complete graphs and the hypercube; that the butterfly has
exactly one forward path between each first-stage and each last-stage switch; and that zoo additions keep the
original links, nest, and with nearest-first add the shortest links.

Measured on an HP Z840 (Xeon E5-2690 v3; Python 3.12.3, networkx 3.6.1), 2026-11-18:

- all 10 tests pass;
- the 64-router sweep with seeds 1, 2 and 3: 50 topologies, all connected, in 1.0 s in all (0.03 s or less each),
  and a second run gives byte-identical files (50 of 50 SHA-256 equal);
- random-regular at 256 routers, d = 3 to 255: 14 topologies in 3.1 s in all, the largest with 32,640 links.

## Not here yet

- Emitters: FRR IS-IS configurations and containerlab topology files.
- A survey of existing builders, so that this repository links to and wraps them rather than rewriting them.
- Fat-tree (three-tier Clos) by radix.

## License

Two licenses, split by what the file is.

| What | License | File |
|---|---|---|
| Code (`topology_builders/`, `tests/`) | MIT | `LICENSE` |
| Documentation (this README) | CC BY 4.0 | `LICENSE-TEXT` |
