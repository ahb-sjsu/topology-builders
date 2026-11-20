"""Measure flooding and CPU in FRR IS-IS labs written by `clab`, around a link going down and coming back up.

One run of one lab:

1. Deploy it with containerlab, then wait a fixed settle time without querying the routers.
2. Check that every router has one adjacency Up per link and the same LSPs as every other router. If not, keep
   checking every 5 s (the run records how long that took).
3. Snapshot every router: the PDU counters and flooding-reduction counters of `show isis summary`, and the CPU time
   of isisd and zebra from /proc. This is the bring-up phase.
4. A quiet window: snapshot, wait the window length with no event and no queries, snapshot, then check that no
   router's LSPs changed. It measures the background work (hellos, timers) that every window contains.
5. For each chosen link in turn: snapshot, take it down, wait the window, snapshot, then check that every router
   holds the same LSPs, including a newer LSP from each end of the link. Bring the link back up and do the same.
6. Destroy the lab.

Every window is the difference between a snapshot taken just before it and one at its end, so the checks between
windows are never counted. The link windows are also reported net of the quiet window, which has the same length:
the work the event caused. Bring-up counts from the routers' start, so it includes the convergence check. A link
window's outcome is satisfied when every router holds the same LSPs and the new ones, violated when it does not,
and unknown when a router could not be read; the quiet window's is satisfied when nothing changed. Each run is one
JSON line.

Labs given together (the off and on labs of one topology) take turns, and the order alternates between repeats.
They must have the same topology file; the same links are used for all of them. Before each run the harness waits
while the hottest CPU sensor is above a limit.

Events (`kind`): `link` takes one link down and up; `node` takes every link of one router down at once and brings
them up (its neighbours lose it at the same moment, as when it fails); `multi` takes several links down at once,
chosen so that the graph stays connected, and brings them up. For `node`, the failed router is left out of the
consistency check while it is down, and each of its neighbours must have a newer LSP.

Options: `timing` reads each router's FRR log (written by labs made with `clab --timing-logs`) and records, per
router, when it first held the new LSP of every router whose LSP the event changed: built it, or received it. The
convergence time of a window is the last of these, from the moment of the event. `profile` records isisd's own CPU
accounting per event handler (`show event cpu`), cleared at the start of every window."""
import calendar
import json
import os
import random
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

from . import output as O

FORMAT = "topology-builders measure 0.4"
SECTIONS = {"TX counters per PDU type:": "tx", "RX counters per PDU type:": "rx",
            "Drop counters per PDU type:": "drop", "Flooding reduction:": "fr"}
COUNTER = re.compile(r"^\s*([A-Za-z0-9 ]+?)\s*:\s*(\d+)\s*$")
LSP = re.compile(r"^(\S+-\d\d)\s+(\*\s+)?\d+\s+0x([0-9a-fA-F]+)\s", re.MULTILINE)
EVENT_ROW = re.compile(r"^\s*(\d+)\s+(\d+)\.(\d{3})\s+(\d+)(?:\s+\d+){7}\s+[RWTEX ]{1,5}\s+(\S+)\s*$")
LOG_LSP = re.compile(r"^(\d{4})/(\d\d)/(\d\d) (\d\d):(\d\d):(\d\d)\.(\d{6}) .*ISIS-Upd \([^)]*\): "
                     r"(Rcvd|Building|Refreshed our) L\d LSP ([0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{2}-[0-9a-f]{2}), "
                     r"(?:len \d+, )?seq 0x([0-9a-f]+)")
EVENT_KINDS = ("link", "node", "multi")
TIMING_LOG = "/tmp/frr.log"


def _key(label):
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def parse_summary(text):
    """Counters from `show isis summary`: tx_*, rx_*, drop_* per PDU type and fr_* for flooding reduction (absent
    when it is off). Counters of the same name in more than one level are added."""
    out, section = {}, None
    for line in text.splitlines():
        head = line.strip()
        if head in SECTIONS:
            section = SECTIONS[head]
            continue
        m = COUNTER.match(line)
        if section and m:
            k = f"{section}_{_key(m.group(1))}"
            out[k] = out.get(k, 0) + int(m.group(2))
        else:
            section = None
    return out


def parse_database(text):
    """{LSP ID: sequence number} from `show isis database`."""
    return {m.group(1): int(m.group(3), 16) for m in LSP.finditer(text)}


