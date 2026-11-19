"""Measure flooding and CPU in FRR IS-IS labs written by `clab`, around a link going down and coming back up.

One run of one lab:

1. Deploy it with containerlab, then wait a fixed settle time without querying the routers.
2. Check that every router has one adjacency Up per link and the same LSPs as every other router. If not, keep
   checking every 5 s (the run records how long that took).
3. Snapshot every router: the PDU counters and flooding-reduction counters of `show isis summary`, and the CPU time
   of isisd and zebra from /proc. This is the bring-up phase.
4. A quiet window: snapshot, wait the window length with no event and no queries, snapshot, then check that no
   router's LSPs changed. It measures the background work (hellos, timers) that every window contains.
5. Take one link down: snapshot, take it down, wait the window, snapshot, then check that every router holds the
   same LSPs, including a newer LSP from each end of the link. Bring the link back up and do the same again.
6. Destroy the lab.

Every window is the difference between a snapshot taken just before it and one at its end, so the checks between
windows are never counted. The link windows are also reported net of the quiet window, which has the same length:
the work the event caused. Bring-up counts from the routers' start, so it includes the convergence check. A link
window's outcome is satisfied when every router holds the same LSPs and the new ones, violated when it does not,
and unknown when a router could not be read; the quiet window's is satisfied when nothing changed. Each run is one
JSON line.

Labs given together (the off and on labs of one topology) take turns, and the order alternates between repeats.
They must have the same topology file; the same link is used for all of them."""
import json
import os
import random
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

from . import output as O

FORMAT = "topology-builders measure 0.2"
SECTIONS = {"TX counters per PDU type:": "tx", "RX counters per PDU type:": "rx",
            "Drop counters per PDU type:": "drop", "Flooding reduction:": "fr"}
COUNTER = re.compile(r"^\s*([A-Za-z0-9 ]+?)\s*:\s*(\d+)\s*$")
LSP = re.compile(r"^(\S+-\d\d)\s+(\*\s+)?\d+\s+0x([0-9a-fA-F]+)\s", re.MULTILINE)


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


def parse_stat(line):
    """utime + stime, in clock ticks, from one line of /proc/<pid>/stat."""
    fields = line.rsplit(")", 1)[1].split()
    return int(fields[11]) + int(fields[12])


def diff(after, before):
    return {k: after.get(k, 0) - before.get(k, 0) for k in sorted(set(after) | set(before))}


def outcome(databases, before, ends):
    """satisfied / violated / unknown for one window. databases: {router: {LSP: seq} or None}; before: the LSPs every
    router held before the event; ends: the two routers of the link, whose LSPs must have changed."""
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


def pick_link(lab, seed):
    """The link to take down: chosen by the seed and the topology file, so every variant gets the same one."""
    rng = random.Random(f"flap/{lab['source_sha256']}/{seed}")
    return lab["links"][rng.randrange(len(lab["links"]))]


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

    def snapshot(self):
        def one(r):
            try:
                _, out = self.exec(r, self.SNAPSHOT)
                summary, rest = out.split("@@@", 1)
                lines = rest.split("\n")
                lines = [x for x in lines if x.strip()]
                tck = int(lines[0])
                cpu = {x.split()[0]: parse_stat(x.split(" ", 1)[1]) * 1000 / tck for x in lines[1:]}
                return {"counters": parse_summary(summary), "cpu_ms": cpu}
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
    return {"counters": total, "cpu_ms": cpu, "unreadable": sorted(r for r, v in per.items() if v is None)}, per


def run_one(lab, link, settle, window, max_wait, repeat, position):
    rec = {"format": FORMAT, "builder": O.builder_info(), "lab": lab.name, "settings": lab.lab["settings"],
           "source": lab.lab["source"], "source_sha256": lab.lab["source_sha256"], "topology": lab.lab["topology"],
           "repeat": repeat, "position": position, "settle_s": settle, "window_s": window,
           "link": {k: link[k] for k in ("a", "a_port", "b", "b_port")},
           "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "host_start": host_state(), "phases": []}
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
        total, per = totals(lab.snapshot())
        rec["phases"].append({"phase": "bring-up", "seconds": settle, **total, "per_router": per,
                              "outcome": "satisfied" if ok else "violated"})
        before_db = next(iter(dbs.values())) if ok else {}

        def measured_window(event=None):
            # A snapshot right before the window, after any checks, so the checks never fall inside a window.
            base = lab.snapshot()
            if event:
                event()
            time.sleep(window)
            return totals(lab.snapshot(), base)

        quiet, per = measured_window()
        dbs = lab.databases()
        result, detail = steady(dbs, before_db)
        rec["phases"].append({"phase": "quiet", "seconds": window, **quiet, "per_router": per, "outcome": result,
                              "detail": detail})
        if result != "unknown":
            before_db = next(iter(dbs.values()))
        for phase, state in (("link-down", "down"), ("link-up", "up")):
            total, per = measured_window(lambda s=state: lab.link(link["a"], link["a_port"], s))
            dbs = lab.databases()
            result, detail = outcome(dbs, before_db, (link["a"], link["b"]))
            rec["phases"].append({"phase": phase, "seconds": window, **total, "net_of_quiet": net(total, quiet),
                                  "per_router": per, "outcome": result, "detail": detail})
            if result != "unknown":
                before_db = next(iter(dbs.values()))
    finally:
        rec["host_end"] = host_state()
        rec["destroy_s"] = lab.containerlab("destroy")
        rec["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return rec


def run(directories, repeat=1, settle=30, window=30, seed=1, out="measurements.jsonl", max_wait=120):
    labs = [Lab(d) for d in directories]
    sources = {lab.lab["source_sha256"] for lab in labs}
    if len(sources) != 1:
        raise ValueError("the labs were written from different topology files")
    link = pick_link(labs[0].lab, seed)
    records = []
    for i in range(repeat):
        for position, lab in enumerate(order(labs, i)):
            rec = run_one(lab, link, settle, window, max_wait, i, position)
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
        parts.append(f"{p['phase']} LSPs sent {c.get('tx_l2_lsp', 0)}, suppressed {c.get('fr_suppressed_sends', 0)}, "
                     f"{cpu}, {p['outcome']};")
    return " ".join(parts)
