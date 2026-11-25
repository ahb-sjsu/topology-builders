# Flood reduction on flattened butterflies and leaf-spine fabrics: 64 routers

FRR pull request 24128 (`flood-reduction` under `router isis`, draft-ietf-lsr-distoptflood) at commit e263c441,
measured on two structured families of 64 routers: flattened butterflies, every factorization of 64 except the full
mesh (degree 6 to 32), and two-tier leaf-spine fabrics with 2 to 32 spines. Each topology ran with flood reduction off
and on, twice each; in each run 3 links were taken down and brought back up, one at a time, with a 30 s window after
each change. The random regular graph of degree 16 from the [random-regular sweep](../random-regular-n64/README.md)
was run again first, as a check on the change of setup.

Runs of 2026-11-19 17:01 UTC to 2026-11-20 00:38 UTC. Data: `measurements.jsonl.gz` (one JSON line per run, with
per-router figures); `topologies.tar.gz`, the 20 topology files the labs were written from (matched by sha256);
`model.txt`, the flooding model's count for the same links (`tools/model/validate.py`, as in
[random-regular-n64](../random-regular-n64/README.md)). The tables are from `topology-builders report
measurements.jsonl.gz`, rounded. The two-hop
multiplicity (for two routers two hops apart, the mean number of neighbours they share) is computed from the topology
files; it was added to the package after these runs, so the records themselves do not carry it.

## Flattened butterflies: 60% to 75% fewer LSPs for a link change, from degree 6

LSPs are Level-2 LSPs sent, summed over the 64 routers, mean per window; each topology has 12 link windows per variant
(2 runs x 3 links x down and up). CPU is isisd's CPU summed over the routers, net of a quiet window of the same
length; the median is over the 6 pairs (same link and direction, off against on).

| Radices | Degree | Diameter | 2-hop multiplicity | LSPs sent, off | on | Fewer | CPU lower, median (pairs lower) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2x2x2x2x2x2 (6-cube) | 6 | 6 | 2 | 576 | 231 | 60% | 8% (4 of 6) |
| 4x2x2x2x2 | 7 | 5 | 2 | 701 | 256 | 63% | 12% (4 of 6) |
| 4x4x2x2 | 8 | 4 | 2 | 785 | 278 | 65% | 19% (6 of 6) |
| 4x4x4 | 9 | 3 | 2 | 881 | 280 | 68% | 22% (6 of 6) |
| 8x2x2x2 | 10 | 4 | 2 | 1,027 | 351 | 66% | 6% (5 of 6) |
| 8x4x2 | 11 | 3 | 2 | 1,164 | 372 | 68% | -18% (2 of 6) |
| 8x8 | 14 | 2 | 2 | 1,532 | 418 | 73% | 2% (3 of 6) |
| 16x2x2 | 17 | 3 | 2 | 1,873 | 570 | 70% | 6% (4 of 6) |
| 16x4 | 18 | 2 | 2 | 2,000 | 496 | 75% | 18% (5 of 6) |
| 32x2 | 32 | 2 | 2 | did not converge | 560 | | |

- Random regular graphs of the same degree saved far less in the random-regular sweep: 23% at degree 6 and 36% at
  degree 8. They reached 75% only at degree 16. LSP counts carry over between the two setups (see the check below);
  CPU figures do not.
- The CPU an event costs shows no consistent difference on butterflies: the median over pairs runs from 18% more to
  22% less.
- Bring-up, from the routers' start to convergence: 25% to 53% fewer LSPs and 10% to 31% less isisd CPU from degree 6
  to 18, the two runs of each variant never overlapping.

## Leaf-spine: with flood reduction on, a link change costs about 170 to 190 LSPs at any number of spines

| Spines | Leaves | Average degree | 2-hop multiplicity | LSPs sent, off | on | Fewer | CPU lower, median (pairs lower) | Bring-up: fewer LSPs, less CPU |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 2 | 62 | 3.9 | 2.03 | 375 | 168 | 55% | 25% (6 of 6) | 10%, 3% |
| 3 | 61 | 5.7 | 3.09 | 610 | 169 | 72% | 22% (6 of 6) | 18%, 6% |
| 4 | 60 | 7.5 | 4.19 | 802 | 164 | 79% | 29% (6 of 6) | 32%, 13% |
| 6 | 58 | 10.9 | 6.47 | 1,144 | 180 | 84% | 25% (6 of 6) | 33%, 13% |
| 8 | 56 | 14.0 | 8.86 | 1,549 | 180 | 88% | 37% (6 of 6) | 46%, 21% |
| 12 | 52 | 19.5 | 13.9 | 2,252 | 178 | 92% | 29% (6 of 6) | 53%, 31% |
| 16 | 48 | 24.0 | 19.1 | 2,795 | 183 | 93% | 40% (6 of 6) | 66%, 43% |
| 24 | 40 | 30.0 | 28.2 | did not converge | 192 | | | |
| 32 | 32 | 32.0 | 32.0 | did not converge | 194 | | | |

- With flood reduction off, LSPs for a link change grow with the number of spines; with it on they stay between 164
  and 194 from 2 spines to 32.
- isisd CPU for a link change is lower with flood reduction on in every pair at every size that converged, by a
  median of 22% to 40%: the most consistent CPU result of the three families.
- The leaves have only as many links as there are spines, but every spine is linked to every leaf, so two leaves
  share all the spines. That redundancy is what the two-hop multiplicity counts.

## At 960 and 1,024 links, without flood reduction the routers never converged on 20 CPUs

