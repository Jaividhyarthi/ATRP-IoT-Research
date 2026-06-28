"""
eval_01_multirun.py — Multiple Runs Averaged with Std
ATRP Research | Jai Vidhyarthi | Synthara | 2026

WHY THIS FILE:
Single-run results can be lucky or unlucky.
Running each protocol 10 times with different random seeds
and averaging gives statistically stable results.
Mean ± std proves our results are consistent, not a fluke.
"""

import random
import json
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from graph   import build_iot_graph, GATEWAY
from trust   import tw_initialise, tw_update, ZONE_TRUSTED
from routing import atrp_route, dijkstra_route, aodv_route, rpl_route, random_walk_route

SEEDS        = [42, 123, 256, 789, 999, 314, 271, 161, 577, 438]
NUM_TICKS    = 1000
FAILURE_RATE = 0.02
LAMBDA       = 0.7
PACKETS_PER_TICK = 5

BG      = '#0f172a'
SURFACE = '#1e293b'
BORDER  = '#334155'
TEXT    = '#e2e8f0'
SOFT    = '#94a3b8'
COLORS  = {
    'atrp':'#3b82f6','dijkstra':'#f59e0b',
    'aodv':'#8b5cf6','rpl':'#06b6d4','random':'#ef4444'
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
    delivered = 0
    total_packets = 0

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


def run_multirun():
    print("\n" + "="*60)
    print("  EVAL 01: Multi-Run Averaged PDR (10 seeds)")
    print("="*60)

    G = build_iot_graph()
    protocols = ['atrp','dijkstra','aodv','rpl','random']
    labels    = ['ATRP','Dijkstra','AODV','RPL','Random Walk']
    all_results = {}

    for protocol, label in zip(protocols, labels):
        pdrs = []
        for seed in SEEDS:
            pdr = single_run(G, protocol, seed)
            pdrs.append(pdr)
        avg = round(float(np.mean(pdrs)), 2)
        std = round(float(np.std(pdrs)),  2)
        all_results[protocol] = {
            'label': label, 'pdrs': pdrs,
            'mean': avg, 'std': std
        }
        print(f"  {label:<12} Mean={avg}%  Std=±{std}%  "
              f"Min={min(pdrs)}%  Max={max(pdrs)}%")

    # Plot
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(SURFACE)
    ax.tick_params(colors=SOFT, labelsize=9)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    for sp in ['bottom','left']:
        ax.spines[sp].set_color(BORDER)
    ax.grid(axis='y', color=BORDER, alpha=0.5, zorder=0)

    means  = [all_results[p]['mean'] for p in protocols]
    stds   = [all_results[p]['std']  for p in protocols]
    colors = [COLORS[p] for p in protocols]

    bars = ax.bar(labels, means, color=colors, width=0.6, zorder=3,
                  yerr=stds, capsize=6,
                  error_kw={'ecolor': SOFT, 'elinewidth': 2})
    bars[0].set_edgecolor('#93c5fd')
    bars[0].set_linewidth(2)

    for bar, mean, std in zip(bars, means, stds):
        ax.text(bar.get_x() + bar.get_width()/2,
                bar.get_height() + std + 0.3,
                f'{mean}%\n±{std}', ha='center', va='bottom',
                color=TEXT, fontsize=9, fontweight='bold')

    ax.set_title('Multi-Run PDR Comparison — 10 Seeds Averaged (ATRP v2)',
                 color=TEXT, fontsize=12, pad=12)
    ax.set_ylabel('Mean PDR (%)', color=SOFT, fontsize=10)
    ax.set_ylim(0, max(means) * 1.35)
    ax.set_xticklabels(labels, color=SOFT)

    plt.tight_layout()
    os.makedirs('figures', exist_ok=True)
    plt.savefig('figures/eval_01_multirun.png', dpi=150,
                bbox_inches='tight', facecolor=BG)
    plt.close()

    os.makedirs('results', exist_ok=True)
    with open('results/eval_01_multirun.json', 'w') as f:
        json.dump(all_results, f, indent=2)

    print(f"\n  Saved -> figures/eval_01_multirun.png")
    print(f"  Saved -> results/eval_01_multirun.json")
    print("\n  eval_01_multirun.py -- DONE\n")
    return all_results


if __name__ == '__main__':
    run_multirun()