import calendar
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


def event_cpu_text():
    fmt = "%5d %10d.%03d %9d %8d %9d %8d %9d %9d %9d %10d  %s  %s"
    head = ("Active   Runtime(ms)   Invoked Avg uSec Max uSecs Avg uSec Max uSecs"
            "  CPU_Warn Wall_Warn Starv_Warn   Type  Event")
    rows = [fmt % (0, 12, 345, 10, 1234, 2000, 1300, 2100, 0, 0, 0, "R    ", "isis_receive"),
            fmt % (1, 0, 500, 2, 250, 300, 260, 310, 0, 0, 0, "  T  ", "lsp_tick")]
    other = [fmt % (0, 1, 0, 1, 1000, 1000, 1000, 1000, 0, 0, 0, "R    ", "isis_receive")]
    total = [fmt % (1, 13, 845, 13, 1065, 2000, 1100, 2100, 0, 0, 0, "RWT  ", "TOTAL")]
    return "\n".join(["Showing statistics for pthread default", head, *rows, "",
                      "Showing statistics for pthread Zebra API", head, *other, "",
                      "Total Event statistics", head, *total])


def test_parse_event_cpu_sums_pthreads_and_skips_the_total():
    assert M.parse_event_cpu(event_cpu_text()) == {"isis_receive": [13.345, 11], "lsp_tick": [0.5, 2]}


def test_log_lines_and_convergence():
    t0 = calendar.timegm((2026, 11, 19, 18, 0, 0))

    def at(us, what):
        return f"2026/11/19 18:00:00.{us:06d} ISIS: [AB12C-DE34F] ISIS-Upd (1): {what}"
    r0, r1 = "0000.0000.0001.00-00", "0000.0000.0002.00-00"
    logs = {
        "r0": at(100000, f"Building L2 LSP {r0}, len 100, seq 0x00000005, cksum 0x1234, lifetime 1199s refresh 900s")
        + "\n" + at(120000, f"Rcvd L2 LSP {r1}, seq 0x00000004, cksum 0x1, lifetime 1199s, len 90, on eth1")
        + "\n" + at(180000, f"Rcvd L2 LSP {r1}, seq 0x00000006, cksum 0x2, lifetime 1199s, len 90, on eth1"),
        "r1": at(110000, f"Refreshed our L2 LSP {r1}, len 90, seq 0x00000006, cksum 0x2, lifetime 1199s refresh 900s")
        + "\n" + at(150000, f"Rcvd L2 LSP {r0}, seq 0x00000005, cksum 0x1234, lifetime 1199s, len 100, on eth2"),
        "r2": at(200000, f"Rcvd L2 LSP {r0}, seq 0x00000005, cksum 0x1234, lifetime 1199s, len 100, on eth1")
        + "\nsomething else\n" + at(300000, f"Rcvd L2 LSP {r1}, seq 0x00000007, cksum 0x3, lifetime 1199s, len 90, on eth3"),
    }
    parsed = {r: M.parse_log_lsps(t) for r, t in logs.items()}
    assert parsed["r0"][0] == (t0 + 0.1, "Building", r0, 5) and len(parsed["r2"]) == 2
    c = M.convergence(parsed, {r0: 5, r1: 6}, t0 + 0.05)
    assert c["per_router_ms"] == {"r0": 130.0, "r1": 100.0, "r2": 250.0}
    assert (c["max_ms"], c["median_ms"], c["missing"]) == (250.0, 130.0, [])
    # r0's LSP built at .100, last held at .200 (r2); r1's built at .110, last held at .300 (r2): 190 ms.
    assert c["flood_ms"] == 190.0
    c = M.convergence(dict(parsed, r3=None, r4=[]), {r0: 5, r1: 6}, t0 + 0.05)
    assert c["max_ms"] is None and c["missing"] == ["r3", "r4"] and c["median_ms"] == 130.0 and c["flood_ms"] is None


def test_logged_ids():
    lab = {"routers": [{"name": "r0", "net": "49.0001.0000.0000.0001.00"},
                       {"name": "r10", "net": "49.0001.0000.0000.000b.00"}]}
    assert M.logged_ids(lab, ["r0.00-00", "r10.00-01", "x.00-00"]) == {"r0.00-00": "0000.0000.0001.00-00",
                                                                        "r10.00-01": "0000.0000.000b.00-01"}


def lab_of(g):
    from topology_builders import clab as C
    routers, links = C.plan(g)
    return {"source_sha256": "ef" * 32, "routers": routers, "links": links}


