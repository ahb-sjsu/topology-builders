# Topology builders

Generators for network topologies whose density can be stepped while the number of routers stays fixed, so that
an experiment can tell the effect of density from the effect of size. The first use is testing an IS-IS flooding
reduction on denser and denser topologies.

## Families

| Family | What it is | Density knob at N routers |
|---|---|---|
| `random-regular` | Every router has exactly d links, chosen at random. networkx `random_regular_graph`; above d = (N - 1)/2, the complement of a random (N - 1 - d)-regular graph. A disconnected draw is drawn again. | d = 3, 4, 6, 8, 12, ... up to N - 1 (with N odd, even d only) |
| `leaf-spine` | Two-tier Clos: every leaf is linked to every spine | 2, 3, 4, 6, 8, ... spines up to N/2, the rest leaves |
| `flattened-butterfly` | Routers on a grid of radices k1 x k2 x ...; each is linked to every router that differs from it in one coordinate (Kim, Dally and Abts, ISCA 2007). One radix N is the full mesh; all radices 2 is the hypercube. | every factorization of N (a prime N has only the full mesh) |
| `zoo` | A Topology Zoo graph, in TopoHub's packaging, made denser by adding links: at random, or shortest great-circle distance first | target average degree, up to N - 1 |
| `k-ary-n-fly` | The butterfly: n stages of k^(n-1) switches, each linked to the k switches of the next stage whose position differs from its own in one base-k digit. Switches only, no hosts. | none: the size grows with k and n, so it is not in the sweep |

Random-regular and flattened-butterfly both end at the full mesh. Leaf-spine is densest at N/2 spines, where the
average degree is N/2.

The two ways of adding links to a Zoo graph give very different networks. On TataNld (143 routers, 181 links), at
an average degree of 8 the diameter is 16 hops with nearest-first and 4 with random links. Added links are nested:
with the same method and seed, every link added for a lower target is also there at a higher one, so a denser graph
differs from a sparser one only by the extra links.

## Output

Each topology is one JSON file in NetworkX node-link form, with keys `nodes` and `edges`, the shape TopoHub uses.
It can be read with `networkx.node_link_graph(data, edges="edges")`. Routers are named `r0`, `r1`, .... The graph
attributes record:

- the family, its parameters and how it was built;
- routers, links, average degree, density, minimum and maximum degree, whether it is connected, and the diameter in
  hops (left out, as null, when routers x links is over 20 million);
- the versions of this package, Python and networkx.

The `sweep` and `zoo` commands also write `manifest.json`, with each file's SHA-256 and summary. Nodes, edges and
keys are sorted, so the same versions and parameters give byte-identical files.

## Use

```
pip install topology-builders
```

The command is `topology-builders`; `python -m topology_builders` does the same.

```
python -m topology_builders sweep --routers 64 --seeds 1,2,3 --out out/n64
python -m topology_builders zoo <topohub>/data/topozoo/TataNld.json --method nearest --degrees 4,8,16 --out out/tata
python -m topology_builders build flattened-butterfly --radices 8,8 --out ff-8x8.json
python -m topology_builders build k-ary-n-fly --k 4 --stages 3 --out fly-4x3.json
```

Without `--degrees`, `zoo` steps from just above the graph's own average degree to the full mesh. The Zoo data is
not included, because TopoHub's packaging states no licence: point `zoo` at a local copy.

## FRR IS-IS labs

