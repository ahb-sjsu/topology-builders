# The overlay: FRR labs without privileges

containerlab needs root, and so does anything that creates network namespaces, veth pairs or routes. On a cluster
whose pods get no added capabilities, the labs therefore run inside a guest kernel instead: QEMU, in software
emulation (TCG), as an ordinary user, with no capabilities and no `/dev/kvm`. All the privilege the labs need lives in
the guest. Inside it are Docker and containerlab, an FRR image and topology-builders, so the same `clab`, `measure`
and `report` commands run unchanged, on the same FRR image as the host labs.

```mermaid
flowchart LR
    subgraph pod["Pod or host process: uid 1000, no capabilities, no KVM"]
        Q["QEMU, TCG"] --> G
        subgraph G["Guest kernel: root inside"]
            DK["Docker + containerlab"] --> L["FRR lab: routers, veth pairs"]
            M["topology-builders measure"] --> L
        end
        S[("9p shared folder: job.sh in, results out")] <--> G
    end
```

| File | What it does |
|---|---|
| `build.sh` | Bakes the guest once, with KVM: Ubuntu 24.04, Docker and containerlab copied from the host, an FRR image, topology-builders. Writes `golden-flat.qcow2`. |
| `guest/` | Installed in the guest by the bake. At boot, `tb-job.sh` mounts the 9p share, runs `job.sh` with a timeout, writes `out/`, and powers off. |
| `run_tcg.sh` | Runs one job in the guest under TCG, unprivileged, on a host. |
| `jobs/validate16.sh` | The 16-router validation: random regular, degree 4; CPU per handler for one link; timing for link, router and multi-link failures. |
| `pod/` | The pod image (`build_image.sh`, `Dockerfile`, `entry.sh`) and a submitter for nats-bursting (`submit_nats.py`). The pod prints its results to its log, gzipped and base64-encoded between markers. |

Example, on a host with KVM for the bake:

```
pip download pip networkx==3.7 -d wheels && pip wheel --no-deps . -w wheels
KVM_SUDO=1 CPUSET=44-47 tools/overlay/build.sh work frr-distoptflood:e263c441 wheels
CPUSET=44-47 tools/overlay/run_tcg.sh work validate16 tools/overlay/jobs/validate16.sh 4 4096
tools/overlay/pod/build_image.sh work tools/overlay/jobs/validate16.sh ghcr.io/<owner>/tb-overlay:v16 push
```

Software emulation is slow. On 2026-11-20, with 4 vCPUs on an HP Z840, deploying the 16-router lab took 225 s,
against 9 s on the host, and the routers needed 60 s more than on the host to converge. With the labs' normal timers
(1 s hellos) the slowdown shows in the counts too: in that first validation every run converged and 23 of 24 windows
were consistent, but LSP counts for bring-up and for links coming up were 1.5 to 2.7 times the host's (link-down
counts were close). The window-by-window comparison below gives the ranges per kind of window. CPU times and convergence times inside the guest are not comparable with the host's either; compare
them only with other runs in the same setup. QEMU's user-mode networking and the 9p share create nothing on the
host's network.

Status, 2026-11-20. The 16-router validation (random graph of degree 4) passed in a cluster pod as well: uid 1000,
no capabilities, no KVM, 2 vCPUs, 96 minutes, every window consistent. Averaged over link-down and link-up windows,
flood reduction off and on sent 138 and 93 LSPs per change in the pod against 96 and 61 on the host. Window by
window, on the host's guest against the host itself, with the labs' 1 s hellos: link-down windows came within 17%
of the host's counts; link-up, router and multi-link windows were 1.2 to 1.7 times the host's, and bring-up 1.5 to
2.6 times. A rerun with hello, LSP generation, settle and window times scaled by 10 brought bring-up to 1.2 to 1.4
times the host's and left link-down as close as before, but 3 of 4 link-up windows were still converging after
100 s; the CSNP and retransmit intervals were not scaled. Scaling those timers alone is not a fix. Use the guest
for link-down windows, and for flood reduction off against on with this caveat; not for absolute counts of other
events, CPU or times.
