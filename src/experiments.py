"""
experiments.py — Lambda Grid Search + Weight Sensitivity Analysis
ATRP Research | Jai Vidhyarthi | Synthara | 2026

WHY THIS FILE:
Reviewers will challenge two things:
  1. "Why lambda=0.3? Seems arbitrary."
  2. "Why those specific weights? How did you derive them?"

This file answers both empirically.

Experiment 2: Lambda Grid Search
  Run ATRP with lambda from 0.0 to 1.0 in steps of 0.1
  Record PDR for each lambda value
  The lambda that gives highest PDR is the optimal value
  If lambda=0.3 wins — our choice is validated

Experiment 3: Weight Sensitivity Analysis
  Run ATRP with 6 different weight combinations
  Record PDR for each
  If default weights win — our weight derivation is validated
"""

import random
import math
import json
import os
import numpy as np

from graph      import build_iot_graph, GATEWAY, NUM_NODES
from trust      import tw_initialise, tw_update, ZONE_TRUSTED, MAX_LAT, BATTERY_MAX
from routing    import atrp_route
from simulation import NUM_TICKS, FAILURE_RATE, PACKETS_PER_TICK, RANDOM_SEED


# ═══════════════════════════════════════════════════
#  EXPERIMENT 2: LAMBDA GRID SEARCH
# ═══════════════════════════════════════════════════
def experiment_lambda(G):
    """
    WHY THIS EXPERIMENT:
    Lambda controls the explore-exploit tradeoff in ATRP's cost function.
      lambda=0.0 → pure trust routing (may take very long paths)
      lambda=1.0 → pure distance routing (identical to Dijkstra)
      lambda=0.3 → our proposed optimal value

    We validate this by running ATRP with 11 lambda values
    and measuring PDR for each. The winning lambda is the optimal one.
    This is a standard hyperparameter grid search — common in ML papers
    and now being applied to routing protocol tuning.
    """
    print("\n" + "="*60)
    print("  EXPERIMENT 2: Lambda Grid Search")
    print("  Validating optimal explore-exploit parameter")
    print("="*60)

    lambdas   = [round(x, 1) for x in np.arange(0.0, 1.1, 0.1)]
    pdr_vals  = []
    cost_vals = []

    for lam in lambdas:
        random.seed(RANDOM_SEED)
        np.random.seed(RANDOM_SEED)

        nodes = list(G.nodes())
        tw, uptime, failures, tx_count, lat_sum, battery, total_t = tw_initialise(nodes)
        failed_nodes = set()

        delivered     = 0
        total_packets = 0
        path_costs    = []

        for tick in range(NUM_TICKS):
            for n in nodes:
                roll = random.random()
                if n in failed_nodes:
                    event = 'recover' if roll < FAILURE_RATE * 3 else 'silent'
                    if event == 'recover':
                        failed_nodes.discard(n)
                elif roll < FAILURE_RATE:
                    event = 'failure'
                    failed_nodes.add(n)
                else:
                    event = 'observe'
                tw_update(n, event, tw, uptime, failures,
                          tx_count, lat_sum, battery, total_t, dt=1)

            for _ in range(PACKETS_PER_TICK):
                src = random.choice([n for n in nodes if n != GATEWAY])
                total_packets += 1
                path = atrp_route(G, src, GATEWAY, tw, lam=lam)
                if path is None:
                    continue
                delivered_ok = True
                for node in path[1:]:
                    if node in failed_nodes:
                        delivered_ok = False
                        break
                    if random.random() > tw.get(node, 0.5) * 0.95:
                        delivered_ok = False
                        break
                if delivered_ok:
                    delivered += 1
                path_costs.append(len(path) - 1)

        pdr  = round((delivered / max(1, total_packets)) * 100, 2)
        cost = round(float(np.mean(path_costs)), 2) if path_costs else 0
        pdr_vals.append(pdr)
        cost_vals.append(cost)
        print(f"  lambda={lam:.1f}  PDR={pdr}%  PathCost={cost}")

    best_idx = int(np.argmax(pdr_vals))
    best_lam = lambdas[best_idx]
    best_pdr = pdr_vals[best_idx]

    print(f"\n  Optimal lambda = {best_lam}  ->  PDR = {best_pdr}%")
    if best_lam == 0.3:
        print("  CONFIRMED: lambda=0.3 is optimal — paper claim validated.")
    else:
        print(f"  NOTE: Empirical optimum is {best_lam}. "
              f"Update paper claim accordingly.")

    results = {
        'lambdas'  : lambdas,
        'pdr_vals' : pdr_vals,
        'cost_vals': cost_vals,
        'optimal'  : best_lam,
        'best_pdr' : best_pdr,
    }
    os.makedirs('results', exist_ok=True)
    with open('results/experiment2_lambda_search.json', 'w') as f:
        json.dump(results, f, indent=2)
    print(f"  Saved -> results/experiment2_lambda_search.json")

    return results


