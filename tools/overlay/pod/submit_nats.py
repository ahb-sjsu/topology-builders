#!/usr/bin/env python3
"""Submit one overlay pod as a Kubernetes Job through a nats-bursting submitter.

The pod (entry.sh) boots the guest, runs its job, prints the results to the pod log and exits by itself, with a hard
timeout, so the Job never idles. It requests no GPU; requests equal limits. QEMU keeps the requested CPUs busy from
the start, and entry.sh pre-allocates the guest's memory, so the requested resources are in use for the whole life
of the pod, startup included. Size the request to the guest: CPUs = vCPUs, and memory = guest memory plus about
0.5 GiB for QEMU (its translated-code cache is capped at 256 MB in entry.sh).

Usage: NATS_BURSTING_PATH=<checkout> python3 submit_nats.py <job name> <image> [cpu] [memory] [ephemeral] [timeout s]
Collect the results with: kubectl -n <namespace> logs job/<job name>
"""
import os
import sys
import time

sys.path.insert(0, os.environ.get("NATS_BURSTING_PATH", "."))
from nats_bursting.client import Client
from nats_bursting.descriptor import JobDescriptor, Resources


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    name, image = argv[0], argv[1]
    cpu, memory, eph, timeout = (argv[2:] + ["2", "3Gi", "6Gi", "10800"][len(argv) - 2:])[:4]
    d = JobDescriptor(
        name=name,
        image=image,
        resources=Resources(cpu=cpu, memory=memory, ephemeral_storage=eph, gpu=0),
        labels={"atlas.io/batch": name, "app": "tb-overlay"},
        backoff_limit=0,
        env={"TB_SMP": cpu, "TB_TIMEOUT": timeout},
    )
    with Client() as c:
        r = c.submit_and_wait(d, timeout=60)
    print(f"submitted: job_id={r.job_id} accepted={getattr(r, 'accepted', None)} status={r.status}")
    print(f"[{time.strftime('%H:%M:%S')}] then: kubectl logs job/{name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
