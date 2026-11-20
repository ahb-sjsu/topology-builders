"""The flooding model on k-ary fat-trees, each beside a random regular graph of the same number of routers and
(rounded) average degree, with the method and table of results/model-nfly/nfly_model.py, whose functions it uses.

    python results/model-fat-tree/fat_tree_model.py > results/model-fat-tree/model.txt
"""
import os
import sys

import networkx as nx

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model-nfly"))
import nfly_model as N

from topology_builders import families as F

RADICES = (4, 6, 8, 10, 12, 16, 20, 24)


def main():
    print("| Topology | Routers | Links | Average degree | Two-hop paths | LSPs off, lockstep | LSPs off, jittered "
          "| LSPs on | Saving |")
    print("|---|---|---|---|---|---|---|---|---|")
    for k in RADICES:
        g = F.fat_tree(k)
        print(N.row(f"fat-tree, k = {k}", g), flush=True)
        n = g.number_of_nodes()
        d = round(2 * g.number_of_edges() / n)
        d += (n * d) % 2  # n * d must be even
        rr = F.random_regular(n, d, 1)
        assert nx.is_connected(rr)
        print(N.row(f"random graph, degree {d}", rr), flush=True)


if __name__ == "__main__":
    main()
