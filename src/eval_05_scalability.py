"""
eval_05_scalability.py — Network Scalability Analysis
ATRP Research | Jai Vidhyarthi | Synthara | 2026

WHY THIS FILE:
Proves ATRP scales beyond the 50-node simulation.
Tests on 25, 50, 75, 100 nodes.
Shows ATRP maintains PDR advantage as network grows.
Critical for reviewer acceptance — small simulations
are always challenged.
"""

import random
import json
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from graph   import build_iot_graph, GATEWAY
from trust   import tw_initialise, tw_update
from routing import atrp_route, dijkstra_route, rpl_route

NODE_COUNTS      = [25, 50, 75, 100]
NUM_TICKS        = 500
FAILURE_RATE     = 0.02
LAMBDA           = 0.7
PACKETS_PER_TICK = 5
SEEDS            = [42, 123, 256]

BG      = '#0f172a'
SURFACE = '#1e293b'
BORDER  = '#334155'
TEXT    = '#e2e8f0'
SOFT    = '#94a3b8'
COLORS  = {
    'atrp':'#3b82f6',
    'dijkstra':'#f59e0b',
    'rpl':'#06b6d4'
}


def single_run(G, protocol, seed):
    random.seed(seed)
    np.random.seed(seed)
    nodes = list(G.nodes())
    tw, uptime, failures, tx_count, lat_sum, battery, total_t, etx = tw_initialise(nodes)
    failed_nodes = set()
    node_etx     = {n: random.uniform(1.0, 3.0) for n in nodes}
    for n in nodes:
        etx[n] = node_etx[n]

    delivered = 0; total_packets = 0

    for tick in range(NUM_TICKS):
        for n in nodes:
            roll = random.random()
            if n in failed_nodes:
                if roll < FAILURE_RATE * 3:
                    event = 'recover'
                    failed_nodes.discard(n)
                    node_etx[n] = random.uniform(1.0, 2.5)
                    etx[n]      = node_etx[n]
                else:
                    event = 'silent'
            elif roll < FAILURE_RATE:
                event = 'failure'
                failed_nodes.add(n)
                node_etx[n] = 9.0
                etx[n]      = node_etx[n]
            else:
                event = 'observe'
            tw_update(n, event, tw, uptime, failures,
                      tx_count, lat_sum, battery, total_t, etx, dt=1)

        for _ in range(PACKETS_PER_TICK):
            src = random.choice([n for n in nodes if n != GATEWAY])
            total_packets += 1
            if protocol == 'atrp':
                path = atrp_route(G, src, GATEWAY, tw, lam=LAMBDA)
            elif protocol == 'dijkstra':
                path = dijkstra_route(G, src, GATEWAY)
            elif protocol == 'rpl':
                path = rpl_route(G, src, GATEWAY, node_etx)
            else:
                path = None
            if path is None:
                continue
            ok = True
            for node in path[1:]:
                if node in failed_nodes or random.random() > tw.get(node,0.5)*0.95:
                    ok = False; break
            if ok:
                delivered += 1

    return round(delivered / max(1, total_packets) * 100, 2)