def parse_event_cpu(text):
    """{handler: [CPU ms, calls]} from `show event cpu` of one daemon, summed over its pthreads. The final "Total
    Event statistics" table is left out."""
    out = {}
    for line in text.split("Total Event statistics")[0].splitlines():
        m = EVENT_ROW.match(line)
        if m:
            row = out.setdefault(m.group(5), [0.0, 0])
            row[0] = round(row[0] + int(m.group(2)) + int(m.group(3)) / 1000, 3)
            row[1] += int(m.group(4))
    return out


def parse_log_lsps(text):
    """[(epoch seconds, "Rcvd", "Building" or "Refreshed our", LSP ID, seq)] from an FRR log with `debug isis
    update-packets` and `log timestamp precision 6`. A router's own LSP is "Building" when first made and "Refreshed
    our" when regenerated. Log times are read as UTC, the time zone of FRR's containers."""
    out = []
    for line in text.splitlines():
        m = LOG_LSP.match(line)
        if m:
            y, mo, d, h, mi, sec, us = (int(x) for x in m.groups()[:7])
            t = calendar.timegm((y, mo, d, h, mi, sec)) + us / 1e6
            out.append((t, m.group(8), m.group(9), int(m.group(10), 16)))
    return out


def logged_ids(lab, lsps):
    """{LSP ID as `show isis database` prints it, e.g. "r5.00-00": as FRR's log prints it, "0000.0000.0006.00-00"}."""
    sysid = lsp_sysids(lab)
    out = {}
    for lsp in lsps:
        name, _, rest = lsp.partition(".")
        if name in sysid:
            out[lsp] = f"{sysid[name]}.{rest}"
    return out


def lsp_sysids(lab):
    """{router name: system ID as FRR logs it}, e.g. {"r0": "0000.0000.0001"}, from the NETs in lab.json."""
    return {r["name"]: ".".join(r["net"].split(".")[-4:-1]) for r in lab["routers"]}


def convergence(logs, targets, t_event):
    """When each router first held every target LSP. logs: {router: parse_log_lsps output, or None if unreadable};
    targets: {LSP ID as logged: new seq}; t_event: epoch seconds. A router holds an LSP once its log shows it built
    or received that LSP at the new sequence number or later. Returns per-router milliseconds after the event (None
    when the log never shows every target), the maximum (None if any router is missing), the median, and the
    missing routers. flood_ms is the flooding alone: for each target LSP, from the moment its originator built it
    to the moment the last router held it, the largest over the targets (None if any router is missing)."""
    per, have = {}, {}
    for r, lines in logs.items():
        if lines is None:
            per[r] = None
            continue
        latest = []
        for lsp, seq in targets.items():
            times = [t for t, _, i, s in lines if i == lsp and s >= seq]
            latest.append(min(times) if times else None)
            have[(r, lsp)] = min(times) if times else None
        per[r] = None if not latest or None in latest else round(1000 * (max(latest) - t_event), 3)
    built = {}
    for lines in logs.values():
        for t, kind, lsp, seq in lines or []:
            if kind != "Rcvd" and lsp in targets and seq >= targets[lsp]:
                built[lsp] = min(t, built.get(lsp, t))
    flood = None
    if targets and have and None not in have.values() and set(built) == set(targets):
        flood = round(1000 * max(t - built[lsp] for (_, lsp), t in have.items()), 3)
    done = sorted(v for v in per.values() if v is not None)
    missing = sorted(r for r, v in per.items() if v is None)
    mid = len(done) // 2
    median = None if not done else done[mid] if len(done) % 2 else round((done[mid - 1] + done[mid]) / 2, 3)
    return {"per_router_ms": per, "max_ms": done[-1] if done and not missing else None, "median_ms": median,
            "missing": missing, "flood_ms": flood if not missing else None}


def parse_stat(line):
    """utime + stime, in clock ticks, from one line of /proc/<pid>/stat."""
    fields = line.rsplit(")", 1)[1].split()
    return int(fields[11]) + int(fields[12])


def diff(after, before):
    return {k: after.get(k, 0) - before.get(k, 0) for k in sorted(set(after) | set(before))}


