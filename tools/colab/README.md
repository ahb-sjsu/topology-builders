# The labs on Google Colab

The labs without Docker: every router is a network namespace of the Colab machine running real FRR daemons, every
link a veth pair, driven by `measure --backend netns` inside `unshare -Urnm`.

**Status (2026-11-20):** not yet run end to end. A Colab CPU runtime allowed a user namespace with veth pairs on
2026-11-20 (root, capabilities `0xa82c25fb`: Docker's default set plus SYS_ADMIN and SYS_PTRACE); Kaggle's runtime
did not (unshare is refused). The namespace backend's unit tests pass. `test_in_docker.sh` is the next check.

| File | What it does |
|---|---|
| `topology_builders_colab.ipynb` | The notebook: check the runtime, set up, build a topology, measure flood reduction off and on, report, download the measurements. |
| `setup.sh` | Builds FRR from FRR pull request 24128 (riw777/frr at e263c441) with only mgmtd, zebra, staticd and isisd, and installs topology-builders. Ubuntu 24.04, as root. |
| `test_in_docker.sh` | Runs the recipe on any Linux machine with Docker, in a container with Colab's capabilities and no network: setup, then a 16-router random graph and a k = 4 fat-tree. |

Start small: each router runs four FRR daemons, and a lab too large for the machine does not converge. CPU time on
a shared cloud machine is noisy; compare flood reduction off against on within one run.