# ═══════════════════════════════════════════════════
#  EXPERIMENT 3: WEIGHT SENSITIVITY ANALYSIS
# ═══════════════════════════════════════════════════
def run_with_weights(G, weights, seed=RANDOM_SEED):
    """
    Run ATRP simulation with custom TW weights.
    weights = [w1, w2, w3, w4] — must sum to 1.0
    Returns PDR.
    """
    w1, w2, w3, w4 = weights
    random.seed(seed)
    np.random.seed(seed)

    nodes = list(G.nodes())
    tw, uptime, failures, tx_count, lat_sum, battery, total_t = tw_initialise(nodes)
    failed_nodes = set()

    delivered     = 0
    total_packets = 0

    for tick in range(NUM_TICKS):
        for n in nodes:
            roll = random.random()
            if n in failed_nodes:
                if roll < FAILURE_RATE * 3:
                    failed_nodes.discard(n)
                    tw_update(n, 'recover', tw, uptime, failures,
                              tx_count, lat_sum, battery, total_t, dt=1)
                else:
                    tw_update(n, 'silent', tw, uptime, failures,
                              tx_count, lat_sum, battery, total_t, dt=1)
            elif roll < FAILURE_RATE:
                failed_nodes.add(n)
                tw_update(n, 'failure', tw, uptime, failures,
                          tx_count, lat_sum, battery, total_t, dt=1)
            else:
                # Custom weight recomputation
                total_t[n]  += 1
                uptime[n]   += 1
                tx_count[n] += 1
                battery[n]   = max(1.0, battery[n] - random.uniform(0.1, 0.5))
                lat_sample   = random.uniform(10, MAX_LAT * 0.6)
                lat_sum[n]  += lat_sample

                U = uptime[n]  / max(1, total_t[n])
                R = 1 - (failures[n] / max(1, tx_count[n]))
                L = 1 - ((lat_sum[n] / max(1, tx_count[n])) / MAX_LAT)
                E = battery[n] / BATTERY_MAX

                tw[n] = max(0.01, min(1.0, w1*U + w2*R + w3*L + w4*E))

        for _ in range(PACKETS_PER_TICK):
            src = random.choice([n for n in nodes if n != GATEWAY])
            total_packets += 1
            path = atrp_route(G, src, GATEWAY, tw, lam=0.7)
            if path is None:
                continue
            ok = True
            for node in path[1:]:
                if node in failed_nodes:
                    ok = False; break
                if random.random() > tw.get(node, 0.5) * 0.95:
                    ok = False; break
            if ok:
                delivered += 1

    return round((delivered / max(1, total_packets)) * 100, 2)


