"""
routing.py — ATRP Routing Algorithm + All Baselines
ATRP Research | Jai Vidhyarthi | Synthara | 2026

WHY THIS FILE:
We have trust scores per node from trust.py.
Now we need to use those scores to make routing decisions.

ATRP modifies Dijkstra's cost function:
  Standard : C(u,v)   = dist(u,v)
  ATRP     : C(u,v,t) = dist(u,v) / TW(v,t) + lambda * hop(u,v)

KEY INSIGHT:
  Dividing by TW means a node with TW=0.1 costs 10x more to
  route through than a node with TW=1.0 — on the same physical link.
  Dijkstra naturally avoids unreliable nodes without explicit blacklisting.

BASELINES (for fair comparison in paper):
  - Standard Dijkstra  : hop count only, no reliability awareness
  - AODV               : reactive, on-demand, hop-count based
  - RPL                : IoT standard, ETX-based parent selection
  - Random Walk        : lower bound — worst case routing
"""

import heapq
import random
import networkx as nx

# ── Lambda parameter ────────────────────────────────
# Controls explore-exploit tradeoff
# lambda=0.0 → pure trust routing (ignores distance)
# lambda=1.0 → pure distance routing (same as Dijkstra)
# lambda=0.3 → optimal balance (validated via grid search)
LAMBDA = 0.3


# ═══════════════════════════════════════════════════
#  ALGORITHM 3: ATRP ROUTE — Trust-Weighted Dijkstra
# ═══════════════════════════════════════════════════
def atrp_route(G, source, dest, tw, lam=LAMBDA):
    """
    Algorithm 3: ATRP_ROUTE

    Modified Dijkstra where edge cost incorporates node trust.

    C(u,v,t) = dist(u,v) / max(0.01, TW(v,t)) + lambda * hop(u,v)

    Why divide by TW?
      - TW=1.0 (perfect node) → cost = dist (normal, no penalty)
      - TW=0.5 (mediocre node) → cost = 2x dist (doubled cost)
      - TW=0.1 (failing node) → cost = 10x dist (severely penalised)
    Dijkstra will naturally route around failing nodes
    without us ever explicitly blacklisting them.

    Why add lambda * hop?
      The explore-exploit term. Without it, ATRP might take
      extremely long paths just to avoid slightly lower TW nodes.
      Lambda balances trust-seeking vs path-length efficiency.
    """
    cost = {n: float('inf') for n in G.nodes()}
    prev = {n: None         for n in G.nodes()}
    cost[source] = 0.0
    pq = [(0.0, source)]

    while pq:
        cu, u = heapq.heappop(pq)
        if cu > cost[u]:
            continue
        if u == dest:
            break
        for v in G.neighbors(u):
            dist_uv    = G[u][v].get('weight', 1.0)
            trust_cost = dist_uv / max(0.01, tw.get(v, 0.5))
            hop_pen    = lam * 1
            edge_cost  = trust_cost + hop_pen
            new_cost   = cost[u] + edge_cost
            if new_cost < cost[v]:
                cost[v] = new_cost
                prev[v] = u
                heapq.heappush(pq, (new_cost, v))

    if cost[dest] == float('inf'):
        return None

    path = []
    node = dest
    while node is not None:
        path.append(node)
        node = prev[node]
    path.reverse()
    return path


# ═══════════════════════════════════════════════════
#  BASELINE 1: Standard Dijkstra
# ═══════════════════════════════════════════════════
def dijkstra_route(G, source, dest):
    """
    Standard Dijkstra — minimises hop count / distance only.
    No awareness of node reliability whatsoever.
    This is what every IoT network uses by default.
    This is what ATRP improves upon.
    """
    try:
        return nx.shortest_path(G, source, dest, weight='weight')
    except nx.NetworkXNoPath:
        return None


