# Four Topology Zoo networks, as they are and made denser

Four networks of the Internet Topology Zoo in TopoHub's packaging, measured on 2026-11-22:

| Network | Routers | Links |
|---|---:|---:|
| TataNld | 143 | 181 |
| Uninett2011 | 66 | 93 |
| Uunet | 42 | 77 |
| AttMpls | 25 | 56 |

- **Densities:** each network as it is, and also made denser with `zoo --method nearest` (shortest great-circle links
  first) to average degree 4 and 8, where those are above its own.
- **Timers:** all of them under the study's timers (hello 1 s x 3, `lsp-gen-interval` 2, 30 s windows). The four
  networks as they are also ran under FRR's defaults (hello 3 s x 10, `lsp-gen-interval` 30, 60 s windows).
- **Setup:** as in [operator-timers](../operator-timers/README.md): KVM guests, the namespace backend, FRR pull
  request 24128 at e263c441, two runs per variant, three links per run.
- **Every run converged,** and every window ended consistent.

## Link changes

Mean LSPs sent per link window, off -> on (link-down and link-up windows pooled, 12 per variant). `tables.txt` adds
bring-up and isisd CPU.

| Network | Added links | Average degree | Diameter | Two-hop multiplicity | Timers | LSPs off -> on | Saving |
|---|---:|---:|---:|---:|---|---|---:|
| TataNld | 0 | 2.53 | 28 | 1.05 | study | 468 -> 425 | 9% |
| | 0 | 2.53 | 28 | 1.05 | FRR defaults | 467 -> 425 | 9% |
| | 105 | 4.00 | 22 | 1.26 | study | 776 -> 469 | 40% |
| | 391 | 8.00 | 16 | 2.27 | study | 1,656 -> 595 | 64% |
| Uninett2011 | 0 | 2.82 | 9 | 1.07 | study | 254 -> 219 | 14% |
| | 0 | 2.82 | 9 | 1.07 | FRR defaults | 252 -> 218 | 13% |
| | 39 | 4.00 | 9 | 1.17 | study | 379 -> 238 | 37% |
| | 171 | 8.00 | 8 | 2.01 | study | 784 -> 278 | 64% |
| Uunet | 0 | 3.67 | 8 | 1.27 | study | 232 -> 140 | 40% |
| | 0 | 3.67 | 8 | 1.27 | FRR defaults | 226 -> 140 | 38% |
| | 91 | 8.00 | 5 | 2.18 | study | 556 -> 133 | 76% |
| AttMpls | 0 | 4.48 | 5 | 1.41 | study | 180 -> 78 | 56% |
| | 0 | 4.48 | 5 | 1.41 | FRR defaults | 178 -> 79 | 55% |
| | 44 | 8.00 | 4 | 2.38 | study | 337 -> 88 | 74% |

## What this shows

- **As they are, the four save 9% to 56% of the LSPs for a link change.** The order follows the two-hop
  multiplicity, not the size: TataNld 9% at 1.05, Uninett2011 14% at 1.07, Uunet 40% at 1.27 and AttMpls 56% at
  1.41.
- **At low multiplicity they save what random graphs save; above it, more.** TataNld and Uninett2011 are close to
  random regular graphs of similar multiplicity: 8% to 15% near 1.01 to 1.08, in `random-regular-n128`,
  `random-regular-n256` and the 64-router seeds. Uunet and AttMpls save more than the 64-router random graphs nearest
  their multiplicity: 23% at 1.18 (degree 6) and 36% at 1.42 (degree 8), in
  [random-regular-n64](../random-regular-n64/README.md). As with the butterflies, structure that the multiplicity does
  not capture changes the saving.
- **Made denser, they save more.** At average degree 4, TataNld and Uninett2011 save 40% and 37%. At 8, all four save
  64% to 76%. The links added are the shortest, as an operator adding regional links would choose. On TataNld
  they raise the two-hop multiplicity to 1.26 at degree 4 and keep the long paths: the diameter is still 16 at degree
  8 (4 with random links, top-level README).
- **FRR's default timers change nothing here.** The saving for a link change is the same within 2 points on all
  four. Bring-up savings shrink to 1% to 10%, as on the 64-router graphs (`../operator-timers`).
- **isisd CPU** for a link change is too small to measure in these networks: hundreds of milliseconds to a few
  seconds per window, summed over all routers, with differences of either sign. One is -349%, on 38 against 168 ms.

The flooding model's comparison for these files is not done yet.

## Data not included

The topology files are not here, because TopoHub's packaging states no license (see the top-level README). To
rebuild them from a local TopoHub copy:

```
topology-builders zoo <topohub>/data/topozoo/<Name>.json --method nearest --degrees <targets> --out topos/zoo-<Name>
```

`topologies.txt` lists the targets per network and each resulting file's sha256. The first target is just under the
network's own average degree, so no link is added. The links taken down follow from each file's sha256, so a file
that matches gives the same links. The source files' sha256, to check a copy against:

| Network | Source file sha256 |
|---|---|
| AttMpls | 0740b25cfce9a2596294ae73d045181bc939a0b7d55f99d7568ff0316fd7bc7d |
| TataNld | 63bef0d57890585f7fd943afc1d051e6ae08bfd7d368ecbf53532ea8c3f4661d |
| Uninett2011 | 0bbf4b152519fa1cdbbe24f3679e59827c9b225d972beccf573ba322a1c947b7 |
| Uunet | b892ff7f49c0c2bd06e37287619161d8d195b6cc5ed9a68fe35d12eccbe6dabb |

## One interrupted lab

During an ISP outage on 2026-11-22, the home router stopped answering at 19:22 UTC. The host's network watchdog
then stopped the AttMpls lab under FRR's defaults after 3 of its 4 runs. It ran again, complete, from 20:07 to 20:42
on the same topology file (same sha256). The table uses the complete run; the three interrupted runs are in
`interrupted-attmpls-frr-defaults.jsonl.gz`.

## Files

- `measurements.jsonl.gz`: the 56 records (14 labs x 2 variants x 2 runs). They carry each network's summary and
  the links taken down, not the graph.
- `tables.txt`: from `zoo_tables.py`. `topology-builders report` does not yet label Zoo graphs readably, so its
  report is not included.
- `topologies.txt`: zoo targets and topology sha256 per file.

```
python results/topology-zoo/zoo_tables.py results/topology-zoo/measurements.jsonl.gz
```
