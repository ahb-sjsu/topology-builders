# Analysis: the tree-bound table, four figures and the CPU statistics

These scripts read the published data in `results/` and measure nothing. Their outputs are in `output/` and
`figures/`; rerun from these files on the results of this commit, they give the same text outputs byte for byte.

| Script | Output | What it computes |
|---|---|---|
| `data.py` | | The window rules every output uses, and one row per graph and timer setting (a graph's runs from several folders pooled by family, parameters and size). |
| `tree_bound.py` | `output/tree_bound.txt`, `output/tree_bound.json` | LSPs sent per link-down window, flood reduction off and on, against the floor 2(n - 1) (two changed LSPs, each reaching n - 1 routers) and full flooding without duplicate suppression; the saving, and the share of the copies above the floor that flood reduction removed. |
| `figures.py` | `figures/fig1-density` to `fig4-failures` (.pdf, .png), `output/figures.txt` | LSPs per link-down against degree; saving against two-hop multiplicity; isisd CPU by event handler with per-run ranges; flooding time after one link, three links or a router fail. `figures.txt` lists every plotted number. |
| `review_checks.py` | `output/review_checks.txt` | (A) two triangles sharing a router: multiplicity 1, yet the model removes copies; (B) Spearman rank correlation and R² of a line in the logarithm, for saving against degree and against two-hop multiplicity; (C) isisd CPU per link change paired by run; (D) those pairs pooled per family and degree with 95% intervals. |
| `runtimes.py` | `output/runtimes.txt` | Runs per campaign, the time each run took and the campaign's span. |
| `retransmissions.py` | `output/retransmissions.txt` | For the 256-router graph of degree 16 under FRR's default timers: LSPs sent per link window as a share of full flooding, with FRR's LSP retransmission and CSNP/PSNP counters. |

**Window rules** (`data.py`). A link change is one link-down or link-up window, and LSPs are the level-2 LSPs sent,
summed over all routers. Only windows whose outcome is "satisfied" count. Timing runs are left out of counts and CPU.

**CPU statistics** (`review_checks.py`, parts C and D). For each run, isisd's CPU net of the idle window is averaged
over the run's satisfied link windows. The off and on runs with the same repeat index in a campaign form a pair, whose
saving is 1 - on/off of those averages. Pooled over the graphs of one family and degree, every pair is one value, so
each graph counts by its number of pairs. The interval is the mean plus or minus t(0.975, k - 1) s / sqrt(k) over the
k pair savings (Student's t). On the Colab sessions, one session is one value: the saving of its mean off and on runs.

```
pip install -e . matplotlib
cd tools/analysis
python tree_bound.py ../../results scratch output > output/tree_bound.txt
python figures.py ../../results scratch figures > output/figures.txt
python review_checks.py ../../results scratch > output/review_checks.txt
python runtimes.py ../../results > output/runtimes.txt
python retransmissions.py ../../results > output/retransmissions.txt
```

`scratch` receives the topology files extracted from the `topologies.tar.gz` archives. The failure analyses (the
mechanism lab and the cache experiment) are in `tools/model` and their results folders.
