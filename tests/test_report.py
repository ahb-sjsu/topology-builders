import gzip
import json
import subprocess
import sys
from pathlib import Path

from topology_builders import report as R

ROOT = Path(__file__).resolve().parents[1]


def record(on, repeat, down, up, bring_up=(1000, 500.0), sha="aa", topology=None):
    """A measure record with one link: (LSPs sent, isisd ms net of quiet) for its down and up windows."""
    def window(phase, lsps, net):
        return {"phase": phase, "link": 0, "counters": {"tx_l2_lsp": lsps}, "cpu_ms": {"isisd": net + 100.0},
                "net_of_quiet": {"counters": {}, "cpu_ms": {"isisd": net}}, "outcome": "satisfied"}
    return {"source_sha256": sha, "repeat": repeat, "converged": True, "settings": {"flood_reduction": on},
            "topology": topology or {"family": "random-regular", "parameters": {"routers": 8, "degree": 3, "seed": 1},
                                     "routers": 8, "links": 12, "average_degree": 3.0},
            "phases": [{"phase": "bring-up", "counters": {"tx_l2_lsp": bring_up[0]}, "cpu_ms": {"isisd": bring_up[1]},
                        "outcome": "satisfied"},
                       {"phase": "quiet", "counters": {}, "cpu_ms": {"isisd": 100.0}, "outcome": "satisfied"},
                       window("link-down", *down), window("link-up", *up)]}


def test_rows_pool_pair_and_save():
    recs = [record(False, 0, (40, 200.0), (60, 400.0), (1000, 500.0)),
            record(True, 0, (10, 150.0), (20, 450.0), (800, 400.0)),
            record(True, 1, (12, 170.0), (22, 410.0), (820, 420.0)),
            record(False, 1, (44, 220.0), (64, 380.0), (1020, 520.0))]
    (row,) = R.rows(recs)
    assert row["topology"] == "random regular, degree 3, seed 1" and row["runs"] == {"off": 2, "on": 2}
    off, on = row["windows"]["off"], row["windows"]["on"]
    assert off["lsps"] == {"mean": 52, "min": 40, "max": 64} and on["lsps"]["mean"] == 16
    assert off["satisfied"] == off["windows"] == 4 and row["lsp_saving"] == 1 - 16 / 52
    assert off["net_ms"]["mean"] == 300.0 and on["net_ms"]["mean"] == 295.0
    # Down: 210 off against 160 on (lower); up: 390 off against 430 on (higher).
    assert row["pairs"]["n"] == 2 and row["pairs"]["lsps_lower_on"] == 2 and row["pairs"]["net_lower_on"] == 1
    assert abs(row["pairs"]["median_net_saving"] - ((1 - 160 / 210) + (1 - 430 / 390)) / 2) < 1e-12
    assert row["bring_up"]["off"]["lsps"]["mean"] == 1010 and row["bring_up"]["on"]["converged"] == 2
    assert (row["bring_up"]["off"]["quiet_satisfied"], row["bring_up"]["off"]["quiet"]) == (2, 2)
    assert abs(row["bring_up_ms_saving"] - (1 - 410 / 510)) < 1e-12


def test_rows_sorted_by_family_then_degree_and_labelled():
    ls = {"family": "leaf-spine", "parameters": {"routers": 6, "leaves": 4, "spines": 2}, "routers": 6, "links": 8,
          "average_degree": 2.67}
    fb = {"family": "flattened-butterfly", "parameters": {"routers": 8, "radices": [4, 2]}, "routers": 8,
          "links": 16, "average_degree": 4.0}
    rr = {"family": "random-regular", "parameters": {"routers": 8, "degree": 6, "seed": 1}, "routers": 8,
          "links": 24, "average_degree": 6.0}
    recs = [record(on, 0, (5, 1.0), (5, 1.0), sha=s, topology=t)
            for s, t in (("rr6", rr), ("ls", ls), ("fb", fb), ("rr3", None)) for on in (False, True)]
    table = R.rows(recs)
    assert [r["topology"] for r in table] == ["flattened butterfly 4 x 2", "leaf-spine, 4 leaves x 2 spines",
                                              "random regular, degree 3, seed 1", "random regular, degree 6, seed 1"]
    text = R.text(table)
    assert "flattened butterfly 4 x 2" in text and text.count("\n") == 2 * len(table) + 5


def test_read_and_command(tmp_path):
    recs = [record(False, 0, (40, 200.0), (60, 400.0)), record(True, 0, (10, 150.0), (20, 450.0))]
    plain, packed = tmp_path / "a.jsonl", tmp_path / "b.jsonl.gz"
    plain.write_text(json.dumps(recs[0]) + "\n")
    with gzip.open(packed, "wt", encoding="utf-8") as fh:
        fh.write(json.dumps(recs[1]) + "\n")
    assert R.read([plain, packed]) == recs
    out = subprocess.run([sys.executable, "-m", "topology_builders", "report", str(plain), str(packed), "--json"],
                         check=True, cwd=ROOT, capture_output=True, text=True).stdout
    assert json.loads(out)[0]["lsp_saving"] == 1 - 30 / 100


