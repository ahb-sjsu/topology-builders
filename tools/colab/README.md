# The labs on Google Colab

The labs without Docker: every router is a network namespace of the Colab machine running real FRR daemons, every
link a veth pair, driven by `measure --backend netns` inside `unshare -Urnm`.

**Status (2026-11-20):** passed end to end in `test_in_docker.sh` (a container with Colab's permissions, 2 CPUs, no
network): a 16-router random graph and a k = 4 fat-tree, flood reduction off and on; every run converged, every
window was consistent, and no router missed a new LSP ([results](../../results/colab-shaped/README.md)). A Colab CPU
runtime allowed a user namespace with veth pairs on 2026-11-20 (root, capabilities `0xa82c25fb`: Docker's default set
plus SYS_ADMIN and SYS_PTRACE); Kaggle's runtime did not (unshare is refused).

**On Colab itself (2026-11-21, `topology_builders_sessions.ipynb`, probe):** a 16-router random graph of degree 4,
flood reduction off and on, two runs each, converged in every run with every window consistent on three runtime
types, and a 32-router graph of degree 8 on two of them; the records were not kept (the sessions wrote to the
runtime's disk). Link-down windows, LSPs sent off and on: 82 and 56 on the free TPU v5e-1 runtime, 73 and 52 on the
free CPU runtime, 78 and 54 on a Pro CPU runtime with high memory, against 75 to 81 and 52 to 53 in Docker labs of a
graph built with the same parameters.

| Runtime (2026-11-21) | CPUs | Memory | What we saw |
|---|---:|---:|---|
| CPU, free | 2 (Intel Xeon 2.2 GHz) | 13 GB | setup 381 s; 16 and 32 routers converged |
| T4 GPU, free | 2 | 13 GB | no more CPUs than the CPU runtime |
| TPU v5e-1, free | 24 (AMD EPYC 7B13) | 47 GB | 16 routers converged; after about an hour of three such sessions, Colab refused new TPU sessions for usage limits |
| CPU with high memory, Pro | 8 | 51 GB | setup 153 s; 16 and 32 routers converged; about 0.26 compute units an hour |
| L4 GPU, Pro | 12 | 53 GB | about 1.9 compute units an hour |
| A100 GPU, Pro | 12 | 167 GB | about 8.9 compute units an hour |

Every runtime ran Ubuntu 24.04 with the same capabilities. Several sessions run at once, one per notebook copy. In our
runs, the free sessions we reopened after the browser window that held them had closed were gone, while a Pro session
was still running. Colab asked a person to confirm presence (a reCAPTCHA) once, when a fourth session was being
opened, and `drive.mount` needs the account holder's consent in each session; after that consent, run the remaining
cells again.

| File | What it does |
|---|---|
| `topology_builders_colab.ipynb` | The notebook: check the runtime, set up, build a topology, measure flood reduction off and on, report, download the measurements. |
| `topology_builders_sessions.ipynb` | For several sessions at once: `PLAN = 'probe'` records what a runtime type offers (CPUs, memory, setup time) and climbs a ladder of labs from 16 to 64 routers until one does not converge; `PLAN = 'batch'` runs a fixed list of labs. Every record gets a `session` and a `runtime` field; with `USE_DRIVE` the records and a copy of the FRR build go to Google Drive. |
| `setup.sh` | Builds FRR from FRR pull request 24128 (riw777/frr at e263c441) with only mgmtd, zebra, staticd and isisd, and installs topology-builders. Ubuntu 24.04, as root. |
| `test_in_docker.sh` | Runs the recipe on any Linux machine with Docker, in a container with Colab's capabilities and no network: setup, then a 16-router random graph and a k = 4 fat-tree. `REUSE_IMAGE=1` skips the setup when its image exists. |
| `check_results.py` | Pass or fail for a run: every run converged, every window consistent, no router missing a new LSP. |

Start small: each router runs four FRR daemons, and a lab too large for the machine does not converge. CPU time on
a shared cloud machine is noisy; compare flood reduction off against on within one run.
