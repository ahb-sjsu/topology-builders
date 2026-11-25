#!/bin/bash
# Second guest of the cache experiment (the first could not read the nocache image): the same failures, nocache and
# stock alternating, so that each variant has two runs per topology (stock's first runs are in the first guest).
# Each lab's output goes to /share/out/<variant>-r<n>/.
set -u
mkdir -p /images
mount -t 9p -o trans=virtio,version=9p2000.L,msize=262144,ro images /images || { echo "no images share"; exit 3; }
for i in tb-colab-test tb-colab-nocache; do docker load -i /images/$i.tar | tail -1 || exit 4; done
docker image inspect tb-colab-nocache:latest > /dev/null || { echo "ABORT nocache image not loaded"; exit 4; }
status=0
run() {  # image variant topology reduction
  echo "LAB_START $2 $3 $4 $(date -u +%FT%TZ)"
  docker run --rm --network none --pull never --cap-add SYS_ADMIN --cap-add SYS_PTRACE \
    --security-opt apparmor=unconfined -v /share:/share "$1:latest" bash /share/inner.sh "$2" "$3" "$4"
  rc=$?
  echo "LAB_DONE $2 $3 $4 exit $rc $(date -u +%FT%TZ)"
  [ $rc = 0 ] || status=1
}
run tb-colab-nocache nocache-r1 fb444 on
run tb-colab-test stock-r2 fb444 on
run tb-colab-nocache nocache-r2 fb444 on
run tb-colab-nocache nocache-r1 ls16 on
run tb-colab-test stock-r2 ls16 on
run tb-colab-nocache nocache-r2 ls16 on
exit $status
