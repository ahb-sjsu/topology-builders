#!/bin/bash
# Run one job in the overlay guest under unprivileged TCG (no capabilities, no KVM), as a cluster pod would:
#
# Usage: tools/overlay/run_tcg.sh <work directory> <run name> <job script> [vCPUs, default 4] [MiB, default 4096]
#            [timeout s, default 5400]
# Environment: CPUSET=44-47  pin QEMU to these CPUs (taskset). Unset: no pinning.
#
# The job script runs inside the guest from a 9p shared folder; it writes its results to /share/out, which is
# <work directory>/runs/<run name>/share/out here. The guest powers off when the job ends.
set -u
[ $# -ge 3 ] || { sed -n '2,9p' "$0"; exit 2; }
D=$1 NAME=$2 JOB=$3 SMP=${4:-4} MEM=${5:-4096} TO=${6:-5400}
R=$D/runs/$NAME
rm -rf "$R"; mkdir -p "$R/share/out"
cp "$JOB" "$R/share/job.sh"
echo "$TO" > "$R/share/timeout"
qemu-img create -f qcow2 -F qcow2 -b "$D/golden-flat.qcow2" "$R/run.qcow2" 10G > /dev/null
PRE=()
[ -n "${CPUSET:-}" ] && PRE+=(taskset -c "$CPUSET")
echo "=== $NAME: TCG, $SMP vCPUs, $MEM MiB, uid $(id -un), $(date -u +%FT%TZ) ==="
"${PRE[@]}" timeout $((TO + 600)) qemu-system-x86_64 -M pc -accel tcg,thread=multi -cpu max -m "$MEM" -smp "$SMP" \
  -drive file="$R/run.qcow2",if=virtio,format=qcow2 \
  -virtfs local,path="$R/share",mount_tag=share,security_model=none,id=share \
  -netdev user,id=n0 -device virtio-net-pci,netdev=n0 \
  -serial file:"$R/console.log" -display none -no-reboot &
Q=$!
sleep 5
P=$(pgrep -f "^qemu-system-x86_64 .*file=$R/run.qcow2" | head -1)
echo "--- QEMU process (expect uid != 0 and CapEff 0) ---"
grep -E '^(Uid|CapEff)' "/proc/$P/status"
wait $Q
echo "=== qemu exit $? $(date -u +%FT%TZ) ==="
cat "$R/share/out/guest.txt" 2> /dev/null
echo "job exit: $(cat "$R/share/out/EXIT" 2> /dev/null || echo none)"
tail -40 "$R/share/out/job.log" 2> /dev/null
rm -f "$R/run.qcow2"
echo "TCG_RUN_DONE $NAME"
