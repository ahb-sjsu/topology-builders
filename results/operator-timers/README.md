# The study's timers against FRR's defaults

The same topology files under two timer sets, on 2026-11-22. One is the study's: hello 1 s x 3, `lsp-gen-interval`
2, as in every other result here. The other is FRR's defaults (`isis_constants.h`): hello 3 s x 10,
`lsp-gen-interval` 30. Both use 60 s windows, so that a 30 s generation interval has room. The four 64-router files
are those of the families and seeds runs. The 256-router file is that of `random-regular-n256`, whose labs under the
study's timers never converged.

- **Setup:** every lab in a KVM guest (`tools/overlay/run_vm.sh`), 16 vCPUs on CPUs 12-23,36-43 of an HP Z840, with
  no network device. Inside it, the namespace backend in the `tb-colab-test` image: FRR pull request 24128 at
  e263c441, built by `tools/colab/setup.sh`. Flood reduction off and on, two runs each, three links taken down and
  brought back up per run.
- **Every run converged,** and every window ended consistent (24 of 24 per row).

## Link changes

Mean LSPs sent per link window, off -> on; isisd ms per link window net of the quiet window, summed over the
routers.

| Topology | Timers | LSPs off -> on | Saving | isisd ms off -> on | Saving |
|---|---|---|---:|---|---:|
| Random regular, degree 16, 64 routers | study | 1,587 -> 436 | 73% | 1,937 -> 1,448 | 25% |
| | FRR defaults | 1,606 -> 433 | 73% | 2,558 -> 2,019 | 21% |
| Flattened butterfly 4 x 4 x 4 | study | 892 -> 276 | 69% | 1,544 -> 791 | 49% |
| | FRR defaults | 848 -> 275 | 68% | 1,022 -> 592 | 42% |
| Leaf-spine, 48 leaves x 16 spines | study | 2,560 -> 175 | 93% | 3,046 -> 1,830 | 40% |
| | FRR defaults | 2,636 -> 176 | 93% | 2,733 -> 1,022 | 63% |
| Random regular, degree 32, 64 routers | study | 3,696 -> 235 | 94% | 6,445 -> 3,396 | 47% |
| | FRR defaults | 3,683 -> 232 | 94% | 5,368 -> 2,898 | 46% |
| Random regular, degree 16, 256 routers | FRR defaults | 9,085 -> 7,013 | 23% | 79,550 -> 84,913 | -7% |

## Bring-up

Mean LSPs sent from the routers' start.

| Topology | Study timers, off -> on | Saving | FRR defaults, off -> on | Saving |
|---|---|---:|---|---:|
| Random regular, degree 16, 64 routers | 168,678 -> 110,066 | 35% | 76,956 -> 72,174 | 6% |
| Flattened butterfly 4 x 4 x 4 | 66,584 -> 42,468 | 36% | 44,550 -> 41,212 | 7% |
| Leaf-spine, 48 leaves x 16 spines | 168,310 -> 115,781 | 31% | 118,328 -> 109,756 | 7% |
| Random regular, degree 32, 64 routers | 714,944 -> 216,851 | 70% | 168,016 -> 147,858 | 12% |
| Random regular, degree 16, 256 routers | never converged (`random-regular-n256`) | | 3,885,868 -> 2,904,726 | 25% |

## What this shows

- **Link changes do not depend on the timers.** On the four 64-router graphs, flood reduction's LSP saving for a
  link change is the same under both sets, within one point, and the LSPs sent with it on agree within 3 per window
  (436 and 433, 276 and 275, 175 and 176, 235 and 232).
- **Bring-up does.** Under FRR's defaults, bring-up without flood reduction sends far fewer LSPs: 168,016 against
  714,944 at degree 32, and fewer than half at degree 16. The saving then shrinks from 31-70% to 6-12%. A likely
  reason, not checked against the logs: the 30 s generation interval folds many adjacency changes into each new LSP.
- **The 256-router graph of degree 16 converges under FRR's defaults.** Under the study's timers it never did, on
  the host's 20 CPUs or in an hour in a guest. Here every run converged. Its link-change saving is 23%, less than at
  64 routers of the same degree (73%), as the two-hop multiplicity falls with size (1.50 against 3.94).
- **isisd CPU** falls by 21% to 63% per link change on the 64-router graphs, under both sets. That is more than in
  the earlier host runs, and noisy: single windows vary up to sevenfold within a variant, and two came out negative
  net of the quiet window. At 256 routers it does not fall at all. Route computation (`isis_run_spf_cb`, about 80 s
  per link window summed over the routers) is nearly all of isisd's time there, and flood reduction does not shorten
  it (`report-frr-default-timers.txt`, per handler).

One topology file per graph, three links, two runs. Without flood reduction, namespace labs send 8% to 10% fewer
LSPs than Docker labs on the same links (`tools/overlay/README.md`). The flooding model's comparison for these files
is not done yet.

## Files

- `measurements.jsonl.gz`: all 36 records (9 labs x 2 variants x 2 runs). The timer set is in each record's
  `settings` (`hello_interval`, `hello_multiplier`, `lsp_gen_interval`).
- `report-study-timers.txt`, `report-frr-default-timers.txt`: `topology-builders report`, one per timer set, so
  that the sets never pool.
- `topologies.tar.gz`: the five topology files. The links taken down follow from each file's sha256.

## How it was run

```
topology-builders clab <file>.json --out labs/<name> --name <name> \
    [--hello-interval 3 --hello-multiplier 10 --lsp-gen-interval 30]    # the second set: FRR's defaults
# in a KVM guest, through tools/overlay/run_vm.sh and tools/overlay/jobs/netns:
unshare -Urnm topology-builders measure labs/<name>/off labs/<name>/on --backend netns --profile --links 3 \
    --repeat 2 --max-wait 600 --window 60
topology-builders report measurements.jsonl.gz
```
