"""Tables from the JSON lines that `measure` writes: one row per topology, flood reduction off against on.

Link changes pool every link-down and link-up window of every run.  The paired comparison takes each link and
direction, averages it over the repeats with flood reduction off and with it on, and counts the pairs in which the
`on` figure is lower.  CPU for the link windows is isisd time net of the quiet window; for bring-up it is isisd
time from the routers' start.  LSPs are the Level-2 LSPs sent, summed over all routers.

Events of another kind (`node`, `multi`: see measure) are reported the same way with `kind`. `pooled` merges the
rows of graphs that differ only in their seed. `timing_text` and `profile_text` add the convergence times and the
CPU per isisd event handler of runs made with `measure --timing` or `--profile`."""
import gzip
import json
from statistics import mean, median

from .measure import net_isisd_ms

LINK_PHASES = ("link-down", "link-up")


def _phases(kind):
    return (f"{kind}-down", f"{kind}-up")


def _index(p):
    return p.get("event", p.get("link"))


def read(paths):
    """Records from JSON-lines files, gzipped or not, in order."""
    records = []
    for path in paths:
        opener = gzip.open if str(path).endswith(".gz") else open
        with opener(path, "rt", encoding="utf-8") as fh:
            records += [json.loads(x) for x in fh if x.strip()]
    return records


def label(topology, seed=True):
    """A short name for a topology: its family and the parameters that set its density."""
    family, p = topology.get("family"), topology.get("parameters") or {}
    if family == "random-regular":
        return f"random regular, degree {p['degree']}" + (f", seed {p['seed']}" if seed else "")
    if family == "leaf-spine":
        return f"leaf-spine, {p['leaves']} leaves x {p['spines']} spines"
    if family == "flattened-butterfly":
        return "flattened butterfly " + " x ".join(map(str, p["radices"]))
    if family == "zoo":
        name = f"{p.get('name')} (Topology Zoo)"
        if not p.get("added_links"):
            return f"{name}, as it is"
        name += f", {p['added_links']} links added ({p.get('method')}), average degree {p.get('average_degree'):g}"
        return name + (f", seed {p['seed']}" if seed and p.get("method") == "random" and "seed" in p else "")
    return f"{family} {json.dumps(p, sort_keys=True)}"


def _namer(records):
    """label(), with the number of routers added where one label covers graphs of more than one size in `records`,
    so that rows, pools and the timing and per-handler tables keep those graphs apart."""
    sizes = {}  # by the label without the seed, so that the graphs of one size pool alike
    for rec in records:
        sizes.setdefault(label(rec["topology"], seed=False), set()).add(rec["topology"].get("routers"))

    def name(topology, seed=True):
        n = label(topology, seed)
        return f"{n}, {topology.get('routers')} routers" if len(sizes.get(label(topology, False), ())) > 1 else n
    return name


def _span(values):
    return {"mean": mean(values), "min": min(values), "max": max(values)} if values else None


def _saving(off, on):
    return None if not off or not on or off["mean"] == 0 else 1 - on["mean"] / off["mean"]


def rows(records, kind="link"):
    """One dict per topology, in order of family, then average degree. Event windows are those of `kind`."""
    phases = _phases(kind)
    name = _namer(records)
    by_source = {}
    for rec in records:
        if rec.get("timing"):
            continue  # timing runs log every LSP, which costs CPU: they are reported by timing_text only
        by_source.setdefault(rec["source_sha256"], []).append(rec)
    out = []
    for recs in by_source.values():
        t = recs[0]["topology"]
        side = {"off": [r for r in recs if not r["settings"]["flood_reduction"]],
                "on": [r for r in recs if r["settings"]["flood_reduction"]]}
        row = {"topology": name(t), "pool": name(t, seed=False), "family": t.get("family"),
               "routers": t.get("routers"), "links": t.get("links"), "diameter": t.get("diameter"),
               "two_hop_multiplicity": t.get("two_hop_multiplicity"),
               "average_degree": t.get("average_degree"), "runs": {k: len(v) for k, v in side.items()}}
        windows, bring_up, pairs = {}, {}, {}
        for k, rs in side.items():
            link = [p for r in rs for p in r["phases"] if p["phase"] in phases]
            windows[k] = {"lsps": _span([p["counters"].get("tx_l2_lsp", 0) for p in link]),
                          "net_ms": _span([x for x in map(net_isisd_ms, link) if x is not None]),
                          "satisfied": sum(p["outcome"] == "satisfied" for p in link), "windows": len(link)}
            up = [p for r in rs for p in r["phases"] if p["phase"] == "bring-up"]
            quiet = [p for r in rs for p in r["phases"] if p["phase"] == "quiet"]
            bring_up[k] = {"lsps": _span([p["counters"].get("tx_l2_lsp", 0) for p in up]),
                           "ms": _span([p["cpu_ms"].get("isisd", 0) for p in up]),
                           "converged": sum(bool(r.get("converged")) for r in rs),
                           "quiet_satisfied": sum(p["outcome"] == "satisfied" for p in quiet), "quiet": len(quiet)}
            for p in link:
                if (n := net_isisd_ms(p)) is not None:
                    pair = pairs.setdefault((_index(p), p["phase"]), {"off": [], "on": []})
                    pair[k].append((p["counters"].get("tx_l2_lsp", 0), n))
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


