from pathlib import Path

import pytest

from topology_builders import measure as M

FIX = Path(__file__).resolve().parent / "fixtures"


def summary_on():
    return (FIX / "isis-summary-on.txt").read_text()


def test_parse_summary_reads_pdu_and_flooding_reduction_counters():
    c = M.parse_summary(summary_on())
    assert (c["tx_p2p_iih"], c["tx_l2_lsp"], c["tx_l2_csnp"], c["tx_l2_psnp"], c["tx_lsp_rxmt"]) == (73, 48, 8, 14, 0)
    assert (c["rx_p2p_iih"], c["rx_l2_lsp"], c["rx_l2_csnp"], c["rx_l2_psnp"]) == (70, 35, 8, 15)
    assert (c["fr_reduced_lsps"], c["fr_fallbacks"], c["fr_selected"], c["fr_suppressed_sends"]) == (7, 12, 5, 12)
    assert not any(k.startswith("drop_") for k in c)
    assert not any("regenerated" in k or "purged" in k or "run_count" in k for k in c)


def test_parse_summary_without_flooding_reduction():
    # The same output with the flooding-reduction block removed, as with the feature off.
    lines = summary_on().splitlines()
    i = lines.index("    Flooding reduction:")
    off = "\n".join(lines[:i] + lines[i + 5:])
    c = M.parse_summary(off)
    assert c["tx_l2_lsp"] == 48 and not any(k.startswith("fr_") for k in c)


def test_parse_database_and_stat():
    db = M.parse_database((FIX / "isis-database.txt").read_text())
    assert len(db) == 8 and db["r0.00-00"] == 3 and db["r6.00-00"] == 2
    _, tck, stat = (FIX / "pidof-clk-stat.txt").read_text().splitlines()[:3]
    assert tck == "100" and M.parse_stat(stat) == 6


def test_outcome():
    before = {"r0.00-00": 3, "r1.00-00": 3, "r2.00-00": 3}
    after = {"r0.00-00": 4, "r1.00-00": 4, "r2.00-00": 3}
    assert M.outcome({"r0": after, "r1": dict(after), "r2": dict(after)}, before, ("r0", "r1"))[0] == "satisfied"
    lagging = {"r0": after, "r1": dict(after), "r2": before}
    result, detail = M.outcome(lagging, before, ("r0", "r1"))
    assert result == "violated" and detail["routers_differing"] == ["r2"]
    result, detail = M.outcome({"r0": before, "r1": before}, before, ("r0", "r1"))
    assert result == "violated" and detail["ends_without_new_lsp"] == ["r0", "r1"]
    assert M.outcome({"r0": after, "r1": None}, before, ("r0", "r1"))[0] == "unknown"


def test_steady_and_net():
    before = {"r0.00-00": 3, "r1.00-00": 3}
    assert M.steady({"r0": dict(before), "r1": dict(before)}, before) == ("satisfied", {"routers_changed": []})
    changed = {"r0.00-00": 4, "r1.00-00": 3}
    assert M.steady({"r0": changed, "r1": dict(before)}, before) == ("violated", {"routers_changed": ["r0"]})
    assert M.steady({"r0": None, "r1": before}, before)[0] == "unknown"
    window = {"counters": {"tx_l2_lsp": 40, "tx_p2p_iih": 100}, "cpu_ms": {"isisd": 900.0}, "unreadable": []}
    quiet = {"counters": {"tx_p2p_iih": 98}, "cpu_ms": {"isisd": 850.0}, "unreadable": []}
    assert M.net(window, quiet) == {"counters": {"tx_l2_lsp": 40, "tx_p2p_iih": 2}, "cpu_ms": {"isisd": 50.0}}
    assert M.net(window, dict(quiet, unreadable=["r3"])) is None


def test_pick_link_and_order():
    links = [{"a": f"r{i}", "a_port": "eth1", "b": f"r{i + 1}", "b_port": "eth1"} for i in range(20)]
    lab = {"source_sha256": "ab" * 32, "links": links}
    assert M.pick_link(lab, 1) == M.pick_link(dict(lab), 1) and M.pick_link(lab, 1) in links
    assert len({M.pick_link(lab, s)["a"] for s in range(10)}) > 1
    assert M.order(["off", "on"], 0) == ["off", "on"] and M.order(["off", "on"], 1) == ["on", "off"]


def test_pick_links_and_wait_cool():
    links = [{"a": f"r{i}", "a_port": "eth1", "b": f"r{i + 1}", "b_port": "eth1"} for i in range(20)]
    lab = {"source_sha256": "cd" * 32, "links": links}
    five = M.pick_links(lab, 3, 5)
    assert len(five) == 5 and len({x["a"] for x in five}) == 5 and five[0] == M.pick_link(lab, 3)
    assert M.pick_links(lab, 3, 5) == five and M.pick_links(lab, 3, 20) != links
    with pytest.raises(ValueError):
        M.pick_links(lab, 3, 21)
    temps, slept = iter([85.0, 81.0, 79.5]), []
    assert M.wait_cool(80.0, read=lambda: next(temps), sleep=slept.append, poll=30) == 60 and slept == [30, 30]
    assert M.wait_cool(80.0, read=lambda: None, sleep=slept.append) == 0


def test_totals_and_summarize():
    before = {"r0": {"counters": {"tx_l2_lsp": 10}, "cpu_ms": {"isisd": 50.0}},
              "r1": {"counters": {"tx_l2_lsp": 5}, "cpu_ms": {"isisd": 20.0}}}
    after = {"r0": {"counters": {"tx_l2_lsp": 14, "fr_suppressed_sends": 2}, "cpu_ms": {"isisd": 60.0}},
             "r1": None}
    total, per = M.totals(after, before)
    assert total["counters"] == {"fr_suppressed_sends": 2, "tx_l2_lsp": 4} and total["cpu_ms"] == {"isisd": 10.0}
    assert total["unreadable"] == ["r1"] and per["r1"] is None
    rec = {"lab": "x-on", "settings": {"flood_reduction": True},
           "phases": [{"phase": "link-down", "outcome": "satisfied", **total,
                       "net_of_quiet": {"counters": {}, "cpu_ms": {"isisd": 3.0}}}]}
    rows = M.summarize([rec, rec])
    assert rows == [{"lab": "x-on", "flood_reduction": True, "phase": "link-down", "runs": 2, "lsps_sent": 4.0,
                     "suppressed_sends": 2.0, "isisd_ms": 10.0, "isisd_net_ms": 3.0, "outcomes": {"satisfied": 2}}]
