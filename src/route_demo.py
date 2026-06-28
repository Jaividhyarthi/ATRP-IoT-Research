"""
route_demo.py — Route Demonstration for All 7 Algorithms
ATRP Research | Jai Vidhyarthi | Synthara | 2026

PURPOSE:
  Display-only script. Shows which route each algorithm selects
  on the same 8-node IoT network. Does NOT affect any experiment
  results, PDR numbers, or paper figures.

RUN:
  python3 src/route_demo.py

OUTPUT:
  - Terminal: step-by-step route for every algorithm
  - figures/route_demo.png: visual comparison of all routes
"""

import heapq
import random
import math
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

random.seed(42)

# ─────────────────────────────────────────────
#  NETWORK DEFINITION
#  8 nodes: 0=Gateway, 1-7=Sensors
#  Node 3 = FAILING (TW=0.10, 40% packet loss)
# ─────────────────────────────────────────────
NODES = list(range(8))
GATEWAY = 0
SOURCE  = 6

# Adjacency list: {node: {neighbour: distance}}
GRAPH = {
    0: {1:2, 2:4, 3:1},
    1: {0:2, 3:1, 4:3},
    2: {0:4, 4:2, 5:5},
    3: {0:1, 1:1, 5:1},
    4: {1:3, 2:2, 6:2},
    5: {2:5, 3:1, 6:3},
    6: {4:2, 5:3},
    7: {5:2},
}

# Trust Weight scores (simulated after 200 ticks)
TW = {
    0: 0.97,   # Gateway — stable
    1: 0.92,   # Healthy sensor
    2: 0.88,   # Healthy sensor
    3: 0.10,   # FAILING — 40% packet loss
    4: 0.91,   # Healthy sensor
    5: 0.85,   # Healthy sensor
    6: 0.89,   # Source sensor
    7: 0.82,   # Healthy sensor
}

# ETX values for RPL
NODE_ETX = {
    0: 1.0, 1: 1.5, 2: 2.0,
    3: 9.0,  # bad link — failing node
    4: 1.8, 5: 2.5, 6: 2.2, 7: 3.0,
}

LAMBDA = 0.7  # ATRP explore-exploit parameter

NODE_LABELS = {
    0: 'Node 0 (GATEWAY)',
    1: 'Node 1',
    2: 'Node 2',
    3: 'Node 3 [FAILING TW=0.10]',
    4: 'Node 4',
    5: 'Node 5',
    6: 'Node 6 (SOURCE)',
    7: 'Node 7',
}

# Node positions for diagram
POS = {
    0: (5.5, 8.0),
    1: (2.5, 6.5),
    2: (7.5, 6.5),
    3: (1.5, 4.5),
    4: (4.5, 4.5),
    5: (7.0, 4.0),
    6: (4.5, 1.5),
    7: (8.5, 2.5),
}


# ─────────────────────────────────────────────
#  ALGORITHM 1: DIJKSTRA
# ─────────────────────────────────────────────
def dijkstra(graph, source, dest):
    """
    Standard Dijkstra — minimises physical distance only.
    No reliability awareness. Selects shortest path.
    """
    dist = {n: float('inf') for n in graph}
    prev = {n: None for n in graph}
    dist[source] = 0
    pq = [(0, source)]

    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        if u == dest:
            break
        for v, w in graph[u].items():
            nd = dist[u] + w
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))

    return reconstruct(prev, source, dest), dist[dest]


# ─────────────────────────────────────────────
#  ALGORITHM 2: BELLMAN-FORD (Distance Vector)
# ─────────────────────────────────────────────
def bellman_ford(graph, source, dest):
    """
    Bellman-Ford / Distance Vector routing.
    Relaxes all edges V-1 times.
    Same result as Dijkstra on positive-weight graphs.
    """
    dist = {n: float('inf') for n in graph}
    prev = {n: None for n in graph}
    dist[source] = 0

    # Collect all edges
    edges = []
    for u in graph:
        for v, w in graph[u].items():
            edges.append((u, v, w))

    # Relax V-1 times
    for _ in range(len(graph) - 1):
        updated = False
        for u, v, w in edges:
            if dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
                prev[v] = u
                updated = True
        if not updated:
            break

    return reconstruct(prev, source, dest), dist[dest]


# ─────────────────────────────────────────────
#  ALGORITHM 3: LINK STATE (OSPF / Dijkstra on full map)
# ─────────────────────────────────────────────
def link_state_ospf(graph, source, dest):
    """
    Link State / OSPF.
    Every node has complete network map (LSDB).
    Runs Dijkstra on the full topology.
    In this simulation: identical to Dijkstra since
    we already have the full graph.
    Key difference from DV: faster convergence on failure.
    """
    # OSPF cost = inverse bandwidth (simulated as distance here)
    # In real OSPF: cost = 10^8 / bandwidth
    # Here we use same graph weights for fair comparison
    path, cost = dijkstra(graph, source, dest)
    return path, cost