def pooled(table):
    """Rows of graphs that differ only in their seed, merged: each saving as the mean over graphs, with its range
    across graphs; counts summed. Keys as in rows, plus "graphs" and "<saving>_range"."""
    groups = {}
    for r in table:
        groups.setdefault((r["family"] or "", r["average_degree"] or 0, r["pool"]), []).append(r)
    out = []
    for (_, _, name), rs in sorted(groups.items()):
        mult = [r["two_hop_multiplicity"] for r in rs if r.get("two_hop_multiplicity") is not None]
        diam = [r["diameter"] for r in rs if r.get("diameter") is not None]
        row = {"topology": name, "pool": name, "family": rs[0]["family"], "routers": rs[0]["routers"],
               "links": rs[0]["links"], "average_degree": rs[0]["average_degree"], "graphs": len(rs),
               "two_hop_multiplicity": round(mean(mult), 4) if mult else None,
               "diameter": max(diam) if diam else None,
               "runs": {k: sum(r["runs"][k] for r in rs) for k in ("off", "on")}}
        for key in ("lsp_saving", "net_saving", "bring_up_lsp_saving", "bring_up_ms_saving"):
            vals = [r[key] for r in rs if r[key] is not None]
            row[key] = mean(vals) if vals else None
            row[key + "_range"] = [min(vals), max(vals)] if vals else None
        row["windows"] = {k: {"lsps": _merge([r["windows"][k]["lsps"] for r in rs]),
                              "net_ms": _merge([r["windows"][k]["net_ms"] for r in rs]),
                              "satisfied": sum(r["windows"][k]["satisfied"] for r in rs),
                              "windows": sum(r["windows"][k]["windows"] for r in rs)} for k in ("off", "on")}
        row["bring_up"] = {k: {"lsps": _merge([r["bring_up"][k]["lsps"] for r in rs]),
                               "ms": _merge([r["bring_up"][k]["ms"] for r in rs]),
                               **{c: sum(r["bring_up"][k][c] for r in rs)
                                  for c in ("converged", "quiet_satisfied", "quiet")}} for k in ("off", "on")}
        savings = [r["pairs"]["median_net_saving"] for r in rs if r["pairs"]["median_net_saving"] is not None]
        row["pairs"] = {"n": sum(r["pairs"]["n"] for r in rs),
                        "lsps_lower_on": sum(r["pairs"]["lsps_lower_on"] for r in rs),
                        "net_lower_on": sum(r["pairs"]["net_lower_on"] for r in rs),
                        "median_net_saving": median(savings) if savings else None}
        out.append(row)
    return sorted(out, key=lambda r: (r["family"] or "", r["average_degree"] or 0, r["topology"]))


def _merge(spans):
    spans = [x for x in spans if x]
    if not spans:
        return None
    return {"mean": mean(x["mean"] for x in spans), "min": min(x["min"] for x in spans),
            "max": max(x["max"] for x in spans)}


