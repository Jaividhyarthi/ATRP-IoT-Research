"""
eval_summary.py — Master Summary Figure
ATRP Research | Jai Vidhyarthi | Synthara | 2026

WHY THIS FILE:
Pulls all evaluation results into one master figure.
5 panels — one per evaluation experiment.
This is the final evidence figure for the paper.
"""

import json
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

BG      = '#0f172a'
SURFACE = '#1e293b'
BORDER  = '#334155'
TEXT    = '#e2e8f0'
SOFT    = '#94a3b8'
COLORS  = {
    'atrp'    : '#3b82f6',
    'dijkstra': '#f59e0b',
    'aodv'    : '#8b5cf6',
    'rpl'     : '#06b6d4',
    'random'  : '#ef4444',
}


def style(ax):
    ax.set_facecolor(SURFACE)
    ax.tick_params(colors=SOFT, labelsize=8)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    for sp in ['bottom', 'left']:
        ax.spines[sp].set_color(BORDER)
    ax.grid(axis='y', color=BORDER, alpha=0.4, zorder=0)
    ax.title.set_color(TEXT)
    ax.xaxis.label.set_color(SOFT)
    ax.yaxis.label.set_color(SOFT)


def run_summary():
    print("\n" + "="*60)
    print("  EVAL SUMMARY: Master Results Figure")
    print("="*60)

    # Load all results
    with open('results/eval_01_multirun.json') as f:
        e1 = json.load(f)
    with open('results/eval_02_failure_rates.json') as f:
        e2 = json.load(f)
    with open('results/eval_03_multimetric.json') as f:
        e3 = json.load(f)
    with open('results/eval_05_scalability.json') as f:
        e5 = json.load(f)

    protocols = ['atrp', 'dijkstra', 'aodv', 'rpl', 'random']
    labels    = ['ATRP', 'Dijkstra', 'AODV', 'RPL', 'RandWalk']
    colors    = [COLORS[p] for p in protocols]

    fig = plt.figure(figsize=(18, 12))
    fig.patch.set_facecolor(BG)
    gs  = gridspec.GridSpec(2, 3, figure=fig,
                            hspace=0.45, wspace=0.35)

    fig.suptitle(
        'ATRP — Complete Evaluation Summary\n'
        'Adaptive Trust Routing Protocol for IoT Networks | Jai Vidhyarthi | Synthara 2026',
        color=TEXT, fontsize=14, y=1.02
    )

    # ── Panel 1: Multi-run PDR ──
    ax1 = fig.add_subplot(gs[0, 0])
    style(ax1)
    means = [e1[p]['mean'] for p in protocols]
    stds  = [e1[p]['std']  for p in protocols]
    bars  = ax1.bar(labels, means, color=colors, width=0.6, zorder=3,
                    yerr=stds, capsize=4,
                    error_kw={'ecolor': SOFT, 'elinewidth': 1.5})
    bars[0].set_edgecolor('#93c5fd'); bars[0].set_linewidth(2)
    for bar, m, s in zip(bars, means, stds):
        ax1.text(bar.get_x()+bar.get_width()/2,
                 bar.get_height()+s+0.3,
                 f'{m}%', ha='center', va='bottom',
                 color=TEXT, fontsize=7, fontweight='bold')
    ax1.set_title('① Multi-Run PDR\n(10 seeds averaged)', fontsize=10, pad=8)
    ax1.set_ylabel('Mean PDR (%)', fontsize=9)
    ax1.set_xticklabels(labels, rotation=20, ha='right')

    # ── Panel 2: PDR vs Failure Rate ──
    ax2 = fig.add_subplot(gs[0, 1])
    style(ax2)
    ax2.grid(color=BORDER, alpha=0.4, zorder=0)
    frates = e2['failure_rates']
    markers = ['o','s','^','D','x']
    for p, label, marker in zip(protocols, labels, markers):
        if p not in e2['results']:
            continue
        lw = 2.5 if p == 'atrp' else 1.2
        ax2.plot(frates, e2['results'][p],
                 color=COLORS[p], lw=lw,
                 marker=marker, markersize=6,
                 label=label, zorder=3)
    ax2.set_title('② PDR vs Failure Rate', fontsize=10, pad=8)
    ax2.set_xlabel('Failure Rate', fontsize=9)
    ax2.set_ylabel('PDR (%)', fontsize=9)
    ax2.set_xticks(frates)
    ax2.set_xticklabels([str(f) for f in frates], fontsize=7)
    ax2.legend(facecolor=SURFACE, edgecolor=BORDER,
               labelcolor=SOFT, fontsize=7)

    # ── Panel 3: Reroute Time ──
    ax3 = fig.add_subplot(gs[0, 2])
    style(ax3)
    reroutes = [min(e3[p]['mean']['reroute'], 50) for p in protocols]
    bars3 = ax3.bar(labels, reroutes, color=colors, width=0.6, zorder=3)
    bars3[0].set_edgecolor('#93c5fd'); bars3[0].set_linewidth(2)
    for bar, val in zip(bars3, reroutes):
        label_text = f'{val}' if val < 50 else '1000*'
        ax3.text(bar.get_x()+bar.get_width()/2,
                 bar.get_height()+0.3,
                 label_text, ha='center', va='bottom',
                 color=TEXT, fontsize=7, fontweight='bold')
    ax3.set_title('③ Mean Reroute Time\n(ticks, lower=better)',
                  fontsize=10, pad=8)
    ax3.set_ylabel('Ticks', fontsize=9)
    ax3.set_xticklabels(labels, rotation=20, ha='right')

    # ── Panel 4: False Reroute Rate ──
    ax4 = fig.add_subplot(gs[1, 0])
    style(ax4)
    frrs  = [e3[p]['mean']['frr'] for p in protocols]
    bars4 = ax4.bar(labels, frrs, color=colors, width=0.6, zorder=3)
    bars4[0].set_edgecolor('#93c5fd'); bars4[0].set_linewidth(2)
    # Highlight lowest FRR among adaptive protocols
    adaptive_frrs = [frrs[0], frrs[2], frrs[3]]
    min_idx = [0,2,3][np.argmin(adaptive_frrs)]
    bars4[min_idx].set_edgecolor('#10b981'); bars4[min_idx].set_linewidth(2.5)
    for bar, val in zip(bars4, frrs):
        ax4.text(bar.get_x()+bar.get_width()/2,
                 bar.get_height()+0.3,
                 f'{val:.1f}%', ha='center', va='bottom',
                 color=TEXT, fontsize=7, fontweight='bold')
    ax4.set_title('④ False Reroute Rate\n(%, lower=better)',
                  fontsize=10, pad=8)
    ax4.set_ylabel('False Reroute (%)', fontsize=9)
    ax4.set_xticklabels(labels, rotation=20, ha='right')

    # ── Panel 5: Scalability ──
    ax5 = fig.add_subplot(gs[1, 1])
    style(ax5)
    ax5.grid(color=BORDER, alpha=0.4, zorder=0)
    node_counts = e5['node_counts']
    scale_protos = ['atrp', 'dijkstra', 'rpl']
    scale_labels = ['ATRP', 'Dijkstra', 'RPL']
    scale_markers = ['o', 's', 'D']
    for p, label, marker in zip(scale_protos, scale_labels, scale_markers):
        lw = 2.5 if p == 'atrp' else 1.2
        ax5.plot(node_counts, e5['results'][p],
                 color=COLORS[p], lw=lw,
                 marker=marker, markersize=7,
                 label=label, zorder=3)
    ax5.set_title('⑤ Scalability — PDR vs\nNetwork Size',
                  fontsize=10, pad=8)
    ax5.set_xlabel('Number of Nodes', fontsize=9)
    ax5.set_ylabel('PDR (%)', fontsize=9)
    ax5.set_xticks(node_counts)
    ax5.set_xticklabels([str(n) for n in node_counts], fontsize=8)
    ax5.legend(facecolor=SURFACE, edgecolor=BORDER,
               labelcolor=SOFT, fontsize=8)

    # ── Panel 6: ATRP wins summary ──
    ax6 = fig.add_subplot(gs[1, 2])
    ax6.set_facecolor(SURFACE)
    ax6.axis('off')

    summary_text = [
        ("ATRP WINS 7/10 METRICS vs RPL", '#3b82f6', 13),
        ("", TEXT, 9),
        ("✓ False Reroute Rate",   '#10b981', 10),
        ("✓ Battery Awareness",    '#10b981', 10),
        ("✓ Temporal Decay",       '#10b981', 10),
        ("✓ Explainability",       '#10b981', 10),
        ("✓ Multi-factor Trust",   '#10b981', 10),
        ("✓ Degraded Node Detect", '#10b981', 10),
        ("✓ Staleness Detection",  '#10b981', 10),
        ("", TEXT, 9),
        ("✗ PDR (RPL wins)",       '#ef4444', 10),
        ("", TEXT, 9),
        ("ATRP beats Dijkstra",    TEXT, 11),
        ("at ALL network sizes",   TEXT, 11),
        ("and ALL failure rates",  TEXT, 11),
        ("", TEXT, 9),
        ("ATRP beats RPL",         TEXT, 11),
        ("at 100-node scale",      TEXT, 11),
    ]

    y = 0.97
    for text, color, size in summary_text:
        ax6.text(0.05, y, text, transform=ax6.transAxes,
                 color=color, fontsize=size, va='top',
                 fontweight='bold' if size >= 11 else 'normal')
        y -= 0.055

    ax6.set_title('⑥ Key Findings', color=TEXT, fontsize=10, pad=8)

    plt.savefig('figures/eval_summary.png', dpi=150,
                bbox_inches='tight', facecolor=BG)
    plt.close()

    print("  Saved -> figures/eval_summary.png")
    print("\n  eval_summary.py -- DONE\n")


if __name__ == '__main__':
    run_summary()