# ─────────────────────────────────────────────
#  ALGORITHM 4: AODV
# ─────────────────────────────────────────────
def aodv(graph, source, dest, failed_nodes=None):
    """
    AODV: Ad-hoc On-Demand Distance Vector.
    Reactive — finds route only when needed.
    Removes completely failed/offline nodes.
    Selects by hop count (BFS).
    Cannot detect degraded nodes (only dead ones).
    """
    if failed_nodes is None:
        failed_nodes = set()

    # Build subgraph without failed nodes
    sub = {n: {v: w for v, w in nbrs.items()
               if v not in failed_nodes}
           for n, nbrs in graph.items()
           if n not in failed_nodes}

    if source not in sub or dest not in sub:
        return None, float('inf')

    # BFS for fewest hops (AODV behaviour)
    from collections import deque
    prev = {n: None for n in sub}
    visited = {source}
    q = deque([source])

    while q:
        u = q.popleft()
        if u == dest:
            break
        for v in sub.get(u, {}):
            if v not in visited:
                visited.add(v)
                prev[v] = u
                q.append(v)

    path = reconstruct(prev, source, dest)
    if path is None:
        return None, float('inf')

    # Calculate actual distance cost
    cost = sum(graph[path[i]][path[i+1]]
               for i in range(len(path)-1)
               if path[i+1] in graph[path[i]])
    return path, cost


# ─────────────────────────────────────────────
#  ALGORITHM 5: RPL
# ─────────────────────────────────────────────
def rpl(graph, source, dest, node_etx):
    """
    RPL: Routing Protocol for Low-Power and Lossy Networks.
    Builds DODAG tree rooted at gateway.
    Each node selects preferred parent by minimising Rank.
    Rank = accumulated ETX cost from root.
    High ETX on Node 3 causes it to be avoided.
    """
    # Dijkstra using ETX as edge cost
    rank  = {n: float('inf') for n in graph}
    prev  = {n: None for n in graph}
    rank[source] = 0
    pq = [(0, source)]

    while pq:
        r, u = heapq.heappop(pq)
        if r > rank[u]:
            continue
        for v in graph[u]:
            etx_cost = node_etx.get(v, 1.0)
            new_rank = rank[u] + etx_cost
            if new_rank < rank[v]:
                rank[v] = new_rank
                prev[v] = u
                heapq.heappush(pq, (new_rank, v))

    # Reconstruct from source to dest following preferred parents
    path = reconstruct(prev, source, dest)
    if path is None:
        return None, float('inf')

    cost = sum(graph[path[i]][path[i+1]]
               for i in range(len(path)-1)
               if path[i+1] in graph.get(path[i], {}))
    return path, cost


# ─────────────────────────────────────────────
#  ALGORITHM 6: RANDOM WALK
# ─────────────────────────────────────────────
def random_walk(graph, source, dest, max_steps=30):
    """
    Random Walk: move to a random neighbour at each step.
    No intelligence, no optimisation.
    Included as lower bound baseline.
    """
    path    = [source]
    visited = {source}
    current = source

    for _ in range(max_steps):
        if current == dest:
            return path, len(path) - 1
        nbrs = [n for n in graph.get(current, {})
                if n not in visited]
        if not nbrs:
            nbrs = list(graph.get(current, {}).keys())
        if not nbrs:
            return None, float('inf')
        current = random.choice(nbrs)
        path.append(current)
        visited.add(current)

    if dest in path:
        idx = path.index(dest)
        return path[:idx+1], idx
    return None, float('inf')


# ─────────────────────────────────────────────
#  ALGORITHM 7: ATRP (Our Protocol)
# ─────────────────────────────────────────────
def atrp(graph, source, dest, tw, lam=LAMBDA):
    """
    ATRP: Adaptive Trust Routing Protocol.
    Modified Dijkstra with trust-weighted cost function:
      C(u,v,t) = dist(u,v) / TW(v,t) + lambda * hop(u,v)

    TW(v) low → cost very high → naturally avoided.
    Node 3 has TW=0.10 → cost multiplied by 10.
    """
    cost = {n: float('inf') for n in graph}
    prev = {n: None for n in graph}
    cost[source] = 0
    pq = [(0.0, source)]

    while pq:
        cu, u = heapq.heappop(pq)
        if cu > cost[u]:
            continue
        if u == dest:
            break
        for v, dist_uv in graph[u].items():
            trust_cost = dist_uv / max(0.01, tw.get(v, 0.5))
            hop_pen    = lam * 1
            edge_cost  = trust_cost + hop_pen
            new_cost   = cost[u] + edge_cost
            if new_cost < cost[v]:
                cost[v] = new_cost
                prev[v] = u
                heapq.heappush(pq, (new_cost, v))

    path = reconstruct(prev, source, dest)
    if path is None:
        return None, float('inf')

    # Report actual physical distance cost
    dist_cost = sum(graph[path[i]][path[i+1]]
                    for i in range(len(path)-1)
                    if path[i+1] in graph.get(path[i], {}))
    return path, round(cost[dest], 2)