def timing_text(records, kind="link"):
    """Convergence times of timing runs: per topology, flood reduction off and on, the median over windows of the
    time until the last router held the new LSPs (and the slowest window), in ms; windows with a router whose log
    never showed them are counted as missing."""
    groups = {}
    name = _namer(records)
    for rec in records:
        if not rec.get("timing"):
            continue
        fr = "on" if rec["settings"]["flood_reduction"] else "off"
        for p in rec["phases"]:
            if p["phase"] in _phases(kind) and p.get("timing"):
                g = groups.setdefault((rec["topology"].get("family") or "", rec["topology"].get("average_degree") or 0,
                                       name(rec["topology"])), {"off": [], "on": []})
                g[fr].append((p["timing"]["max_ms"], p["timing"].get("flood_ms")))
    if not groups:
        return ""
    w = max(len(k[2]) for k in groups)
    title = (f"Convergence after each {kind} event (timing runs), ms, off -> on: median and slowest window from the "
             "event to the last router holding the new LSPs; median flooding alone, from each LSP's origin; windows "
             "with a router missing the new LSPs")
    head = (f"{'topology':<{w}} {'median off':>10} {'on':>8} {'slowest off':>11} {'on':>8} {'flooding off':>12} "
            f"{'on':>8} {'missing':>9}")
    lines = ["", title, head]

    def f(x):
        return "-" if x is None else f"{x:,.1f}"
    for key in sorted(groups):
        g = groups[key]
        cells = []
        for k in ("off", "on"):
            done = sorted(x for x, _ in g[k] if x is not None)
            flood = sorted(y for _, y in g[k] if y is not None)
            cells.append((median(done) if done else None, done[-1] if done else None,
                          median(flood) if flood else None, len(g[k]) - len(done)))
        lines.append(f"{key[2]:<{w}} {f(cells[0][0]):>10} {f(cells[1][0]):>8} {f(cells[0][1]):>11} "
                     f"{f(cells[1][1]):>8} {f(cells[0][2]):>12} {f(cells[1][2]):>8} {cells[0][3]:>4} {cells[1][3]:>4}")
    return "\n".join(lines) + "\n"


def profile_text(records, kind="link", top=8):
    """isisd CPU per event handler in profile runs: per topology and handler, mean ms per event window net of the
    quiet window, off and on, for the handlers with the most CPU."""
    groups = {}
    name = _namer(records)
    for rec in records:
        if not rec.get("profile") or rec.get("timing"):
            continue
        fr = "on" if rec["settings"]["flood_reduction"] else "off"
        key = (rec["topology"].get("family") or "", rec["topology"].get("average_degree") or 0, name(rec["topology"]))
        for p in rec["phases"]:
            ev = (p.get("net_of_quiet") or {}).get("event_cpu_ms")
            if p["phase"] in _phases(kind) and ev is not None:
                g = groups.setdefault(key, {"off": [], "on": []})
                g[fr].append(ev)
    if not groups:
        return ""
    lines = ["", f"isisd CPU per event handler, mean ms per {kind} window net of the quiet window, off -> on"]
    for key in sorted(groups):
        g = groups[key]
        means = {}
        for k in ("off", "on"):
            names = {n for ev in g[k] for n in ev}
            means[k] = {n: mean(ev.get(n, 0) for ev in g[k]) for n in names} if g[k] else {}
        names = sorted(set(means["off"]) | set(means["on"]),
                       key=lambda n: -max(means["off"].get(n, 0), means["on"].get(n, 0)))[:top]
        lines.append(f"{key[2]} ({len(g['off'])} and {len(g['on'])} windows)")
        for n in names:
            lines.append(f"  {n:<40} {means['off'].get(n, 0):>10,.1f} {means['on'].get(n, 0):>10,.1f}")
    return "\n".join(lines) + "\n"


def _n(span):
    return "-" if span is None else f"{span['mean']:,.0f}"


def _pct(x):
    return "-" if x is None else f"{100 * x:.0f}%"


def text(table, kind="link"):
    """The rows as two plain-text tables: changes of the given kind, then bring-up."""
    w = max([len(r["topology"]) for r in table] + [8])
    title = (f"{kind.capitalize()} changes: every {kind}-down and {kind}-up window; diameter and two-hop "
             "multiplicity of the topology; mean LSPs sent and isisd ms net of the quiet window, off -> on; pairs "
             "with the on figure lower; windows satisfied")
    head = (f"{'topology':<{w}} {'degree':>6} {'diam':>4} {'2-hop':>5} {'LSPs off':>9} {'on':>7} {'saving':>6} "
            f"{'pairs':>5} {'net ms off':>10} {'on':>7} {'saving':>6} {'pairs':>5} {'median':>6} {'satisfied':>9}")
    lines = [title, head]
    for r in table:
        o, n, p = r["windows"]["off"], r["windows"]["on"], r["pairs"]
        ok = f"{o['satisfied'] + n['satisfied']}/{o['windows'] + n['windows']}"
        mult = r.get("two_hop_multiplicity")
        lines.append(f"{r['topology']:<{w}} {r['average_degree']!s:>6} {r.get('diameter') or '-'!s:>4} "
                     f"{'-' if mult is None else f'{mult:.2f}':>5} {_n(o['lsps']):>9} {_n(n['lsps']):>7} "
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
