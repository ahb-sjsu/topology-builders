#!/bin/bash
# Build the overlay pod image from a baked guest and one job script, and optionally push it.
#
# Usage: tools/overlay/pod/build_image.sh <work directory with golden-flat.qcow2> <job script> <image tag> [push]
# Example: tools/overlay/pod/build_image.sh /archive/experiments/tb-overlay tools/overlay/jobs/validate16.sh \
#              ghcr.io/<owner>/tb-overlay:v16 push
# --network host: the build's RUN steps use the host's network directly, so no build container interface is
# created on the host.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
[ $# -ge 3 ] || { sed -n '2,9p' "$0"; exit 2; }
D=$1 JOB=$2 TAG=$3
C=$D/podimg
mkdir -p "$C"
ln -f "$D/golden-flat.qcow2" "$C/golden-flat.qcow2"
cp "$HERE/Dockerfile" "$HERE/entry.sh" "$C/"
cp "$JOB" "$C/job.sh"
docker build --network host -t "$TAG" "$C"
docker image inspect "$TAG" --format 'image {{.Id}} size {{.Size}}'
[ "${4:-}" = push ] && docker push "$TAG" | tail -1
echo "IMAGE_DONE $TAG"