def outcome(databases, before, ends, exclude=()):
    """satisfied / violated / unknown for one window. databases: {router: {LSP: seq} or None}; before: the LSPs every
    router held before the event; ends: the routers whose LSPs must have changed (the two ends of a link, or every
    neighbour of a failed router); exclude: routers left out of the check (a failed router)."""
    databases = {r: db for r, db in databases.items() if r not in exclude}
    if any(db is None for db in databases.values()):
        return "unknown", {"unreadable": sorted(r for r, db in databases.items() if db is None)}
    reference = next(iter(databases.values()))
    differing = sorted(r for r, db in databases.items() if db != reference)
    stale = [e for e in ends if not any(lsp.startswith(f"{e}.") and seq > before.get(lsp, -1)
                                         for lsp, seq in reference.items())]
    detail = {"routers_differing": differing, "ends_without_new_lsp": stale}
    return ("satisfied" if not differing and not stale else "violated"), detail


def steady(databases, before):
    """Outcome of the quiet window: satisfied when every router still holds exactly the LSPs it held before, so the
    window saw background work only; violated when an LSP changed; unknown when a router could not be read."""
    if any(db is None for db in databases.values()):
        return "unknown", {"unreadable": sorted(r for r, db in databases.items() if db is None)}
    changed = sorted(r for r, db in databases.items() if db != before)
    return ("satisfied" if not changed else "violated"), {"routers_changed": changed}


def net(total, quiet):
    """A window's counters and CPU minus the quiet window's, which has the same length: the work the event caused.
    None when a router could not be read in either window."""
    if total["unreadable"] or quiet["unreadable"]:
        return None
    return {"counters": diff(total["counters"], quiet["counters"]),
            "cpu_ms": {k: round(v, 1) for k, v in diff(total["cpu_ms"], quiet["cpu_ms"]).items()}}


def pick_links(lab, seed, k=1):
    """k different links to take down, one after another: chosen by the seed and the topology file, so every variant
    gets the same ones. The first is the one pick_link gives."""
    n = len(lab["links"])
    if not 1 <= k <= n:
        raise ValueError(f"cannot pick {k} of {n} links")
    rng = random.Random(f"flap/{lab['source_sha256']}/{seed}")
    picked = []
    while len(picked) < k:
        i = rng.randrange(n)
        if i not in picked:
            picked.append(i)
    return [lab["links"][i] for i in picked]


def pick_link(lab, seed):
    """The link to take down: chosen by the seed and the topology file, so every variant gets the same one."""
    return pick_links(lab, seed, 1)[0]


def pick_events(lab, seed, kind="link", count=1, fail=2):
    """`count` events of one kind, chosen by the seed and the topology file, so every variant gets the same ones.
    Each is {"kind", "links"} and, for node, "router". link: the links of pick_links. node: `count` different
    routers, each with all its links. multi: `count` different sets of `fail` links each, every set chosen so that
    the graph stays connected without it."""
    if kind == "link":
        return [{"kind": "link", "links": [x]} for x in pick_links(lab, seed, count)]
    if kind not in EVENT_KINDS:
        raise ValueError(f"event kind must be one of {EVENT_KINDS}, got {kind}")
    rng = random.Random(f"{kind}/{lab['source_sha256']}/{seed}")
    routers = [r["name"] for r in lab["routers"]]
    if kind == "node":
        if not 1 <= count <= len(routers):
            raise ValueError(f"cannot pick {count} of {len(routers)} routers")
        return [{"kind": "node", "router": r, "links": [x for x in lab["links"] if r in (x["a"], x["b"])]}
                for r in rng.sample(routers, count)]
    import networkx as nx
    g = nx.Graph()
    g.add_nodes_from(routers)
    g.add_edges_from((x["a"], x["b"]) for x in lab["links"])
    if not 2 <= fail <= len(lab["links"]):
        raise ValueError(f"cannot fail {fail} of {len(lab['links'])} links at once")
    chosen, tries = [], 0
    while len(chosen) < count:
        tries += 1
        if tries > 1000 * count:
            raise ValueError(f"found fewer than {count} sets of {fail} links that keep the graph connected")
        idx = sorted(rng.sample(range(len(lab["links"])), fail))
        h = g.copy()
        h.remove_edges_from((lab["links"][i]["a"], lab["links"][i]["b"]) for i in idx)
        if idx not in chosen and nx.is_connected(h):
            chosen.append(idx)
    return [{"kind": "multi", "links": [lab["links"][i] for i in idx]} for idx in chosen]


