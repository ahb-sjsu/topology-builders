"""A model of IS-IS LSP flooding, with and without distributed flooding reduction as specified in
draft-ietf-lsr-distoptflood-14 ("IS-IS Distributed Flooding Reduction", White, Hegde, Przygienda, Jalil, Voyer,
30 July 2026): the reflood decision of section 1.2.3 and the reverse optimization of section 1.2.2. It counts LSP
transmissions; it does not model CPU, timers, retransmissions, the flooding failure recovery of section 1.2.4, or
the database exchange over a new adjacency.

Where the draft leaves a choice open, this module makes one and says so:
- Step 1C(iii) excludes routers "on the shortest path" from the transmitting neighbor (TN) towards the originator;
  section 1.2.2 speaks of "any of the shortest paths". Both are read here as any shortest path.
- Step 3's Fletcher-16 is read as the draft's Figure 2 pins it: over the 8-octet LSP ID (system ID, pseudonode,
  fragment shifted down by 3 bits), a running byte sum A and a running sum B of A, H = B * 256 + A, with modulo 255
  replaced by folding the carry back in (x & 0xFF) + (x >> 8). Figure 2's inputs never carry, so the fold is the
  common simplified variant, not something the figure tests.
- The draft has no rule for a neighbor the topology snapshot does not show as adjacent (for example a new adjacency
  whose LSPs have not yet passed the two-way check); `unknown` chooses: "flood" (default) or "skip".
- When the calculation cannot be made (TN or the local router missing from the snapshot, or not adjacent in it),
  the router floods normally.
- The draft allows more than one reflooder per two-hop router (section 1.2.6) without specifying it; this module
  implements the single reflooder of Step 4.
Measured behavior decides between these readings: see tools/model/compare_decisions.py.

Flooding of one LSP (`flood`): its originator sends it to every neighbor. A router receiving it for the first time
from TN decides its send set (every neighbor but TN without reduction, `decide` with it) and sends after a
processing delay to those it has not meanwhile received the LSP from (ISO 10589 clears the send flag for a
neighbor a copy arrives from). Links take a fixed delay plus optional uniform jitter.

Snapshot. A router decides with the topology in its LSP database, in which a link counts only if both ends list it.
At a router's first decision after one link changes, its database holds the new LSP of one end at most, so the
changed link fails the two-way check whether it went down or up; `flood_link_change` decides with the topology
without that link."""
import heapq
from collections import deque
from dataclasses import dataclass

INF = float("inf")


def lsp_hash(sysid, pseudonode=0, fragment=0):
    """H of section 1.2.3 Step 3 for the LSP ID (system ID as an int, pseudonode, fragment)."""
    a = b = 0
    for octet in sysid.to_bytes(6, "big") + bytes([pseudonode, fragment >> 3]):
        a += octet
        a = (a & 0xFF) + (a >> 8)
        b += a
        b = (b & 0xFF) + (b >> 8)
    return (b << 8 | a) & 0xFFFF


def system_id(net):
    """The system ID of an IS-IS NET as an int: the three groups before the selector, whatever the area's length
    ("49.0001.0000.0000.0001.00" -> 1)."""
    return int("".join(net.split(".")[-4:-1]), 16)


class Topology:
    """Adjacency sets of routers, their system IDs (ints), and hop distances from any router, cached."""

    def __init__(self, adj, sysid):
        self.adj = {v: frozenset(n) for v, n in adj.items()}
        self.sysid = sysid
        self._dist = {}

    @classmethod
    def from_lab(cls, routers, links):
        """From a lab's routers and links, as clab.plan returns them and lab.json stores them."""
        adj = {r["name"]: set() for r in routers}
        for x in links:
            adj[x["a"]].add(x["b"])
            adj[x["b"]].add(x["a"])
        return cls(adj, {r["name"]: system_id(r["net"]) for r in routers})

    def without(self, links):
        cut = {frozenset(x) for x in links}
        return Topology({v: {n for n in ns if frozenset((v, n)) not in cut} for v, ns in self.adj.items()},
                        self.sysid)

    def hops(self, root):
        d = self._dist.get(root)
        if d is None:
            d, frontier = {root: 0}, deque([root])
            while frontier:
                u = frontier.popleft()
                for v in self.adj.get(u, ()):
                    if v not in d:
                        d[v] = d[u] + 1
                        frontier.append(v)
            self._dist[root] = d
        return d

    def linked(self, u, v):
        return v in self.adj.get(u, ())


@dataclass(frozen=True)
class Decision:
    """One router's reflood decision. applied: the calculation was made (else normal flooding). thl, rnl: sizes of
    the two-hop and remote neighbor lists after Step 1; start: N of Step 3; selected: Step 4B reached the router;
    suppressed: neighbors other than TN the LSP is not sent to."""
    send: frozenset
    applied: bool
    selected: bool = False
    thl: int = 0
    rnl: int = 0
    start: int = 0
    suppressed: int = 0