# ─────────────────────────────────────────────
#  HELPER: Reconstruct path from prev dict
# ─────────────────────────────────────────────
def reconstruct(prev, source, dest):
    if prev[dest] is None and dest != source:
        return None
    path = []
    node = dest
    while node is not None:
        path.append(node)
        node = prev[node]
    path.reverse()
    if path[0] != source:
        return None
    return path


# ─────────────────────────────────────────────
#  PRINT ROUTE — detailed step by step
# ─────────────────────────────────────────────
def print_route(name, path, cost, tw, note=''):
    print(f"\n  {'─'*56}")
    print(f"  {name}")
    print(f"  {'─'*56}")

    if path is None:
        print(f"  ✗ No path found!")
        return

    # Path arrow
    arrow = ' → '.join(str(n) for n in path)
    print(f"  Route : {arrow}")
    print(f"  Hops  : {len(path)-1}")
    print(f"  Cost  : {cost}")

    # Step by step
    print(f"\n  Step-by-step:")
    for i in range(len(path)-1):
        u, v = path[i], path[i+1]
        dist = GRAPH[u].get(v, '?')
        tw_v = tw.get(v, '?')
        zone = ('AVOID  ✗' if tw_v < 0.4
                else 'MONITOR ~' if tw_v < 0.7
                else 'TRUSTED ✓') if isinstance(tw_v, float) else ''
        print(f"  Step {i+1}: Node {u} → Node {v}  "
              f"dist={dist}  TW={tw_v:.2f}  [{zone}]")

    # Warning if path goes through failing node
    if 3 in path and path.index(3) not in [0, len(path)-1]:
        print(f"\n  ⚠️  WARNING: Route passes through FAILING Node 3!")
        print(f"     Node 3 TW=0.10 → ~40% packet loss")
    else:
        print(f"\n  ✓  Node 3 avoided — reliable path!")

    if note:
        print(f"\n  Note: {note}")


