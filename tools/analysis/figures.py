"""Four figures from the published data in `results/`. Single-column width (3.33 in), legible in greyscale: series
differ by marker shape, fill and line style, never by color alone.

    python figures.py <topology-builders results folder> <scratch dir> <output dir>

Writes fig1-density, fig2-multiplicity, fig3-cpu and fig4-failures as .pdf and .png, and prints the numbers each
figure plots (figures.txt), so that every quoted number can be traced. Window rules are data.py's."""
import gzip
import json
import os
import sys
from statistics import mean

import matplotlib

matplotlib.use("Agg")
import data
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

W = 3.33
INK, MID, LIGHT, HAIR = "#000000", "#6e6e6e", "#bdbdbd", "#e3e3e3"
plt.rcParams.update({
    "font.size": 7, "axes.labelsize": 7, "xtick.labelsize": 6.5, "ytick.labelsize": 6.5, "legend.fontsize": 6,
    "font.family": "sans-serif", "pdf.fonttype": 42, "ps.fonttype": 42, "axes.linewidth": 0.5,
    "xtick.major.width": 0.5, "ytick.major.width": 0.5, "xtick.minor.width": 0.4, "ytick.minor.width": 0.4,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": HAIR,
    "grid.linewidth": 0.4, "grid.linestyle": "-", "axes.axisbelow": True, "legend.frameon": False,
    "lines.linewidth": 1.0, "lines.markersize": 4, "savefig.dpi": 300, "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02})


def save(fig, out, name):
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(out, f"{name}.{ext}"))
    plt.close(fig)


def fig1(results, index, out):
    """LSPs per link-down window against degree: the density sweep, random regular graphs of 64 routers, seed 1."""
    rr = sorted((r for r in data.rows(data.records(results, ["random-regular-n64"]), index)
                 if r["family"] == "random-regular"), key=lambda r: r["degree"])
    print("Figure 1: density sweep (random-regular-n64), LSPs per satisfied link-down window, mean [min, max]")
    fig, ax = plt.subplots(figsize=(W, 2.2))
    xs = [r["degree"] for r in rr]
    ax.plot(xs, [data.tree_bound(r)[1] for r in rr], color=MID, lw=0.8, ls=":",
            label="full flooding, no duplicate suppression")
    for key, style, lab in (("off", {"marker": "o", "color": INK, "mfc": INK}, "flood reduction off"),
                            ("on", {"marker": "o", "color": INK, "mfc": "white", "ls": "--"}, "flood reduction on")):
        pts = [(r["degree"], r[key]["down"]) for r in rr if r[key]["down"]]
        ys = [mean(v) for _, v in pts]
        err = [[mean(v) - min(v) for _, v in pts], [max(v) - mean(v) for _, v in pts]]
        ax.errorbar([d for d, _ in pts], ys, yerr=err, lw=1.0, elinewidth=0.5, capsize=1.5, ms=3.5, label=lab,
                    **style)
        for d, v in pts:
            print(f"  {key:>3} degree {d:>4.0f}: {mean(v):8.1f} [{min(v)}, {max(v)}] over {len(v)} windows")
    floor = data.tree_bound(rr[0])[0]
    ax.axhline(floor, color=MID, lw=0.8, ls=(0, (4, 2)), label=f"spanning-tree floor, 2(n-1) = {floor}")
    for r in rr:
        if not r["off"]["down"]:
            ax.annotate("off: never\nconverged", xy=(r["degree"], mean(r["on"]["down"])), xytext=(0, 9),
                        textcoords="offset points", ha="center", va="bottom", fontsize=5.5, color=MID)
            print(f"  off degree {r['degree']:.0f}: no satisfied window ({r['off']['windows']} windows, "
                  f"{r['off']['converged']} of {r['off']['runs']} runs converged)")
    ax.set_yscale("log")
    ax.set_ylim(90, 8000)
    ax.set_xscale("log", base=2)
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{x:g}" for x in xs])
    ax.minorticks_off()
    ax.set_xlabel("degree (64 routers, random regular)")
    ax.set_ylabel("LSPs sent per link-down")
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, handlelength=2.2, columnspacing=1.0)
    save(fig, out, "fig1-density")


