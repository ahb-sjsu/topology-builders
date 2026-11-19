"""Turn a topology file into a containerlab lab of FRR routers running IS-IS.

The configuration follows the topotest of FRR's distoptflood implementation (FRR pull request 24128,
tests/topotests/isis_flood_reduction_topo1): level-2-only; every link point-to-point with a /31; a passive loopback
/32; hello interval 1 s with multiplier 3; lsp-gen-interval 2. Flooding reduction is the single line
`flood-reduction` under `router isis`, written only when it is switched on, so the configuration with it off also
loads on FRR builds that lack the change.

Node kinds: `linux` (the default) mounts frr.conf, daemons and vtysh.conf into any FRR image and works with every
containerlab version; `frr` is containerlab's own FRR kind, which needs containerlab 0.80.0 or later.  A CPU set
(containerlab's `cpu-set`, e.g. "12-23") confines every router of the lab to those CPUs, so a dense lab cannot take
the whole host.

Timing logs (`timing_logs`) make every router log each LSP it builds or receives, with microsecond timestamps, to
/tmp/frr.log, for `measure --timing`. They cost CPU, so labs with them are for timing, not for CPU figures.

Addresses: router i has loopback 10.255.0.0 + i + 1 and system ID i + 1 in hexadecimal; link j has
10.0.0.0 + 2j and + 2j + 1.  Ports are numbered eth1, eth2, ... on each router in the order of its links in the
sorted link list."""
import hashlib
import ipaddress
import json
import os
import re

from . import output as O

LOOPBACKS = ipaddress.ip_network("10.255.0.0/16")
LINKS = ipaddress.ip_network("10.0.0.0/9")
IMAGES = {"linux": "quay.io/frrouting/frr:10.7.1", "frr": "quay.io/frrouting/frr:containerlab-10.7.1"}
FORMAT = "topology-builders containerlab-frr-isis 0.1"
DAEMONS = ("bgpd", "ospfd", "ospf6d", "ripd", "ripngd", "isisd", "pimd", "pim6d", "ldpd", "nhrpd", "eigrpd",
           "babeld", "sharpd", "pbrd", "bfdd", "fabricd", "vrrpd", "pathd")


def lab_name(text):
    """A containerlab lab name from a file name: lower case letters, digits and hyphens."""
    name = re.sub(r"[^a-z0-9-]+", "-", text.lower()).strip("-")[:48].strip("-")
    if not name:
        raise ValueError(f"no usable lab name in {text!r}")
    return name


def _router_names(g):
    """Map every node to r0, r1, ...  Files from this package already use those names; other node-link files
    (TopoHub's, for one) are renamed in sorted order, numerically when every id is an integer."""
    nodes = list(g.nodes)
    if all(re.fullmatch(r"r\d+", str(v)) for v in nodes):
        return {v: v for v in nodes}
    try:
        order = sorted(nodes, key=lambda v: int(v))
    except (TypeError, ValueError):
        order = sorted(nodes, key=str)
    return {v: f"r{i}" for i, v in enumerate(order)}


def plan(g, area="49.0001"):
    """Routers and links with their ports, addresses and IS-IS NETs.  Returns (routers, links)."""
    names = _router_names(g)
    order = sorted(g.nodes, key=lambda v: int(names[v][1:]))
    if len(order) > LOOPBACKS.num_addresses - 2:
        raise ValueError(f"{len(order)} routers is more than the {LOOPBACKS.num_addresses - 2} loopbacks")
    index = {v: i for i, v in enumerate(order)}
    edges = sorted((tuple(sorted(e, key=index.get)) for e in g.edges if e[0] != e[1]),
                   key=lambda e: (index[e[0]], index[e[1]]))
    if len(edges) > LINKS.num_addresses // 2:
        raise ValueError(f"{len(edges)} links is more than the {LINKS.num_addresses // 2} /31s available")
    ports = {v: 0 for v in order}
    links = []
    for j, (u, v) in enumerate(edges):
        ports[u] += 1
        ports[v] += 1
        base = LINKS.network_address + 2 * j
        link = {"a": names[u], "a_port": f"eth{ports[u]}", "a_address": f"{base}/31",
                "b": names[v], "b_port": f"eth{ports[v]}", "b_address": f"{base + 1}/31"}
        metric = g.edges[u, v].get("metric")
        if metric is not None:
            link["metric"] = int(metric)
        links.append(link)
    routers = []
    for i, v in enumerate(order):
        sid = f"{i + 1:012x}"
        r = {"name": names[v], "loopback": f"{LOOPBACKS.network_address + i + 1}/32",
             "net": f"{area}.{sid[0:4]}.{sid[4:8]}.{sid[8:12]}.00", "ports": ports[v]}
        if names[v] != v:
            r["original_id"] = v
        routers.append(r)
    return routers, links


def frr_conf(router, interfaces, settings):
    """FRR configuration of one router.  `interfaces`: (port, address, metric or None), in port order."""
    s = settings
    lines = ["frr defaults traditional", f"hostname {router['name']}", "log stdout informational", "!"]
    if s["debug_flooding"]:
        lines += ["debug isis flooding", "!"]
    if s.get("timing_logs"):
        lines += ["log file /tmp/frr.log debugging", "log timestamp precision 6", "debug isis update-packets", "!"]
    lines += ["interface lo", f" ip address {router['loopback']}", " ip router isis 1", " isis passive", "exit",
              "!"]
    for port, address, metric in interfaces:
        lines += [f"interface {port}", f" ip address {address}", " ip router isis 1",
                  " isis network point-to-point", f" isis hello-interval {s['hello_interval']}",
                  f" isis hello-multiplier {s['hello_multiplier']}"]
        if metric is not None:
            lines.append(f" isis metric {metric}")
        lines += ["exit", "!"]
    lines += ["router isis 1", " is-type level-2-only", f" net {router['net']}",
              f" lsp-gen-interval {s['lsp_gen_interval']}"]
    if s["flood_reduction"]:
        lines.append(" flood-reduction")
    lines += ["exit", "!"]
    return "\n".join(lines) + "\n"


