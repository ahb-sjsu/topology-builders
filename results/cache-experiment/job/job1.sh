#!/bin/bash
# Inside the overlay guest (run_vm.sh): the mechanism lab's router and multi-link failures (4x4x4 flattened butterfly,
# leaf-spine 48 x 16), replayed with FRR PR 24128 at e263c441 as it is ("stock", tb-colab-test) and with the
# flood-reduction decision topology rebuilt at every decision ("nocache", tb-colab-nocache). Flood reduction on for
# both; the butterfly also without flood reduction, as the control. Variants alternate per topology. Each lab's
# output is copied to /share/out/<variant>/ as it finishes. The images share holds both images (docker save).
set -u
mkdir -p /images
mount -t 9p -o trans=virtio,version=9p2000.L,msize=262144,ro images /images || { echo "no images share"; exit 3; }
for i in tb-colab-test tb-colab-nocache; do docker load -i /images/$i.tar | tail -1; done
status=0
run() {  # image variant topology reduction
  echo "LAB_START $2 $3 $4 $(date -u +%FT%TZ)"
  docker run --rm --network none --cap-add SYS_ADMIN --cap-add SYS_PTRACE --security-opt apparmor=unconfined \
    -v /share:/share "$1:latest" bash /share/inner.sh "$2" "$3" "$4"
  rc=$?
  echo "LAB_DONE $2 $3 $4 exit $rc $(date -u +%FT%TZ)"
  [ $rc = 0 ] || status=1
}
run tb-colab-test stock fb444 on
run tb-colab-nocache nocache fb444 on
run tb-colab-test stock ls16 on
run tb-colab-nocache nocache ls16 on
run tb-colab-test stock fb444 off
exit $status