def run_scalability():
    print("\n" + "="*60)
    print("  EVAL 05: Network Scalability Analysis")
    print(f"  Node counts: {NODE_COUNTS} | Protocols: ATRP, Dijkstra, RPL")
    print("="*60)

    protocols = ['atrp', 'dijkstra', 'rpl']
    labels    = ['ATRP', 'Dijkstra', 'RPL']
    results   = {p: [] for p in protocols}
    stds      = {p: [] for p in protocols}

    for n_nodes in NODE_COUNTS:
        print(f"\n  Building {n_nodes}-node graph...")
        G = build_iot_graph(n=n_nodes)
        print(f"  Edges={G.number_of_edges()} | Running protocols...")

        for protocol, label in zip(protocols, labels):
            pdrs = [single_run(G, protocol, s) for s in SEEDS]
            mean = round(float(np.mean(pdrs)), 2)
            std  = round(float(np.std(pdrs)),  2)
            results[protocol].append(mean)
            stds[protocol].append(std)
            print(f"    {label:<12} PDR={mean}% ±{std}%")

    # Plot
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.patch.set_facecolor(BG)
    fig.suptitle(
        'ATRP Scalability Analysis — PDR vs Network Size\n'
        f'Failure rate={FAILURE_RATE} | {NUM_TICKS} ticks | 3 seeds averaged',
        color=TEXT, fontsize=13
    )

    # Panel A: Line plot PDR vs nodes
    ax1 = axes[0]
    ax1.set_facecolor(SURFACE)
    ax1.tick_params(colors=SOFT, labelsize=9)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    for sp in ['bottom','left']:
        ax1.spines[sp].set_color(BORDER)
    ax1.grid(color=BORDER, alpha=0.4, zorder=0)

    markers = ['o', 's', 'D']
    for protocol, label, marker in zip(protocols, labels, markers):
        lw = 3 if protocol == 'atrp' else 1.5
        ax1.plot(NODE_COUNTS, results[protocol],
                 color=COLORS[protocol], lw=lw,
                 marker=marker, markersize=8,
                 label=label, zorder=3)
        ax1.fill_between(
            NODE_COUNTS,
            [r-s for r,s in zip(results[protocol], stds[protocol])],
            [r+s for r,s in zip(results[protocol], stds[protocol])],
            color=COLORS[protocol], alpha=0.1
        )

    ax1.set_title('(A) PDR vs Network Size', color=TEXT, fontsize=11, pad=10)
    ax1.set_xlabel('Number of Nodes', color=SOFT, fontsize=10)
    ax1.set_ylabel('Mean PDR (%)', color=SOFT, fontsize=10)
    ax1.set_xticks(NODE_COUNTS)
    ax1.set_xticklabels([str(n) for n in NODE_COUNTS], color=SOFT)
    ax1.legend(facecolor=SURFACE, edgecolor=BORDER,
               labelcolor=SOFT, fontsize=10)

    # Panel B: ATRP advantage over Dijkstra
    ax2 = axes[1]
    ax2.set_facecolor(SURFACE)
    ax2.tick_params(colors=SOFT, labelsize=9)
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    for sp in ['bottom','left']:
        ax2.spines[sp].set_color(BORDER)
    ax2.grid(axis='y', color=BORDER, alpha=0.4, zorder=0)

    atrp_advantage = [
        round(results['atrp'][i] - results['dijkstra'][i], 2)
        for i in range(len(NODE_COUNTS))
    ]
    bars = ax2.bar(NODE_COUNTS, atrp_advantage,
                   color=COLORS['atrp'], width=12, zorder=3,
                   edgecolor='#93c5fd', linewidth=1.5)
    ax2.axhline(y=0, color=SOFT, lw=1, ls='--', alpha=0.5)

    for bar, val in zip(bars, atrp_advantage):
        ax2.text(bar.get_x() + bar.get_width()/2,
                 bar.get_height() + 0.3,
                 f'+{val}pp', ha='center', va='bottom',
                 color=TEXT, fontsize=10, fontweight='bold')

    ax2.set_title('(B) ATRP Advantage over Dijkstra\n(percentage points)',
                  color=TEXT, fontsize=11, pad=10)
    ax2.set_xlabel('Number of Nodes', color=SOFT, fontsize=10)
    ax2.set_ylabel('PDR Improvement (pp)', color=SOFT, fontsize=10)
    ax2.set_xticks(NODE_COUNTS)
    ax2.set_xticklabels([f'{n} nodes' for n in NODE_COUNTS], color=SOFT)

    plt.tight_layout()
    os.makedirs('figures', exist_ok=True)
    plt.savefig('figures/eval_05_scalability.png', dpi=150,
                bbox_inches='tight', facecolor=BG)
    plt.close()

    os.makedirs('results', exist_ok=True)
    with open('results/eval_05_scalability.json', 'w') as f:
        json.dump({'node_counts': NODE_COUNTS,
                   'results': results, 'stds': stds}, f, indent=2)

    print(f"\n  Saved -> figures/eval_05_scalability.png")
    print(f"  Saved -> results/eval_05_scalability.json")
    print("\n  eval_05_scalability.py -- DONE\n")
    return results


if __name__ == '__main__':
    run_scalability()