| Topology | Links | Runs converged, off | on | Bring-up LSPs, off | on |
|---|---:|---:|---:|---:|---:|
| Flattened butterfly 32x2 | 1,024 | 0 of 2 | 2 of 2 | 15.3 million | 266,000 |
| Leaf-spine, 40 leaves x 24 spines | 960 | 0 of 2 | 2 of 2 | 16.9 million | 240,000 |
| Leaf-spine, 32 leaves x 32 spines | 1,024 | 0 of 2 | 2 of 2 | 18.0 million | 269,000 |

- With flood reduction off, the routers' LSP databases still differed after 300 s more of checking, in every run;
  the quiet and link windows were then violated. With it on, every run passed the first check, 30 s after
  deployment, and every window was satisfied.
- The leaf-spine fabric with 16 spines (768 links) converged with flood reduction off. In the random-regular sweep,
  which had about 25 CPUs and no pinning, degree 32 (1,024 links) converged and degree 48 (1,536) did not. On these
  20 CPUs the limit falls somewhere between 768 and 960 links, whatever the family. That is an inference from these
  few points, not a measured threshold. A fat-tree with k = 12 (180 routers, 864 links) later converged without
  flood reduction on the same 20 CPUs ([fat-tree](../fat-tree/README.md)).
- All 64 routers share the CPU set, so this is about the total work, not about a router with CPUs of its own. The
  load average on the host reached about 200 during these runs; the work stayed on the container's 20 CPUs, the
  hottest CPU sensor read at most 76 C at the start and end of each run, and the host's own network was not
  affected.

## Check: random regular, degree 16, in both setups

| Degree 16, off -> on | Random-regular sweep (host, unpinned) | This setup (container, 20 CPUs) |
|---|---|---|
| LSPs per link change | 1,749 -> 436 (75% fewer) | 1,684 -> 435 (74% fewer) |
| isisd CPU per link change, median over pairs | 19% lower (6 of 6) | 10% lower (6 of 6) |
| Bring-up | 47% fewer LSPs, 25% less CPU | 48% fewer LSPs, 26% less CPU |

LSP counts and bring-up figures carry over between these two Docker setups; the CPU figure for a single link
change does not. On Colab's namespace labs, bring-up saved less (15% to 32%;
[colab-sessions](../colab-sessions/README.md)).
Compare CPU across families only within one setup.

## Two-hop multiplicity, not degree, lines up with the saving at low degree

Three topologies with a two-hop multiplicity near 2 save about the same share of link-change LSPs, at very different
degrees: the 6-cube (degree 6) 60%, leaf-spine with 2 spines (degree 3.9) 55%, and the random regular graph of degree
12 (multiplicity 2.35) 59%, the last from the random-regular sweep. The random regular graph of degree 6 has a
multiplicity of 1.18 and saves 23%, although its expansion (second adjacency eigenvalue over degree) is the same as
the 6-cube's, 0.68 and 0.67. Where two routers are joined by more than one two-hop path, a flooding rule that decides
from two hops can choose which neighbor passes the LSP on; it also drops copies across triangles, so the
multiplicity is an indicator, not a condition. Within the butterflies the multiplicity stays at 2 while the saving still rises
from 60% to 75% with degree, so degree matters as well. This is a pattern across a few graphs, one of each, not a
fitted model.

## How it was run

```
topology-builders sweep --routers 64 --out topos
topology-builders clab topos/<file> --out labs/<name> --name <name> --image frr-distoptflood:e263c441 \
    --cpu-set 12-23,36-43
topology-builders measure labs/<name>/off labs/<name>/on --repeat 2 --links 3 --max-wait 300 --out families.jsonl
```

- Configuration and image as in the random-regular sweep: the pull request's topotest configuration (level-2-only,
  point-to-point, hello 1 s x 3, lsp-gen-interval 2) and FRR built from riw777/frr at e263c441.
- Setup: containerlab and its own Docker (29.1.3) ran inside a privileged LXD container with nesting, with its own
  network namespace and limited to CPUs 12-23 and 36-43 of the host (an HP Z840 with two Xeon E5-2690 v3, 25 logical
  CPUs online); every router was also pinned to those CPUs. containerlab 0.78.2, topology-builders 0.1.0.
- A watcher on the host checked every minute that its own uplink was configured and could reach the router, and
  would have stopped the sweep before the next topology if not. It never did.
- Other load: from 19:18 to 19:29 UTC, during the 8x8 butterfly's runs, a small lab of ours ran in a container
  limited to CPUs 44-47, which share physical cores with CPUs 20-23, four of the routers' 20; that container's
  one-minute setup at 19:07 fell during the 8x4x2 butterfly's runs. They can have raised CPU times in the windows
  they overlapped; LSP counts do not depend on them. No other topology overlapped such a job.
- Background load throughout: a console demo engine of ours (running since 2026-09-28) used about 60% of one CPU on
  average, and the host's own Docker daemons, outside the lab container, three to five CPUs. The engine may run on
  any of CPUs 12-23 and 36-47, the routers' among them, so it slows whichever routers share a CPU with it at the
  time; that affects both variants alike, since they took turns, and does not change which LSPs are sent. An earlier
  version of this README did not mention it.
- The links are chosen from the topology file and seed 1, the same for off and on; the labs take turns and the
  order alternates between the two runs. Before each run the harness waited until the hottest CPU sensor was below
  80 C.

## Not covered by these runs

- One graph per topology, 64 routers, 2 runs and 3 links each.
- Convergence time, and failures other than one link at a time: see [timing-n64](../timing-n64/README.md) (router
  and three-link failures) and [flap10-n64](../flap10-n64/README.md) (ten links at once).