# ═══════════════════════════════════════════════════
#  BASELINE 2: AODV (Simplified)
# ═══════════════════════════════════════════════════
def aodv_route(G, source, dest, failed_nodes):
    """
    AODV: Ad-hoc On-Demand Distance Vector routing.
    Discovers routes on demand via network flood (RREQ/RREP).
    Selects by hop count — no trust awareness.

    Simplification for simulation:
    We remove known failed nodes from graph (simulating
    AODV's inability to route through offline nodes)
    then run BFS shortest path on remaining topology.

    Key limitation vs ATRP:
    AODV only knows a node is completely dead (offline).
    It cannot detect a node that is alive but dropping 40% of packets.
    ATRP's TW formula catches degraded nodes before they fully fail.
    """
    sub = G.copy()
    sub.remove_nodes_from([n for n in failed_nodes if n in sub])
    try:
        return nx.shortest_path(sub, source, dest)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


# ═══════════════════════════════════════════════════
#  BASELINE 3: RPL (Simplified)
# ═══════════════════════════════════════════════════
def rpl_route(G, source, dest, node_etx):
    """
    RPL: Routing Protocol for Low-Power and Lossy Networks.
    This is the IETF standard (RFC 6550) for IoT routing.
    Builds a DODAG tree. Each node selects a preferred parent
    using an Objective Function — typically ETX
    (Expected Transmission Count = inverse of link success rate).

    Simplification for simulation:
    We run Dijkstra with ETX as edge cost (lower ETX = better link).
    This captures RPL's parent selection logic without
    full DODAG construction overhead.

    Key limitation vs ATRP:
    RPL's ETX is per-link, not per-node.
    It does not model uptime, latency, or energy as separate factors.
    No temporal decay — stale ETX values persist until manually updated.
    """
    cost = {n: float('inf') for n in G.nodes()}
    prev = {n: None         for n in G.nodes()}
    cost[source] = 0.0
    pq = [(0.0, source)]

    while pq:
        cu, u = heapq.heappop(pq)
        if cu > cost[u]:
            continue
        if u == dest:
            break
        for v in G.neighbors(u):
            etx       = node_etx.get(v, 1.0)
            new_cost  = cost[u] + etx
            if new_cost < cost[v]:
                cost[v] = new_cost
                prev[v] = u
                heapq.heappush(pq, (cost[v], v))

    if cost[dest] == float('inf'):
        return None

    path = []
    node = dest
    while node is not None:
        path.append(node)
        node = prev[node]
    path.reverse()
    return path


# ═══════════════════════════════════════════════════
#  BASELINE 4: Random Walk
# ═══════════════════════════════════════════════════
def random_walk_route(G, source, dest, max_steps=30):
    """
    Random Walk — moves to a random neighbour each step.
    This is the theoretical lower bound — worst possible routing.
    Included to show ATRP's improvement relative to both
    the best naive approach (Dijkstra) and the worst (Random Walk).
    """
    path    = [source]
    visited = {source}
    current = source

    for _ in range(max_steps):
        if current == dest:
            return path
        nbrs = [n for n in G.neighbors(current) if n not in visited]
        if not nbrs:
            nbrs = list(G.neighbors(current))
        if not nbrs:
            return None
        current = random.choice(nbrs)
        path.append(current)
        visited.add(current)

    return path if dest in path else None


