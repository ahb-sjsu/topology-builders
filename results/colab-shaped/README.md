# The Colab recipe, in a container shaped like Colab

`tools/colab/test_in_docker.sh` run on 2026-11-20: the recipe the Colab notebook uses, in a Docker container with a
Colab CPU runtime's permissions. **This is not a run on Colab itself.** The container is Ubuntu 24.04, root, with
Docker's default capabilities plus SYS_ADMIN and SYS_PTRACE (`CapEff 0xa82c25fb`, the set a Colab CPU runtime showed
on 2026-11-20), no network, and 2 CPUs of a two-socket Xeon workstation.

- **FRR:** built inside the container by `tools/colab/setup.sh` from FRR pull request 24128 (riw777/frr at e263c441),
  with libyang 2.1.128 built from source and only mgmtd, zebra, staticd and isisd. The `image` field in the records'
  lab settings is the lab writer's default for Docker labs and was not used.
- **Labs:** `measure --backend netns` inside `unshare -Urnm`: every router a network namespace with its own host
  name, every link a veth pair. A 16-router random graph of degree 4 (seed 1) and a k = 4 fat-tree (20 switches),
  flood reduction off and on, one run each, two links taken down and up, with timing logs and isisd's per-handler
  CPU accounting on.
- **Check** (`tools/colab/check_results.py`, [check.txt](check.txt)): every run converged, every window was
  consistent, and no router missed a new LSP.

**Against the Docker labs.** The same 16-router graph ran earlier in containerlab on the same workstation (FRR from
the same commit, three runs per variant: [docker-host.jsonl.gz](docker-host.jsonl.gz)); the two topology files
differ only in metadata, with the same 32 links. LSPs sent per window:

| Topology | Labs | Flood reduction | Bring-up | Link down | Link up | Flooding after a link goes down, ms |
|---|---|---|---|---|---|---|
| random, degree 4 | namespaces | off | 996 | 66-76 | 100-101 | 15-109 |
| random, degree 4 | namespaces | on | 985 | 51-53 | 72-82 | 10-21 |
| random, degree 4 | Docker | off | 1,265-1,313 | 75-81 | 105-111 | - |
| random, degree 4 | Docker | on | 1,160-1,193 | 52-53 | 70-79 | - |
| fat-tree k = 4 | namespaces | off | 1,268 | 65-67 | 99-107 | 13-14 |
| fat-tree k = 4 | namespaces | on | 1,258 | 44-46 | 67-72 | 25 |

Link-change counts in the namespace labs are within 12% of the Docker labs' on the same graph (the links taken down
differ: each run picks them by the topology file's hash). Bring-up sends 15 to 24% fewer LSPs, perhaps because the
routers start closer together in time without containers to create. With one run each and debug logging on, read
these as a check that the recipe works and agrees with the Docker labs, not as measurements; CPU times are not
comparable across the two setups.

Files: [netns.jsonl.gz](netns.jsonl.gz) (this run), [docker-host.jsonl.gz](docker-host.jsonl.gz) (the Docker labs),
[check.txt](check.txt). Reproduce on any Linux machine with Docker: `tools/colab/test_in_docker.sh 0-3 0-1`.
