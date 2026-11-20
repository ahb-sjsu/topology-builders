"""The flooding model against draft-ietf-lsr-distoptflood-14: the reference checksums of its Figure 2, and decisions
worked out by hand from section 1.2.3 on small graphs (routers a, b, c, d with system IDs 1-4)."""
from topology_builders import flood_model as M

IDS = {"a": 1, "b": 2, "c": 3, "d": 4}


def topo(*edges):
    adj = {v: set() for v in IDS}
    for u, v in edges:
        adj[u].add(v)
        adj[v].add(u)
    return M.Topology(adj, IDS)


def test_lsp_hash_matches_figure_2():
    cases = [(0x010203040506, 0x00, 0x6215, [1, 2, 1, 4, 5]), (0x010203040506, 0x07, 0x6215, [1, 2, 1, 4, 5]),
             (0x010203040506, 0x0F, 0x6316, [0, 1, 2, 1, 4]), (0x000102030405, 0x01, 0x410F, [1, 2, 3, 0, 5])]
    for sysid, fragment, h, mods in cases:
        assert M.lsp_hash(sysid, 0, fragment) == h
        assert [h % n for n in range(2, 7)] == mods


def test_system_ids_from_a_lab():
    from topology_builders import clab as C
    from topology_builders import families as F

    assert M.system_id("49.0001.0000.0000.0001.00") == 1
    assert M.system_id("49.0000.0000.0001.0a00.00") == 0x00000001_0A00
    t = M.Topology.from_lab(*C.plan(F.random_regular(16, 4, 1)))
    assert sorted(t.sysid.values()) == list(range(1, 17))  # distinct: the RNL order and the hash depend on them
    assert all(len(n) == 4 for n in t.adj.values())


def test_square_decisions():
    # a-b-c-d-a, LSP of a. Both b and d have THL {c} and RNL [b, d]; H(a) = 0x0301, so N = 1 and the walk starts
    # at d: d is selected and refloods to c, b is not.
    g = topo(("a", "b"), ("b", "c"), ("c", "d"), ("d", "a"))
    assert M.lsp_hash(1) == 0x0301
    b = M.decide(g, "b", "a", "a", g.adj["b"])
    d = M.decide(g, "d", "a", "a", g.adj["d"])
    assert (b.send, b.selected, b.thl, b.rnl, b.start, b.suppressed) == (frozenset(), False, 1, 2, 1, 1)
    assert (d.send, d.selected, d.thl, d.rnl, d.start, d.suppressed) == (frozenset("c"), True, 1, 2, 1, 0)
    # c, receiving from d: its only two-hop router, b, is a neighbor of the originator (Step 1C(ii)).
    c = M.decide(g, "c", "d", "a", g.adj["c"])
    assert (c.send, c.thl, c.selected) == (frozenset(), 0, False)
    assert M.flood(g.adj, g, ["a"], True)["sent"] == 3
    assert M.flood(g.adj, g, ["a"], False)["sent"] == 4  # c gets it from b and d at once and sends to neither


def test_full_mesh_and_path():
    k4 = topo(*[(u, v) for u in IDS for v in IDS if u < v])
    assert M.decide(k4, "b", "a", "a", k4.adj["b"]).thl == 0
    assert M.flood(k4.adj, k4, ["a"], True)["sent"] == 3
    assert M.flood(k4.adj, k4, ["a"], False)["sent"] == 9
    path = topo(("a", "b"), ("b", "c"), ("c", "d"))
    for reduction in (False, True):
        r = M.flood(path.adj, path, ["a"], reduction)
        assert r["sent"] == 3 and r["reached"]["a"] == set(IDS)


def test_link_changes_and_unknown_neighbors():
    g = topo(("a", "b"), ("b", "c"), ("c", "d"), ("d", "a"))
    for reduction in (False, True):  # without a-b the square is a path: three sends per LSP either way
        assert M.flood_link_change(g, ("a", "b"), "down", reduction)["sent"] == 6
    snap = g.without([("a", "b")])
    # Link coming up: b has the adjacency, the snapshot does not show it, so b floods normally.
    dec = M.decide(snap, "b", "a", "a", g.adj["b"])
    assert not dec.applied and dec.send == frozenset("c")
    # A neighbor missing from the snapshot gets the LSP with unknown="flood", not with "skip": a, receiving c's LSP
    # from d, has an empty THL (its two-hop router b neighbors the originator) but an adjacency to b that the
    # snapshot lacks.
    assert M.decide(snap, "a", "d", "c", {"d", "b"}).send == frozenset("b")
    assert M.decide(snap, "a", "d", "c", {"d", "b"}, unknown="skip").send == frozenset()
    up = M.flood_link_change(g, ("a", "b"), "up", True)
    assert up["reached"] == {"a": set(IDS), "b": set(IDS)}
