"""One output format for every builder: NetworkX node-link JSON (keys "nodes" and "edges", the shape TopoHub uses for
the Topology Zoo), with the family, parameters and summary numbers in the graph attributes.  Nodes and edges are
sorted and keys are sorted, so the same versions and the same parameters give the same bytes."""
import hashlib
import json
import os
import platform

import networkx as nx

from . import __version__

FORMAT = "topology-builders node-link 0.1"
DIAMETER_LIMIT = 20_000_000  # routers x links above which the distances are not computed
PATHS_LIMIT = 20_000_000  # sum of squared degrees above which the two-hop multiplicity is not computed


def builder_info():
    return {"package": "topology-builders", "version": __version__,
            "python": platform.python_version(), "networkx": nx.__version__}


def _key(v):
    return int(v[1:])


def distances(g):
    """{hop distance: number of router pairs at that distance}, each pair counted once, by a breadth-first search
    from every router."""
    counts = {}
    for s in g:
        for d in nx.single_source_shortest_path_length(g, s).values():
            if d:
                counts[d] = counts.get(d, 0) + 1
    return {d: c // 2 for d, c in sorted(counts.items())}


def two_hop_multiplicity(g):
    """The mean number of neighbours shared by two routers that are two hops apart: how many two-hop paths join
    them. Above 1, a router two hops from a sender can be reached through more than one of its neighbours, and a
    two-hop flooding rule such as draft-ietf-lsr-distoptflood's can pick one of them. It is an indicator, not a
    condition: such a rule also drops copies across triangles, where this can be 1. None when no two routers are two
    hops apart (a full mesh, or no links)."""
    total = pairs = 0
    for v in g:
        near = g[v]
        common = {}
        for u in near:
            for w in g[u]:
                if w != v and w not in near:
                    common[w] = common.get(w, 0) + 1
        total += sum(common.values())
        pairs += len(common)
    return round(total / pairs, 4) if pairs else None


def summary(g):
    """Size, degree and distance figures of a topology. The distances (diameter, mean distance, share of router
    pairs at most two hops apart) are left out, as None, when the graph is disconnected or routers x links is over
    DIAMETER_LIMIT; the two-hop multiplicity when the sum of squared degrees is over PATHS_LIMIT."""
    n, m = g.number_of_nodes(), g.number_of_edges()
    deg = [d for _, d in g.degree()]
    connected = n > 0 and nx.is_connected(g)
    dist = distances(g) if connected and n > 1 and n * m <= DIAMETER_LIMIT else None
    pairs = sum(dist.values()) if dist else 0
    return {"routers": n, "links": m,
            "average_degree": round(2 * m / n, 4) if n else 0,
            "density": round(2 * m / (n * (n - 1)), 6) if n > 1 else 0,
            "min_degree": min(deg, default=0), "max_degree": max(deg, default=0),
            "connected": connected,
            "diameter": max(dist) if dist else (0 if connected and n == 1 else None),
            "mean_distance": round(sum(d * c for d, c in dist.items()) / pairs, 4) if pairs else None,
            "pairs_within_2": round((dist.get(1, 0) + dist.get(2, 0)) / pairs, 4) if pairs else None,
            "two_hop_multiplicity": two_hop_multiplicity(g) if sum(d * d for d in deg) <= PATHS_LIMIT else None}


def document(g):
    nodes = sorted(g.nodes, key=_key)
    edges = sorted((tuple(sorted(e, key=_key)) for e in g.edges), key=lambda e: (_key(e[0]), _key(e[1])))
    graph = dict(g.graph, **summary(g), format=FORMAT, builder=builder_info())
    return {"directed": False, "multigraph": False, "graph": graph,
            "nodes": [dict(g.nodes[v], id=v) for v in nodes],
            "edges": [dict(g.edges[u, v], source=u, target=v) for u, v in edges]}


def dumps(g):
    return json.dumps(document(g), sort_keys=True, indent=1, ensure_ascii=False) + "\n"


def write(g, path):
    """Write one topology; return its manifest entry."""
    doc = document(g)
    keys = ("routers", "links", "average_degree", "density", "min_degree", "max_degree", "connected", "diameter",
            "mean_distance", "pairs_within_2", "two_hop_multiplicity")
    data = (json.dumps(doc, sort_keys=True, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
    with open(path, "wb") as fh:
        fh.write(data)
    entry = {"file": os.path.basename(path), "sha256": hashlib.sha256(data).hexdigest(),
             "family": doc["graph"]["family"], "parameters": doc["graph"]["parameters"]}
    entry.update({k: doc["graph"][k] for k in keys})
    return entry


def write_manifest(directory, entries, command):
    doc = {"format": FORMAT, "builder": builder_info(), "command": command, "files": entries}
    with open(os.path.join(directory, "manifest.json"), "wb") as fh:
        fh.write((json.dumps(doc, sort_keys=True, indent=1, ensure_ascii=False) + "\n").encode("utf-8"))


def read(path):
    """A topology file back as a networkx Graph, attributes included."""
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    g = nx.Graph(**d["graph"])
    for v in d["nodes"]:
        attrs = dict(v)
        g.add_node(attrs.pop("id"), **attrs)
    for e in d["edges"]:
        attrs = dict(e)
        g.add_edge(attrs.pop("source"), attrs.pop("target"), **attrs)
    return g
