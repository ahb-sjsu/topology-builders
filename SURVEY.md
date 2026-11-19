# Survey of topology builders

Checked 2026-11-18. Each entry was checked against its primary source: the repository (licence file and last
commit through the GitHub or GitLab API), the project's documentation, or its paper. "Unverified" marks what could
not be checked. Licences are as stated in the licence file, which is not always what GitHub reports. Nothing listed
here was run, except NetworkX, which this repository uses.

The question: is there already a findable collection of network topology builders, meaning code that generates
topologies, as distinct from collections of topology data? And if not, what exists that this repository should link
to or wrap instead of rewriting?

## Summary

- **No maintained catalogue of network topology builders was found.** The lists that exist are frozen: the ns-2
  topology generation page (last modified 2001), Sally Floyd's ICIR list (2008), and CAIDA's tools taxonomy (not
  maintained since 2004, and it lists no generators). The most recent survey of network topology generators found
  is Haddadi et al., 2008.
- **The closest living collections are each something narrower.**
  - FNSS has generators, parsers and exporters to simulators, but was last released in 2020.
  - EvalNet has 25 data-centre and HPC generators and is active, but writes adjacency lists and has no exporters.
  - TopoHub is mainly a dataset, with one generator family (Gabriel graphs). It uses the same output format as this
    repository.
  - SST's `anytopo_utility` returns NetworkX graphs for four HPC families.
- **Fixed-size density is available in pieces.** Graph libraries have it (random regular, G(n, m), Harary graphs),
  as do the Jellyfish generators. Topology Bench publishes a pre-generated grid of 10 densities at every size from
  10 to 100 nodes, but its generator is closed source. No tool found treats a density sweep as a command.
- **From graph to router configuration is the main gap.** No maintained tool was found that takes an arbitrary graph
  file and writes FRR IS-IS configuration.
  - VFTGen writes FRR IS-IS and OpenFabric for fat-trees only, states no licence, and was last changed in 2021.
  - topomate reads an edge list and writes FRR IS-IS, but was last changed in 2021.
  - AutoNetkit 0.11 has a Quagga IS-IS template; it is Python 2, from 2014.
  - netlab writes FRR IS-IS from its own YAML, and has no graph import.
  - dot2net goes from a DOT graph to FRR configs to containerlab, and ships no IS-IS template.

## 1. Catalogues, collections and surveys

