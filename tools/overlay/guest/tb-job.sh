#!/bin/bash
# Guest side of an overlay run: if the host shares a folder (9p tag "share") holding job.sh, run it with the
# timeout in the share's "timeout" file (default 3600 s), log to share/out/, then power off. Without a share (the
# bake), do nothing.
set -u
mkdir -p /share
modprobe 9pnet_virtio 2> /dev/null || true
if ! mount -t 9p -o trans=virtio,version=9p2000.L,msize=262144 share /share 2> /dev/null; then
  echo "TB-JOB no share" > /dev/ttyS0
  exit 0
fi
mkdir -p /share/out
T=$(cat /share/timeout 2> /dev/null || echo 3600)
{
  echo "TB-JOB start $(date -u +%FT%TZ) cpus $(nproc) mem $(free -m | awk '/Mem/ {print $2}') MiB kernel $(uname -r)"
  cat /var/log/tb-version /var/log/tb-image-id
} > /share/out/guest.txt
for i in $(seq 1 60); do docker info > /dev/null 2>&1 && break; sleep 2; done
cd /share
timeout "$T" bash /share/job.sh > /share/out/job.log 2>&1
echo $? > /share/out/EXIT
echo "TB-JOB done $(date -u +%FT%TZ) exit $(cat /share/out/EXIT)" | tee -a /share/out/guest.txt > /dev/ttyS0
sync
systemctl poweroff