def decide(snap, local, tn, origin, neighbors, unknown="flood", pseudonode=0, fragment=0):
    """The reflood decision of router `local`, whose adjacencies are `neighbors`, for the LSP of `origin` received
    from `tn`, computed on snapshot `snap`."""
    neighbors = frozenset(neighbors)
    normal = Decision(neighbors - {tn}, applied=False)
    if local == tn or origin == local or not snap.linked(local, tn) or not snap.linked(tn, local):
        return normal
    d_origin = snap.hops(origin)
    d_tn = d_origin.get(tn, INF)

    # Step 1: routers two hops from TN form the THL, less the originator (i), its neighbors (ii) and those on a
    # shortest path from TN towards the originator, which lie two hops closer to it than TN (iii). TN's
    # neighbors form the RNL (D).
    one_hop = snap.adj[tn]
    two_hop = set().union(*(snap.adj[m] for m in one_hop)) - one_hop - {tn}
    thl = {x for x in two_hop
           if d_origin.get(x, INF) >= 2 and not (d_tn < INF and d_origin.get(x, INF) == d_tn - 2)}
    # Step 2: the RNL in system-ID order. Step 3: the starting index.
    rnl = sorted(one_hop, key=snap.sysid.__getitem__)
    start = lsp_hash(snap.sysid[origin], pseudonode, fragment) % len(rnl)
    first_thl = len(thl)

    # Step 4: walk the RNL from `start` until the THL is empty or the walk wraps; each member other than the local
    # router removes the THL routers adjacent to it (C, skipping members running another reduction scheme, does
    # not arise in a uniform network).
    selected = False
    for k in range(len(rnl)):
        if not thl:
            break
        member = rnl[(start + k) % len(rnl)]
        if member == local:
            selected = True
            break
        thl -= snap.adj[member]

    # Send set: when selected, the THL routers still uncovered that are adjacent to the local router (4B); never
    # back to TN, nor to a neighbor one hop closer to the originator (section 1.2.2); neighbors the snapshot does
    # not show as adjacent per `unknown`.
    d_local = d_origin.get(local, INF)
    send = set()
    for n in neighbors:
        if n == tn:
            continue
        if not snap.linked(local, n):
            if unknown == "flood":
                send.add(n)
        elif selected and n in thl and not (d_local < INF and d_origin.get(n, INF) == d_local - 1):
            send.add(n)
    return Decision(frozenset(send), True, selected, first_thl, len(rnl), start,
                    sum(1 for n in neighbors if n != tn and n not in send))


def flood(actual, snap, origins, reduction, link_delay=1.0, jitter=0.0, proc=0.0, rng=None, starts=None,
          unknown="flood"):
    """Flood a new LSP from each of `origins` (sent at starts[o], default 0) over adjacencies `actual` ({router:
    neighbors}), deciding on snapshot `snap`. Returns a dict: sent (transmissions), per_router (by sender), reached
    ({origin: routers}), last ({origin: time the last router got it}), fallbacks (decisions not applied) and
    suppressed. jitter > 0 adds uniform [0, jitter) to each link delay and needs rng."""
    starts = starts or {}
    queue, order = [], 0
    have = {o: {o: starts.get(o, 0.0)} for o in origins}
    heard = {o: {} for o in origins}
    pending = {}
    totals = {"sent": 0, "per_router": {}, "fallbacks": 0, "suppressed": 0}

    def push(t, *event):
        nonlocal order
        heapq.heappush(queue, (t, order, *event))
        order += 1

    for o in origins:
        pending[(o, o)] = frozenset(actual[o])
        push(starts.get(o, 0.0), "send", o, o, None)
    while queue:
        t, _, kind, o, v, u = heapq.heappop(queue)
        if kind == "arrive":
            heard[o].setdefault(v, set()).add(u)
            if v in have[o]:
                continue
            have[o][v] = t
            if reduction:
                dec = decide(snap, v, u, o, actual[v], unknown)
                totals["fallbacks"] += not dec.applied
                totals["suppressed"] += dec.suppressed if dec.applied else 0
                pending[(o, v)] = dec.send
            else:
                pending[(o, v)] = frozenset(actual[v]) - {u}
            push(t + proc, "send", o, v, None)
        else:
            for w in sorted(pending.pop((o, v)), key=snap.sysid.__getitem__):
                if w in heard[o].get(v, ()):
                    continue
                totals["sent"] += 1
                totals["per_router"][v] = totals["per_router"].get(v, 0) + 1
                push(t + link_delay + (jitter * rng.random() if jitter else 0.0), "arrive", o, w, v)
    totals["reached"] = {o: set(have[o]) for o in origins}
    totals["last"] = {o: max(have[o].values()) for o in origins}
    return totals


def flood_link_change(topo, link, state, reduction, **kw):
    """The two new LSPs of one link change, originated by the link's ends. Adjacencies include the link if state
    is "up"; decisions use the topology without it (see the module docstring)."""
    snap = topo.without([link])
    return flood((topo if state == "up" else snap).adj, snap, list(link), reduction, **kw)
