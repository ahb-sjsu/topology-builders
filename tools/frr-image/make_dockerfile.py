"""Write a version of FRR's docker/alpine/Dockerfile that Docker's classic builder can run.

FRR's file needs BuildKit (docker buildx) for two things: the `# syntax=` line, and `COPY --exclude=...` in the last
stage, which leaves out the dev, doc and dbg packages. This drops the first and turns the second into an extra
stage, apk-filter, that deletes the excluded packages, so the final image installs the same set. Every other line is
copied unchanged, and the script stops if the lines it expects are not there.

Usage: python3 make_dockerfile.py <FRR source directory> <output file>"""
import re
import sys


def convert(text):
    lines = [x for x in text.splitlines() if not x.startswith("# syntax=")]
    start = next((i for i, x in enumerate(lines) if x.startswith("COPY --exclude=")), None)
    if start is None:
        raise SystemExit("no 'COPY --exclude=' line: FRR's Dockerfile has changed, check it by hand")
    end, instr = start, lines[start]
    while instr.endswith("\\"):
        end += 1
        instr = instr[:-1].rstrip() + " " + lines[end].strip()
    excludes = re.findall(r"--exclude=(\S+)", instr)
    m = re.search(r"--from=(\S+)\s+(\S+)\s+(\S+)\s*$", instr)
    if not excludes or not m:
        raise SystemExit(f"cannot read the COPY --exclude instruction: {instr}")
    stage, src, dst = m.groups()
    final = max(i for i in range(start) if lines[i].startswith("FROM "))
    base = lines[final].split()[1]
    insert = final
    while insert > 0 and lines[insert - 1].startswith("#"):
        insert -= 1
    names = " -o ".join(f"-name '{e.split('/')[-1]}'" for e in excludes)
    stage_lines = [
        "# Written by topology-builders tools/frr-image/make_dockerfile.py: the packages FRR's file leaves out with",
        "# COPY --exclude (BuildKit only) are deleted in this stage instead.",
        f"FROM {base} as apk-filter",
        f"COPY --from={stage} {src} {dst}",
        f"RUN find {dst.rstrip('/')} -type f \\( {names} \\) -delete",
        "",
    ]
    out = lines[:insert] + stage_lines + lines[insert:start] + [f"COPY --from=apk-filter {dst} {dst}"]
    out += lines[end + 1:]
    instructions = [x for x in out if not x.startswith("#")]
    if any("--exclude" in x for x in instructions) or any(x.startswith("# syntax=") for x in out):
        raise SystemExit("conversion left a BuildKit-only line in place")
    return "\n".join(out) + "\n"


def main(source, output):
    with open(f"{source}/docker/alpine/Dockerfile", encoding="utf-8") as fh:
        text = fh.read()
    with open(output, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(convert(text))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