MARKERS = [  # (test, legend label, marker, filled)
    (lambda r: r["family"] == "random-regular" and r["routers"] == 64, "random regular, 64", "o", True),
    (lambda r: r["family"] == "random-regular" and r["routers"] == 128, "random regular, 128", "s", True),
    (lambda r: r["family"] == "random-regular" and r["routers"] == 256, "random regular, 256", "^", True),
    (lambda r: r["family"] == "flattened-butterfly", "flattened butterfly", "D", False),
    (lambda r: r["family"] == "leaf-spine", "leaf-spine", "s", False),
    (lambda r: r["family"] == "k-ary-n-fly", "k-ary n-fly", "x", True),
    (lambda r: r["family"] == "fat-tree", "fat-tree", "+", True),
    (lambda r: r["family"] == "zoo", "Topology Zoo", "v", False),
]


def usable(r):
    """At least one full run's link windows (3 links, down and up) satisfied with flood reduction off and on."""
    return all(r[k]["satisfied"] >= 6 for k in ("off", "on"))


def fig2(rows, out):
    """Link-change LSP saving against two-hop multiplicity, every study graph with the topotest timers."""
    rs = [r for r in rows if r["timers"] == "topotest" and r["multiplicity"] and usable(r)]
    print("\nFigure 2: link-change LSP saving (down and up windows pooled) against two-hop multiplicity")
    fig, ax = plt.subplots(figsize=(W, 2.4))
    for test, lab, marker, filled in MARKERS:
        mine = sorted((r for r in rs if test(r)), key=lambda r: r["multiplicity"])
        if not mine:
            continue
        xs, ys = [r["multiplicity"] for r in mine], [100 * data.saving(r, "link") for r in mine]
        if marker in "x+":
            ax.scatter(xs, ys, marker=marker, s=20, linewidths=0.8, c=INK, label=lab, zorder=3)
        else:
            ax.scatter(xs, ys, marker=marker, s=14, linewidths=0.7, facecolors=INK if filled else "white",
                       edgecolors=INK, label=lab, zorder=3)
        for r, y in zip(mine, ys):
            print(f"  {lab:<20} {r['label'][:44]:<44} n {r['routers']:>3} deg {r['degree']:>5.1f} "
                  f"2hop {r['multiplicity']:>6.2f} saving {y:5.1f}%  (windows off {r['off']['satisfied']}, "
                  f"on {r['on']['satisfied']})")
    ax.set_xscale("log")
    ticks = [1, 1.5, 2, 3, 4, 6, 8, 16, 32]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{t:g}" for t in ticks])
    ax.minorticks_off()
    ax.set_ylim(0, 100)
    ax.set_xlabel("two-hop multiplicity")
    ax.set_ylabel("LSPs saved per link change (%)")
    ax.legend(loc="lower right", ncol=2, handletextpad=0.3, columnspacing=0.8, borderaxespad=0.2)
    save(fig, out, "fig2-multiplicity")
    for r in rows:
        if r["timers"] == "topotest" and r not in rs:
            print(f"  left out: {r['label']}, {r['routers']} routers (satisfied windows off "
                  f"{r['off']['satisfied']}/{r['off']['windows']}, on {r['on']['satisfied']}/{r['on']['windows']}; "
                  f"multiplicity {r['multiplicity']})")


GROUPS = (("route computation (SPF)", lambda h: h == "isis_run_spf_cb", "#3a3a3a", None),
          ("receiving PDUs", lambda h: h == "isis_receive", "#9a9a9a", "////"),
          ("other handlers", lambda h: h not in ("isis_run_spf_cb", "isis_receive"), "#dcdcdc", None))