def experiment_weights(G):
    """
    WHY THIS EXPERIMENT:
    Our TW formula uses weights w1=0.30, w2=0.35, w3=0.20, w4=0.15.
    Reviewers will ask: why these specific values?

    We answer by testing 6 different weight configurations
    and showing our default weights produce the highest PDR.
    This converts a design choice into an empirical result.

    Weight configurations tested:
      Default  : our proposed weights from the paper
      Equal    : all components weighted equally (null hypothesis)
      Uptime   : heavily favour uptime signal
      Reliability: heavily favour packet loss signal
      Latency  : heavily favour latency signal
      Energy   : heavily favour energy signal
    """
    print("\n" + "="*60)
    print("  EXPERIMENT 3: Weight Sensitivity Analysis")
    print("  Validating TW formula weight derivation")
    print("="*60)

    configs = [
        ([0.30, 0.35, 0.20, 0.15], "Default  (w1=0.30,w2=0.35,w3=0.20,w4=0.15)"),
        ([0.25, 0.25, 0.25, 0.25], "Equal    (w1=w2=w3=w4=0.25)"),
        ([0.50, 0.20, 0.20, 0.10], "Uptime-heavy   (w1=0.50)"),
        ([0.15, 0.55, 0.20, 0.10], "Reliability-heavy (w2=0.55)"),
        ([0.20, 0.25, 0.45, 0.10], "Latency-heavy  (w3=0.45)"),
        ([0.20, 0.25, 0.15, 0.40], "Energy-heavy   (w4=0.40)"),
    ]

    weight_results = []
    for weights, label in configs:
        pdr = run_with_weights(G, weights)
        weight_results.append({
            'label'  : label,
            'weights': weights,
            'pdr'    : pdr,
        })
        marker = " <-- DEFAULT" if weights == [0.30, 0.35, 0.20, 0.15] else ""
        print(f"  {label:<45}  PDR = {pdr}%{marker}")

    best = max(weight_results, key=lambda x: x['pdr'])
    print(f"\n  Best config: {best['label'].strip()}")
    print(f"  Best PDR   : {best['pdr']}%")

    if best['weights'] == [0.30, 0.35, 0.20, 0.15]:
        print("  CONFIRMED: Default weights are optimal — paper claim validated.")
    else:
        print(f"  NOTE: {best['label'].strip()} outperforms default.")
        print(f"  Consider updating weights in paper.")

    os.makedirs('results', exist_ok=True)
    with open('results/experiment3_weight_sensitivity.json', 'w') as f:
        json.dump(weight_results, f, indent=2)
    print(f"  Saved -> results/experiment3_weight_sensitivity.json")

    return weight_results

def experiment_weights_multirun(G, runs=5):
    """
    Run weight sensitivity across multiple random seeds.
    Averages out simulation variance to get stable results.
    """
    print("\n" + "="*60)
    print("  EXPERIMENT 3b: Weight Sensitivity — 5 Seeds Averaged")
    print("="*60)

    configs = [
        ([0.30, 0.35, 0.20, 0.15], "Default"),
        ([0.25, 0.25, 0.25, 0.25], "Equal"),
        ([0.50, 0.20, 0.20, 0.10], "Uptime-heavy"),
        ([0.15, 0.55, 0.20, 0.10], "Reliability-heavy"),
        ([0.20, 0.25, 0.45, 0.10], "Latency-heavy"),
        ([0.20, 0.25, 0.15, 0.40], "Energy-heavy"),
    ]

    seeds = [42, 123, 256, 789, 999]
    final = []

    for weights, label in configs:
        pdrs = [run_with_weights(G, weights, seed=s) for s in seeds]
        avg  = round(float(np.mean(pdrs)), 2)
        std  = round(float(np.std(pdrs)),  2)
        final.append({'label': label, 'weights': weights,
                      'avg_pdr': avg, 'std': std, 'pdrs': pdrs})
        print(f"  {label:<22} Avg PDR={avg}%  Std={std}%")

    best = max(final, key=lambda x: x['avg_pdr'])
    print(f"\n  Winner across 5 seeds: {best['label']} "
          f"-> Avg PDR={best['avg_pdr']}%")

    os.makedirs('results', exist_ok=True)
    with open('results/experiment3b_multirun.json', 'w') as f:
        json.dump(final, f, indent=2)
    print(f"  Saved -> results/experiment3b_multirun.json")
    return final

if __name__ == '__main__':
    print("\n" + "="*60)
    print("  ATRP — Experiments 2 & 3")
    print("="*60)

    G = build_iot_graph()

    lambda_results  = experiment_lambda(G)
    weight_results  = experiment_weights(G)
    multirun_results = experiment_weights_multirun(G)

    print("\n  experiments.py -- DONE\n")