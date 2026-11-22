#!/bin/bash
# Run one job in the overlay guest as a KVM virtual machine (libvirt), isolated from the host:
#   - its own kernel: the lab's namespaces, veth pairs, routes and FRR processes exist only in the guest, so a lab, however
#     it misbehaves, cannot hold the host kernel's networking locks or flood the host with processes;
#   - no network device: the job goes in, and its results come out, through a 9p shared folder;
#   - vCPUs and QEMU's own threads confined to CPUSET at CPU weight 10 (host services have 100), so host services win
#     every contention; memory is the guest's RAM;
#   - started by an ordinary user in the libvirt group: no sudo anywhere.
# It refuses to start while the host-network watchdog's STOP file exists or another job VM runs, and destroys its VM
# when STOP appears or at the timeout.
#
# Usage: tools/overlay/run_vm.sh <work directory> <run name> <job directory> [vCPUs 8] [MiB 16384] [timeout s 5400]
#   The job directory holds job.sh and whatever it needs; it is copied to the share. <work directory>/golden-flat.qcow2
#   is the guest (build.sh); <work directory>/images, if present, is shared read-only as 9p tag "images".
# Environment: CPUSET (default 12-23,36-43), STOP (default /archive/experiments/tb-families/STOP)
set -u
[ $# -ge 3 ] || { sed -n '2,15p' "$0"; exit 2; }
D=$(cd "$1" && pwd) NAME=$2 JOB=$3 SMP=${4:-8} MEM=${5:-16384} TO=${6:-5400}
CPUSET=${CPUSET:-12-23,36-43}
STOP=${STOP:-/archive/experiments/tb-families/STOP}
V="virsh -q -c qemu:///system"
DOM=tb-vm-$NAME R=$D/runs/$NAME
[ -e "$STOP" ] && { echo "REFUSED $NAME: $STOP exists: $(cat "$STOP")"; exit 1; }
$V list --name | grep -q '^tb-vm-' && { echo "REFUSED $NAME: a job VM is already running"; exit 1; }
[ -f "$JOB/job.sh" ] || { echo "REFUSED $NAME: no $JOB/job.sh"; exit 1; }
rm -rf "$R"; mkdir -p "$R/share/out"
cp -r "$JOB"/. "$R/share/"
echo "$TO" > "$R/share/timeout"
chmod -R a+rwX "$R/share"   # QEMU runs as libvirt-qemu
qemu-img create -q -f qcow2 -F qcow2 -b "$D/golden-flat.qcow2" "$R/run.qcow2" 10G
IMAGES=
[ -d "$D/images" ] && IMAGES="<filesystem type='mount' accessmode='squash'><source dir='$D/images'/><target dir='images'/><readonly/></filesystem>"
cat > "$R/domain.xml" <<EOF
<domain type='kvm'>
  <name>$DOM</name>
  <memory unit='MiB'>$MEM</memory>
  <vcpu placement='static' cpuset='$CPUSET'>$SMP</vcpu>
  <cputune><shares>10</shares><emulatorpin cpuset='$CPUSET'/></cputune>
  <os><type arch='x86_64' machine='pc'>hvm</type><boot dev='hd'/></os>
  <features><acpi/><apic/></features>
  <cpu mode='host-passthrough'/>
  <on_poweroff>destroy</on_poweroff><on_reboot>destroy</on_reboot><on_crash>destroy</on_crash>
  <devices>
    <disk type='file' device='disk'>
      <driver name='qemu' type='qcow2'/><source file='$R/run.qcow2'/><target dev='vda' bus='virtio'/>
    </disk>
    <filesystem type='mount' accessmode='squash'><source dir='$R/share'/><target dir='share'/></filesystem>
    $IMAGES
    <serial type='file'><source path='$R/console.log'/><target port='0'/></serial>
    <memballoon model='none'/>
  </devices>
</domain>
EOF
echo "=== $NAME: KVM guest, $SMP vCPUs on CPUs $CPUSET, $MEM MiB, timeout $TO s, $(date -u +%FT%TZ) ==="
$V create "$R/domain.xml" > /dev/null || { echo "VM_START_FAILED $NAME"; exit 1; }
echo "network devices in the guest: $($V domiflist "$DOM" | grep -c .); QEMU user: $(ps -o user= -p "$(pgrep -f "guest=$DOM," | head -1)")"
t0=$(date +%s)
while $V domstate "$DOM" 2> /dev/null | grep -q running; do
  if [ -e "$STOP" ]; then $V destroy "$DOM" > /dev/null; echo "VM_DESTROYED $NAME: $STOP appeared"; break; fi
  if [ $(($(date +%s) - t0)) -gt $((TO + 600)) ]; then $V destroy "$DOM" > /dev/null; echo "VM_DESTROYED $NAME: timeout"; break; fi
  sleep 10
done
echo "=== $NAME ended $(date -u +%FT%TZ) after $(($(date +%s) - t0)) s; job exit $(cat "$R/share/out/EXIT" 2> /dev/null || echo none) ==="
rm -f "$R/run.qcow2"
echo "VM_RUN_DONE $NAME"