def handler_means(recs, phases):
    """Per topology and variant: mean ms per satisfied window of converged profile runs, per handler group
    (negative counter noise counted as 0), the number of windows, and each run's mean total (the replication unit:
    windows within a run are not independent)."""
    acc, runs = {}, {}
    for r in recs:
        if not r.get("profile") or r.get("timing") or not r.get("converged"):
            continue
        t = r["topology"]
        key = (t["family"], t["average_degree"], t["routers"])
        fr = "on" if r["settings"]["flood_reduction"] else "off"
        mine = []
        for p in r["phases"]:
            ev = (p.get("net_of_quiet") or {}).get("event_cpu_ms")
            if p["phase"] in phases and ev is not None and p["outcome"] == "satisfied":
                mine.append([sum(max(v, 0) for h, v in ev.items() if test(h)) for _, test, _, _ in GROUPS])
        acc.setdefault(key, {"off": [], "on": []})[fr].extend(mine)
        if mine:
            runs.setdefault(key, {"off": [], "on": []})[fr].append(mean(sum(w) for w in mine))
    return {k: {fr: ([mean(c) for c in zip(*v)], len(v), runs[k][fr]) if v else None for fr, v in d.items()}
            for k, d in acc.items()}


def name(key):
    fam, deg, n = key
    return {"random-regular": f"random, degree {deg:g}", "flattened-butterfly": "butterfly 4x4x4",
            "leaf-spine": "leaf-spine, 16 spines"}.get(fam, f"{fam} {deg:g}") + ("" if n == 64 else f", {n} routers")


def bars(ax, means, order, scale, unit):
    y, ticks, labels = 0, [], []
    for key in order:
        ends = []
        for fr in ("off", "on"):
            v, nwin, run_totals = means[key][fr]
            left = 0
            for (lab, _, color, hatch), x in zip(GROUPS, v):
                ax.barh(y, x * scale, left=left, height=0.8, color=color, edgecolor="white", linewidth=0.6,
                        hatch=hatch, label=lab if not ticks else None)
                left += x * scale
            lo, hi = min(run_totals) * scale, max(run_totals) * scale
            ax.plot([lo, hi], [y, y], color=INK, linewidth=0.7, solid_capstyle="butt", zorder=3)
            ax.plot([lo, lo], [y - 0.22, y + 0.22], color=INK, linewidth=0.7, zorder=3)
            ax.plot([hi, hi], [y - 0.22, y + 0.22], color=INK, linewidth=0.7, zorder=3)
            ends.append(max(left, hi))
            ticks.append(y)
            labels.append(fr)
            print(f"  {name(key):<24} {fr:>3} ({nwin:>3} windows, {len(run_totals)} runs): total {sum(v) * scale:9.2f} "
                  f"{unit}, run means {lo:.2f} to {hi:.2f}; "
                  + ", ".join(f"{g[0].split(' (')[0]} {x * scale:.2f} ({100 * x / sum(v):.0f}%)"
                              for g, x in zip(GROUPS, v)))
            y += 1
        ax.text(max(ends) * 1.02, y - 1.5, name(key), va="center", ha="left", fontsize=6)
        y += 0.5
    ax.set_yticks(ticks)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)


def fig3(results, out):
    """isisd CPU by handler, net of the idle window: one link change (a) and ten simultaneous flaps (b)."""
    one = handler_means(data.records(results, ["seeds-n64"]), ("link-down", "link-up"))
    ten = handler_means(data.records(results, ["flap10-n64"]), ("multi-down", "multi-up"))
    order1 = [k for k in sorted(one, key=lambda k: (k[0] != "random-regular", k[1]))
              if one[k]["off"] is not None and one[k]["on"] is not None]
    order10 = sorted(ten, key=lambda k: k[1])
    print("\nFigure 3a: isisd CPU per link window by handler, mean, satisfied windows of converged profile runs")
    fig, (a, b) = plt.subplots(2, 1, figsize=(W, 3.5),
                               gridspec_kw={"height_ratios": [len(order1) * 2.5, len(order10) * 2.5 + 0.6]})
    bars(a, one, order1, 1.0, "ms")
    a.set_xlim(0, 5600)
    a.set_xlabel("isisd CPU per link change, net of the idle window (ms, all routers)")
    print("Figure 3b: ten links at once, per window")
    bars(b, ten, order10, 1e-3, "s")
    b.set_xlim(0, 23)
    b.set_xlabel("isisd CPU per ten-link window, net of the idle window (s, all routers)")
    for ax, t in ((a, "(a)"), (b, "(b)")):
        ax.text(-0.01, 1.0, t, transform=ax.transAxes, ha="right", va="bottom", fontsize=7)
    handles, labels = a.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3, handlelength=1.4,
               columnspacing=1.0)
    fig.tight_layout(h_pad=0.8)
    left_out = [name(k) for k in one if one[k]["off"] is None or one[k]["on"] is None]
    print("  left out (a variant with no converged profile run):", left_out)
    save(fig, out, "fig3-cpu")


