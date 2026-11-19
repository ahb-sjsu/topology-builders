"""Check a deployed lab: every router has one IS-IS adjacency Up per link, and holds an LSP from every router.

Usage: python3 check_isis.py <lab dir with lab.json> [timeout seconds]"""
import json
import re
import subprocess
import sys
import time


def vtysh(container, command):
    p = subprocess.run(["docker", "exec", container, "vtysh", "-c", command], capture_output=True, text=True,
                       timeout=60, check=False)
    return p.stdout + p.stderr


def state(lab):
    out = {}
    for r in lab["routers"]:
        c = f"clab-{lab['name']}-{r['name']}"
        up = sum(1 for line in vtysh(c, "show isis neighbor").splitlines() if re.search(r"\bUp\b", line))
        lsps = {m.group(1) for m in re.finditer(r"^\s*(\S+)\.00-\d\d\s", vtysh(c, "show isis database"), re.MULTILINE)}
        out[r["name"]] = (up, r["ports"], len(lsps))
    return out


def main(lab_dir, timeout):
    with open(f"{lab_dir}/lab.json", encoding="utf-8") as fh:
        lab = json.load(fh)
    n = len(lab["routers"])
    t0 = time.time()
    while True:
        s = state(lab)
        bad = {k: v for k, v in s.items() if v[0] != v[1] or v[2] != n}
        if not bad or time.time() - t0 > timeout:
            break
        time.sleep(5)
    print(f"lab {lab['name']}: {n} routers, {len(lab['links'])} links, after {time.time() - t0:.0f} s: "
          f"adjacencies up = links on {sum(v[0] == v[1] for v in s.values())}/{n} routers; "
          f"full database ({n} LSPs) on {sum(v[2] == n for v in s.values())}/{n}")
    for k, v in sorted(bad.items(), key=lambda kv: int(kv[0][1:]))[:10]:
        print(f"  {k}: {v[0]} up of {v[1]} ports, {v[2]} LSPs")
    sys.exit(0 if not bad else 1)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 120)