def daemons_file():
    """The daemons file for the linux kind: isisd only (zebra, mgmtd, staticd and watchfrr always run)."""
    lines = ["# Written by topology-builders. zebra, mgmtd, staticd and watchfrr always run."]
    lines += [f"{d}={'yes' if d == 'isisd' else 'no'}" for d in DAEMONS]
    lines += ["vtysh_enable=yes", 'zebra_options="  -A 127.0.0.1 -s 90000000"', 'mgmtd_options="  -A 127.0.0.1"',
              'isisd_options="  -A 127.0.0.1"', 'staticd_options="-A 127.0.0.1"']
    return "\n".join(lines) + "\n"


def topology_yaml(name, routers, links, kind, image, cpu_set=None):
    lines = [f"name: {name}", "", "topology:", "  kinds:", f"    {kind}:", f"      image: {image}"]
    if cpu_set:
        lines.append(f'      cpu-set: "{cpu_set}"')
    if kind == "frr":
        lines += ["      daemons:", "        - isisd"]
    lines.append("  nodes:")
    for r in routers:
        n = r["name"]
        lines += [f"    {n}:", f"      kind: {kind}"]
        if kind == "frr":
            lines.append(f"      startup-config: {n}/frr.conf")
        else:
            lines += ["      binds:", f"        - {n}/frr.conf:/etc/frr/frr.conf",
                      f"        - {n}/daemons:/etc/frr/daemons", f"        - {n}/vtysh.conf:/etc/frr/vtysh.conf"]
    lines.append("  links:")
    for x in links:
        lines.append(f'    - endpoints: ["{x["a"]}:{x["a_port"]}", "{x["b"]}:{x["b_port"]}"]')
    return "\n".join(lines) + "\n"


def write_lab(source, out, name=None, flood_reduction=False, kind="linux", image=None, hello_interval=1,
              hello_multiplier=3, lsp_gen_interval=2, area="49.0001", debug_flooding=False, cpu_set=None,
              timing_logs=False):
    """Write one lab into directory `out`; return its manifest."""
    if kind not in IMAGES:
        raise ValueError(f"kind must be one of {sorted(IMAGES)}, got {kind}")
    if cpu_set is not None and not re.fullmatch(r"\d+(-\d+)?(,\d+(-\d+)?)*", cpu_set):
        raise ValueError(f"a CPU set is a list like 12-23,36-43, got {cpu_set!r}")
    with open(source, "rb") as fh:
        source_sha = hashlib.sha256(fh.read()).hexdigest()
    g = O.read(source)
    name = lab_name(name or os.path.splitext(os.path.basename(source))[0])
    settings = {"flood_reduction": bool(flood_reduction), "kind": kind, "image": image or IMAGES[kind],
                "hello_interval": hello_interval, "hello_multiplier": hello_multiplier,
                "lsp_gen_interval": lsp_gen_interval, "area": area, "debug_flooding": bool(debug_flooding)}
    if cpu_set:
        settings["cpu_set"] = cpu_set
    if timing_logs:
        settings["timing_logs"] = True
    routers, links = plan(g, area)
    interfaces = {r["name"]: [] for r in routers}
    for x in links:
        interfaces[x["a"]].append((x["a_port"], x["a_address"], x.get("metric")))
        interfaces[x["b"]].append((x["b_port"], x["b_address"], x.get("metric")))
    os.makedirs(out, exist_ok=True)
    files = []

    def put(rel, text):
        data = text.encode("utf-8")
        path = os.path.join(out, rel)
        os.makedirs(os.path.dirname(path) or out, exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)
        files.append({"file": rel, "sha256": hashlib.sha256(data).hexdigest()})

    put(f"{name}.clab.yml", topology_yaml(name, routers, links, kind, settings["image"], cpu_set))
    for r in routers:
        ports = sorted(interfaces[r["name"]], key=lambda p: int(p[0][3:]))
        put(f"{r['name']}/frr.conf", frr_conf(r, ports, settings))
        if kind == "linux":
            put(f"{r['name']}/daemons", daemons_file())
            put(f"{r['name']}/vtysh.conf", "service integrated-vtysh-config\n")
    lab = {"name": name, "settings": settings, "source": os.path.basename(source), "source_sha256": source_sha,
           "topology": {k: g.graph.get(k) for k in ("family", "parameters", "routers", "links", "average_degree")},
           "routers": routers, "links": links}
    put("lab.json", json.dumps(lab, sort_keys=True, indent=1) + "\n")
    manifest = {"format": FORMAT, "builder": O.builder_info(), "name": name, "settings": settings,
                "source": os.path.basename(source), "source_sha256": source_sha,
                "routers": len(routers), "links": len(links), "files": files}
    with open(os.path.join(out, "manifest.json"), "wb") as fh:
        fh.write((json.dumps(manifest, sort_keys=True, indent=1) + "\n").encode("utf-8"))
    return manifest