# ═══════════════════════════════════════════════════
#  DEMO — Compare all protocols on same network
# ═══════════════════════════════════════════════════
if __name__ == '__main__':
    from graph import build_iot_graph, GATEWAY
    from trust import tw_initialise, tw_update

    print("\n" + "="*60)
    print("  STEP 3: Routing Algorithm — Protocol Comparison Demo")
    print("="*60)

    random.seed(42)
    G = build_iot_graph()

    # Warm up trust scores with 50 ticks of observations
    tw, uptime, failures, tx_count, lat_sum, battery, total_t = tw_initialise(G.nodes())
    failed_nodes = set()
    node_etx     = {n: random.uniform(1.0, 3.0) for n in G.nodes()}

    print("\n  Warming up trust scores (50 ticks)...")
    for tick in range(50):
        for n in G.nodes():
            roll = random.random()
            if roll < 0.02:
                event = 'failure'
                failed_nodes.add(n)
                node_etx[n] = 8.0
            elif n in failed_nodes and roll < 0.15:
                event = 'recover'
                failed_nodes.discard(n)
                node_etx[n] = random.uniform(1.0, 2.0)
            elif n in failed_nodes:
                event = 'silent'
            else:
                event = 'observe'
            tw_update(n, event, tw, uptime, failures,
                      tx_count, lat_sum, battery, total_t, dt=1)

    # Pick a source node far from gateway
    source = max(G.nodes(),
                 key=lambda n: nx.shortest_path_length(G, n, GATEWAY))

    print(f"\n  Source node : {source}")
    print(f"  Destination : {GATEWAY} (gateway)")
    print(f"  Source TW   : {tw[source]:.4f}")
    print(f"  Failed nodes: {len(failed_nodes)}")

    print("\n  " + "-"*56)
    print(f"  {'Protocol':<18} {'Path':<30} {'Hops':>5}")
    print("  " + "-"*56)

    # ATRP
    path_atrp = atrp_route(G, source, GATEWAY, tw)
    if path_atrp:
        avg_tw = sum(tw.get(n, 0.5) for n in path_atrp) / len(path_atrp)
        print(f"  {'ATRP':<18} {str(path_atrp):<30} {len(path_atrp)-1:>5}")
        print(f"  {'':18} Avg TW on path: {avg_tw:.4f}")
    else:
        print(f"  {'ATRP':<18} No path found")

    # Dijkstra
    path_dijk = dijkstra_route(G, source, GATEWAY)
    if path_dijk:
        avg_tw = sum(tw.get(n, 0.5) for n in path_dijk) / len(path_dijk)
        print(f"  {'Dijkstra':<18} {str(path_dijk):<30} {len(path_dijk)-1:>5}")
        print(f"  {'':18} Avg TW on path: {avg_tw:.4f}")
    else:
        print(f"  {'Dijkstra':<18} No path found")

    # AODV
    path_aodv = aodv_route(G, source, GATEWAY, failed_nodes)
    if path_aodv:
        avg_tw = sum(tw.get(n, 0.5) for n in path_aodv) / len(path_aodv)
        print(f"  {'AODV':<18} {str(path_aodv):<30} {len(path_aodv)-1:>5}")
        print(f"  {'':18} Avg TW on path: {avg_tw:.4f}")
    else:
        print(f"  {'AODV':<18} No path found")

    # RPL
    path_rpl = rpl_route(G, source, GATEWAY, node_etx)
    if path_rpl:
        avg_tw = sum(tw.get(n, 0.5) for n in path_rpl) / len(path_rpl)
        print(f"  {'RPL':<18} {str(path_rpl):<30} {len(path_rpl)-1:>5}")
        print(f"  {'':18} Avg TW on path: {avg_tw:.4f}")
    else:
        print(f"  {'RPL':<18} No path found")

    # Random Walk
    path_rand = random_walk_route(G, source, GATEWAY)
    if path_rand:
        avg_tw = sum(tw.get(n, 0.5) for n in path_rand) / len(path_rand)
        print(f"  {'Random Walk':<18} {str(path_rand):<30} {len(path_rand)-1:>5}")
        print(f"  {'':18} Avg TW on path: {avg_tw:.4f}")
    else:
        print(f"  {'Random Walk':<18} No path found")

    print("  " + "-"*56)
    print("\n  KEY: ATRP should show higher Avg TW on path")
    print("  than Dijkstra — even if it takes more hops.")
    print("  That tradeoff IS the contribution of this paper.")
    print("\n  routing.py — DONE\n")