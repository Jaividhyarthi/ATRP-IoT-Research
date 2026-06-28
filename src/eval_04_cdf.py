"""
eval_04_cdf.py — CDF of Packet Delivery vs Path Length
ATRP Research | Jai Vidhyarthi | Synthara | 2026

WHY THIS FILE:
PDR gives one number — average delivery rate.
CDF shows the full distribution:
  X axis — path length (hops)
  Y axis — cumulative % of packets successfully delivered

A protocol with higher CDF at every hop count
is strictly better across all network conditions.
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

NUM_TICKS        = 1000
FAILURE_RATE     = 0.02
LAMBDA           = 0.7
PACKETS_PER_TICK = 5
RANDOM_SEED      = 42

BG      = '#0f172a'
SURFACE = '#1e293b'
BORDER  = '#334155'
TEXT    = '#e2e8f0'
SOFT    = '#94a3b8'
COLORS  = {
    'atrp':'#3b82f6','dijkstra':'#f59e0b',
    'aodv':'#8b5cf6','rpl':'#06b6d4','random':'#ef4444'
}


def run_cdf_collection(G, protocol, seed=RANDOM_SEED):
    """
    Run simulation and collect per-packet delivery status
    and path length. Returns two lists:
      delivered_hops — hop counts of delivered packets
      failed_hops    — hop counts of failed packets
    """
    random.seed(seed)
    np.random.seed(seed)
    nodes = list(G.nodes())
    tw, uptime, failures, tx_count, lat_sum, battery, total_t, etx = tw_initialise(nodes)
    failed_nodes = set()
    node_etx     = {n: random.uniform(1.0, 3.0) for n in nodes}
    for n in nodes:
        etx[n] = node_etx[n]

    delivered_hops = []
    failed_hops    = []

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
            if protocol == 'atrp':
                path = atrp_route(G, src, GATEWAY, tw, lam=LAMBDA)
            elif protocol == 'dijkstra':
                path = dijkstra_route(G, src, GATEWAY)
            elif protocol == 'aodv':
                path = aodv_route(G, src, GATEWAY, failed_nodes)
            elif protocol == 'rpl':
                path = rpl_route(G, src, GATEWAY, node_etx)
            else:
                continue
            if path is None:
                continue

            hops = len(path) - 1
            ok   = True
            for node in path[1:]:
                if node in failed_nodes or random.random() > tw.get(node,0.5)*0.95:
                    ok = False; break

            if ok:
                delivered_hops.append(hops)
            else:
                failed_hops.append(hops)

    return delivered_hops, failed_hops


def run_cdf():
    print("\n" + "="*60)
    print("  EVAL 04: CDF of Packet Delivery vs Path Length")
    print("="*60)

    G = build_iot_graph()
    protocols = ['atrp', 'dijkstra', 'aodv', 'rpl']
    labels    = ['ATRP', 'Dijkstra', 'AODV', 'RPL']
    all_data  = {}

    for protocol, label in zip(protocols, labels):
        print(f"  Collecting {label}...", end=' ', flush=True)
        d_hops, f_hops = run_cdf_collection(G, protocol)
        total     = len(d_hops) + len(f_hops)
        delivered = len(d_hops)
        pdr       = round(delivered / max(1, total) * 100, 2)
        all_data[protocol] = {
            'label'         : label,
            'delivered_hops': d_hops,
            'failed_hops'   : f_hops,
            'pdr'           : pdr
        }
        print(f"Delivered={delivered} | Failed={len(f_hops)} | PDR={pdr}%")

    # Plot CDF
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.patch.set_facecolor(BG)
    fig.suptitle(
        'CDF of Packet Delivery — Path Length Distribution\n'
        '50 nodes | 1000 ticks | Failure rate=0.02',
        color=TEXT, fontsize=13
    )

    # Panel A: CDF of delivered packets by hop count
    ax1 = axes[0]
    ax1.set_facecolor(SURFACE)
    ax1.tick_params(colors=SOFT, labelsize=9)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    for sp in ['bottom','left']:
        ax1.spines[sp].set_color(BORDER)
    ax1.grid(color=BORDER, alpha=0.4, zorder=0)

    for protocol, label in zip(protocols, labels):
        d_hops = all_data[protocol]['delivered_hops']
        if not d_hops:
            continue
        sorted_hops = np.sort(d_hops)
        cdf = np.arange(1, len(sorted_hops)+1) / len(sorted_hops)
        lw  = 3 if protocol == 'atrp' else 1.5
        ax1.plot(sorted_hops, cdf * 100,
                 color=COLORS[protocol], lw=lw,
                 label=f'{label} (PDR={all_data[protocol]["pdr"]}%)',
                 zorder=3)

    ax1.set_title('(A) CDF of Delivered Packets by Hop Count',
                  color=TEXT, fontsize=11, pad=10)
    ax1.set_xlabel('Path Length (hops)', color=SOFT, fontsize=10)
    ax1.set_ylabel('Cumulative % of Delivered Packets', color=SOFT, fontsize=10)
    ax1.legend(facecolor=SURFACE, edgecolor=BORDER,
               labelcolor=SOFT, fontsize=9)
    ax1.set_xlim(0, 10)

    # Panel B: Delivery rate by hop count (bar)
    ax2 = axes[1]
    ax2.set_facecolor(SURFACE)
    ax2.tick_params(colors=SOFT, labelsize=9)
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    for sp in ['bottom','left']:
        ax2.spines[sp].set_color(BORDER)
    ax2.grid(axis='y', color=BORDER, alpha=0.4, zorder=0)

    max_hops = 8
    x = np.arange(1, max_hops+1)
    width = 0.2
    offsets = [-1.5, -0.5, 0.5, 1.5]

    for i, (protocol, label) in enumerate(zip(protocols, labels)):
        d_hops = all_data[protocol]['delivered_hops']
        f_hops = all_data[protocol]['failed_hops']
        rates  = []
        for h in range(1, max_hops+1):
            d = d_hops.count(h)
            f = f_hops.count(h)
            rate = d / max(1, d+f) * 100
            rates.append(rate)
        lw = 2 if protocol == 'atrp' else 1
        ax2.bar(x + offsets[i]*width, rates,
                width=width, color=COLORS[protocol],
                label=label, zorder=3,
                edgecolor='#93c5fd' if protocol=='atrp' else 'none',
                linewidth=lw)

    ax2.set_title('(B) Delivery Success Rate by Hop Count',
                  color=TEXT, fontsize=11, pad=10)
    ax2.set_xlabel('Path Length (hops)', color=SOFT, fontsize=10)
    ax2.set_ylabel('Delivery Rate (%)', color=SOFT, fontsize=10)
    ax2.set_xticks(x)
    ax2.set_xticklabels([f'{h} hop{"s" if h>1 else ""}' for h in x],
                        color=SOFT, fontsize=8)
    ax2.legend(facecolor=SURFACE, edgecolor=BORDER,
               labelcolor=SOFT, fontsize=9)
    ax2.set_ylim(0, 110)

    plt.tight_layout()
    os.makedirs('figures', exist_ok=True)
    plt.savefig('figures/eval_04_cdf.png', dpi=150,
                bbox_inches='tight', facecolor=BG)
    plt.close()

    os.makedirs('results', exist_ok=True)
    save_data = {p: {'label': all_data[p]['label'],
                     'pdr': all_data[p]['pdr']}
                 for p in protocols}
    with open('results/eval_04_cdf.json', 'w') as f:
        json.dump(save_data, f, indent=2)

    print(f"\n  Saved -> figures/eval_04_cdf.png")
    print(f"  Saved -> results/eval_04_cdf.json")
    print("\n  eval_04_cdf.py -- DONE\n")
    return all_data


if __name__ == '__main__':
    run_cdf()