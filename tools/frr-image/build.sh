#!/bin/bash
# Build an FRR container image from any FRR commit with FRR's own Alpine packaging (docker/alpine in the FRR tree),
# using Docker's classic builder, so no buildx is needed. The image has the layout of the official
# quay.io/frrouting/frr images, so `topology-builders clab --image <tag>` labs run on it. FRR's packaging also runs
# FRR's unit tests; the build fails if they do.
#
# Usage: tools/frr-image/build.sh <work directory> <FRR git URL> <full commit SHA> <image tag>
# Environment:
#   CPUSET=36-47  CPUs for the build. FRR's APKBUILD runs make -j $(nproc), and nproc follows the cpuset.
#                 Unset: no cap.
#   THERMAL=1     hold the build under batch-probe's ThermalController (thermal_pause.py; pip install batch-probe).
# Example, FRR pull request 24128 (draft-ietf-lsr-distoptflood):
#   CPUSET=36-47 THERMAL=1 tools/frr-image/build.sh work https://github.com/riw777/frr \
#       e263c441160c7cf25749a9695978ffe5649678f9 frr-distoptflood:e263c441
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
[ $# -eq 4 ] || { sed -n '2,15p' "$0"; exit 2; }
W=$1 URL=$2 REF=$3 TAG=$4
[[ $REF =~ ^[0-9a-f]{40}$ ]] || { echo "give the full 40-character commit SHA, not $REF"; exit 2; }
mkdir -p "$W" && cd "$W" || exit 1
echo "START $(date -u +%FT%TZ)"
[ -d src/.git ] || git clone -q --filter=blob:none "$URL" src || exit 1
git -C src fetch -q origin "$REF" || true
git -C src checkout -q "$REF" || exit 1
test "$(git -C src rev-parse HEAD)" = "$REF" || { echo "BUILD_EXIT checkout-mismatch"; exit 1; }
python3 "$HERE/make_dockerfile.py" src Dockerfile.classic || exit 1
GITREV=$(git -C src rev-parse --short=10 HEAD)
PKGVER=$(printf '%u' "0x$GITREV")
echo "source $URL $REF pkgver $PKGVER"
CPU=()
[ -n "${CPUSET:-}" ] && CPU=(--cpuset-cpus="$CPUSET")
if [ "${THERMAL:-0}" = 1 ]; then
  N=$(taskset -c "${CPUSET:-0-$(($(getconf _NPROCESSORS_CONF) - 1))}" nproc)
  docker ps -aq --no-trunc > before.txt
  rm -f stop
  python3 "$HERE/thermal_pause.py" before.txt stop "$N" > thermal.log 2>&1 &
fi
docker build "${CPU[@]}" -f Dockerfile.classic --build-arg PKGVER="$PKGVER" \
  --label "org.opencontainers.image.revision=$REF" --label "org.opencontainers.image.source=$URL" \
  -t "$TAG" src > build.log 2>&1
rc=$?
if [ "${THERMAL:-0}" = 1 ]; then touch stop; wait; fi
echo "BUILD_EXIT $rc $(date -u +%FT%TZ)"
docker image inspect "$TAG" --format '{{.Id}} {{.Size}}' 2>&1
exit $rc