EVENTS = (("link-down", "link"), ("multi-down", "3 links"), ("node-down", "router"))
SHORT = {"random-regular": lambda p: f"random {p['degree']}", "flattened-butterfly": lambda p: "butterfly",
         "leaf-spine": lambda p: "leaf-spine"}  # the caption names them: degree 8 and 16, 4x4x4, 16 spines


def fig4(results, out):
    """Flooding time per failure window: from each new LSP's origin to the last router holding it (debug-log
    timestamps), flood reduction off and on."""
    with gzip.open(os.path.join(results, "timing-n64", "measurements.jsonl.gz"), "rt", encoding="utf-8") as fh:
        recs = [json.loads(x) for x in fh if x.strip()]
    groups = {}
    for r in recs:
        t = r["topology"]
        top = SHORT[t["family"]](t["parameters"])
        fr = "on" if r["settings"]["flood_reduction"] else "off"
        for p in r["phases"]:
            ms = (p.get("timing") or {}).get("flood_ms")
            if p["phase"] in dict(EVENTS) and ms is not None:
                groups.setdefault((t["family"] != "random-regular", t["average_degree"], top), {}).setdefault(
                    p["phase"], {"off": [], "on": []})[fr].append(ms / 1000)
    print("\nFigure 4: flooding time per window (s), from each new LSP's origin to the last router holding it")
    fig, ax = plt.subplots(figsize=(W - 0.75, 2.7))
    y, ticks, labels = 0, [], []
    for key in sorted(groups):
        top = key[2]
        for phase, ev in EVENTS:
            d = groups[key].get(phase)
            if not d:
                continue
            ax.scatter(d["off"], [y - 0.17] * len(d["off"]), marker="o", s=10, facecolors=INK, edgecolors=INK,
                       linewidths=0.6, zorder=3)
            ax.scatter(d["on"], [y + 0.17] * len(d["on"]), marker="o", s=10, facecolors="white", edgecolors=INK,
                       linewidths=0.6, zorder=3)
            ticks.append(y)
            labels.append(f"{top}: {ev}")
            print(f"  {top:<22} {ev:<12} off {sorted(round(x, 3) for x in d['off'])}  on "
                  f"{sorted(round(x, 3) for x in d['on'])}")
            y += 1
        y += 0.4
    ax.axvline(1.0, color=MID, lw=0.6, ls="-", zorder=1)
    ax.set_xscale("log")
    ax.set_xlim(0.012, 15)
    ax.set_xticks([0.02, 0.05, 0.1, 0.3, 1, 3, 10])
    ax.set_xticklabels(["0.02", "0.05", "0.1", "0.3", "1", "3", "10"])
    ax.minorticks_off()
    ax.set_yticks(ticks)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("flooding time after the failure (s, log scale)")
    handles = [Line2D([], [], marker="o", ls="", mfc=INK, mec=INK, ms=3.5, label="flood reduction off"),
               Line2D([], [], marker="o", ls="", mfc="white", mec=INK, ms=3.5, label="flood reduction on")]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2)
    save(fig, out, "fig4-failures")


def main(results, scratch, out):
    os.makedirs(out, exist_ok=True)
    index = data.topology_index(results, scratch)
    fig1(results, index, out)
    fig2(data.rows(data.records(results, data.STUDY), index), out)
    fig3(results, out)
    fig4(results, out)


if __name__ == "__main__":
    main(*sys.argv[1:4])
