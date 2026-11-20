#!/bin/bash
# Bake the overlay guest: Ubuntu 24.04 with Docker and containerlab (copied from this host, for the same versions as
# the host's labs), an FRR image, and topology-builders. The guest later runs under unprivileged QEMU-TCG
# (run_tcg.sh, or pod/ on a cluster): all the privilege that labs need (network namespaces, veth pairs, routes) is
# inside the guest kernel, so the QEMU process needs no capabilities and no /dev/kvm. The bake itself uses KVM.
# QEMU uses user-mode networking only: nothing is created on the host's network.
#
# Usage: tools/overlay/build.sh <work directory> <FRR image tag> <wheel directory>
#   The wheel directory holds pip-*.whl, networkx-*.whl and topology_builders-*.whl (pip download / pip wheel).
# Environment:
#   CPUSET=44-47  CPUs for the bake (taskset). Unset: no cap.
#   KVM_SUDO=1    run the bake's QEMU through sudo, when this user cannot open /dev/kvm.
# Output: <work directory>/golden-flat.qcow2, a flattened image with no backing file.
# Example: tools/overlay/build.sh /archive/experiments/tb-overlay frr-distoptflood:e263c441 wheels
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
[ $# -eq 3 ] || { sed -n '2,16p' "$0"; exit 2; }
D=$1 IMG=$2 WHEELS=$(cd "$3" && pwd)
P=$D/payload
mkdir -p "$D" "$P/bin" "$P/wheels"
cd "$D"
BASE=noble-server-cloudimg-amd64.img
if [ ! -f "$BASE" ]; then
  echo "=== downloading the Ubuntu 24.04 cloud image ==="
  wget -q "https://cloud-images.ubuntu.com/noble/current/$BASE" -O "$BASE.part" && mv "$BASE.part" "$BASE"
fi

echo "=== payload: Docker and containerlab from the host, the FRR image, topology-builders ==="
for b in dockerd docker containerd containerd-shim-runc-v2 runc docker-proxy docker-init containerlab; do
  install -m 0755 "$(command -v $b)" "$P/bin/$b"
done
docker save "$IMG" -o "$P/frr-image.tar"
echo "$IMG" > "$P/frr-image.tag"
cp "$WHEELS"/pip-*.whl "$WHEELS"/networkx-*.whl "$WHEELS"/topology_builders-*.whl "$P/wheels/"
cp "$HERE"/guest/install.sh "$HERE"/guest/tb-job.sh "$HERE"/guest/tb-job.service "$HERE"/guest/docker.service "$P/"
rm -f payload.iso
genisoimage -quiet -V PAYLOAD -J -R -o payload.iso "$P"

cat > user-data <<'EOF'
#cloud-config
ssh_pwauth: false
package_update: true
packages: [iptables]
runcmd:
  - bash -c 'apt-get install -y linux-modules-extra-$(uname -r) > /var/log/tb-lme.log 2>&1 || true'
  - bash -c 'apt-get purge -y snapd unattended-upgrades > /var/log/tb-purge.log 2>&1 || true'
  - [ systemctl, disable, --now, apt-daily.timer, apt-daily-upgrade.timer ]
  - [ mkdir, -p, /mnt/payload ]
  - [ mount, -L, PAYLOAD, /mnt/payload ]
  - bash -c 'bash /mnt/payload/install.sh > /var/log/tb-install.log 2>&1; echo "===TB-INSTALL-EXIT=== $?" > /dev/ttyS0; tail -3 /var/log/tb-install.log > /dev/ttyS0'
  - [ touch, /etc/cloud/cloud-init.disabled ]
final_message: "===TB-CLOUDINIT-DONE==="
power_state: {mode: poweroff, timeout: 60, condition: true}
EOF
cat > meta-data <<'EOF'
instance-id: tb-overlay-golden-0
local-hostname: tb-overlay
EOF
cloud-localds seed.iso user-data meta-data
rm -f disk.qcow2
qemu-img create -f qcow2 -F qcow2 -b "$D/$BASE" disk.qcow2 10G > /dev/null

PRE=()
[ -n "${CPUSET:-}" ] && PRE+=(taskset -c "$CPUSET")
[ "${KVM_SUDO:-0}" = 1 ] && PRE=(sudo -n "${PRE[@]}")
echo "=== bake with KVM, 4 vCPUs, 4 GiB $(date -u +%FT%TZ) ==="
"${PRE[@]}" timeout 2400 qemu-system-x86_64 -M pc -accel kvm -cpu host -m 4096 -smp 4 \
  -drive file=disk.qcow2,if=virtio,format=qcow2 \
  -drive file=seed.iso,if=virtio,format=raw,media=cdrom \
  -drive file=payload.iso,if=virtio,format=raw,media=cdrom \
  -netdev user,id=n0 -device virtio-net-pci,netdev=n0 \
  -serial file:bake-console.log -display none -no-reboot
echo "=== bake exit $? $(date -u +%FT%TZ) ==="
[ "${KVM_SUDO:-0}" = 1 ] && sudo -n chown "$(id -u):$(id -g)" disk.qcow2 bake-console.log
grep -a -E 'TB-INSTALL|TB-CLOUDINIT' bake-console.log | tail -6
qemu-img convert -c -O qcow2 disk.qcow2 golden-flat.qcow2
ls -la golden-flat.qcow2
echo "=== BUILD_DONE $(date -u +%FT%TZ) ==="