def event_ends(event):
    """(routers whose LSP the event changes, routers left out of the check while it is down)."""
    ends = sorted({x[e] for x in event["links"] for e in ("a", "b")}, key=lambda r: int(r[1:]))
    if event["kind"] == "node":
        return [r for r in ends if r != event["router"]], [event["router"]]
    return ends, []


def wait_cool(max_temp, read=None, sleep=time.sleep, poll=30, limit=3600):
    """Wait while the hottest CPU sensor is above max_temp (deg C); return the seconds waited. No sensor: no wait."""
    read = read or (lambda: host_state().get("cpu_temp_max_c"))
    waited = 0
    while waited < limit:
        t = read()
        if t is None or t <= max_temp:
            break
        sleep(poll)
        waited += poll
    return waited


def order(labs, repeat):
    """Which labs run in repeat `repeat`: the given order, reversed on odd repeats."""
    return list(labs) if repeat % 2 == 0 else list(reversed(labs))


def host_state():
    state = {}
    try:
        with open("/proc/loadavg", encoding="utf-8") as fh:
            state["loadavg_1m"] = float(fh.read().split()[0])
    except OSError:
        pass
    temps = []
    for d in sorted(os.listdir("/sys/class/hwmon")) if os.path.isdir("/sys/class/hwmon") else []:
        base = f"/sys/class/hwmon/{d}"
        try:
            with open(f"{base}/name", encoding="utf-8") as fh:
                if fh.read().strip() != "coretemp":
                    continue
            for f in os.listdir(base):
                if f.startswith("temp") and f.endswith("_input"):
                    with open(f"{base}/{f}", encoding="utf-8") as fh:
                        temps.append(int(fh.read()) / 1000)
        except OSError:
            continue
    if temps:
        state["cpu_temp_max_c"] = max(temps)
    return state


