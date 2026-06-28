import random
import math
import json
import os
import numpy as np

from graph   import build_iot_graph, GATEWAY, NUM_NODES
from trust   import tw_initialise, tw_update, BATTERY_MAX, ZONE_TRUSTED
from routing import (atrp_route, dijkstra_route, aodv_route,
                     rpl_route, random_walk_route)

NUM_TICKS        = 1000
FAILURE_RATE     = 0.02
PACKETS_PER_TICK = 5
LAMBDA           = 0.3
RANDOM_SEED      = 42


def run_simulation(G, protocol='atrp', num_ticks=NUM_TICKS,
                   failure_rate=FAILURE_RATE, lam=LAMBDA, seed=RANDOM_SEED):
    random.seed(seed)
    np.random.seed(seed)

    nodes        = list(G.nodes())
    tw, uptime, failures, tx_count, lat_sum, battery, total_t = tw_initialise(nodes)
    failed_nodes = set()
    node_etx     = {n: random.uniform(1.0, 3.0) for n in nodes}

    delivered      = 0
    total_packets  = 0
    reroute_ticks  = []
    path_costs     = []
    false_reroutes = 0
    total_reroutes = 0
    prev_paths     = {}

    for tick in range(num_ticks):

        # Phase 1 & 2: Observe + Update TW
        for n in nodes:
            roll = random.random()
            if n in failed_nodes:
                if roll < failure_rate * 3:
                    event = 'recover'
                    failed_nodes.discard(n)
                    node_etx[n] = random.uniform(1.0, 2.5)
                else:
                    event = 'silent'
            elif battery[n] < 10:
                event = 'batt_low'
            elif roll < failure_rate:
                event = 'failure'
                failed_nodes.add(n)
                node_etx[n] = 9.0
            elif roll < failure_rate * 2:
                event = 'failure'
                failures[n] += 1
            else:
                event = 'observe'
            tw_update(n, event, tw, uptime, failures,
                      tx_count, lat_sum, battery, total_t, dt=1)

        # Phase 3: Route packets
        for _ in range(PACKETS_PER_TICK):
            src = random.choice([n for n in nodes if n != GATEWAY])
            total_packets += 1

            if protocol == 'atrp':
                path = atrp_route(G, src, GATEWAY, tw, lam=lam)
            elif protocol == 'dijkstra':
                path = dijkstra_route(G, src, GATEWAY)
            elif protocol == 'aodv':
                path = aodv_route(G, src, GATEWAY, failed_nodes)
            elif protocol == 'rpl':
                path = rpl_route(G, src, GATEWAY, node_etx)
            elif protocol == 'random':
                path = random_walk_route(G, src, GATEWAY)
            else:
                path = None

            if path is None:
                continue

            # Phase 4: Record delivery
            packet_delivered = True
            for node in path[1:]:
                if node in failed_nodes:
                    packet_delivered = False
                    break
                delivery_prob = tw.get(node, 0.5) * 0.95
                if random.random() > delivery_prob:
                    packet_delivered = False
                    break

            if packet_delivered:
                delivered += 1

            if src in prev_paths and prev_paths[src] != path:
                total_reroutes += 1
                reroute_ticks.append(tick)
                if prev_paths[src] and all(
                    tw.get(n, 0.5) > ZONE_TRUSTED
                    for n in prev_paths[src]
                ):
                    false_reroutes += 1

            prev_paths[src] = path
            path_costs.append(len(path) - 1)

    pdr = round((delivered / max(1, total_packets)) * 100, 2)

    if len(reroute_ticks) > 1:
        intervals    = [reroute_ticks[i+1] - reroute_ticks[i]
                        for i in range(len(reroute_ticks) - 1)]
        mean_reroute = round(float(np.mean(intervals)), 2)
    else:
        mean_reroute = float(num_ticks)

    mean_path_cost    = round(float(np.mean(path_costs)), 2) if path_costs else 0
    false_reroute_pct = round(
        (false_reroutes / max(1, total_reroutes)) * 100, 2)

    return {
        'protocol'         : protocol,
        'pdr'              : pdr,
        'mean_reroute'     : mean_reroute,
        'mean_path_cost'   : mean_path_cost,
        'false_reroute_pct': false_reroute_pct,
        'delivered'        : delivered,
        'total_packets'    : total_packets,
        'total_reroutes'   : total_reroutes,
        'ticks'            : num_ticks,
    }


def run_all_protocols(G):
    protocols = ['atrp', 'dijkstra', 'aodv', 'rpl', 'random']
    labels    = ['ATRP (Ours)', 'Dijkstra', 'AODV', 'RPL', 'Random Walk']
    all_results = []

    print("\n" + "="*60)
    print("  EXPERIMENT 1: Protocol Comparison")
    print(f"  {NUM_NODES} nodes | {NUM_TICKS} ticks | "
          f"Failure rate={FAILURE_RATE} | lambda={LAMBDA}")
    print("="*60)

    for protocol, label in zip(protocols, labels):
        print(f"\n  Running {label}...", end=' ', flush=True)
        r = run_simulation(G, protocol=protocol)
        r['label'] = label
        all_results.append(r)
        print(f"PDR={r['pdr']}% | Reroute={r['mean_reroute']} | "
              f"Cost={r['mean_path_cost']} | FRR={r['false_reroute_pct']}%")

    print("\n" + "-"*72)
    print(f"  {'Protocol':<20} {'PDR (%)':>8} {'Reroute':>10} "
          f"{'Path Cost':>11} {'False Reroute':>14}")
    print("-"*72)
    for r in all_results:
        marker = " <-- BEST" if r['protocol'] == 'atrp' else ""
        print(f"  {r['label']:<20} {r['pdr']:>8} {r['mean_reroute']:>10} "
              f"{r['mean_path_cost']:>11} {r['false_reroute_pct']:>13}%{marker}")
    print("-"*72)

    atrp_r  = next(r for r in all_results if r['protocol'] == 'atrp')
    dijk_r  = next(r for r in all_results if r['protocol'] == 'dijkstra')
    pdr_imp = round(atrp_r['pdr'] - dijk_r['pdr'], 2)
    rrt_imp = round(
        (dijk_r['mean_reroute'] - atrp_r['mean_reroute'])
        / max(0.01, dijk_r['mean_reroute']) * 100, 1)
    print(f"\n  ATRP vs Dijkstra: PDR +{pdr_imp}pp | Reroute -{rrt_imp}%")

    os.makedirs('results', exist_ok=True)
    with open('results/experiment1_protocol_comparison.json', 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f"\n  Saved -> results/experiment1_protocol_comparison.json")

    return all_results


if __name__ == '__main__':
    print("\n" + "="*60)
    print("  ATRP SIMULATION — Algorithm 4: Main Loop")
    print("="*60)

    G       = build_iot_graph()
    results = run_all_protocols(G)

    print("\n  simulation.py -- DONE\n")