"""Tables from the JSON lines that `measure` writes: one row per topology, flood reduction off against on.

Link changes pool every link-down and link-up window of every run.  The paired comparison takes each link and
direction, averages it over the repeats with flood reduction off and with it on, and counts the pairs in which the
`on` figure is lower.  CPU for the link windows is isisd time net of the quiet window; for bring-up it is isisd
time from the routers' start.  LSPs are the Level-2 LSPs sent, summed over all routers."""
import gzip
import json
from statistics import mean, median

LINK_PHASES = ("link-down", "link-up")


def read(paths):
    """Records from JSON-lines files, gzipped or not, in order."""
    records = []
    for path in paths:
        opener = gzip.open if str(path).endswith(".gz") else open
        with opener(path, "rt", encoding="utf-8") as fh:
            records += [json.loads(x) for x in fh if x.strip()]
    return records


def label(topology):
    """A short name for a topology: its family and the parameters that set its density."""
    family, p = topology.get("family"), topology.get("parameters") or {}
    if family == "random-regular":
        return f"random regular, degree {p['degree']}, seed {p['seed']}"
    if family == "leaf-spine":
        return f"leaf-spine, {p['leaves']} leaves x {p['spines']} spines"
    if family == "flattened-butterfly":
        return "flattened butterfly " + " x ".join(map(str, p["radices"]))
    return f"{family} {json.dumps(p, sort_keys=True)}"


def _span(values):
    return {"mean": mean(values), "min": min(values), "max": max(values)} if values else None


def _saving(off, on):
    return None if not off or not on or off["mean"] == 0 else 1 - on["mean"] / off["mean"]


def rows(records):
    """One dict per topology, in order of family, then average degree."""
    by_source = {}
    for rec in records:
        by_source.setdefault(rec["source_sha256"], []).append(rec)
    out = []
    for recs in by_source.values():
        t = recs[0]["topology"]
        side = {"off": [r for r in recs if not r["settings"]["flood_reduction"]],
                "on": [r for r in recs if r["settings"]["flood_reduction"]]}
        row = {"topology": label(t), "family": t.get("family"), "routers": t.get("routers"), "links": t.get("links"),
               "average_degree": t.get("average_degree"), "runs": {k: len(v) for k, v in side.items()}}
        windows, bring_up, pairs = {}, {}, {}
        for k, rs in side.items():
            link = [p for r in rs for p in r["phases"] if p["phase"] in LINK_PHASES]
            windows[k] = {"lsps": _span([p["counters"].get("tx_l2_lsp", 0) for p in link]),
                          "net_ms": _span([p["net_of_quiet"]["cpu_ms"].get("isisd", 0) for p in link
                                           if p.get("net_of_quiet")]),
                          "satisfied": sum(p["outcome"] == "satisfied" for p in link), "windows": len(link)}
            up = [p for r in rs for p in r["phases"] if p["phase"] == "bring-up"]
            quiet = [p for r in rs for p in r["phases"] if p["phase"] == "quiet"]
            bring_up[k] = {"lsps": _span([p["counters"].get("tx_l2_lsp", 0) for p in up]),
                           "ms": _span([p["cpu_ms"].get("isisd", 0) for p in up]),
                           "converged": sum(bool(r.get("converged")) for r in rs),
                           "quiet_satisfied": sum(p["outcome"] == "satisfied" for p in quiet), "quiet": len(quiet)}
            for p in link:
                if p.get("net_of_quiet"):
                    pair = pairs.setdefault((p["link"], p["phase"]), {"off": [], "on": []})
                    pair[k].append((p["counters"].get("tx_l2_lsp", 0), p["net_of_quiet"]["cpu_ms"].get("isisd", 0)))
        both = [x for x in pairs.values() if x["off"] and x["on"]]
        lsp = [(mean(a for a, _ in x["off"]), mean(a for a, _ in x["on"])) for x in both]
        cpu = [(mean(b for _, b in x["off"]), mean(b for _, b in x["on"])) for x in both]
        savings = [1 - on / off for off, on in cpu if off > 0]
        row.update(windows=windows, bring_up=bring_up,
                   lsp_saving=_saving(windows["off"]["lsps"], windows["on"]["lsps"]),
                   net_saving=_saving(windows["off"]["net_ms"], windows["on"]["net_ms"]),
                   bring_up_lsp_saving=_saving(bring_up["off"]["lsps"], bring_up["on"]["lsps"]),
                   bring_up_ms_saving=_saving(bring_up["off"]["ms"], bring_up["on"]["ms"]),
                   pairs={"n": len(both), "lsps_lower_on": sum(on < off for off, on in lsp),
                          "net_lower_on": sum(on < off for off, on in cpu),
                          "median_net_saving": median(savings) if savings else None})
        out.append(row)
    return sorted(out, key=lambda r: (r["family"] or "", r["average_degree"] or 0, r["topology"]))


def _n(span):
    return "-" if span is None else f"{span['mean']:,.0f}"


def _pct(x):
    return "-" if x is None else f"{100 * x:.0f}%"


def text(table):
    """The rows as two plain-text tables: link changes, then bring-up."""
    w = max([len(r["topology"]) for r in table] + [8])
    title = ("Link changes: every link-down and link-up window; mean LSPs sent and isisd ms net of the quiet window, "
             "off -> on; pairs with the on figure lower; windows satisfied")
    head = (f"{'topology':<{w}} {'degree':>6} {'LSPs off':>9} {'on':>7} {'saving':>6} {'pairs':>5} "
            f"{'net ms off':>10} {'on':>7} {'saving':>6} {'pairs':>5} {'median':>6} {'satisfied':>9}")
    lines = [title, head]
    for r in table:
        o, n, p = r["windows"]["off"], r["windows"]["on"], r["pairs"]
        ok = f"{o['satisfied'] + n['satisfied']}/{o['windows'] + n['windows']}"
        lines.append(f"{r['topology']:<{w}} {r['average_degree']!s:>6} {_n(o['lsps']):>9} {_n(n['lsps']):>7} "
                     f"{_pct(r['lsp_saving']):>6} {p['lsps_lower_on']:>2}/{p['n']:<2} {_n(o['net_ms']):>10} "
                     f"{_n(n['net_ms']):>7} {_pct(r['net_saving']):>6} {p['net_lower_on']:>2}/{p['n']:<2} "
                     f"{_pct(p['median_net_saving']):>6} {ok:>9}")
    title = ("Bring-up: mean LSPs sent and isisd ms from the routers' start, off -> on; runs converged, and quiet "
             "windows satisfied, off and on")
    head = (f"{'topology':<{w}} {'degree':>6} {'LSPs off':>11} {'on':>9} {'saving':>6} {'ms off':>11} "
            f"{'on':>9} {'saving':>6} {'converged':>9} {'quiet':>9}")
    lines += ["", title, head]
    for r in table:
        o, n = r["bring_up"]["off"], r["bring_up"]["on"]
        ok = f"{o['converged']}/{r['runs']['off']} {n['converged']}/{r['runs']['on']}"
        quiet = f"{o['quiet_satisfied']}/{o['quiet']} {n['quiet_satisfied']}/{n['quiet']}"
        lines.append(f"{r['topology']:<{w}} {r['average_degree']!s:>6} {_n(o['lsps']):>11} {_n(n['lsps']):>9} "
                     f"{_pct(r['bring_up_lsp_saving']):>6} {_n(o['ms']):>11} {_n(n['ms']):>9} "
                     f"{_pct(r['bring_up_ms_saving']):>6} {ok:>9} {quiet:>9}")
    return "\n".join(lines) + "\n"
