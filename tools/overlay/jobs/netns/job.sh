#!/bin/bash
# Inside the overlay guest (run_vm.sh): one lab pair on the namespace backend, in the same container image as the host
# labs (tb-colab-test: FRR pull request 24128 built by tools/colab/setup.sh). The run's share holds this script,
# labs/<name>/off and on (from `topology-builders clab`), topology_builders/ (the source to run) and measure.args (the
# measure options). Each record is appended to /share/out/measurements.jsonl as it finishes, so a destroyed guest keeps
# every finished record. The images share holds tb-colab-test.tar (docker save).
set -u
mkdir -p /images
mount -t 9p -o trans=virtio,version=9p2000.L,msize=262144,ro images /images || { echo "no images share"; exit 3; }
docker load -i /images/tb-colab-test.tar | tail -1
# The share's files belong on the host to QEMU's user, which the lab's user namespace does not map: create the
# records file here, outside that namespace, writable by all, or every append after the first is refused.
install -m 666 /dev/null /share/out/measurements.jsonl
docker run --rm --network none --cap-add SYS_ADMIN --cap-add SYS_PTRACE --security-opt apparmor=unconfined \
  -v /share:/share tb-colab-test:latest bash -c '
  set -u
  cp -r /share/topology_builders/. "$(python3 -c "import os, topology_builders as t; print(os.path.dirname(t.__file__))")"/
  /usr/lib/frr/isisd --version | head -1
  mkdir -p /work && cp -r /share/labs /work/ && cd /work && n=$(ls labs)
  unshare -Urnm python3 -m topology_builders measure labs/$n/off labs/$n/on --backend netns $(cat /share/measure.args) \
    --out /share/out/measurements.jsonl'
