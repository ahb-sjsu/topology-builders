#!/bin/bash
# Runs once inside the guest during the bake (build.sh), from the payload disc.
set -eux
P=/mnt/payload
install -m 0755 $P/bin/* /usr/bin/
install -m 0644 $P/docker.service /etc/systemd/system/docker.service
groupadd -f docker
systemctl daemon-reload
systemctl enable --now docker
for i in $(seq 1 30); do docker info > /dev/null 2>&1 && break; sleep 2; done
docker load -i $P/frr-image.tar
docker image inspect "$(cat $P/frr-image.tag)" --format '{{.Id}}' > /var/log/tb-image-id
python3 -m venv --without-pip --system-site-packages /opt/tb-venv
PIP=$(ls $P/wheels/pip-*.whl | head -1)
/opt/tb-venv/bin/python "$PIP/pip" install --no-index --find-links $P/wheels networkx topology_builders
/opt/tb-venv/bin/python -c 'import topology_builders as t; print("topology-builders", t.__version__)' \
  > /var/log/tb-version
install -m 0755 $P/tb-job.sh /usr/local/bin/tb-job.sh
install -m 0644 $P/tb-job.service /etc/systemd/system/tb-job.service
systemctl enable tb-job.service
echo "TB-INSTALL image $(cat /var/log/tb-image-id) $(cat /var/log/tb-version) docker $(docker version --format '{{.Server.Version}}') clab $(containerlab version | grep -i ' version' | awk '{print $2}')"