class Lab:
    """A lab directory written by `clab`, and the commands that drive it."""

    SNAPSHOT = ("vtysh -c 'show isis summary'; echo '@@@'; getconf CLK_TCK; "
                "for d in isisd zebra; do echo \"$d $(cat /proc/$(pidof $d)/stat)\"; done")

    def __init__(self, directory, workers=16):
        self.dir = directory
        with open(os.path.join(directory, "lab.json"), encoding="utf-8") as fh:
            self.lab = json.load(fh)
        self.name = self.lab["name"]
        self.routers = [r["name"] for r in self.lab["routers"]]
        self.ports = {r["name"]: r["ports"] for r in self.lab["routers"]}
        self.pool = ThreadPoolExecutor(max_workers=workers)

    def container(self, router):
        return f"clab-{self.name}-{router}"

    def exec(self, router, script, timeout=60):
        p = subprocess.run(["docker", "exec", self.container(router), "sh", "-c", script], capture_output=True,
                           text=True, timeout=timeout, check=False)
        return p.returncode, p.stdout

    def each(self, fn):
        return dict(zip(self.routers, self.pool.map(fn, self.routers)))

    def containerlab(self, action):
        topo = f"{self.name}.clab.yml"
        args = ["containerlab", action, "-t", topo] + (["--cleanup"] if action == "destroy" else [])
        t0 = time.time()
        p = subprocess.run(args, cwd=self.dir, capture_output=True, text=True, timeout=1800, check=False)
        if p.returncode:
            raise RuntimeError(f"containerlab {action} {self.name} failed: {(p.stdout + p.stderr)[-500:]}")
        return round(time.time() - t0, 2)

    def snapshot(self, events=None):
        """Counters and CPU of every router. events="show" adds isisd's per-handler CPU accounting (`show event
        cpu`); events="clear" resets it after reading the rest."""
        script = self.SNAPSHOT
        if events == "show":
            script += "; echo '@@EV@@'; vtysh -d isisd -c 'show event cpu'"
        elif events == "clear":
            script += "; vtysh -d isisd -c 'clear event cpu' > /dev/null"

        def one(r):
            try:
                _, out = self.exec(r, script)
                out, _, ev = out.partition("@@EV@@")
                summary, rest = out.split("@@@", 1)
                lines = rest.split("\n")
                lines = [x for x in lines if x.strip()]
                tck = int(lines[0])
                cpu = {x.split()[0]: parse_stat(x.split(" ", 1)[1]) * 1000 / tck for x in lines[1:]}
                snap = {"counters": parse_summary(summary), "cpu_ms": cpu}
                if events == "show":
                    snap["event_cpu"] = parse_event_cpu(ev)
                return snap
            except (ValueError, IndexError, subprocess.TimeoutExpired):
                return None
        return self.each(one)

    def databases(self):
        def one(r):
            try:
                rc, out = self.exec(r, "vtysh -c 'show isis database'")
                return parse_database(out) if rc == 0 else None
            except subprocess.TimeoutExpired:
                return None
        return self.each(one)

    def adjacencies(self):
        def one(r):
            try:
                rc, out = self.exec(r, "vtysh -c 'show isis neighbor'")
                return sum(1 for x in out.splitlines() if re.search(r"\bUp\b", x)) if rc == 0 else None
            except subprocess.TimeoutExpired:
                return None
        return self.each(one)

    def converged(self):
        adj, dbs = self.adjacencies(), self.databases()
        if any(v is None for v in dbs.values()):
            return False, dbs
        ref = next(iter(dbs.values()))
        n = len(self.routers)
        ok = (all(adj[r] == self.ports[r] for r in self.routers) and all(db == ref for db in dbs.values())
              and len({lsp.split(".")[0] for lsp in ref}) == n)
        return ok, dbs

    def link(self, router, port, state):
        rc, _ = self.exec(router, f"ip link set {port} {state}")
        if rc:
            raise RuntimeError(f"ip link set {port} {state} failed on {router}")

    def apply(self, event, state):
        """Set the event's links down or up, every router's share in its own `docker exec`, all at once; return the
        earliest time (epoch seconds, read inside the routers) at which one of them had done so. A link is set from
        its a end, except for a node event, which sets every port of the failed router itself."""
        ports = {}
        for x in event["links"]:
            if event["kind"] == "node":
                end = "a" if x["a"] == event["router"] else "b"
            else:
                end = "a"
            ports.setdefault(x[end], []).append(x[f"{end}_port"])

        def one(router):
            script = "; ".join(f"ip link set {p} {state}" for p in ports[router]) + "; date +%s.%N"
            rc, out = self.exec(router, script)
            if rc:
                raise RuntimeError(f"setting {ports[router]} {state} failed on {router}")
            return float(out.split()[-1])
        return min(self.pool.map(one, list(ports)))

    def log_path(self, router):
        return TIMING_LOG

    def clear_logs(self):
        self.each(lambda r: self.exec(r, f": > {self.log_path(r)}"))

    def read_logs(self):
        def one(r):
            try:
                rc, out = self.exec(r, f"grep -E 'ISIS-Upd .*: (Rcvd|Building|Refreshed our) L' {self.log_path(r)}")
                return parse_log_lsps(out) if rc in (0, 1) else None
            except subprocess.TimeoutExpired:
                return None
        return self.each(one)