| Name | What it collects | Generators or data | Last activity | Licence | Link |
|---|---|---|---|---|---|
| ns-2 topology generation page (ISI) | Links to Inet, GT-ITM, Tiers, BRITE | Links | Last modified 2001-11-22 | Not stated | [page](https://www.isi.edu/nsnam/ns/ns-topogen.html) |
| ICIR "Topologies" (Sally Floyd) | Links to GT-ITM, BRITE, Inet, Tiers, Rocketfuel, SGB-format generators | Links | Last modified January 2008 | Not stated | [page](https://www.icir.org/models/topologies.html) |
| CAIDA tools taxonomy, topology section | Measurement, visualisation and analysis tools | Neither | "Not actively maintained since 2004" | Not stated | [page](https://www-old.caida.org/tools/taxonomy/topology.xml) |
| OMNeT++ models and tools catalogue | A GT-ITM converter, a BRITE exporter patch, ReaSE | Links | Topology entries from 2008-2013 | Not stated | [page](https://omnetpp.org/download/models-and-tools) |
| ns-3 topology-read and BRITE module | Readers for Inet, Orbis and Rocketfuel files; BRITE built from ns-3's fork | Readers and one generator | Docs updated 2026-11-14 | GPL-2.0 (ns-3) | [topology-read](https://www.nsnam.org/docs/models/html/topology.html), [BRITE](https://www.nsnam.org/docs/models/html/brite.html) |
| FNSS (Saino, Cocora, Pavlou) | Generators: Erdős–Rényi, Waxman, Barabási–Albert, GLP, ring, star, mesh, two- and three-tier, fat-tree, BCube. Parsers: Rocketfuel, CAIDA, Inet, BRITE, Zoo, aSHIIP. Exporters: ns-2, Mininet, OMNeT++, jFed, AutoNetkit | Generators, parsers, exporters | Last commit 2024-11-13; last PyPI release 0.9.1, 2020-10-24 | BSD-2-Clause | [repo](https://github.com/fnss/fnss) |
| EvalNet (SPCL, ETH Zurich; IPDPS 2026) | 25 interconnect generators (see section 3) and path-diversity analysis | Generators | Last commit 2026-07-14 | BSD-3-Clause text with an added disclaimer | [repo](https://github.com/spcl/EvalNet) |
| TopoHub (Jurkiewicz) | 3,600 seeded Gabriel graphs; Zoo, SNDlib, CAIDA and synthetic backbone sets; generator code for Gabriel graphs and backbones; a Mininet helper | Data and one generator family | Last commit 2026-10-11 | Code MIT; data not stated | [repo](https://github.com/piotrjurkiewicz/topohub) |
| Topology Bench (Matzner et al., UCL) | 105 real optical networks and 270,900 synthetic ones | Data only: its README marks the generator "Closed Source" | Zenodo v4, 2024-10-11 | Data CC BY 4.0 | [Zenodo](https://zenodo.org/records/13921775) |
| GNNet / RouteNet datasets (BNN-UPC) | Simulated samples on topologies generated with PLOD | Data; the generator is not shipped | Repos pushed 2024-2025 | Mixed; dataset none stated | [dataset](https://bnn.upc.edu/challenge/gnnet2021/dataset/) |
| Awesome lists | networktocode/awesome-network-automation covers lab tools but has no generator section; the graph-generation lists cover deep-learning generators | Links | Active | Various | [awesome-network-automation](https://github.com/networktocode/awesome-network-automation) |

Survey papers:

- H. Tangmunarunkit, R. Govindan, S. Jamin, S. Shenker, W. Willinger, "Network topology generators: degree-based
  vs. structural," ACM SIGCOMM 2002, pp. 147-159, doi:10.1145/633025.633040. Degree-based generators match the
  large-scale structure of measured topologies better than the structural (hierarchical) ones.
- H. Haddadi, M. Rio, G. Iannaccone, A. Moore, R. Mortier, "Network topologies: inference, modeling, and
  generation," IEEE Communications Surveys & Tutorials 10(2):48-69, 2008, doi:10.1109/COMST.2008.4564479. Router- and
  AS-level inference, models and generators; Table 2 compares GT-ITM, Inet, BRITE, PFP and IGen.
- A. Bonifati, I. Holubová, A. Prat-Pérez, S. Sakr, "Graph generators: state of the art and open challenges," ACM
  Computing Surveys 53(2), 2020, doi:10.1145/3379445. General graph generators; computer-network topologies are not
  among its areas.
- D. Chakrabarti, C. Faloutsos, "Graph mining: laws, generators, and algorithms," ACM Computing Surveys 38(1), 2006,
  doi:10.1145/1132952.1132954.

## 2. Internet, WAN and AS-level generators

| Name | What it builds | Fixed-size density knob | Output | Licence | Last activity | Link |
|---|---|---|---|---|---|---|
| NetworkX 3.7 | Random regular, G(n, m), G(n, p), Waxman, random geometric, Barabási–Albert, configuration and Chung–Lu models, joint-degree (2K), `random_internet_as_graph`, Harary graphs, hypercube | Yes: `random_regular_graph(d, n)`, `gnm_random_graph(n, m)`, `hnm_harary_graph(n, m)`, Waxman `beta`, geometric radius | Node-link JSON, GraphML, GML, DOT, edge lists and more | BSD-3-Clause | Release 3.7, 2026-09-21 | [repo](https://github.com/networkx/networkx) |
| igraph | G(n, m), k-regular, geometric random, Barabási–Albert, degree-sequence, Chung–Lu, SBM, Kautz, de Bruijn. No Waxman. | Yes: G(n, m), k-regular, radius | GraphML, GML, Pajek, edge lists, DOT | GPL-2.0 | C core 1.0.1, 2025-12-26 | [repo](https://github.com/igraph/igraph) |
| graph-tool 3.9 | Degree-sampled random graphs, rewiring, Price (BA), SBMs, geometric, Delaunay, kNN, lattices | Yes: degree sampler, radius, k | .gt, GraphML, GML, DOT | LGPL-3.0-or-later | conda-forge 3.9, 2026-09-24 | [docs](https://graph-tool.skewed.de/static/docs/stable/generation.html) |
| SNAP | G(n, m), k-regular, power-law, configuration model, preferential attachment, small world, forest fire, R-MAT | Yes: `GenRndGnm`, `GenRndDegK` | Edge list, Pajek, DOT | BSD-3-Clause | Last commit 2023-02-28; dormant | [repo](https://github.com/snap-stanford/snap) |
| TopoHub | Gabriel graphs, 5 to 500 nodes | No: a Gabriel graph is fixed by its node positions | Node-link JSON (`edges`), GML, SVG; Mininet classes | MIT | Last commit 2026-10-11 | [repo](https://github.com/piotrjurkiewicz/topohub) |
| MoleNetwork / molenetgen (Sánchez-Macián et al.) | Operator-style backbone, metro core and metro aggregation | Yes: node count plus a degree distribution | Excel, images | GPL-3.0 | Pushed 2025-07-16 | [repo](https://github.com/amacian/molenetgen) |
| dk-series (Nakajima) | dK randomisation (d = 0 to 2.5) of an input graph | No: keeps the input's size and link count; useful to randomise a graph after densifying it | Edge list; NetworkX and igraph | MIT | Pushed 2026-03-19 | [repo](https://github.com/kazuibasou/dk-series) |
| COLD (Bowden, Roughan, Bean; CoNEXT 2014) | Cost-optimised PoP-level networks by genetic algorithm | Indirect: link cost weights | MATLAB struct | None stated | Last commit 2012-06-18 | [repo](https://github.com/rhysbowden/COLD) |
| BRITE (Boston University) | Waxman and Barabási–Albert, router or AS level, hierarchies | Yes: links per new node `m` | BRITE format | Original: README permissive, source headers "research only". ns-3 fork: GPL-2.0 | BU: "no longer supported"; ns-3 fork last commit 2026-05-01 | [BU](https://www.cs.bu.edu/brite/), [ns-3 fork](https://gitlab.com/nsnam/BRITE) |
| GT-ITM (Georgia Tech) | Waxman and other flat random graphs, N-level hierarchy, transit-stub | Yes: edge probability `alpha` | Stanford GraphBase; `sgb2ns` for ns-2 | None stated | Tarballs 1997-98 | [page](https://sites.cc.gatech.edu/projects/gtitm/) |
| Tiers 1.1 (Doar) | WAN/MAN/LAN hierarchy | Yes: redundancy per level | Text; awk converter for ns-2 | Custom: modified code may be distributed only as patches | 1998; ISI link returns 403, Wayback copy downloads | via ns-2 page |
| IGen 0.15 (Quoitin) | Network-design heuristics (MENTOR, Delaunay, two-trees, Harary), IGP weights | Yes for Harary k at fixed n | GML, BRITE, TOTEM and others; C-BGP scripts | README says LGPL, COPYING is GPL-2.0 | 2009-2010; still downloadable | [site](http://igen.sourceforge.net) |
| Inet-3.0 (U. Michigan) | AS-level graphs matching a degree distribution (N ≥ 3037 recommended) | Weak: fraction of degree-1 nodes | Text | BSD-style with an acknowledgement clause | 2002; site dead, Wayback copy downloads | (dead) |
| Orbis 0.70a, nem 0.9.6, aSHIIP | dK-series; power-law Internet-like; AS-level hierarchy | Unverified | Unverified | Orbis BSD-4-Clause (CAIDA catalogue); nem LGPL-3.0 (its page) | Downloads fail (403, server error, TLS) | (unreachable) |

Not found: code for the HOT generators of Li, Alderson, Willinger and Doyle (SIGCOMM 2004), and a standalone PLRG
implementation. The PLRG model is available as Chung–Lu in NetworkX, igraph and SNAP.

Waxman's parameters are named the other way round in different tools: FNSS, GT-ITM and BRITE call the density
scale `alpha`, NetworkX calls it `beta`. A wrapper has to normalise them.

## 3. Data-centre and HPC interconnect generators

| Name | What it builds | Fixed-size density knob | Output | Licence | Last activity | Link |
|---|---|---|---|---|---|---|
| EvalNet (Besta et al.) | Hypercube, torus, flattened butterfly, multi-layer full mesh, orthogonal fat tree, Jellyfish, HyperX, Dragonfly, fat tree, Xpander, Slim Fly, Delorme, PolarFly (Brown) and its extension, Bundlefly, Kautz, arrangement network, XGFT, k-ary n-tree, mesh, Tofu, Cascade Dragonfly, SpectralFly, Megafly, PolarStar | Jellyfish `r n`. Xpander sizes are (d + 1) × the lifts. The algebraic families tie size to degree. | Adjacency list (`.adj.txt`) | BSD-3-Clause text with an added disclaimer | Last commit 2026-07-14 | [repo](https://github.com/spcl/EvalNet) |
| SST/Merlin `anytopo_utility` (Sandia) | Dragonfly, Slim Fly, PolarFly, Jellyfish, with shortest-path routing tables | `JellyfishTopo(n, degree, seed)`; the others come as precomputed pairs | NetworkX graph in memory; Merlin `anytopo` reads NetworkX or GraphML | BSD-3-Clause | Added 2026-06-29; in SST 16.1.0 | [repo](https://github.com/sstsimulator/sst-elements/tree/master/src/sst/elements/merlin/topology/anytopo_utility) |
| SST/Merlin topologies | Torus, mesh, fat tree, Dragonfly, HyperX, PolarFly, PolarStar, any graph | Parallel links only (HyperX `width`, Dragonfly link counts) | Inside the simulator | BSD-3-Clause | Release 16.1.0, 2026-11-11 | [repo](https://github.com/sstsimulator/sst-elements) |
| TopoBench (Singla, Jyothi, Godfrey et al.; ETH fork with Kassing) | Jellyfish, fat tree, VL2, BCube, DCell, Dragonfly, flattened butterfly, hypercube, LPS Ramanujan, Xpander | Jellyfish switches and ports | Linear programs for Gurobi; Xpander edge list | MIT | 2016 (original), 2018 (ETH fork) | [original](https://github.com/ankitsingla/topobench), [ETH](https://github.com/ndal-eth/topobench) |
| netbench (Kassing, Valadarsky, Singla) | MATLAB and Python generators: Xpander, Jellyfish, fat tree, BCube, DCell, binary butterfly, hypercube, LPS, 3-D torus | `jellyfish.m(n, d)`; Xpander needs n a multiple of d + 1 | `.topology` edge list | MIT (core and generators) | Last commit 2018-06-01 | [repo](https://github.com/ndal-eth/netbench) |
| BookSim 2 (Stanford) | k-ary n-fly, mesh, torus, flattened butterfly, Dragonfly, fat tree, any graph from file | No | Inside the simulator | BSD-2-Clause | Last commit on master 2017-06-27 | [repo](https://github.com/booksim/booksim2) |
| htsim (Broadcom csg-htsim) | Fat tree (2 or 3 tiers, oversubscribed), BCube, CamCube, Dragonfly, VL2, graph from file | Partly (per-tier radix) | Inside the simulator | BSD-2-Clause | Last commit 2026-03-23 | [repo](https://github.com/Broadcom/csg-htsim) |
| CODES (Argonne et al.) | Dragonfly variants, fat tree, Slim Fly, torus, express mesh | Unverified | Binary connection files | BSD-3-Clause | Last commit 2026-07-19 | [repo](https://github.com/codes-org/codes) |
| SimGrid | Torus, fat tree, Dragonfly clusters in platform files | Fat-tree parallel links | Inside the simulator | LGPL-2.1-only | v4.1, 2025-11-11 | [docs](https://simgrid.org/doc/latest/Platform_examples.html) |
| VFTGen (Kathará; Caiazzi, Scazzariello, Ariemma) | Three-level fat trees, single or multi plane, with Kathará lab and FRR configs | Parallel links per neighbour (`--ls_parallel`, `--st_parallel`, `--ring_parallel`) at fixed node counts | Kathará lab directory | None stated | Last commit 2021-05-28 | [repo](https://github.com/KatharaFramework/VFTGen) |
| containerlab `generate` | Multi-tier Clos, adjacent tiers fully meshed | No | containerlab topology file; no routing configs | BSD-3-Clause | Pushed 2026-11-18 | [docs](https://containerlab.dev/cmd/generate/) |
| Mininet `topolib`; RipL | Tree, 2-D torus; fat tree (RipL) | No | Mininet objects | BSD-3-Clause; RipL GPL-2.0 | 2023; RipL 2013 (moved to brandonheller/ripl) | [Mininet](https://github.com/mininet/mininet), [RipL](https://github.com/brandonheller/ripl) |
| PolarFly (Intel Labs) | PolarFly and its extension; converter to BookSim | No: size q² + q + 1 | BookSim `anynet` | MIT (archive) | GitHub 404; Zenodo copy 2022-09-02 | [Zenodo](https://zenodo.org/records/7042175) |

Two kinds of density knob appear here. Most tools vary the number of neighbours (Jellyfish degree). VFTGen, SST's
HyperX and SimGrid's fat tree instead add parallel links between routers that are already neighbours, which raises
the number of links and adjacencies without adding neighbours. For a flooding test these are different
experiments.

Not found: a standalone generator that exports a k-ary n-fly as a graph file (BookSim's exists only inside the
simulator; netbench's is binary only); a data-centre topology helper in ns-3 mainline (merge request 89, open since
2019, is not merged), INET or OMNeT++ core; an official home for INRFlow.

## 4. From a topology to a running lab

| Name | What it does | Reads an arbitrary graph file | Writes FRR IS-IS | Licence | Last activity | Link |
|---|---|---|---|---|---|---|
| containerlab | Container and VM labs from a YAML file; an `frr` node kind that handles daemons and `frr.conf` | No | No (minimal FRR config only) | BSD-3-Clause | v0.83.0, 2026-11-07 | [repo](https://github.com/srl-labs/containerlab) |
| netlab (ipspace) | Abstract YAML topology to containerlab or Vagrant plus device configs; leaf-spine `fabric` plugin | No | Yes, from its own YAML (`module: [isis]`) | MIT | PyPI `networklab` 26.10, 2026-10-03 | [repo](https://github.com/ipspace/netlab) |
| dot2net (Kobayashi et al.; CNSM 2023) | DOT graph plus config templates to per-node configs and containerlab, TiNET or Kathará files; can split across hosts | Yes: DOT | No template shipped (OSPF, BGP, RIP, EVPN examples) | Apache-2.0 | v0.8.1, 2026-08-25 | [repo](https://github.com/cpflat/dot2net) |
| topomate | YAML plus an edge-list file to FRR containers joined by Open vSwitch | Yes: edge list | Yes (`frr/isis.go`) | MIT | Last commit 2021-07-28 | [repo](https://github.com/topomate/topomate) |
| VFTGen | Fat-tree Kathará labs (see section 3) | No | Yes: isisd, and fabricd (OpenFabric) | None stated | Last commit 2021-05-28 | [repo](https://github.com/KatharaFramework/VFTGen) |
| AutoNetkit (Knight; CoNEXT 2013) | High-level graph to device configs; reads Topology Zoo GraphML | Yes: GraphML, JSON | 0.11.2: Quagga isisd (Python 2, 2014). 0.12: no IS-IS | BSD-3-Clause | Last commit 2021-07-06; github.com/sk2/autonetkit returns 404 | [repo](https://github.com/sk2/autonetkit-py) |
| FRR topotests (Topogen, topojson) | FRR's own test harness on Linux namespaces | Yes: a link dict or its own JSON schema | No: topojson builds OSPF, BGP, PIM, static, not IS-IS | ISC (these files) | Active | [topogen.py](https://github.com/FRRouting/frr/blob/master/tests/topotests/lib/topogen.py) |
| munet (LabN) | Namespaces, containers and VMs from a JSON, YAML or TOML config; runs under FRR topotests | No | No | GPL-2.0 | v0.17.3, 2026-09-16 | [repo](https://github.com/LabNConsulting/munet) |
| Kathará | Container labs from `lab.conf` or a Python API; FRR images; Kubernetes back end | No | No | GPL-3.0 | v3.8.4, 2026-11-06 | [repo](https://github.com/KatharaFramework/Kathara) |
| IPMininet | Mininet with FRR (OSPF, BGP, RIPng, PIM), OpenR and others | No | No IS-IS | GPL-2.0 | Last commit 2022-12-03 | [repo](https://github.com/cnp3/ipmininet) |
| nrx (netreplica) | NetBox or Cytoscape JSON to containerlab and other lab formats | Cytoscape JSON (with NetworkX output: unverified) | No | Apache-2.0 | v0.9.0, 2026-03-05 | [repo](https://github.com/netreplica/nrx) |
| topology_converter (NVIDIA/Cumulus) | Graphviz DOT to Vagrant and Ansible | Yes: DOT | No routing config | GPL-2.0 | v5.0.9, 2024-05-08; moved to GitLab | [repo](https://gitlab.com/cumulus-consulting/tools/topology_converter) |
| clabernetes, clab-io-draw, gns3fy | containerlab on Kubernetes; draw.io to containerlab; GNS3 API wrapper | No | No | BSD-3-Clause; MIT; MIT | Active; active; PyPI 2023 | [clabernetes](https://github.com/clabernetes/clabernetes) |

VFTGen configures FRR's OpenFabric daemon (fabricd). IETF Datatracker records draft-white-distoptflood as replacing
draft-white-openfabric, so VFTGen's OpenFabric labs are an earlier test bed for the same line of work.

Scale is unverified for every tool here at a few hundred FRR routers on one host.

## 5. What this means for this repository

**Wrap or read, with permissive licences:**
- NetworkX (used already).
- EvalNet's adjacency lists, for Slim Fly, Dragonfly, HyperX, PolarFly, Xpander and the rest.
- TopoHub's Gabriel graphs, which already use our output format.
- FNSS's data-centre families and its parsers.
- SST's `anytopo_utility`.

**Link to only:**
- VFTGen: no licence.
- Topology Bench: closed generator; the data is CC BY 4.0.
- BRITE, GT-ITM, Tiers and IGen: unclear or restrictive licences.
- Orbis, nem and aSHIIP: no longer downloadable.

**Write, because nothing maintained does it:**
- An exporter from a graph file to containerlab with FRR IS-IS configuration.
- An exporter to netlab YAML, as an independent second path.
- dot2net is worth evaluating first, because it already splits labs across hosts.

**Already new here:**
- A density sweep at a fixed number of routers as one command.
- A standalone k-ary n-fly exported as a graph file.
- Topology Zoo graphs made denser by nested link additions.

## 6. Dead or moved links (2026-11-18)

- topology-zoo.org: timed out. A mirror without a licence file is at
  [sk2/topologyzoo](https://github.com/sk2/topologyzoo), last commit 2012.
- Inet (topology.eecs.umich.edu/inet): redirect loop.
- Tiers at ISI: 403.
- Orbis: 403, and no archived copy.
- nem: download returns a server error.
- aSHIIP: TLS failure.
- github.com/sk2/autonetkit: 404; the code is at sk2/autonetkit-py.
- github.com/CumulusNetworks/topology_converter: 404; moved to GitLab.
- github.com/IntelLabs/PolarFly: 404; the Zenodo copy remains.
- github.com/mininet/ripl: 404; the code is at brandonheller/ripl.
