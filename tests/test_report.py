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