class NetnsLab(Lab):
    """The same lab with every router in a network namespace of this machine instead of a container: no Docker or
    containerlab. Each router's FRR daemons run as root with `-N <router>`, so each has its own configuration and
    sockets under /etc/frr/<router> and /var/run/frr/<router>; links are veth pairs. It needs root, or a user and
    mount namespace in which this process is root (`unshare -Urnm`), which is how it runs on Colab. Commands enter a
    router with `nsenter --net=`, not `ip netns exec` or `ip -n`: those remount /sys, which a user namespace inside a
    container is usually not allowed to do. The FRR binaries are taken from TB_FRR_LIB (default /usr/lib/frr)."""

    DAEMONS = ("mgmtd", "zebra", "staticd", "isisd")
    NETNS_DIR = "/run/netns"

    def __init__(self, directory, workers=16, etc_base="/etc/frr", run_base="/var/run/frr", frr_lib=None):
        super().__init__(directory, workers)
        self.etc_base, self.run_base = etc_base, run_base
        self.frr_lib = frr_lib or os.environ.get("TB_FRR_LIB", "/usr/lib/frr")

    def run_dir(self, router):
        return f"{self.run_base}/{router}"

    def enter(self, router):
        return ["nsenter", f"--net={self.NETNS_DIR}/{router}", "--"]

    def log_path(self, router):
        return f"{self.run_dir(router)}/frr.log"

    def exec(self, router, script, timeout=60):
        # vtysh and pidof are redefined so the scripts written for containers address this router's daemons.
        pre = (f'vtysh() {{ command vtysh -N {router} "$@"; }}; '
               f"pidof() {{ cat {self.run_dir(router)}/$1.pid; }}; ")
        p = subprocess.run(self.enter(router) + ["sh", "-c", pre + script], capture_output=True, text=True,
                           timeout=timeout, check=False)
        return p.returncode, p.stdout

    def _run(self, args, timeout=120):
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        if p.returncode:
            raise RuntimeError(f"{' '.join(args)} failed: {(p.stdout + p.stderr)[-300:]}")

    def commands_deploy(self):
        """The commands deploy runs, in order (argument lists), after the configuration files are written."""
        cmds = []
        for r in self.routers:
            cmds += [["ip", "netns", "add", r], self.enter(r) + ["ip", "link", "set", "lo", "up"]]
        for j, x in enumerate(self.lab["links"]):
            ta, tb = f"tbv{j}a", f"tbv{j}b"
            cmds += [["ip", "link", "add", ta, "netns", x["a"], "type", "veth", "peer", "name", tb, "netns", x["b"]],
                     self.enter(x["a"]) + ["ip", "link", "set", ta, "name", x["a_port"], "up"],
                     self.enter(x["b"]) + ["ip", "link", "set", tb, "name", x["b_port"], "up"]]
        for d in self.DAEMONS:
            for r in self.routers:
                rd = self.run_dir(r)
                cmds.append(self.enter(r) + [f"{self.frr_lib}/{d}", "-N", r, "-d", "-u", "root", "-g", "root", "-A",
                                             "127.0.0.1", "-i", f"{rd}/{d}.pid", "-z", f"{rd}/zserv.api"]
                            + (["-s", "90000000"] if d == "zebra" else []))
        return cmds

    def _write_configs(self):
        for r in self.routers:
            etc, rd = f"{self.etc_base}/{r}", self.run_dir(r)
            os.makedirs(etc, exist_ok=True)
            os.makedirs(rd, exist_ok=True)
            with open(os.path.join(self.dir, r, "frr.conf"), encoding="utf-8") as fh:
                conf = fh.read().replace(f"log file {TIMING_LOG} ", f"log file {self.log_path(r)} ")
            with open(f"{etc}/frr.conf", "w", encoding="utf-8") as fh:
                fh.write(conf)
            with open(f"{etc}/vtysh.conf", "w", encoding="utf-8") as fh:
                fh.write("service integrated-vtysh-config\n")

    def containerlab(self, action):
        t0 = time.time()
        if action == "deploy":
            self._write_configs()
            first_zebra = self.enter(self.routers[0]) + [f"{self.frr_lib}/zebra"]
            for cmd in self.commands_deploy():
                if cmd[:len(first_zebra)] == first_zebra:
                    time.sleep(1)  # mgmtd of every router up before the daemons that connect to it
                self._run(cmd)
            time.sleep(1)
            for r in self.routers:
                self._run(self.enter(r) + ["vtysh", "-N", r, "-b"])
        else:
            pids = []
            for r in self.routers:
                for d in reversed(self.DAEMONS):
                    try:
                        with open(f"{self.run_dir(r)}/{d}.pid", encoding="utf-8") as fh:
                            pid = int(fh.read().strip())
                        os.kill(pid, 15)
                        pids.append(pid)
                    except (OSError, ValueError):
                        pass
            deadline = time.time() + 30
            while pids and time.time() < deadline:  # gone before the next lab reuses their directories
                pids = [p for p in pids if os.path.exists(f"/proc/{p}")]
                time.sleep(0.2)
            for r in self.routers:
                subprocess.run(["ip", "netns", "del", r], capture_output=True, check=False)
        return round(time.time() - t0, 2)


BACKENDS = {"docker": Lab, "netns": NetnsLab}


