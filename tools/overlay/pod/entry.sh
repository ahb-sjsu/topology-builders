#!/bin/bash
# NRP pod entrypoint for the topology-builders overlay: a SELF-TERMINATING job. Boots the guest (FRR pull request
# 24128 image, Docker, containerlab, topology-builders) under unprivileged TCG with its memory allocated up front,
# runs /opt/job.sh inside it through a 9p share, prints the results to the pod log, and exits. A hard timeout
# guarantees termination; QEMU keeps the CPUs busy from the first second.
set -u
SMP=${TB_SMP:-2}; MEM=${TB_MEM:-2048}; TO=${TB_TIMEOUT:-5400}
echo "=== TB OVERLAY POD $(date -u +%FT%TZ) node=${NODE_NAME:-?} ==="
echo "identity: $(id)"
grep -E 'CapEff|CapPrm' /proc/self/status || true
echo "kvm present: $([ -e /dev/kvm ] && echo yes || echo no)   accel=tcg  vcpus=$SMP  mem=${MEM}MiB  nproc=$(nproc)"
R=/tmp/run
mkdir -p $R/share/out
cp /opt/job.sh $R/share/job.sh
echo "$TO" > $R/share/timeout
qemu-img create -f qcow2 -F qcow2 -b /opt/golden.qcow2 $R/run.qcow2 10G > /dev/null
timeout $((TO + 300)) qemu-system-x86_64 -M pc -accel tcg,thread=multi,tb-size=256 -cpu max -m "$MEM" -mem-prealloc -smp "$SMP" \
  -drive file=$R/run.qcow2,if=virtio,format=qcow2 \
  -virtfs local,path=$R/share,mount_tag=share,security_model=none,id=share \
  -netdev user,id=n0 -device virtio-net-pci,netdev=n0 \
  -serial file:$R/console.log -display none -no-reboot
echo "=== qemu exit $? $(date -u +%FT%TZ) ==="
cat $R/share/out/guest.txt 2> /dev/null
EXIT=$(cat $R/share/out/EXIT 2> /dev/null || echo none)
echo "job exit: $EXIT"
echo "--- job log ---"
cat $R/share/out/job.log 2> /dev/null
for f in validate.jsonl validate2.jsonl; do
  if [ -s $R/share/out/$f ]; then
    echo "=== BEGIN $f.gz.b64 ==="
    gzip -9 -c $R/share/out/$f | base64 -w 0
    echo
    echo "=== END $f.gz.b64 ==="
  fi
done
if [ "$EXIT" = 0 ] && [ -s $R/share/out/validate.jsonl ] && [ -s $R/share/out/validate2.jsonl ]; then
  echo "RESULT=PASS"; exit 0
fi
echo "RESULT=FAIL"; exit 1
