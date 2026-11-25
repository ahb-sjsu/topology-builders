#!/bin/bash
# In the container: one collect_events.py lab. Arguments: variant topology reduction (on or off).
set -u
V=$1 T=$2 RED=$3
cp -r /share/topology_builders/. "$(python3 -c 'import os, topology_builders as t; print(os.path.dirname(t.__file__))')"/
echo "isisd $(sha256sum /usr/lib/frr/isisd | cut -c1-16) $(/usr/lib/frr/isisd --version | head -1)"
mkdir -p /work && cd /work || exit 1
unshare -Urnm python3 /share/model/collect_events.py --out /work/mech --topology "/share/in/$T.json" \
  --events "/share/in/$T-events.json" --reduction "$RED"
rc=$?
mkdir -p "/share/out/$V"
cp -r /work/mech/. "/share/out/$V/" || rc=1
exit $rc
