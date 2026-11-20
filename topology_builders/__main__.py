"""Command line: python -m topology_builders {sweep, zoo, build, clab, measure, report} ...  Run with -h for the
options."""
import argparse
import json
import os
import sys
import time

from . import clab as C
from . import families as F
from . import output as O
from . import sweep as S
from . import zoo as Z


def _ints(text):
    return [int(x) for x in text.split(",") if x]


def _floats(text):
    return [float(x) if "." in x else int(x) for x in text.split(",") if x]


def _table(entries):
    w = max([len(e["file"]) for e in entries] + [4])
    print(f"{'file':<{w}}  routers  links  avg degree  diameter  2-hop multiplicity  seconds")
    for e in entries:
        print(f"{e['file']:<{w}}  {e['routers']:>7}  {e['links']:>5}  {e['average_degree']:>10}  "
              f"{e['diameter']!s:>8}  {e['two_hop_multiplicity']!s:>18}  {e.pop('_seconds'):>7}")


def _run(jobs, out, argv):
    os.makedirs(out, exist_ok=True)
    entries = []
    for name, build in jobs:
        t0 = time.time()
        g = build()
        entry = O.write(g, os.path.join(out, name))
        entry["_seconds"] = round(time.time() - t0, 2)
        entries.append(entry)
    O.write_manifest(out, [{k: v for k, v in e.items() if k != "_seconds"} for e in entries], argv)
    _table(entries)
    print(f"{len(entries)} topologies and manifest.json in {out}")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    p = argparse.ArgumentParser(prog="python -m topology_builders",
                                description="Topologies whose density can be stepped at a fixed number of routers.")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("sweep", help="topologies with one number of routers, from sparse to the full mesh")
    s.add_argument("--routers", type=int, required=True)
    s.add_argument("--families", default=",".join(S.FAMILIES), help="comma-separated (default: all three)")
    s.add_argument("--seeds", default="1", help="seeds for random-regular, comma-separated (default 1)")
    s.add_argument("--out", required=True, help="output directory")

    z = sub.add_parser("zoo", help="Topology Zoo graphs (TopoHub JSON) made denser by adding links")
    z.add_argument("graphs", nargs="+", help="TopoHub JSON files")
    z.add_argument("--degrees", help="target average degrees, comma-separated (default: steps up to the full mesh)")
    z.add_argument("--method", choices=("random", "nearest"), default="random")
    z.add_argument("--seeds", default="1", help="seeds for --method random, comma-separated (default 1)")
    z.add_argument("--out", required=True, help="output directory")

    b = sub.add_parser("build", help="one topology")
    b.add_argument("family", choices=("random-regular", "leaf-spine", "flattened-butterfly", "k-ary-n-fly",
                                      "fat-tree"))
    b.add_argument("--routers", type=int, help="random-regular")
    b.add_argument("--degree", type=int, help="random-regular")
    b.add_argument("--seed", type=int, default=1, help="random-regular (default 1)")
    b.add_argument("--leaves", type=int, help="leaf-spine")
    b.add_argument("--spines", type=int, help="leaf-spine")
    b.add_argument("--radices", help="flattened-butterfly, comma-separated, e.g. 8,8")
    b.add_argument("--k", type=int, help="k-ary-n-fly; fat-tree (even)")
    b.add_argument("--stages", type=int, help="k-ary-n-fly")
    b.add_argument("--out", required=True, help="output file")

    c = sub.add_parser("clab", help="a containerlab lab of FRR routers running IS-IS, from one topology file")
    c.add_argument("topology", help="topology file (node-link JSON, as written by this package or TopoHub)")
    c.add_argument("--out", required=True, help="output directory")
    c.add_argument("--name", help="lab name (default: from the file name); -on or -off is appended")
    c.add_argument("--flood-reduction", choices=("on", "off", "both"), default="both",
                   help="write FRR's flood-reduction line (FRR pull request 24128); both (default): one lab in "
                        "<out>/off and one in <out>/on")
    c.add_argument("--kind", choices=("linux", "frr"), default="linux",
                   help="containerlab node kind (default linux; frr needs containerlab 0.80.0 or later)")
    c.add_argument("--image", help=f"FRR image (default {C.IMAGES['linux']}, or {C.IMAGES['frr']} for --kind frr)")
    c.add_argument("--hello-interval", type=int, default=1, help="seconds (default 1)")
    c.add_argument("--hello-multiplier", type=int, default=3, help="default 3")
    c.add_argument("--lsp-gen-interval", type=int, default=2, help="seconds (default 2)")
    c.add_argument("--area", default="49.0001", help="IS-IS area (default 49.0001)")
    c.add_argument("--debug-flooding", action="store_true",
                   help="add 'debug isis flooding' (verbose: it changes CPU measurements)")
    c.add_argument("--cpu-set", help="run every router on these CPUs only, e.g. 12-23,36-43 (containerlab cpu-set)")
    c.add_argument("--timing-logs", action="store_true",
                   help="log every LSP built or received, with microsecond times, for measure --timing (costs CPU)")

    m = sub.add_parser("measure", help="deploy labs written by clab and measure flooding and CPU around a link flap")
    m.add_argument("labs", nargs="+", help="lab directories of one topology, e.g. <out>/off <out>/on")
    m.add_argument("--repeat", type=int, default=1, help="runs of each lab; the order alternates (default 1)")
    m.add_argument("--settle", type=int, default=30, help="seconds after deploy before the first check (default 30)")
    m.add_argument("--window", type=int, default=30, help="seconds after the link goes down, and up (default 30)")
    m.add_argument("--seed", type=int, default=1, help="chooses the links (default 1)")
    m.add_argument("--event", default="link",
                   help="link: one link down and up; node: every link of one router at once; multi: --fail links "
                        "at once, keeping the graph connected; several comma-separated, e.g. link,node,multi, run in "
                        "that order (default link)")
    m.add_argument("--links", "--events", dest="links", type=int, default=1,
                   help="events per run, one after another (default 1)")
    m.add_argument("--fail", type=int, default=2, help="links per multi event (default 2)")
    m.add_argument("--timing", action="store_true",
                   help="convergence time per window from the routers' logs (labs written with clab --timing-logs)")
    m.add_argument("--profile", action="store_true", help="isisd CPU per event handler (show event cpu) per window")
    m.add_argument("--backend", choices=("docker", "netns"), default="docker",
                   help="docker: containerlab (default); netns: every router in a network namespace of this machine, "
                        "no Docker (needs root, or unshare -Urnm, as on Colab)")
    m.add_argument("--max-temp", type=float, default=80.0,
                   help="before each run, wait while the hottest CPU sensor is above this, deg C (default 80)")
    m.add_argument("--max-wait", type=int, default=120,
                   help="seconds to keep checking for convergence after the settle time (default 120)")
    m.add_argument("--out", default="measurements.jsonl", help="JSON lines, appended (default measurements.jsonl)")

    r = sub.add_parser("report", help="per topology, flood reduction off against on, from measure's JSON lines")
    r.add_argument("files", nargs="+", help="JSON-lines files written by measure (.jsonl or .jsonl.gz)")
    r.add_argument("--json", action="store_true", help="print the rows as JSON instead of tables")
    r.add_argument("--event", choices=("link", "node", "multi"), default="link", help="which events (default link)")
    r.add_argument("--pool-seeds", action="store_true",
                   help="one row per family and parameters, pooling graphs that differ only in their seed")

    a = p.parse_args(argv)
    if a.command == "measure" and not set(a.event.split(",")) <= {"link", "node", "multi"}:
        p.error(f"--event takes link, node and multi, comma-separated; got {a.event}")
    if a.command == "sweep":
        _run(S.plan(a.routers, a.families.split(","), _ints(a.seeds)), a.out, argv)
    elif a.command == "zoo":
        jobs = []
        for path in a.graphs:
            name = os.path.splitext(os.path.basename(path))[0]
            degrees = _floats(a.degrees) if a.degrees else Z.default_degrees(path)
            seeds = _ints(a.seeds) if a.method == "random" else [None]
            for d in degrees:
                for sd in seeds:
                    tag = f"-s{sd}" if sd is not None else ""
                    jobs.append((f"zoo-{name}-avg{d:g}-{a.method}{tag}.json",
                                 lambda p=path, d=d, sd=sd: Z.denser(p, d, a.method, sd if sd is not None else 1)))
        _run(jobs, a.out, argv)
    elif a.command == "measure":
        from . import measure as M
        records = M.run(a.labs, repeat=a.repeat, settle=a.settle, window=a.window, seed=a.seed, out=a.out,
                        max_wait=a.max_wait, links=a.links, max_temp=a.max_temp, kind=a.event, fail=a.fail,
                        timing=a.timing, profile=a.profile, backend=a.backend)
        print(f"{'lab':<28} {'reduction':<9} {'phase':<9} {'runs':>4} {'LSPs sent':>9} {'suppressed':>10} "
              f"{'isisd ms':>8} {'net of quiet':>12}  outcomes")
        for r in M.summarize(records):
            net = "" if r["isisd_net_ms"] is None else r["isisd_net_ms"]
            print(f"{r['lab']:<28} {'on' if r['flood_reduction'] else 'off':<9} {r['phase']:<9} {r['runs']:>4} "
                  f"{r['lsps_sent']:>9} {r['suppressed_sends']:>10} {r['isisd_ms']:>8} {net:>12}  {r['outcomes']}")
        print(f"{len(records)} runs appended to {a.out}")
    elif a.command == "report":
        from . import report as R
        records = R.read(a.files)
        table = R.rows(records, a.event)
        if a.pool_seeds:
            table = R.pooled(table)
        extra = "" if a.pool_seeds else R.timing_text(records, a.event) + R.profile_text(records, a.event)
        sys.stdout.write(json.dumps(table, indent=1) + "\n" if a.json else R.text(table, a.event) + extra)
    elif a.command == "clab":
        base = C.lab_name(a.name or os.path.splitext(os.path.basename(a.topology))[0])
        for on in {"on": [True], "off": [False], "both": [False, True]}[a.flood_reduction]:
            tag = "on" if on else "off"
            out = os.path.join(a.out, tag) if a.flood_reduction == "both" else a.out
            m = C.write_lab(a.topology, out, name=f"{base}-{tag}", flood_reduction=on, kind=a.kind,
                            image=a.image, hello_interval=a.hello_interval, hello_multiplier=a.hello_multiplier,
                            lsp_gen_interval=a.lsp_gen_interval, area=a.area, debug_flooding=a.debug_flooding,
                            cpu_set=a.cpu_set, timing_logs=a.timing_logs)
            print(f"{out}: lab {m['name']}, {m['routers']} routers, {m['links']} links, flood-reduction {tag}. "
                  f"Deploy: containerlab deploy -t {os.path.join(out, m['name'] + '.clab.yml')}")
    else:
        if a.family == "random-regular":
            g = F.random_regular(a.routers, a.degree, a.seed)
        elif a.family == "leaf-spine":
            g = F.leaf_spine(a.leaves, a.spines)
        elif a.family == "flattened-butterfly":
            g = F.flattened_butterfly(_ints(a.radices))
        elif a.family == "fat-tree":
            g = F.fat_tree(a.k)
        else:
            g = F.kary_nfly(a.k, a.stages)
        e = O.write(g, a.out)
        print(f"{a.out}: {e['routers']} routers, {e['links']} links, average degree {e['average_degree']}, "
              f"diameter {e['diameter']}, two-hop multiplicity {e['two_hop_multiplicity']}, sha256 {e['sha256']}")


if __name__ == "__main__":
    main()
