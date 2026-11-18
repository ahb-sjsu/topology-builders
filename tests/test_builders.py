import hashlib
import json
import subprocess
import sys
from pathlib import Path

import networkx as nx
import pytest

from topology_builders import families as F
from topology_builders import output as O
from topology_builders import sweep as S
from topology_builders import zoo as Z

ROOT = Path(__file__).resolve().parents[1]


def degrees(g):
    return {d for _, d in g.degree()}


def test_random_regular_sparse_and_dense():
    for n, d in [(16, 3), (16, 7), (16, 8), (16, 12), (16, 15), (64, 31), (64, 32), (64, 63)]:
        g = F.random_regular(n, d, seed=1)
        assert g.number_of_nodes() == n and degrees(g) == {d} and nx.is_connected(g), (n, d)
        assert O.dumps(g) == O.dumps(F.random_regular(n, d, seed=1)), (n, d)
    assert O.dumps(F.random_regular(64, 8, 1)) != O.dumps(F.random_regular(64, 8, 2))


def test_random_regular_rejects():
    for n, d in [(15, 3), (16, 2), (16, 16)]:
        with pytest.raises(ValueError):
            F.random_regular(n, d)


def test_leaf_spine():
    g = F.leaf_spine(12, 4)
    spines = [v for v in g if g.nodes[v]["role"] == "spine"]
    assert g.number_of_edges() == 48 and nx.is_bipartite(g)
    assert len(spines) == 4 and all(g.degree(v) == 12 for v in spines)
    assert all(g.degree(v) == 4 for v in g if g.nodes[v]["role"] == "leaf")


def test_flattened_butterfly_equals_networkx_products():
    assert nx.is_isomorphic(F.flattened_butterfly([7]), nx.complete_graph(7))
    assert nx.is_isomorphic(F.flattened_butterfly([2] * 4), nx.hypercube_graph(4))
    assert nx.is_isomorphic(F.flattened_butterfly([4, 3]),
                            nx.cartesian_product(nx.complete_graph(4), nx.complete_graph(3)))
    g = F.flattened_butterfly([4, 4, 2])
    assert g.number_of_nodes() == 32 and degrees(g) == {7} and nx.diameter(g) == 3


def test_kary_nfly_one_forward_path_between_ends():
    for k, n in [(2, 3), (3, 3), (2, 4), (4, 2)]:
        g = F.kary_nfly(k, n)
        assert g.number_of_nodes() == n * k ** (n - 1)
        assert g.number_of_edges() == (n - 1) * k ** n
        stage = nx.get_node_attributes(g, "stage")
        dag = nx.DiGraph([(u, v) if stage[u] < stage[v] else (v, u) for u, v in g.edges])
        first = [v for v in g if stage[v] == 0]
        last = [v for v in g if stage[v] == n - 1]
        assert all(len(list(nx.all_simple_paths(dag, a, b))) == 1 for a in first for b in last), (k, n)


def test_factorizations_and_steps():
    assert S.factorizations(12) == [(12,), (6, 2), (4, 3), (3, 2, 2)]
    assert S.factorizations(13) == [(13,)]
    assert S.degree_steps(3, 63) == [3, 4, 6, 8, 12, 16, 24, 32, 48, 63]


def topohub_fixture(tmp_path):
    """Six nodes on the equator, one degree of longitude apart, in a path; a duplicate link and a self-loop; and a
    separate pair of nodes that must be dropped."""
    nodes = [{"id": str(i), "name": "ABCDEF"[i], "pos": [float(i), 0.0]} for i in range(6)]
    nodes += [{"id": "6", "name": "G", "pos": [50.0, 50.0]}, {"id": "7", "name": "H", "pos": [51.0, 50.0]}]
    edges = [{"source": str(i), "target": str(i + 1), "dist": 111.19} for i in range(5)]
    edges += [{"source": "1", "target": "0"}, {"source": "2", "target": "2"}, {"source": "6", "target": "7"}]
    path = tmp_path / "Line.json"
    path.write_text(json.dumps({"directed": False, "multigraph": False, "graph": {"name": "line"},
                                "nodes": nodes, "edges": edges}))
    return path


def test_zoo_nearest(tmp_path):
    g = Z.denser(topohub_fixture(tmp_path), 3, "nearest")
    assert g.number_of_nodes() == 6 and g.number_of_edges() == 9
    assert g.graph["parameters"]["dropped_nodes"] == 2 and g.nodes["r0"]["name"] == "A"
    added = sorted((u, v) for u, v, a in g.edges(data=True) if a["added"])
    assert added == [("r0", "r2"), ("r1", "r3"), ("r2", "r4"), ("r3", "r5")]


def test_zoo_random_keeps_originals_and_nests(tmp_path):
    path = topohub_fixture(tmp_path)
    g3, g4 = Z.denser(path, 3, "random", 1), Z.denser(path, 4, "random", 1)
    assert g3.number_of_edges() == 9 and g4.number_of_edges() == 12
    original = {frozenset((u, v)) for u, v, a in g3.edges(data=True) if not a["added"]}
    assert len(original) == 5
    assert {frozenset(e) for e in g3.edges} <= {frozenset(e) for e in g4.edges}
    assert O.dumps(g3) == O.dumps(Z.denser(path, 3, "random", 1))
    with pytest.raises(ValueError):
        Z.denser(path, 1, "random")


def test_file_round_trip_and_networkx_reader(tmp_path):
    g = F.flattened_butterfly([3, 3])
    O.write(g, tmp_path / "g.json")
    back = O.read(tmp_path / "g.json")
    assert {frozenset(e) for e in back.edges} == {frozenset(e) for e in g.edges}
    data = json.loads((tmp_path / "g.json").read_text())
    assert nx.is_isomorphic(nx.node_link_graph(data, edges="edges"), g)


def test_sweep_command(tmp_path):
    out = tmp_path / "out"
    subprocess.run([sys.executable, "-m", "topology_builders", "sweep", "--routers", "16", "--seeds", "1,2",
                    "--out", str(out)], check=True, cwd=ROOT, capture_output=True)
    files = json.loads((out / "manifest.json").read_text())["files"]
    assert {e["family"] for e in files} == set(S.FAMILIES)
    for e in files:
        data = (out / e["file"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == e["sha256"]
        g = O.read(out / e["file"])
        assert g.number_of_nodes() == 16 and nx.is_connected(g)
    densest = {"random-regular": 15, "flattened-butterfly": 15, "leaf-spine": 8}  # 8 leaves x 8 spines
    for fam in S.FAMILIES:
        avg = [e["average_degree"] for e in files if e["family"] == fam]
        assert avg == sorted(avg) and avg[-1] == densest[fam], fam
