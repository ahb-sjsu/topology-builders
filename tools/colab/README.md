# The labs on Google Colab

The labs without Docker: every router is a network namespace of the Colab machine running real FRR daemons, every
link a veth pair, driven by `measure --backend netns` inside `unshare -Urnm`.

**Status (2026-11-20):** passed end to end in `test_in_docker.sh` (a container with Colab's permissions, 2 CPUs, no
network): a 16-router random graph and a k = 4 fat-tree, flood reduction off and on; every run converged, every
window was consistent, and no router missed a new LSP ([results](../../results/colab-shaped/README.md)). Not yet
run on Colab itself. A Colab CPU runtime allowed a user namespace with veth pairs on 2026-11-20 (root, capabilities
`0xa82c25fb`: Docker's default set plus SYS_ADMIN and SYS_PTRACE); Kaggle's runtime did not (unshare is refused).

| File | What it does |
|---|---|
| `topology_builders_colab.ipynb` | The notebook: check the runtime, set up, build a topology, measure flood reduction off and on, report, download the measurements. |
| `setup.sh` | Builds FRR from FRR pull request 24128 (riw777/frr at e263c441) with only mgmtd, zebra, staticd and isisd, and installs topology-builders. Ubuntu 24.04, as root. |
| `test_in_docker.sh` | Runs the recipe on any Linux machine with Docker, in a container with Colab's capabilities and no network: setup, then a 16-router random graph and a k = 4 fat-tree. `REUSE_IMAGE=1` skips the setup when its image exists. |
| `check_results.py` | Pass or fail for a run: every run converged, every window consistent, no router missing a new LSP. |

Start small: each router runs four FRR daemons, and a lab too large for the machine does not converge. CPU time on
a shared cloud machine is noisy; compare flood reduction off against on within one run.
