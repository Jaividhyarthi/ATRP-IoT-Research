"""
graph.py — IoT Network Topology Builder
ATRP Research | Jai Vidhyarthi | Synthara | 2026

WHY THIS FILE:
Standard IoT sensor networks are modelled as random connected graphs.
Each node = one IoT sensor device.
Each edge = a wireless link between two sensors.
Edge weight = physical distance / signal strength between them.

We use Erdos-Renyi random graph model G(n,p):
  n = number of nodes
  p = probability any two nodes share an edge
  p=0.12 gives realistic sparse IoT connectivity
"""

import networkx as nx
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import random
import json
import os

# ── Constants ──────────────────────────────────────
NUM_NODES    = 50
CONNECTIVITY = 0.12
GATEWAY      = 0
RANDOM_SEED  = 42

random.seed(RANDOM_SEED)


def build_iot_graph(n=NUM_NODES, p=CONNECTIVITY, seed=RANDOM_SEED):
    """
    Build a random connected IoT network graph.
    Keeps regenerating until we get a fully connected graph.
    A disconnected IoT network cannot route — so connectivity is mandatory.
    """
    attempts = 0
    while True:
        attempts += 1
        G = nx.erdos_renyi_graph(n, p, seed=seed + attempts)
        if nx.is_connected(G):
            break

    for u, v in G.edges():
        G[u][v]['weight'] = round(random.uniform(0.5, 3.0), 2)

    print(f"  Graph built in {attempts} attempt(s)")
    print(f"  Nodes      : {G.number_of_nodes()}")
    print(f"  Edges      : {G.number_of_edges()}")
    print(f"  Avg degree : {round(sum(dict(G.degree()).values()) / n, 2)}")
    print(f"  Connected  : {nx.is_connected(G)}")
    print(f"  Gateway    : Node {GATEWAY}")

    return G


def save_graph_info(G, path='results/graph_info.json'):
    """Save graph metadata to results folder for paper reference."""
    os.makedirs('results', exist_ok=True)
    info = {
        'nodes'             : G.number_of_nodes(),
        'edges'             : G.number_of_edges(),
        'avg_degree'        : round(sum(dict(G.degree()).values()) / G.number_of_nodes(), 2),
        'connected'         : nx.is_connected(G),
        'gateway'           : GATEWAY,
        'density'           : round(nx.density(G), 4),
        'avg_shortest_path' : round(nx.average_shortest_path_length(G), 4),
    }
    with open(path, 'w') as f:
        json.dump(info, f, indent=2)
    print(f"\n  Graph info saved → {path}")
    return info


def plot_graph(G, path='figures/01_network_topology.png'):
    """
    Visualise the IoT network topology.
    All nodes are neutral at this stage — no trust scores yet.
    This is Figure 1 in your paper: the raw network before ATRP runs.
    """
    os.makedirs('figures', exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 8))
    fig.patch.set_facecolor('#0f172a')
    ax.set_facecolor('#0f172a')

    pos = nx.spring_layout(G, seed=RANDOM_SEED, k=1.5)

    node_colors = ['#3b82f6' if n == GATEWAY else '#64748b' for n in G.nodes()]
    node_sizes  = [400 if n == GATEWAY else 180 for n in G.nodes()]

    nx.draw_networkx_edges(G, pos, ax=ax, alpha=0.2,
                           edge_color='#334155', width=0.8)
    nx.draw_networkx_nodes(G, pos, ax=ax,
                           node_color=node_colors,
                           node_size=node_sizes, alpha=0.9)
    nx.draw_networkx_labels(G, pos, ax=ax,
                            labels={n: str(n) for n in G.nodes()},
                            font_size=6, font_color='white')

    ax.set_title(
        f'IoT Network Topology — {G.number_of_nodes()} nodes, '
        f'{G.number_of_edges()} edges\nNode 0 = Gateway (blue)',
        color='#e2e8f0', fontsize=12, pad=12
    )
    ax.axis('off')
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches='tight',
                facecolor='#0f172a', edgecolor='none')
    plt.close()
    print(f"  Topology plot saved → {path}")


if __name__ == '__main__':
    print("\n" + "="*50)
    print("  STEP 1: Building IoT Network Graph")
    print("="*50)

    G = build_iot_graph()
    info = save_graph_info(G)
    plot_graph(G)

    print("\n  Graph stats for paper:")
    for k, v in info.items():
        print(f"    {k}: {v}")

    print("\n  graph.py — DONE\n")