def totals(snap_after, snap_before=None):
    """Sum over routers of counter and CPU differences; per-router differences alongside."""
    per, total, cpu = {}, {}, {}
    for r, after in snap_after.items():
        before = (snap_before or {}).get(r) or {"counters": {}, "cpu_ms": {}}
        if after is None:
            per[r] = None
            continue
        d = diff(after["counters"], before["counters"])
        c = {k: round(v, 1) for k, v in diff(after["cpu_ms"], before["cpu_ms"]).items()}
        per[r] = {"counters": d, "cpu_ms": c}
        for k, v in d.items():
            total[k] = total.get(k, 0) + v
        for k, v in c.items():
            cpu[k] = round(cpu.get(k, 0) + v, 1)
    result = {"counters": total, "cpu_ms": cpu, "unreadable": sorted(r for r, v in per.items() if v is None)}
    if any(v and "event_cpu" in v for v in snap_after.values()):
        ev = {}
        for v in snap_after.values():
            for k, (ms, calls) in ((v or {}).get("event_cpu") or {}).items():
                row = ev.setdefault(k, [0.0, 0])
                row[0], row[1] = round(row[0] + ms, 3), row[1] + calls
        result["event_cpu"] = ev
    return result, per


def _brief(link):
    return {k: link[k] for k in ("a", "a_port", "b", "b_port")}


