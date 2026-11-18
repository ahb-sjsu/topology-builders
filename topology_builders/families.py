"""The builders.  Each returns an undirected networkx Graph whose nodes are named r0, r1, ... and whose graph
attributes record the family and the parameters that produced it."""
import itertools
import random

import networkx as nx


def _named(g, family, parameters, order=None):
    """Rename the nodes r0, r1, ... in the given order (default: sorted) and record the family and parameters."""
    order = list(order) if order is not None else sorted(g.nodes)
    h = nx.relabel_nodes(g, {v: f"r{i}" for i, v in enumerate(order)})
    h.graph = {"family": family, "parameters": parameters}
    return h


def random_regular(routers, degree, seed=1):
    """Every router has exactly `degree` links, chosen at random.  Connected.

    Below half of routers - 1 this is networkx's random_regular_graph.  Above it, it is the complement of a random
    (routers - 1 - degree)-regular graph: complementing is a one-to-one map between the two sets of graphs, and the
    sparse side is the one the pairing method handles quickly.  A disconnected draw is drawn again; the attempt
    number is recorded, and the seed and attempt fix the result."""
    n, d = routers, degree
    if not 3 <= d <= n - 1:
        raise ValueError(f"degree must be from 3 to routers - 1 = {n - 1}, got {d}")
    if n * d % 2:
        raise ValueError(f"routers x degree must be even, got {n} x {d}")
    dense = d > (n - 1) / 2
    for attempt in range(1000):
        rng = random.Random(f"random-regular/{n}/{d}/{seed}/{attempt}")
        if dense:
            g = nx.complement(nx.random_regular_graph(n - 1 - d, n, seed=rng))
        else:
            g = nx.random_regular_graph(d, n, seed=rng)
        if nx.is_connected(g):
            break
    else:
        raise RuntimeError(f"no connected {d}-regular graph on {n} routers in 1000 attempts")
    h = _named(g, "random-regular", {"routers": n, "degree": d, "seed": seed})
    h.graph["construction"] = {
        "method": ("complement of networkx random_regular_graph(routers - 1 - degree)" if dense
                   else "networkx random_regular_graph"),
        "attempt": attempt}
    return h


def leaf_spine(leaves, spines):
    """Two-tier Clos: every leaf is linked to every spine."""
    if leaves < 1 or spines < 1:
        raise ValueError("leaves and spines must be at least 1")
    g = nx.complete_bipartite_graph(spines, leaves)
    for v in g:
        g.nodes[v].clear()
        g.nodes[v]["role"] = "spine" if v < spines else "leaf"
    return _named(g, "leaf-spine", {"routers": leaves + spines, "leaves": leaves, "spines": spines})


def flattened_butterfly(radices):
    """Routers on a grid of radices k1 x k2 x ...; each is linked to every router that differs from it in exactly one
    coordinate (Kim, Dally and Abts, ISCA 2007).  The Cartesian product of complete graphs: one radix N is the full
    mesh, all radices 2 is the hypercube.  Degree is the sum of (k - 1)."""
    radices = tuple(int(k) for k in radices)
    if not radices or min(radices) < 2:
        raise ValueError("radices must be one or more integers of at least 2")
    coords = list(itertools.product(*(range(k) for k in radices)))
    g = nx.Graph()
    for c in coords:
        g.add_node(c, coordinates=list(c))
    for c in coords:
        for dim, k in enumerate(radices):
            for x in range(c[dim] + 1, k):
                g.add_edge(c, c[:dim] + (x,) + c[dim + 1:])
    return _named(g, "flattened-butterfly", {"routers": len(coords), "radices": list(radices)}, order=coords)


def kary_nfly(k, stages):
    """The butterfly (k-ary n-fly): `stages` stages of k^(stages - 1) switches.  Switch w of stage s is linked to the
    k switches of stage s + 1 whose positions differ from w only in base-k digit s, so between any switch of the
    first stage and any of the last there is exactly one path that moves forward.  Switches only: no hosts."""
    if k < 2 or stages < 2:
        raise ValueError("k and stages must be at least 2")
    width = k ** (stages - 1)
    order = [(s, w) for s in range(stages) for w in range(width)]
    g = nx.Graph()
    for s, w in order:
        g.add_node((s, w), stage=s, position=w)
    for s in range(stages - 1):
        step = k ** s
        for w in range(width):
            base = w - ((w // step) % k) * step
            for x in range(k):
                g.add_edge((s, w), (s + 1, base + x * step))
    return _named(g, "k-ary-n-fly", {"routers": stages * width, "k": k, "stages": stages}, order=order)
