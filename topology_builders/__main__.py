"""Command line: python -m topology_builders {sweep, zoo, build} ...  Run with -h for the options."""
import argparse
import os
import sys
import time

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
    print(f"{'file':<{w}}  routers  links  avg degree  diameter  seconds")
    for e in entries:
        print(f"{e['file']:<{w}}  {e['routers']:>7}  {e['links']:>5}  {e['average_degree']:>10}  "
              f"{str(e['diameter']):>8}  {e.pop('_seconds'):>7}")


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
    b.add_argument("family", choices=("random-regular", "leaf-spine", "flattened-butterfly", "k-ary-n-fly"))
    b.add_argument("--routers", type=int, help="random-regular")
    b.add_argument("--degree", type=int, help="random-regular")
    b.add_argument("--seed", type=int, default=1, help="random-regular (default 1)")
    b.add_argument("--leaves", type=int, help="leaf-spine")
    b.add_argument("--spines", type=int, help="leaf-spine")
    b.add_argument("--radices", help="flattened-butterfly, comma-separated, e.g. 8,8")
    b.add_argument("--k", type=int, help="k-ary-n-fly")
    b.add_argument("--stages", type=int, help="k-ary-n-fly")
    b.add_argument("--out", required=True, help="output file")

    a = p.parse_args(argv)
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
    else:
        if a.family == "random-regular":
            g = F.random_regular(a.routers, a.degree, a.seed)
        elif a.family == "leaf-spine":
            g = F.leaf_spine(a.leaves, a.spines)
        elif a.family == "flattened-butterfly":
            g = F.flattened_butterfly(_ints(a.radices))
        else:
            g = F.kary_nfly(a.k, a.stages)
        e = O.write(g, a.out)
        print(f"{a.out}: {e['routers']} routers, {e['links']} links, average degree {e['average_degree']}, "
              f"diameter {e['diameter']}, sha256 {e['sha256']}")


if __name__ == "__main__":
    main()
