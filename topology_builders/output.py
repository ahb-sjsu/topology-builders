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
DIAMETER_LIMIT = 20_000_000  # routers x links above which the diameter is not computed


def builder_info():
    return {"package": "topology-builders", "version": __version__,
            "python": platform.python_version(), "networkx": nx.__version__}


def _key(v):
    return int(v[1:])


def summary(g):
    n, m = g.number_of_nodes(), g.number_of_edges()
    deg = [d for _, d in g.degree()]
    connected = n > 0 and nx.is_connected(g)
    return {"routers": n, "links": m,
            "average_degree": round(2 * m / n, 4) if n else 0,
            "density": round(2 * m / (n * (n - 1)), 6) if n > 1 else 0,
            "min_degree": min(deg, default=0), "max_degree": max(deg, default=0),
            "connected": connected,
            "diameter": nx.diameter(g) if connected and n * m <= DIAMETER_LIMIT else None}


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
    data = (json.dumps(doc, sort_keys=True, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
    with open(path, "wb") as fh:
        fh.write(data)
    entry = {"file": os.path.basename(path), "sha256": hashlib.sha256(data).hexdigest(),
             "family": doc["graph"]["family"], "parameters": doc["graph"]["parameters"]}
    entry.update(summary(g))
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
