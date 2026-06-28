"""
node_inspector.py — IoT Device State Inspector
ATRP Research | Jai Vidhyarthi | Synthara | 2026

Proves each node behaves as a real simulated IoT device
by printing live state of every node after simulation.
"""

import random
import json
import os
from graph import build_iot_graph, GATEWAY
from trust import tw_initialise, tw_update, ZONE_AVOID, ZONE_TRUSTED, MAX_LAT, BATTERY_MAX

FAILURE_RATE = 0.02
RANDOM_SEED  = 42
random.seed(RANDOM_SEED)


def get_zone(tw_val):
    if tw_val < ZONE_AVOID:    return 'AVOID  '
    elif tw_val < ZONE_TRUSTED: return 'MONITOR'
    else:                       return 'TRUSTED'


def run_and_inspect(ticks=200):
    G     = build_iot_graph()
    nodes = list(G.nodes())
    tw, uptime, failures, tx_count, lat_sum, battery, total_t = tw_initialise(nodes)
    failed_nodes = set()

    for tick in range(ticks):
        for n in nodes:
            roll = random.random()
            if n in failed_nodes:
                if roll < FAILURE_RATE * 3:
                    event = 'recover'
                    failed_nodes.discard(n)
                else:
                    event = 'silent'
            elif roll < FAILURE_RATE:
                event = 'failure'
                failed_nodes.add(n)
            else:
                event = 'observe'
            tw_update(n, event, tw, uptime, failures,
                      tx_count, lat_sum, battery, total_t, dt=1)

    # Print node state table
    print("\n" + "="*85)
    print("  SIMULATED IoT DEVICE STATE TABLE")
    print(f"  Network: 50 nodes | {ticks} ticks simulated | Failure rate: {FAILURE_RATE}")
    print("="*85)
    print(f"  {'Node':<6} {'Type':<10} {'TW':>6} {'Zone':<10} {'Battery%':>9} "
          f"{'Uptime%':>8} {'Pkt Loss%':>10} {'Status'}")
    print("-"*85)

    node_records = []
    for n in sorted(nodes):
        device_type = 'GATEWAY' if n == GATEWAY else 'SENSOR'
        tw_val      = tw[n]
        zone        = get_zone(tw_val)
        bat_pct     = round(battery[n] / BATTERY_MAX * 100, 1)
        up_pct      = round(uptime[n]  / max(1, total_t[n]) * 100, 1)
        loss_pct    = round(failures[n] / max(1, tx_count[n]) * 100, 1)
        status      = 'FAILED' if n in failed_nodes else 'ONLINE'

        zone_color = {'AVOID  ': '!', 'MONITOR': '~', 'TRUSTED': ' '}[zone]

        print(f"  {n:<6} {device_type:<10} {tw_val:>6.4f} [{zone}]{zone_color} "
              f"{bat_pct:>8}% {up_pct:>7}% {loss_pct:>9}%   {status}")

        node_records.append({
            'node': n, 'type': device_type, 'tw': tw_val,
            'zone': zone.strip(), 'battery_pct': bat_pct,
            'uptime_pct': up_pct, 'loss_pct': loss_pct, 'status': status
        })

    print("-"*85)

    # Summary
    avoid   = [r for r in node_records if r['zone'] == 'AVOID']
    monitor = [r for r in node_records if r['zone'] == 'MONITOR']
    trusted = [r for r in node_records if r['zone'] == 'TRUSTED']
    failed  = [r for r in node_records if r['status'] == 'FAILED']

    print(f"\n  NETWORK SUMMARY after {ticks} ticks:")
    print(f"    Trusted nodes  : {len(trusted)}/50  ({round(len(trusted)/50*100)}%)")
    print(f"    Monitor nodes  : {len(monitor)}/50  ({round(len(monitor)/50*100)}%)")
    print(f"    Avoid nodes    : {len(avoid)}/50  ({round(len(avoid)/50*100)}%)")
    print(f"    Currently down : {len(failed)} nodes")
    print(f"    Avg TW (network): {round(sum(tw.values())/len(nodes), 4)}")
    print(f"    Avg battery    : {round(sum(battery.values())/len(nodes)/BATTERY_MAX*100, 1)}%")

    os.makedirs('results', exist_ok=True)
    with open('results/node_states.json', 'w') as f:
        json.dump(node_records, f, indent=2)
    print(f"\n  Saved -> results/node_states.json")
    print("\n  node_inspector.py -- DONE\n")


if __name__ == '__main__':
    run_and_inspect()