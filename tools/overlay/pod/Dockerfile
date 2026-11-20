# topology-builders overlay pod: the guest image (Ubuntu 24.04 with Docker, containerlab, an FRR image and
# topology-builders) runs inside an unprivileged QEMU-TCG process as a non-root user, with no added capabilities and
# no /dev/kvm, so the pod fits a cluster's default pod security. All the privilege the labs need is in the guest.
# Build context (assembled by build_image.sh): golden-flat.qcow2, entry.sh, job.sh.
FROM ubuntu:24.04

RUN apt-get update \
 && apt-get install -y --no-install-recommends qemu-system-x86 qemu-utils \
 && rm -rf /var/lib/apt/lists/*

# golden-flat.qcow2: flattened (no backing chain), so it is self-contained inside the image.
COPY golden-flat.qcow2 /opt/golden.qcow2
COPY entry.sh /opt/tb_nrp_entry.sh
COPY job.sh /opt/job.sh
# Only the scripts are chmod-ed: a chmod of the 1.2 GB image in its own layer would copy it into a second layer.
RUN chmod 0755 /opt/tb_nrp_entry.sh /opt/job.sh

# ubuntu:24.04 ships UID 1000 ("ubuntu"); run as it, so the pod runs as non-root without a security context.
USER 1000
WORKDIR /tmp
ENTRYPOINT ["/opt/tb_nrp_entry.sh"]
