#!/bin/bash
# Inside the overlay guest: the same 16-router validation as on Atlas's tb-check container (2026-11-19), for a direct
# comparison of native and TCG. Random regular, 16 routers, degree 4, seed 1; FRR pull request 24128 at e263c441.
# 1) CPU per handler: link events, settle 20 s, window 10 s.  2) Timing: link, node and multi events.
set -u
T=/opt/tb-venv/bin/topology-builders
IMG=frr-distoptflood:e263c441
cd /share/out
echo "START $(date -u +%FT%TZ)"
$T build random-regular --routers 16 --degree 4 --seed 1 --out rr16.json
sha256sum rr16.json
$T clab rr16.json --out plain --name v-rr16-p --image $IMG > /dev/null
$T clab rr16.json --out timing --name v-rr16-t --image $IMG --timing-logs > /dev/null
echo "PROFILE $(date -u +%FT%TZ)"
$T measure plain/off plain/on --profile --event link --links 1 --settle 20 --window 10 --max-wait 300 \
  --out validate.jsonl 2>&1 | tail -3
echo "TIMING $(date -u +%FT%TZ)"
$T measure timing/off timing/on --timing --event link,node,multi --links 1 --fail 2 --settle 20 --window 10 \
  --max-wait 300 --out validate2.jsonl 2>&1 | tail -3
for k in link node multi; do echo "== report $k"; $T report validate.jsonl validate2.jsonl --event $k; done
echo "DONE $(date -u +%FT%TZ)"
