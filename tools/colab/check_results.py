"""Pass/fail for a lab run: every run converged, every window was consistent, and no router missed a new LSP.

    python3 check_results.py measurements.jsonl
"""
import json
import sys


def problems(path):
    bad = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            if not r["converged"]:
                bad.append(f"{r['lab']}: did not converge")
            for p in r["phases"]:
                missing = (p.get("timing") or {}).get("missing")
                if p["outcome"] != "satisfied" or missing:
                    bad.append(f"{r['lab']} {p['phase']}: {p['outcome']}" + (f", missing {missing}" if missing else ""))
    return bad


if __name__ == "__main__":
    found = problems(sys.argv[1])
    print("\n".join(found) if found else "every run converged and every window was consistent")
    sys.exit(1 if found else 0)