# ─────────────────────────────────────────────
#  VISUALISATION — all routes on one figure
# ─────────────────────────────────────────────
def plot_all_routes(results):
    fig, axes = plt.subplots(2, 4, figsize=(20, 10))
    fig.patch.set_facecolor('#0f172a')
    fig.suptitle(
        'Route Comparison — All 7 Algorithms on Same IoT Network\n'
        f'Source: Node {SOURCE} → Gateway: Node {GATEWAY} | Node 3 = FAILING (TW=0.10)',
        color='#e2e8f0', fontsize=14, y=1.01
    )

    algo_colors = {
        'Dijkstra':         '#f59e0b',
        'DV (Bellman-Ford)':'#8b5cf6',
        'OSPF (Link State)':'#06b6d4',
        'AODV':             '#f97316',
        'RPL':              '#14b8a6',
        'Random Walk':      '#ef4444',
        'ATRP (Ours)':      '#10b981',
    }

    def draw_network(ax, path, title, color):
        ax.set_facecolor('#1e293b')
        ax.set_xlim(0, 10); ax.set_ylim(0, 10)
        ax.axis('off')
        ax.set_title(title, color='#e2e8f0', fontsize=11, pad=8)

        # Draw all edges
        for u in GRAPH:
            for v, w in GRAPH[u].items():
                if v > u:
                    x1,y1 = POS[u]; x2,y2 = POS[v]
                    ax.plot([x1,x2],[y1,y2], color='#334155',
                            lw=1, zorder=1)
                    ax.text((x1+x2)/2, (y1+y2)/2+0.15, str(w),
                            ha='center', va='bottom', fontsize=7,
                            color='#64748b', zorder=2)

        # Highlight path edges
        if path:
            for i in range(len(path)-1):
                u, v = path[i], path[i+1]
                x1,y1 = POS[u]; x2,y2 = POS[v]
                ax.annotate('', xy=(x2,y2), xytext=(x1,y1),
                    arrowprops=dict(arrowstyle='->', color=color,
                                    lw=2.5, mutation_scale=15),
                    zorder=4)

        # Draw nodes
        for n in NODES:
            x, y = POS[n]
            on_path = path and n in path

            if n == GATEWAY:
                nc = '#3b82f6'
            elif n == 3:
                nc = '#ef4444'
            elif n == SOURCE:
                nc = '#10b981'
            else:
                nc = '#475569'

            size = 250 if n in [GATEWAY, SOURCE] else 180
            alpha = 1.0 if on_path else 0.4

            ax.scatter(x, y, s=size, c=nc, zorder=5, alpha=alpha,
                       edgecolors=color if on_path else '#1e293b',
                       linewidths=2.5 if on_path else 0.5)

            label = f'{n}'
            if n == GATEWAY: label = f'{n}\nGW'
            if n == SOURCE:  label = f'{n}\nSRC'
            if n == 3:       label = f'{n}\n⚠️'
            ax.text(x, y-0.55, label, ha='center', va='top',
                    fontsize=8, color='#e2e8f0' if on_path else '#64748b',
                    fontweight='bold' if on_path else 'normal',
                    zorder=6)

        # Path summary
        if path:
            path_str = '→'.join(str(n) for n in path)
            warn = '⚠️' if 3 in path[1:-1] else '✓'
            ax.text(5, 0.3, f'{warn} {path_str}',
                    ha='center', va='bottom', fontsize=9,
                    color=color if 3 not in path[1:-1] else '#ef4444',
                    fontweight='bold', zorder=7)

    flat_axes = axes.flat
    for ax, (name, path, cost) in zip(list(axes.flat), results):
        draw_network(ax, path, f'{name}\nCost: {cost}', algo_colors.get(name,'#64748b'))

    # Last panel = legend
    axes_list = list(axes.flat)
    ax_leg = axes_list[-1]
    ax_leg.set_facecolor('#1e293b')
    ax_leg.axis('off')
    ax_leg.set_title('Legend', color='#e2e8f0', fontsize=11, pad=8)

    legend_items = [
        ('Node 3 [FAILING TW=0.10]', '#ef4444'),
        ('Gateway (Node 0)', '#3b82f6'),
        ('Source (Node 6)', '#10b981'),
        ('Path goes through Node 3 ⚠️', '#ef4444'),
        ('Path avoids Node 3 ✓', '#10b981'),
    ]
    for i, (label, color) in enumerate(legend_items):
        ax_leg.text(0.05, 0.85-i*0.15, '●', color=color,
                    fontsize=16, transform=ax_leg.transAxes, va='top')
        ax_leg.text(0.2, 0.87-i*0.15, label, color='#94a3b8',
                    fontsize=9, transform=ax_leg.transAxes, va='top')

    plt.tight_layout()
    os.makedirs('figures', exist_ok=True)
    out = 'figures/route_demo.png'
    plt.savefig(out, dpi=150, bbox_inches='tight',
                facecolor='#0f172a', edgecolor='none')
    plt.close()
    print(f"\n  Figure saved → {out}")


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
if __name__ == '__main__':
    print("\n" + "█"*60)
    print("  ROUTE DEMONSTRATION — All 7 Algorithms")
    print("  Same network | Same source→destination")
    print("█"*60)
    print(f"\n  Network : 8 nodes (0=Gateway, 1-7=Sensors)")
    print(f"  Source  : Node {SOURCE}")
    print(f"  Dest    : Node {GATEWAY} (Gateway)")
    print(f"  Failing : Node 3 (TW=0.10, ~40% packet loss)")
    print(f"\n  Node Trust Weights:")
    for n, tw_val in TW.items():
        zone = ('AVOID  ' if tw_val < 0.4
                else 'MONITOR' if tw_val < 0.7
                else 'TRUSTED')
        bar = '█' * int(tw_val * 15)
        print(f"    Node {n}: TW={tw_val:.2f}  [{zone}]  {bar}")

    results = []

    # ── 1. Dijkstra ──
    path, cost = dijkstra(GRAPH, SOURCE, GATEWAY)
    print_route('① DIJKSTRA — Shortest Path (distance only)',
                path, cost, TW,
                'Picks shortest distance. Blind to node reliability.')
    results.append(('Dijkstra', path, cost))

    # ── 2. Bellman-Ford / DV ──
    path, cost = bellman_ford(GRAPH, SOURCE, GATEWAY)
    print_route('② DV / BELLMAN-FORD — Distance Vector',
                path, cost, TW,
                'Same result as Dijkstra. Suffers count-to-infinity on failure.')
    results.append(('DV (Bellman-Ford)', path, cost))

    # ── 3. OSPF / Link State ──
    path, cost = link_state_ospf(GRAPH, SOURCE, GATEWAY)
    print_route('③ OSPF / LINK STATE — Full Network Map + Dijkstra',
                path, cost, TW,
                'Same path as Dijkstra but faster failure recovery via LSA flooding.')
    results.append(('OSPF (Link State)', path, cost))

    # ── 4. AODV ──
    # Node 3 is degraded (not fully offline) in our scenario
    # AODV only avoids fully dead nodes
    # For demo: show AODV WITH Node 3 alive (degraded)
    path_aodv_degraded, cost1 = aodv(GRAPH, SOURCE, GATEWAY, failed_nodes=set())
    # And AODV with Node 3 completely offline
    path_aodv_dead, cost2 = aodv(GRAPH, SOURCE, GATEWAY, failed_nodes={3})
    print_route('④ AODV — On-Demand Reactive (Node 3 degraded/alive)',
                path_aodv_degraded, cost1, TW,
                'Node 3 is alive but dropping 40% packets. AODV cannot detect this.')
    print_route('④ AODV — On-Demand Reactive (Node 3 completely offline)',
                path_aodv_dead, cost2, TW,
                'If Node 3 were dead, AODV finds alternate path via BFS hop-count.')
    results.append(('AODV', path_aodv_dead, cost2))

    # ── 5. RPL ──
    path, cost = rpl(GRAPH, SOURCE, GATEWAY, NODE_ETX)
    print_route('⑤ RPL — DODAG Tree (ETX-based, IoT standard)',
                path, cost, TW,
                'ETX=9.0 on Node 3 makes it expensive. RPL avoids it!')
    results.append(('RPL', path, cost))

    # ── 6. Random Walk ──
    path, cost = random_walk(GRAPH, SOURCE, GATEWAY)
    print_route('⑥ RANDOM WALK — No Intelligence (baseline lower bound)',
                path, cost, TW,
                'Random moves. May go backwards, revisit nodes, use failing node.')
    results.append(('Random Walk', path, cost if path else 'N/A'))

    # ── 7. ATRP ──
    path, cost = atrp(GRAPH, SOURCE, GATEWAY, TW)
    print_route('⑦ ATRP — Adaptive Trust Routing (Our Protocol)',
                path, cost, TW,
                f'TW(Node3)=0.10 → cost = dist/0.10 = 10x expensive. Avoided naturally.')
    results.append(('ATRP (Ours)', path, cost))

    # ── Summary table ──
    print("\n\n" + "="*70)
    print("  FINAL COMPARISON SUMMARY")
    print("="*70)
    print(f"  {'Algorithm':<22} {'Path':<25} {'Cost':>8} {'Node 3?':>10} {'Rating'}")
    print("-"*70)

    ratings = {
        'Dijkstra':          ('YES ⚠️', 'Poor  — ignores reliability'),
        'DV (Bellman-Ford)': ('YES ⚠️', 'Poor  — count-to-infinity issue'),
        'OSPF (Link State)': ('YES ⚠️', 'OK    — fast recovery, still picks bad path'),
        'AODV':              ('NO  ✓',  'Good  — avoids dead nodes, not degraded'),
        'RPL':               ('NO  ✓',  'Good  — ETX detects bad link'),
        'Random Walk':       ('?  🎲',  'Worst — no intelligence'),
        'ATRP (Ours)':       ('NO  ✓',  'Best  — 5-factor trust, avoids degraded nodes'),
    }

    for name, path, cost in results:
        if path:
            path_str = '→'.join(str(n) for n in path)
            node3 = 'YES ⚠️' if path and 3 in path[1:-1] else 'NO  ✓'
        else:
            path_str = 'No path'
            node3 = '?'
        cost_str = str(cost) if cost != float('inf') else '∞'
        rating = ratings.get(name, ('?', '?'))[1]
        print(f"  {name:<22} {path_str:<25} {cost_str:>8} {node3:>10}  {rating}")

    print("="*70)
    print("\n  KEY INSIGHT:")
    print("  Dijkstra / DV / OSPF : pick shortest path → go through failing Node 3")
    print("  AODV                 : avoids dead nodes only, not degraded ones")
    print("  RPL                  : avoids Node 3 via high ETX (1 metric only)")
    print("  ATRP (Ours)          : avoids Node 3 via TW=0.10 (5 metrics + decay)")
    print("  Random Walk          : no intelligence — lower bound baseline")

    # ── Generate figure ──
    plot_all_routes(results)
    print("\n  route_demo.py — DONE\n")
    print("  This is a display-only script.")
    print("  Experiment results are unaffected.\n")