def test_pick_events_node_and_multi():
    import networkx as nx

    from topology_builders import families as F
    lab = lab_of(F.leaf_spine(14, 2))
    nodes = M.pick_events(lab, 1, "node", 3)
    assert len({e["router"] for e in nodes}) == 3 and nodes == M.pick_events(lab, 1, "node", 3)
    for e in nodes:
        assert e["links"] and all(e["router"] in (x["a"], x["b"]) for x in e["links"])
        ends, failed = M.event_ends(e)
        assert failed == [e["router"]] and e["router"] not in ends and len(ends) == len(e["links"])
    multi = M.pick_events(lab, 1, "multi", 4, fail=3)
    assert multi == M.pick_events(lab, 1, "multi", 4, fail=3) and len(multi) == 4
    g = nx.Graph((x["a"], x["b"]) for x in lab["links"])
    for e in multi:
        assert len({(x["a"], x["b"]) for x in e["links"]}) == 3
        h = g.copy()
        h.remove_edges_from((x["a"], x["b"]) for x in e["links"])
        assert nx.is_connected(h) and M.event_ends(e)[1] == []
    assert [e["links"] for e in M.pick_events(lab, 2, "link", 3)] == [[x] for x in M.pick_links(lab, 2, 3)]
    with pytest.raises(ValueError):
        M.pick_events(lab, 1, "multi", 1, fail=1)
    with pytest.raises(ValueError):
        M.pick_events(lab, 1, "storm", 1)


def test_outcome_leaves_out_the_failed_router():
    before = {"r0.00-00": 3, "r1.00-00": 3, "r2.00-00": 3}
    after = {"r0.00-00": 3, "r1.00-00": 4, "r2.00-00": 4}
    dbs = {"r0": dict(before), "r1": dict(after), "r2": dict(after)}
    assert M.outcome(dbs, before, ("r1", "r2"), exclude=("r0",))[0] == "satisfied"
    assert M.outcome(dbs, before, ("r1", "r2"))[0] == "violated"


def test_apply_sets_the_ports_of_each_router_at_once():
    lab = object.__new__(M.Lab)
    calls = []

    class Pool:
        def map(self, fn, items):
            return [fn(i) for i in items]

    def fake_exec(router, script):
        calls.append((router, script))
        return 0, f"{len(calls)}.5\n"
    lab.pool, lab.exec = Pool(), fake_exec
    links = [{"a": "r0", "a_port": "eth1", "b": "r1", "b_port": "eth3"},
             {"a": "r2", "a_port": "eth2", "b": "r0", "b_port": "eth4"}]
    assert lab.apply({"kind": "node", "router": "r0", "links": links}, "down") == 1.5
    assert calls == [("r0", "ip link set eth1 down; ip link set eth4 down; date +%s.%N")]
    calls.clear()
    lab.apply({"kind": "multi", "links": links}, "up")
    assert sorted(calls) == [("r0", "ip link set eth1 up; date +%s.%N"), ("r2", "ip link set eth2 up; date +%s.%N")]


def test_netns_backend_commands_and_configs(tmp_path):
    from topology_builders import clab as C
    from topology_builders import families as F
    from topology_builders import output as O

    src = tmp_path / "t.json"
    O.write(F.leaf_spine(2, 1), str(src))
    C.write_lab(str(src), str(tmp_path / "lab"), name="x", timing_logs=True)
    lab = M.NetnsLab(str(tmp_path / "lab"), etc_base=str(tmp_path / "etc"), run_base=str(tmp_path / "run"),
                     frr_lib="/frr")
    cmds = lab.commands_deploy()
    r0 = lab.routers[0]
    assert cmds[:2] == [["ip", "netns", "add", r0],
                        ["nsenter", f"--net=/run/netns/{r0}", "--", "ip", "link", "set", "lo", "up"]]
    assert not any(c[:2] == ["ip", "-n"] or c[:3] == ["ip", "netns", "exec"] for c in cmds)  # both remount /sys
    veths = [c for c in cmds if c[:3] == ["ip", "link", "add"]]
    assert len(veths) == len(lab.lab["links"]) == 2
    x = lab.lab["links"][0]
    assert lab.enter(x["a"]) + ["ip", "link", "set", "tbv0a", "name", x["a_port"], "up"] in cmds
    starts = [c for c in cmds if c[0] == "nsenter" and c[3].startswith("/frr/")]
    assert [c[3] for c in starts] == [f"/frr/{d}" for d in lab.DAEMONS for _ in lab.routers]
    zebra = next(c for c in starts if c[3] == "/frr/zebra")
    assert zebra[4:6] == ["-N", zebra[1].rsplit("/", 1)[1]] and zebra[-2:] == ["-s", "90000000"]
    assert all(c[c.index("-z") + 1] == f"{lab.run_dir(c[5])}/zserv.api" for c in starts)
    lab._write_configs()
    r = lab.routers[0]
    conf = (tmp_path / "etc" / r / "frr.conf").read_text(encoding="utf-8")
    assert f"log file {lab.log_path(r)} debugging" in conf and "/tmp/frr.log" not in conf
    assert lab.log_path(r) == f"{tmp_path / 'run'}/{r}/frr.log"
    assert (tmp_path / "etc" / r / "vtysh.conf").read_text(encoding="utf-8") == "service integrated-vtysh-config\n"
    assert M.BACKENDS == {"docker": M.Lab, "netns": M.NetnsLab}