def run_one(lab, events, settle, window, max_wait, repeat, position, timing=False, profile=False):
    rec = {"format": FORMAT, "builder": O.builder_info(), "lab": lab.name, "settings": lab.lab["settings"],
           "source": lab.lab["source"], "source_sha256": lab.lab["source_sha256"], "topology": lab.lab["topology"],
           "repeat": repeat, "position": position, "settle_s": settle, "window_s": window,
           "timing": timing, "profile": profile,
           "events": [dict(e, links=[_brief(x) for x in e["links"]]) for e in events],
           "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "host_start": host_state(), "phases": []}
    if all(e["kind"] == "link" for e in events):
        rec["links"] = [_brief(e["links"][0]) for e in events]
    try:
        rec["deploy_s"] = lab.containerlab("deploy")
    except RuntimeError:
        lab.containerlab("destroy")
        raise
    try:
        time.sleep(settle)
        t0, (ok, dbs) = time.time(), lab.converged()
        while not ok and time.time() - t0 < max_wait:
            time.sleep(5)
            ok, dbs = lab.converged()
        rec["converged"], rec["extra_wait_s"] = ok, round(time.time() - t0, 1)
        total, per = totals(lab.snapshot(events="show" if profile else None))
        rec["phases"].append({"phase": "bring-up", "seconds": settle, **total, "per_router": per,
                              "outcome": "satisfied" if ok else "violated"})
        before_db = next(iter(dbs.values())) if ok else {}

        def measured_window(event=None):
            # A snapshot right before the window, after any checks, so the checks never fall inside a window.
            base = lab.snapshot(events="clear" if profile else None)
            if timing:
                lab.clear_logs()
            t_event = event() if event else None
            time.sleep(window)
            total, per = totals(lab.snapshot(events="show" if profile else None), base)
            return total, per, t_event

        quiet, per, _ = measured_window()
        dbs = lab.databases()
        result, detail = steady(dbs, before_db)
        rec["phases"].append({"phase": "quiet", "seconds": window, **quiet, "per_router": per, "outcome": result,
                              "detail": detail})
        if result != "unknown":
            before_db = next(iter(dbs.values()))
        for j, ev in enumerate(events):
            ends, failed = event_ends(ev)
            for state in ("down", "up"):
                if state == "up" and failed:
                    ends, failed = sorted(set(ends) | set(failed), key=lambda r: int(r[1:])), []
                total, per, t_event = measured_window(lambda s=state, e=ev: lab.apply(e, s))
                dbs = lab.databases()
                result, detail = outcome(dbs, before_db, ends, exclude=failed)
                phase = {"phase": f"{ev['kind']}-{state}", "event": j, "seconds": window, **total,
                         "net_of_quiet": net(total, quiet), "per_router": per, "outcome": result, "detail": detail}
                if ev["kind"] == "link":
                    phase["link"] = j
                if profile and "event_cpu" in total and "event_cpu" in quiet:
                    phase["net_of_quiet"] = dict(phase["net_of_quiet"] or {}, event_cpu_ms={
                        k: round(total["event_cpu"].get(k, [0, 0])[0] - quiet["event_cpu"].get(k, [0, 0])[0], 3)
                        for k in sorted(set(total["event_cpu"]) | set(quiet["event_cpu"]))})
                ref = next((db for r, db in dbs.items() if r not in failed and db is not None), None)
                if timing and ref is not None:
                    new = {lsp: seq for lsp, seq in ref.items()
                           if lsp.split(".")[0] in ends and seq > before_db.get(lsp, -1)}
                    ids = logged_ids(lab.lab, new)
                    logs = {r: v for r, v in lab.read_logs().items() if r not in failed}
                    phase["timing"] = dict(convergence(logs, {ids[k]: v for k, v in new.items() if k in ids},
                                                       t_event), event_epoch=t_event, targets=new)
                rec["phases"].append(phase)
                if result != "unknown" and ref is not None:
                    before_db = ref
    finally:
        rec["host_end"] = host_state()
        rec["destroy_s"] = lab.containerlab("destroy")
        rec["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return rec


def run(directories, repeat=1, settle=30, window=30, seed=1, out="measurements.jsonl", max_wait=120, links=1,
        max_temp=80.0, kind="link", fail=2, timing=False, profile=False, backend="docker"):
    """`links` is the number of events per run of each kind; `kind` is one kind or several, comma-separated, run in
    that order (link,node,multi: the links first, then the routers, then the sets of links)."""
    labs = [BACKENDS[backend](d) for d in directories]
    sources = {lab.lab["source_sha256"] for lab in labs}
    if len(sources) != 1:
        raise ValueError("the labs were written from different topology files")
    if timing and not all(lab.lab["settings"].get("timing_logs") for lab in labs):
        raise ValueError("timing needs labs written with clab --timing-logs")
    chosen = [e for k in kind.split(",") for e in pick_events(labs[0].lab, seed, k, links, fail)]
    records = []
    for i in range(repeat):
        for position, lab in enumerate(order(labs, i)):
            cooled = wait_cool(max_temp)
            rec = run_one(lab, chosen, settle, window, max_wait, i, position, timing=timing, profile=profile)
            rec["cool_wait_s"] = cooled
            with open(out, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, sort_keys=True) + "\n")
            records.append(rec)
            print(line(rec), flush=True)
    return records


def summarize(records):
    """Rows of (lab, flood reduction, phase, runs, mean LSPs sent, mean suppressed sends, mean isisd ms,
    outcomes) over all runs."""
    groups = {}
    for rec in records:
        for p in rec["phases"]:
            key = (rec["lab"], rec["settings"]["flood_reduction"], p["phase"])
            groups.setdefault(key, []).append(p)
    rows = []
    for (lab, fr, phase), ps in groups.items():
        n = len(ps)
        outcomes = {}
        for p in ps:
            outcomes[p["outcome"]] = outcomes.get(p["outcome"], 0) + 1
        nets = [p["net_of_quiet"]["cpu_ms"].get("isisd", 0) for p in ps if p.get("net_of_quiet")]
        rows.append({"lab": lab, "flood_reduction": fr, "phase": phase, "runs": n,
                     "lsps_sent": round(sum(p["counters"].get("tx_l2_lsp", 0) for p in ps) / n, 1),
                     "suppressed_sends": round(sum(p["counters"].get("fr_suppressed_sends", 0) for p in ps) / n, 1),
                     "isisd_ms": round(sum(p["cpu_ms"].get("isisd", 0) for p in ps) / n, 1),
                     "isisd_net_ms": round(sum(nets) / len(nets), 1) if nets else None,
                     "outcomes": outcomes})
    return rows


def line(rec):
    """One line per run: per phase, LSPs sent, suppressed sends, isisd CPU, outcome."""
    fr = "on" if rec["settings"]["flood_reduction"] else "off"
    parts = [f"{rec['lab']} repeat {rec['repeat']} flood-reduction {fr}:"]
    for p in rec["phases"]:
        c = p["counters"]
        cpu = f"isisd {p['cpu_ms'].get('isisd', 0):.0f} ms"
        if p.get("net_of_quiet"):
            cpu += f" ({p['net_of_quiet']['cpu_ms'].get('isisd', 0):+.0f} ms net of quiet)"
        conv = ""
        if p.get("timing"):
            conv = f", converged {p['timing']['max_ms']} ms"
        parts.append(f"{p['phase']} LSPs sent {c.get('tx_l2_lsp', 0)}, suppressed {c.get('fr_suppressed_sends', 0)}, "
                     f"{cpu}{conv}, {p['outcome']};")
    return " ".join(parts)
