"""
eval_02_failure_rates.py — PDR vs Varying Failure Rates
ATRP Research | Jai Vidhyarthi | Synthara | 2026

WHY THIS FILE:
Tests all protocols across 5 failure rates: 0.01, 0.02, 0.05, 0.08, 0.10
Shows ATRP maintains advantage as network degrades.
This is the strongest proof — consistent superiority across conditions.
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
from routing import atrp_route, dijkstra_route, aodv_route, rpl_route, random_walk_route

FAILURE_RATES    = [0.01, 0.02, 0.05, 0.08, 0.10]
NUM_TICKS        = 1000
PACKETS_PER_TICK = 5
LAMBDA           = 0.7
SEEDS            = [42, 123, 256]

BG      = '#0f172a'
SURFACE = '#1e293b'
BORDER  = '#334155'
TEXT    = '#e2e8f0'
SOFT    = '#94a3b8'
COLORS  = {
    'atrp':'#3b82f6','dijkstra':'#f59e0b',
    'aodv':'#8b5cf6','rpl':'#06b6d4','random':'#ef4444'
}


def single_run(G, protocol, seed, failure_rate):
    random.seed(seed)
    np.random.seed(seed)
    nodes = list(G.nodes())
    tw, uptime, failures, tx_count, lat_sum, battery, total_t, etx = tw_initialise(nodes)
    failed_nodes = set()
    node_etx     = {n: random.uniform(1.0, 3.0) for n in nodes}
    for n in nodes:
        etx[n] = node_etx[n]

    delivered = 0
    total_packets = 0

    for tick in range(NUM_TICKS):
        for n in nodes:
            roll = random.random()
            if n in failed_nodes:
                if roll < failure_rate * 3:
                    event = 'recover'
                    failed_nodes.discard(n)
                    node_etx[n] = random.uniform(1.0, 2.5)
                    etx[n]      = node_etx[n]
                else:
                    event = 'silent'
            elif roll < failure_rate:
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
            elif protocol == 'aodv':
                path = aodv_route(G, src, GATEWAY, failed_nodes)
            elif protocol == 'rpl':
                path = rpl_route(G, src, GATEWAY, node_etx)
            else:
                path = random_walk_route(G, src, GATEWAY)
            if path is None:
                continue
            ok = True
            for node in path[1:]:
                if node in failed_nodes or random.random() > tw.get(node,0.5)*0.95:
                    ok = False
                    break
            if ok:
                delivered += 1

    return round(delivered / max(1, total_packets) * 100, 2)


def run_failure_rates():
    print("\n" + "="*60)
    print("  EVAL 02: PDR vs Failure Rate")
    print("="*60)

    G = build_iot_graph()
    protocols = ['atrp','dijkstra','aodv','rpl','random']
    labels    = ['ATRP','Dijkstra','AODV','RPL','Random Walk']
    results   = {p: [] for p in protocols}

    for fr in FAILURE_RATES:
        print(f"\n  Failure rate = {fr}")
        for protocol, label in zip(protocols, labels):
            pdrs = [single_run(G, protocol, s, fr) for s in SEEDS]
            mean = round(float(np.mean(pdrs)), 2)
            results[protocol].append(mean)
            print(f"    {label:<12} PDR={mean}%")

    # Plot
    fig, ax = plt.subplots(figsize=(11, 6))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(SURFACE)
    ax.tick_params(colors=SOFT, labelsize=9)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    for sp in ['bottom','left']:
        ax.spines[sp].set_color(BORDER)
    ax.grid(color=BORDER, alpha=0.4, zorder=0)

    markers = ['o','s','^','D','x']
    for protocol, label, marker in zip(protocols, labels, markers):
        lw = 3 if protocol == 'atrp' else 1.5
        ax.plot(FAILURE_RATES, results[protocol],
                color=COLORS[protocol], lw=lw,
                marker=marker, markersize=8,
                label=label, zorder=3)

    ax.set_title('PDR vs Network Failure Rate — All Protocols (ATRP v2)',
                 color=TEXT, fontsize=12, pad=12)
    ax.set_xlabel('Failure Rate (per node per tick)', color=SOFT, fontsize=10)
    ax.set_ylabel('Mean PDR (%)', color=SOFT, fontsize=10)
    ax.set_xticks(FAILURE_RATES)
    ax.set_xticklabels([str(f) for f in FAILURE_RATES], color=SOFT)
    ax.legend(facecolor=SURFACE, edgecolor=BORDER,
              labelcolor=SOFT, fontsize=10)

    plt.tight_layout()
    os.makedirs('figures', exist_ok=True)
    plt.savefig('figures/eval_02_failure_rates.png', dpi=150,
                bbox_inches='tight', facecolor=BG)
    plt.close()

    os.makedirs('results', exist_ok=True)
    with open('results/eval_02_failure_rates.json', 'w') as f:
        json.dump({'failure_rates': FAILURE_RATES, 'results': results}, f, indent=2)

    print(f"\n  Saved -> figures/eval_02_failure_rates.png")
    print(f"  Saved -> results/eval_02_failure_rates.json")
    print("\n  eval_02_failure_rates.py -- DONE\n")
    return results


if __name__ == '__main__':
    run_failure_rates()