`clab` turns one topology file into a [containerlab](https://containerlab.dev) lab of FRR routers running IS-IS:

```
python -m topology_builders clab out/n64/random-regular-n64-d8-s1.json --out labs/rr64-d8
containerlab deploy -t labs/rr64-d8/off/random-regular-n64-d8-s1-off.clab.yml
```

By default it writes two labs, in `off/` and `on/`, which differ only in one line: `flood-reduction` under
`router isis`, the switch added by FRR pull request 24128 (draft-ietf-lsr-distoptflood). The `on` lab needs an FRR
image built with that change; FRR releases reject the command. The configuration follows that pull request's
topotest:

- level-2-only, with a passive loopback /32 on each router (10.255.0.0/16);
- each link point-to-point, with its own /31 (10.0.0.0/9);
- hello interval 1 s, hello multiplier 3, lsp-gen-interval 2 (each can be changed on the command line).

Each lab directory holds the containerlab file, one directory per router, `lab.json` (every router's loopback,
NET and port count, and every link's ports and addresses) and `manifest.json` (SHA-256 of each file). Node kind
`linux` (the default) mounts `frr.conf`, `daemons` and `vtysh.conf` into any FRR image and works with every
containerlab version. `--kind frr` uses containerlab's own FRR kind, which needs containerlab 0.80.0 or later. TopoHub
files can be given directly; their nodes are renamed r0, r1, ... in order, and `lab.json` keeps the original ids.

`python3 tools/check_isis.py <lab directory> [timeout]`, in this repository (pip does not install it), checks a
deployed lab through `docker exec`: every router
must have one adjacency Up per link and an LSP from every router. It retries every 5 s until the timeout (default
120 s) and exits non-zero if the lab never gets there.

Tests: `python -m pytest`. CI runs them, and ruff, on Python 3.10 to 3.13 on every push. They check each family
against its definition: degrees and connectivity; that the
flattened butterfly equals networkx's Cartesian product of complete graphs and the hypercube; that the butterfly has
exactly one forward path between each first-stage and each last-stage switch; and that zoo additions keep the
original links, nest, and with nearest-first add the shortest links. For the labs they check that ports run eth1 to
ethN on every router, that both ends of each link share a /31, that the containerlab file matches the link list, and
that the `on` and `off` configurations differ only in the `flood-reduction` line. For `measure` they check the
parsers against output captured from a live lab (`tests/fixtures`), the outcome rules, the choice of link and the
totals.

Measured on an HP Z840 (Xeon E5-2690 v3; Python 3.12.3, networkx 3.6.1), 2026-11-18:

- all 17 tests pass (23 since `measure` was added);
- the 64-router sweep with seeds 1, 2 and 3: 50 topologies, all connected, in 1.0 s in all (0.03 s or less each),
  and a second run gives byte-identical files (50 of 50 SHA-256 equal);
- random-regular at 256 routers, d = 3 to 255: 14 topologies in 3.1 s in all, the largest with 32,640 links;
- two `off` labs deployed with containerlab 0.78.2 and FRR 10.2.1. In each, every router had one IS-IS adjacency Up
  per link and an LSP from every router: the 8-router flattened butterfly 4 x 2 within 8 s of deployment, and a
  32-router random regular graph of degree 6 (96 links) within 5 s. The 32-router lab took 16 s to deploy, and
  each router used about 20 MiB. In the 8-router lab, router r0 had IS-IS routes to all 7 other loopbacks and
  reached a loopback two hops away.

## An FRR image from any commit

The `on` labs need FRR built with the flood-reduction change. `tools/frr-image/build.sh` builds an image from any FRR
commit with FRR's own Alpine packaging (`docker/alpine` in the FRR tree), so it has the layout of the official
images and the labs run on it unchanged:

```
CPUSET=36-47 THERMAL=1 tools/frr-image/build.sh work https://github.com/riw777/frr \
    e263c441160c7cf25749a9695978ffe5649678f9 frr-distoptflood:e263c441
python -m topology_builders clab topology.json --out lab --image frr-distoptflood:e263c441
```

- It uses Docker's classic builder, so buildx is not needed. FRR's Dockerfile needs BuildKit for two lines, so
  `make_dockerfile.py` writes a version without them: it drops the `# syntax=` line and replaces `COPY --exclude`
  with an extra stage that deletes the same packages. Every other line is FRR's.
- `CPUSET` caps the build's CPUs. FRR's packaging runs `make -j $(nproc)`, and `nproc` follows the cap.
- `THERMAL=1` holds the build under [batch-probe](https://github.com/ahb-sjsu/batch-probe)'s ThermalController.
  `thermal_pause.py` pauses the build's containers while the controller recommends fewer than half the build's
  CPUs.
- FRR's packaging runs FRR's unit tests, and the build fails if they do.

Built on the HP Z840 above, 2026-11-19, from FRR pull request 24128 at e263c441 (FRR 10.9.0-dev):

- 12 minutes on 12 CPUs; the CPU temperature peaked at 75.6 C, and the build was never paused;
- FRR's unit tests: 570 passed, 1 skipped, including the pull request's flood-reduction tests;
- image size 131 MB;
- on the 8-router flattened butterfly, the `off` and `on` labs each reached one adjacency Up per link and an LSP
  from every router within 8 s;
- in the `on` lab, `flood-reduction` was in the running configuration, and `show isis summary` listed the
  flooding-reduction counters;
- that image was built with a first version of these scripts. Rebuilt with `build.sh` itself (9 minutes, peak
  75.4 C), it gave the same FRR and libyang packages and the same test result. The image ID differs: the classic
  builder took steps 1 to 17 from its cache and ran the rest again, from `ARG PKGVER` on, for a reason not found.

## Measuring flooding and CPU

`measure` deploys labs written by `clab` and measures them around a link going down and coming back up:

```
topology-builders clab rr32.json --out labs/rr32 --image frr-distoptflood:e263c441
topology-builders measure labs/rr32/off labs/rr32/on --repeat 2 --out measurements.jsonl
```

One run of one lab:

1. Deploy it, then wait 30 s (`--settle`) without querying the routers.
2. Check that every router has one adjacency Up per link and the same LSPs as every other router; if not, keep
   checking every 5 s, for up to 120 s (`--max-wait`).
3. Snapshot every router: the PDU counters of `show isis summary` (sent, received and dropped, per PDU type), its
   flooding-reduction counters, and the CPU time of isisd and zebra from /proc. This closes the bring-up phase.
4. Take one link down, wait 30 s (`--window`) without querying, snapshot, then check that every router holds the
   same LSPs, including a newer LSP from each end of the link. Bring the link back up and do the same.
5. Destroy the lab.

- Counters and CPU in the link phases are differences between snapshots, so the checks between them are not
  counted. Bring-up counts from the routers' start, so it includes the convergence check.
- Each phase has an outcome: satisfied when every router holds the same LSPs and the new ones, violated when not,
  and unknown when a router could not be read.
- The link is chosen from the topology file and `--seed`, so the off and on labs use the same one. The labs take
  turns, and the order alternates between repeats.
- Each run is one JSON line, with per-router figures and the host's load average and CPU temperature at start and
  end. A table of means per lab and phase is printed at the end.

First runs, 2026-11-19, on the HP Z840 above with the image from FRR pull request 24128 at e263c441, 2 repeats of
each lab. The host's load average was 10 to 15 from other work. LSPs sent, summed over all routers, mean off and on:

| Topology | Bring-up | Link down | Link up |
|---|---|---|---|
| flattened butterfly 4 x 2: 8 routers, 16 links, degree 4 | 417.5 and 334 (-20%) | 45 and 17.5 (-61%) | 68.5 and 26 (-62%) |
| random regular: 32 routers, 96 links, degree 6 | 10,715 and 9,103 (-15%) | 246 and 153.5 (-38%) | 394 and 234 (-41%) |

- All 24 phases were satisfied: every router held every new LSP within the window, with flood reduction off and on.
- The differences between off and on are much larger than between repeats (link down on 32 routers: 256 and 236
  off, 157 and 150 on).
- isisd CPU time over each 30 s window did not differ between off and on (link down on 32 routers: 3,305 and
  3,315 ms). With hellos every second on every link, background work dominates a window of that length.
- Two topologies of different families and sizes, and one link each, say nothing yet about the effect of density.

## Not here yet

- A quiet control window, with no event, to subtract background CPU from the link windows.
- An exporter to netlab, as a second, independent path to FRR IS-IS.
- Fat-tree (three-tier Clos) by radix.

[SURVEY.md](https://github.com/ahb-sjsu/topology-builders/blob/main/SURVEY.md) lists the existing builders and lab tools, with licences and status, so that this repository
can link to and wrap them rather than rewrite them.

## License

Two licenses, split by what the file is.

| What | License | File |
|---|---|---|
| Code (`topology_builders/`, `tests/`) | MIT | `LICENSE` |
| Documentation (this README) | CC BY 4.0 | `LICENSE-TEXT` |
