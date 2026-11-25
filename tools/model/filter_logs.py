"""Copy a mechanism lab's output (collect_events.py), keeping only the log lines that analyze_events.py and
check_builds.py read, from BEFORE + 1 s before the first event's recorded time to 30 s after the last: LSPs received
and built, flood-reduction decisions and fallbacks, route-computation starts ("SPF needed"), received CSNPs, and the
CSNP comparisons that found a newer or older copy (with the line that says which).

    python tools/model/filter_logs.py SRC_LAB DST_LAB
"""
import calendar
import json
import os
import re
import shutil
import sys

from analyze_events import BEFORE

TIME = re.compile(r"(\d{4})/(\d\d)/(\d\d) (\d\d):(\d\d):(\d\d)\.(\d{6})")
KEEP = re.compile(r"Rcvd L2 LSP |Building L2 LSP |Refreshed our L2 LSP |Flooding LSP .* with reduction|"
                  r"Flooding reduction not applicable|ISIS-SPF \(\d+\) L2 SPF needed")
COMPARE = re.compile(r"ISIS-Snp .*: Compare LSP ")
VERDICT = re.compile(r"ISIS-Snp .*:\s+is (newer|older) than ours")


def seconds(line):
    m = TIME.match(line)
    if not m:
        return None
    y, mo, d, h, mi, s, us = (int(x) for x in m.groups())
    return calendar.timegm((y, mo, d, h, mi, s)) + us / 1e6


def main(src, dst):
    with open(os.path.join(src, "events.json"), encoding="utf-8") as fh:
        events = json.load(fh)
    t0, t1 = events[0]["time"] - BEFORE - 1, events[-1]["time"] + 30
    os.makedirs(os.path.join(dst, "logs"), exist_ok=True)
    shutil.copy(os.path.join(src, "events.json"), dst)
    os.makedirs(os.path.join(dst, "lab"), exist_ok=True)
    shutil.copy(os.path.join(src, "lab", "lab.json"), os.path.join(dst, "lab"))
    for f in sorted(os.listdir(os.path.join(src, "logs"))):
        out, pending = [], None
        with open(os.path.join(src, "logs", f), encoding="utf-8", errors="replace") as fh:
            for line in fh:  # the same state machine as analyze_events.parse
                t = seconds(line)
                inside = t is not None and t0 <= t <= t1
                if "ISIS-Snp" in line:
                    if "Rcvd L2 CSNP " in line:
                        if inside:
                            out.append(line)
                        continue
                    if COMPARE.search(line):
                        pending = line if inside else None
                        continue
                    if pending is not None and VERDICT.search(line):
                        out += [pending, line]
                    pending = None
                    continue
                if inside and KEEP.search(line):
                    out.append(line)
        with open(os.path.join(dst, "logs", f), "w", encoding="utf-8") as fh:
            fh.writelines(out)


if __name__ == "__main__":
    main(*sys.argv[1:3])
