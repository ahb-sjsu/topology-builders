"""A Topology Zoo graph, as packaged by TopoHub, made denser by adding links.

TopoHub's files are NetworkX node-link JSON: each node has an id and usually a name and a position [longitude,
latitude]; each edge has a source, a target and usually a length in km ("dist").  Multiple links between the same
two nodes become one, self-loops are dropped, and only the largest connected component is kept.

Added links are nested.  With the same method and seed the candidate links are put in one fixed order and each
target takes a prefix of it, so every link added for a lower average degree is also there at a higher one: a denser
graph differs from a sparser one only by the extra links."""
import hashlib
import json
import math
import os
import random

import networkx as nx

from .sweep import degree_steps


def _km(a, b):
    """Great-circle distance between two [longitude, latitude] positions, in km."""
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def read_topohub(path):
    """The graph of one TopoHub file, its largest connected component, with nodes renamed r<id>."""
    with open(path, "rb") as fh:
        raw = fh.read()
    d = json.loads(raw)
    g = nx.Graph()
    for v in d["nodes"]:
        attrs = {k: v[k] for k in ("name", "pos") if k in v}
        g.add_node(int(v["id"]), **attrs)
    for e in d.get("edges", d.get("links", [])):
        u, v = int(e["source"]), int(e["target"])
        if u != v and not g.has_edge(u, v):
            g.add_edge(u, v, **({"length_km": e["dist"]} if "dist" in e else {}))
    keep = max(nx.connected_components(g), key=lambda c: (len(c), -min(c)))
    dropped = g.number_of_nodes() - len(keep)
    g = nx.relabel_nodes(g.subgraph(keep).copy(), {v: f"r{v}" for v in keep})
    for _, _, a in g.edges(data=True):
        a["added"] = False
    name = os.path.splitext(os.path.basename(path))[0]
    return g, {"source": os.path.basename(path), "source_sha256": hashlib.sha256(raw).hexdigest(),
               "name": name, "dropped_nodes": dropped}


def default_degrees(path):
    """Average degrees from just above the graph's own up to the full mesh."""
    g, _ = read_topohub(path)
    n, m = g.number_of_nodes(), g.number_of_edges()
    return [x for x in degree_steps(3, n - 1) if x > 2 * m / n]


def denser(path, average_degree, method="random", seed=1):
    """The graph of `path` with links added until its average degree reaches `average_degree` (rounded up to a whole
    number of links).  method: "random" (uniform over the missing links, fixed by the seed) or "nearest" (shortest
    great-circle distance first; needs a position on every node; the seed is not used)."""
    g, info = read_topohub(path)
    n, m = g.number_of_nodes(), g.number_of_edges()
    target = math.ceil(average_degree * n / 2 - 1e-9)
    if target > n * (n - 1) // 2:
        raise ValueError(f"average degree {average_degree} is above the full mesh on {n} routers ({n - 1})")
    if target < m:
        raise ValueError(f"{info['name']} already has average degree {2 * m / n:.3f} > {average_degree}")
    key = lambda v: int(v[1:])  # noqa: E731
    missing = sorted((tuple(sorted(e, key=key)) for e in nx.non_edges(g)), key=lambda e: (key(e[0]), key(e[1])))
    pos = nx.get_node_attributes(g, "pos")
    if method == "random":
        random.Random(f"zoo/{info['name']}/{seed}").shuffle(missing)
    elif method == "nearest":
        if len(pos) < n:
            raise ValueError(f"{info['name']}: {n - len(pos)} nodes have no position, so nearest cannot be used")
        missing.sort(key=lambda e: _km(pos[e[0]], pos[e[1]]))
    else:
        raise ValueError(f"method must be random or nearest, got {method}")
    for u, v in missing[:target - m]:
        attrs = {"added": True}
        if u in pos and v in pos:
            attrs["length_km"] = round(_km(pos[u], pos[v]), 2)
        g.add_edge(u, v, **attrs)
    params = {"routers": n, "average_degree": average_degree, "method": method, **info,
              "original_links": m, "added_links": target - m}
    if method == "random":
        params["seed"] = seed
    g.graph = {"family": "zoo", "parameters": params}
    return g
