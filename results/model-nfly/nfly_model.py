"""The flooding model on multistage k-ary n-flies, each beside a random regular graph of the same number of routers
and (rounded) average degree: LSPs sent per link going down, flood reduction off and on.

    python results/model-nfly/nfly_model.py > results/model-nfly/model.txt

Twenty links per topology, chosen with random.Random(7). With flood reduction on, the count barely depends on
timing, so it is computed in lockstep (every link takes one unit, no processing delay). Without it, the count depends
on how many copies a router receives before it sends, so it is given twice: in lockstep, and with each link's delay
drawn from 1 to 2 units (mean of three draws); the two savings bracket the effect of timing."""
import random
import statistics as st

import networkx as nx

from topology_builders import families as F
from topology_builders import flood_model as M

CASES = [(8, 2), (3, 3), (2, 4), (4, 3), (2, 5), (3, 4), (2, 6), (8, 3), (4, 4), (3, 5), (2, 7), (2, 8), (4, 5),
         (2, 9)]
LINKS = 20


def snapshot(g):
    """System IDs 1..N in the builder's order, as clab.plan numbers routers."""
    names = {v: f"r{i}" for i, v in enumerate(g.nodes)}
    return M.Topology({names[v]: {names[u] for u in g.adj[v]} for v in g.nodes},
                      {names[v]: i + 1 for i, v in enumerate(g.nodes)})


def two_hop(g, sample=300, seed=1):
    """Mean number of common neighbors of router pairs two hops apart, over a sample of routers."""
    rng = random.Random(seed)
    counts = []
    for v in rng.sample(list(g.nodes), min(sample, g.number_of_nodes())):
        near, seen = set(g.adj[v]), {}
        for u in near:
            for w in g.adj[u]:
                if w != v and w not in near:
                    seen[w] = seen.get(w, 0) + 1
        counts.extend(seen.values())
    return st.mean(counts)


def row(name, g):
    t = snapshot(g)
    links = sorted((a, b) for a in t.adj for b in t.adj[a] if a < b)
    pick = random.Random(7).sample(links, min(LINKS, len(links)))
    off = st.mean(M.flood_link_change(t, x, "down", False)["sent"] for x in pick)
    rng = random.Random(3)
    off_j = st.mean(M.flood_link_change(t, x, "down", False, jitter=1.0, rng=rng)["sent"] for x in pick for _ in range(3))
    on = st.mean(M.flood_link_change(t, x, "down", True)["sent"] for x in pick)
    n, m = g.number_of_nodes(), g.number_of_edges()
    return (f"| {name} | {n:,} | {m:,} | {2 * m / n:.2f} | {two_hop(g):.2f} | {off:,.0f} | {off_j:,.0f} | {on:,.0f} "
            f"| {100 * (1 - on / off):.0f}% to {100 * (1 - on / off_j):.0f}% |")


def main():
    print("| Topology | Routers | Links | Average degree | Two-hop paths | LSPs off, lockstep | LSPs off, jittered "
          "| LSPs on | Saving |")
    print("|---|---|---|---|---|---|---|---|---|")
    for k, stages in CASES:
        g = F.kary_nfly(k, stages)
        print(row(f"{k}-ary {stages}-fly", g), flush=True)
        n = g.number_of_nodes()
        d = round(2 * g.number_of_edges() / n)
        d += (n * d) % 2  # n * d must be even
        rr = F.random_regular(n, d, 1)
        assert nx.is_connected(rr)
        print(row(f"random graph, degree {d}", rr), flush=True)


if __name__ == "__main__":
    main()
