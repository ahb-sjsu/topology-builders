import ipaddress
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from topology_builders import clab as C
from topology_builders import families as F
from topology_builders import output as O

ROOT = Path(__file__).resolve().parents[1]


def topology(tmp_path, g, name="t.json"):
    path = tmp_path / name
    O.write(g, path)
    return path


def test_plan_ports_addresses_and_nets():
    g = F.flattened_butterfly([4, 2])
    routers, links = C.plan(g)
    assert len(routers) == 8 and len(links) == g.number_of_edges() == 16
    for r in routers:
        assert r["ports"] == g.degree(r["name"])
        mine = sorted(int(p[3:]) for x in links for end, p in (("a", x["a_port"]), ("b", x["b_port"]))
                      if x[end] == r["name"])
        assert mine == list(range(1, r["ports"] + 1))
    for x in links:
        a, b = ipaddress.ip_interface(x["a_address"]), ipaddress.ip_interface(x["b_address"])
        assert a.network == b.network and a.network.prefixlen == 31 and a.ip != b.ip
    assert len({r["loopback"] for r in routers}) == len({r["net"] for r in routers}) == 8
    assert routers[0]["net"] == "49.0001.0000.0000.0001.00" and routers[0]["loopback"] == "10.255.0.1/32"


def test_on_and_off_differ_only_by_the_flood_reduction_line(tmp_path):
    src = topology(tmp_path, F.random_regular(16, 4, 1))
    C.write_lab(src, tmp_path / "off", name="x", flood_reduction=False)
    C.write_lab(src, tmp_path / "on", name="x", flood_reduction=True)
    for i in range(16):
        off = (tmp_path / "off" / f"r{i}" / "frr.conf").read_text().splitlines()
        on = (tmp_path / "on" / f"r{i}" / "frr.conf").read_text().splitlines()
        assert "flood-reduction" not in "\n".join(off)
        assert [x for x in on if x != " flood-reduction"] == off and on.count(" flood-reduction") == 1
        assert on.index(" flood-reduction") > on.index("router isis 1")


def test_topology_file_matches_the_plan(tmp_path):
    g = F.leaf_spine(6, 3)
    src = topology(tmp_path, g)
    for kind in ("linux", "frr"):
        m = C.write_lab(src, tmp_path / kind, name="ls", kind=kind)
        topo = yaml.safe_load((tmp_path / kind / "ls.clab.yml").read_text())
        assert topo["name"] == "ls" and set(topo["topology"]["kinds"]) == {kind}
        nodes = topo["topology"]["nodes"]
        assert sorted(nodes, key=lambda n: int(n[1:])) == [f"r{i}" for i in range(9)]
        ends = [tuple(x["endpoints"]) for x in topo["topology"]["links"]]
        assert len(ends) == len(set(ends)) == 18
        lab = json.loads((tmp_path / kind / "lab.json").read_text())
        assert ends == [(f"{x['a']}:{x['a_port']}", f"{x['b']}:{x['b_port']}") for x in lab["links"]]
        if kind == "linux":
            assert all(len(n["binds"]) == 3 for n in nodes.values())
            assert "isisd=yes" in (tmp_path / kind / "r0" / "daemons").read_text()
        else:
            assert topo["topology"]["kinds"]["frr"]["daemons"] == ["isisd"]
            assert all(n["startup-config"].endswith("/frr.conf") for n in nodes.values())
        for f in m["files"]:
            assert (tmp_path / kind / f["file"]).exists()


def test_interfaces_in_frr_conf_match_links(tmp_path):
    src = topology(tmp_path, F.flattened_butterfly([3, 3]))
    C.write_lab(src, tmp_path / "lab", name="fb")
    lab = json.loads((tmp_path / "lab" / "lab.json").read_text())
    for x in lab["links"]:
        for end in ("a", "b"):
            conf = (tmp_path / "lab" / x[end] / "frr.conf").read_text()
            assert f"interface {x[end + '_port']}\n ip address {x[end + '_address']}\n" in conf


def test_deterministic_and_foreign_ids(tmp_path):
    src = topology(tmp_path, F.random_regular(12, 3, 2))
    a = C.write_lab(src, tmp_path / "a", name="d")
    b = C.write_lab(src, tmp_path / "b", name="d")
    assert a["files"] == b["files"]
    hub = tmp_path / "Hub.json"
    hub.write_text(json.dumps({"directed": False, "multigraph": False, "graph": {"name": "hub"},
                               "nodes": [{"id": str(i)} for i in range(11)],
                               "edges": [{"source": str(i), "target": str(i + 1)} for i in range(10)]}))
    routers, links = C.plan(O.read(hub))
    assert [r["name"] for r in routers] == [f"r{i}" for i in range(11)]
    assert routers[10]["original_id"] == "10" and (links[9]["a"], links[9]["b"]) == ("r9", "r10")


def test_command_writes_both_labs(tmp_path):
    src = topology(tmp_path, F.leaf_spine(4, 2), "Leaf Spine.json")
    subprocess.run([sys.executable, "-m", "topology_builders", "clab", str(src), "--out", str(tmp_path / "out")],
                   check=True, cwd=ROOT, capture_output=True)
    for tag in ("off", "on"):
        m = json.loads((tmp_path / "out" / tag / "manifest.json").read_text())
        assert m["name"] == f"leaf-spine-{tag}" and m["settings"]["flood_reduction"] == (tag == "on")
        assert (tmp_path / "out" / tag / f"leaf-spine-{tag}.clab.yml").exists()


def test_rejects_unknown_kind(tmp_path):
    with pytest.raises(ValueError):
        C.write_lab(topology(tmp_path, F.leaf_spine(2, 2)), tmp_path / "x", kind="docker")
