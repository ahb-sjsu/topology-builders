"""LSPs sent per failure window of a collect_events.py lab: every "Sending L2 LSP" line of every router's log (sent by
flooding or on request after a CSNP or PSNP), from analyze_events.BEFORE seconds before each failure's recorded time
to the next event, its recovery. Needs logs that keep those lines (full logs, or filter_logs.py --sends).

    python tools/model/count_sends.py mech/fb444-on mech/ls16-on
"""
import calendar
import json
import os
import re
import sys

from analyze_events import BEFORE

TIME = re.compile(r"(\d{4})/(\d\d)/(\d\d) (\d\d):(\d\d):(\d\d)\.(\d{6})")


def seconds(line):
    y, mo, d, h, mi, s, us = (int(x) for x in TIME.match(line).groups())
    return calendar.timegm((y, mo, d, h, mi, s)) + us / 1e6


def count(d):
    """[(kind, router or number of links, LSPs sent)] per failure of the lab in directory d."""
    with open(os.path.join(d, "events.json"), encoding="utf-8") as fh:
        events = json.load(fh)
    wins = [(ev["time"] - BEFORE, events[i + 1]["time"], ev["kind"], ev.get("router") or len(ev["links"]))
            for i, ev in enumerate(events) if ev["state"] == "down" and i + 1 < len(events)]
    sent = [0] * len(wins)
    for f in sorted(os.listdir(os.path.join(d, "logs"))):
        with open(os.path.join(d, "logs", f), encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if "Sending L2 LSP" in line:
                    t = seconds(line)
                    for k, (a, b, _, _) in enumerate(wins):
                        if a <= t < b:
                            sent[k] += 1
    return [(kind, what, n) for (_, _, kind, what), n in zip(wins, sent)]


def main(argv=None):
    for d in (argv if argv is not None else sys.argv[1:]):
        for kind, what, n in count(d):
            print(f"{os.path.basename(os.path.normpath(d))} {kind} {what}: {n} LSPs sent")


if __name__ == "__main__":
    main()
