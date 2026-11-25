"""The 256-router random regular graph of degree 16 under FRR's default timers (results/operator-timers): per link
window, LSPs sent and received, LSP retransmissions and sequence-number PDUs, with the LSPs sent as a share of the
full-flooding count U = 2(2(m - 1) - (n - 1)) of a link going down (data.tree_bound).

    python retransmissions.py <topology-builders results folder>
"""
import gzip
import json
import os
import sys


def main(results):
    with gzip.open(os.path.join(results, "operator-timers", "measurements.jsonl.gz"), "rt", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            t = r["topology"]
            if t["routers"] != 256:
                continue
            n, m = t["routers"], t["links"]
            full = 2 * (2 * (m - 1) - (n - 1))
            fr = "on " if r["settings"]["flood_reduction"] else "off"
            tm = "defaults" if r["settings"].get("hello_interval") != 1 else "topotest"
            for p in r["phases"]:
                if p["phase"] in ("link-down", "link-up"):
                    c = p["counters"]
                    print(f"{tm} {fr} repeat {r['repeat']} {p['phase']:<9} {p['outcome']:<10} tx_l2_lsp "
                          f"{c.get('tx_l2_lsp'):>6} ({100 * c.get('tx_l2_lsp', 0) / full:4.0f}% of U={full}) "
                          f"rx_l2_lsp {c.get('rx_l2_lsp'):>6} tx_lsp_rxmt {c.get('tx_lsp_rxmt')} "
                          f"tx_l2_psnp {c.get('tx_l2_psnp')} tx_l2_csnp {c.get('tx_l2_csnp')}")


if __name__ == "__main__":
    main(sys.argv[1])