def test_other_event_kinds_and_pooled_seeds():
    def rr(seed):
        return {"family": "random-regular", "parameters": {"routers": 8, "degree": 3, "seed": seed}, "routers": 8,
                "links": 12, "average_degree": 3.0}

    def node_record(on, sha, seed, lsps):
        r = record(on, 0, (lsps, 100.0), (lsps, 100.0), sha=sha, topology=rr(seed))
        for p in r["phases"]:
            if p["phase"].startswith("link-"):
                p["phase"], p["event"] = p["phase"].replace("link", "node"), p.pop("link")
        return r
    recs = [node_record(False, "s1", 1, 40), node_record(True, "s1", 1, 10),
            node_record(False, "s2", 2, 50), node_record(True, "s2", 2, 25)]
    assert R.rows(recs)[0]["windows"]["off"]["windows"] == 0
    table = R.rows(recs, "node")
    assert [r["lsp_saving"] for r in table] == [0.75, 0.5] and table[0]["pairs"]["n"] == 2
    (pool,) = R.pooled(table)
    assert pool["topology"] == "random regular, degree 3" and pool["graphs"] == 2 and pool["runs"] == {"off": 2, "on": 2}
    assert pool["lsp_saving"] == 0.625 and pool["lsp_saving_range"] == [0.5, 0.75] and pool["pairs"]["n"] == 4
    assert "Node changes" in R.text([pool], "node")


def test_graphs_of_different_sizes_stay_apart():
    def rr(routers, seed):
        return {"family": "random-regular", "parameters": {"routers": routers, "degree": 3, "seed": seed},
                "routers": routers, "links": routers * 3 // 2, "average_degree": 3.0}
    recs = []
    for sha, routers, seed in (("a", 8, 1), ("b", 16, 1), ("c", 16, 2)):
        for on in (False, True):
            r = record(on, 0, (40, 200.0), (60, 400.0), sha=sha, topology=rr(routers, seed))
            r["profile"] = True
            for p in r["phases"][2:]:
                p["net_of_quiet"]["event_cpu_ms"] = {"isis_receive": 30.0 if not on else 10.0}
            recs.append(r)
    table = R.rows(recs)
    assert sorted(r["topology"] for r in table) == ["random regular, degree 3, seed 1, 16 routers",
                                                    "random regular, degree 3, seed 1, 8 routers",
                                                    "random regular, degree 3, seed 2, 16 routers"]
    pools = {p["topology"]: p["graphs"] for p in R.pooled(table)}
    assert pools == {"random regular, degree 3, 8 routers": 1, "random regular, degree 3, 16 routers": 2}
    prof = R.profile_text(recs)
    assert prof.count("isis_receive") == 3 and "seed 1, 8 routers (2 and 2 windows)" in prof
    # one size only: names as before
    assert R.rows(recs[:2])[0]["topology"] == "random regular, degree 3, seed 1"


def test_timing_and_profile_text():
    recs = []
    for on in (False, True):
        r = record(on, 0, (40, 200.0), (60, 400.0))
        r["timing"] = True
        for p, ms in zip(r["phases"][2:], (120.0 if not on else 80.0, None)):
            p["timing"] = {"max_ms": ms, "flood_ms": None if ms is None else ms / 4}
        recs.append(r)
        q = record(on, 0, (40, 200.0), (60, 400.0))
        q["profile"] = True
        for p in q["phases"][2:]:
            p["net_of_quiet"]["event_cpu_ms"] = {"isis_receive": 30.0 if not on else 10.0, "lsp_tick": 5.0}
        recs.append(q)
    assert len(R.rows(recs)) == 1 and R.rows(recs)[0]["runs"] == {"off": 1, "on": 1}
    t = R.timing_text(recs)
    assert "120.0" in t and "80.0" in t and "30.0" in t and "20.0" in t and t.rstrip().endswith("1    1")
    prof = R.profile_text(recs)
    assert prof.index("isis_receive") < prof.index("lsp_tick") and "30.0" in prof and "10.0" in prof
    assert R.timing_text([record(False, 0, (1, 1.0), (1, 1.0))]) == ""


def test_zoo_graphs_get_a_readable_label():
    own = {"family": "zoo", "parameters": {"name": "TataNld", "added_links": 0, "average_degree": 2.527972,
                                           "method": "nearest", "routers": 143}}
    assert R.label(own) == "TataNld (Topology Zoo), as it is"
    denser = {"family": "zoo", "parameters": {"name": "TataNld", "added_links": 105, "average_degree": 4,
                                              "method": "nearest"}}
    assert R.label(denser) == "TataNld (Topology Zoo), 105 links added (nearest), average degree 4"
    rnd = {"family": "zoo", "parameters": {"name": "Uunet", "added_links": 91, "average_degree": 8.0,
                                           "method": "random", "seed": 3}}
    assert R.label(rnd) == "Uunet (Topology Zoo), 91 links added (random), average degree 8, seed 3"
    assert R.label(rnd, seed=False) == "Uunet (Topology Zoo), 91 links added (random), average degree 8"


def test_windows_without_net_cpu_are_left_out_of_cpu_but_not_of_lsps():
    recs = [record(False, 0, (40, 200.0), (60, 400.0)), record(True, 0, (10, 150.0), (20, 450.0))]
    for p in recs[1]["phases"]:
        if p["phase"] == "link-up":
            p["net_of_quiet"] = {"event_cpu_ms": {"isis_receive": 1.0}}  # as records written before 2026-11-23
    (row,) = R.rows(recs)
    assert row["windows"]["on"]["lsps"]["mean"] == 15 and row["windows"]["on"]["net_ms"]["mean"] == 150.0
    assert row["pairs"]["n"] == 1  # the link-up pair has no CPU on one side
