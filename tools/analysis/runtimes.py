"""Run times per campaign: for each folder in `results/` with a measurements file, the number of runs (one lab variant
deployed, measured and destroyed), the time each run took from its start to its end, and the campaign's span.

    python runtimes.py <topology-builders results folder>
"""
import calendar
import gzip
import json
import os
import sys
import time
from statistics import median


def epoch(stamp):
    return calendar.timegm(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ"))


def main(results):
    print(f"{'folder':<22} {'runs':>5} {'routers':>9} {'run, min':>18} {'all runs, h':>11}  span (UTC)")
    for folder in sorted(os.listdir(results)):
        path = os.path.join(results, folder, "measurements.jsonl.gz")
        if not os.path.exists(path):
            continue
        runs = []
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    r = json.loads(line)
                    if r.get("started") and r.get("finished"):
                        runs.append((epoch(r["started"]), epoch(r["finished"]), r["topology"]["routers"]))
        if not runs:
            print(f"{folder:<22} no start and end times in the records")
            continue
        mins = sorted((b - a) / 60 for a, b, _ in runs)
        sizes = sorted({n for _, _, n in runs})
        size = f"{sizes[0]}" if len(sizes) == 1 else f"{sizes[0]}-{sizes[-1]}"
        span = (time.strftime("%Y-%m-%d %H:%M", time.gmtime(min(a for a, _, _ in runs))) + " to "
                + time.strftime("%Y-%m-%d %H:%M", time.gmtime(max(b for _, b, _ in runs))))
        print(f"{folder:<22} {len(runs):>5} {size:>9} {mins[0]:5.1f} to {mins[-1]:5.1f} (med {median(mins):4.1f})"
              f" {sum(mins) / 60:11.1f}  {span}")


if __name__ == "__main__":
    main(sys.argv[1])
