#!/bin/bash
# Test the Colab recipe on a Linux machine with Docker, in a container shaped like a Colab runtime: Ubuntu 24.04,
# root, CAP_SYS_ADMIN but not CAP_NET_ADMIN (a Colab CPU runtime's set on 2026-11-20: CapEff 0xa82c25fb), so the labs
# run only inside `unshare -Urnm`, as in the notebook. Stage 1 runs setup.sh with the network and saves the image;
# stage 2 runs the labs with no network (--network none: no interface is added to the host).
#
#   tools/colab/test_in_docker.sh [build CPUs] [lab CPUs]      e.g. 44-47 44-45
set -euo pipefail
BUILD_CPUS="${1:-0-3}"
LAB_CPUS="${2:-0-1}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IMAGE=tb-colab-test:latest
OUT="${OUT:-$PWD/colab-test-out}"
mkdir -p "$OUT"
t0=$(date +%s)

echo "== stage 1: setup.sh (CPUs $BUILD_CPUS) $(date -u +%FT%TZ)"
docker rm -f tb-colab-build > /dev/null 2>&1 || true
docker run --name tb-colab-build --network host --cpuset-cpus "$BUILD_CPUS" -v "$REPO:/src:ro" ubuntu:24.04 \
  bash -c 'cp -r /src /opt/topology-builders && rm -rf /opt/topology-builders/build && \
           TB_PACKAGE=/opt/topology-builders bash /opt/topology-builders/tools/colab/setup.sh'
docker commit tb-colab-build "$IMAGE" > /dev/null
docker rm tb-colab-build > /dev/null
echo "== stage 1 done in $(( $(date +%s) - t0 )) s"

echo "== stage 2: labs (CPUs $LAB_CPUS) $(date -u +%FT%TZ)"
# Docker's default capabilities plus SYS_ADMIN and SYS_PTRACE is exactly 0xa82c25fb, Colab's set.
docker run --rm --network none --cpuset-cpus "$LAB_CPUS" --cap-add SYS_ADMIN --cap-add SYS_PTRACE \
  --security-opt apparmor=unconfined -v "$OUT:/out" -w /out "$IMAGE" bash -c '
  set -u
  grep -E "^CapEff" /proc/self/status   # expected: 00000000a82c25fb
  ip link add tbx0 type veth peer name tbx1 2>&1 | head -1   # expected: not permitted, as on Colab
  unshare -Urn sh -c "ip link add a type veth peer name b && echo user namespaces: OK"
  T="python3 -m topology_builders"
  $T build random-regular --routers 16 --degree 4 --seed 1 --out rr16-d4.json
  $T build fat-tree --k 4 --out fat-tree-k4.json
  for n in rr16-d4 fat-tree-k4; do
    $T clab $n.json --out labs/$n --name $n --timing-logs > /dev/null
    unshare -Urnm python3 -m topology_builders measure labs/$n/off labs/$n/on --backend netns --links 2 \
      --settle 20 --max-wait 180 --timing --profile --out measurements.jsonl 2>&1 | tail -6
  done
  $T report measurements.jsonl
'
echo "== done in $(( $(date +%s) - t0 )) s; results in $OUT"
