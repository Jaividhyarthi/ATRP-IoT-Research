"""
trust.py — Trust Weight Formula + Decay Update
ATRP Research | Jai Vidhyarthi | Synthara | 2026

WHY THIS FILE:
This is the mathematical core of ATRP.
Standard routing sees all nodes as equal — only distance matters.
ATRP assigns every node a Trust Weight (TW) between 0.0 and 1.0
based on four observable behavioural signals.

PRIMARY FORMULA:
  TW(n,t) = w1*U(n,t) + w2*R(n,t) + w3*L(n,t) + w4*E(n,t)

  U = Uptime ratio        (w1=0.30) — was the node online?
  R = Packet reliability  (w2=0.35) — did packets get through?
  L = Latency score       (w3=0.20) — was it fast?
  E = Energy level        (w4=0.15) — how much battery remains?

DECAY FORMULA:
  TW(n,t) = TW(n,t-1) * exp(-k * dt) + bonus(n,t)
  Models natural staleness — old trust data should erode over time.
"""

import math
import random

# ── Constants ──────────────────────────────────────
W1 = 0.50   # Uptime weight
W2 = 0.25   # Packet reliability weight — highest, primary failure mode
W3 = 0.25   # Latency weight
W4 = 0.10   # Energy weight — lowest, predictive not current

K_DECAY     = 0.05    # Decay constant — how fast trust erodes without new data
MAX_LAT     = 200.0   # Maximum acceptable latency in ms
BATTERY_MAX = 100.0

# Trust zone thresholds
ZONE_AVOID   = 0.4
ZONE_TRUSTED = 0.7


def tw_initialise(nodes):
    """
    Algorithm 1: TW_INITIALISE

    WHY 0.5 as starting value?
      0.0 = ATRP avoids all nodes at start — network cannot route
      1.0 = ATRP over-trusts all nodes — same as blind Dijkstra
      0.5 = neutral Bayesian prior — no assumption made either way

    Returns all state dictionaries needed to track node behaviour.
    """
    tw       = {n: 0.5          for n in nodes}
    uptime   = {n: 0            for n in nodes}
    failures = {n: 0            for n in nodes}
    tx_count = {n: 0            for n in nodes}
    lat_sum  = {n: 0.0          for n in nodes}
    battery  = {n: BATTERY_MAX  for n in nodes}
    total_t  = {n: 1            for n in nodes}

    return tw, uptime, failures, tx_count, lat_sum, battery, total_t


def tw_update(n, event, tw, uptime, failures, tx_count,
              lat_sum, battery, total_t, dt=1, k=K_DECAY):
    """
    Algorithm 2: TW_UPDATE

    Called every simulation tick for every node.
    Two-stage process:
      Stage 1 — Apply temporal decay (trust erodes without fresh data)
      Stage 2 — Apply event-specific reward or penalty

    Events and their logic:
      'success'  — packet delivered successfully → small reward
      'failure'  — packet lost → multiplicative penalty (proportional impact)
      'silent'   — node not heard from → decay only, no reward
      'recover'  — node came back online → larger reward (significant signal)
      'batt_low' — battery under 10% → pre-emptive penalty (avoid before failure)
      'observe'  — full fresh observation → recompute TW from all 4 components
    """
    # Stage 1: Temporal decay
    tw_decayed = tw[n] * math.exp(-k * dt)

    # Stage 2: Event update
    if event == 'success':
        tw[n] = min(1.0, tw_decayed + 0.05)
        tx_count[n] += 1
        uptime[n]   += 1

    elif event == 'failure':
        tw[n] = tw_decayed * 0.70
        failures[n] += 1
        tx_count[n] += 1

    elif event == 'silent':
        tw[n] = tw_decayed

    elif event == 'recover':
        tw[n] = min(1.0, tw_decayed + 0.15)
        uptime[n] += 1

    elif event == 'batt_low':
        tw[n] = tw_decayed * 0.50
        battery[n] = max(1.0, battery[n] - random.uniform(5, 15))

    elif event == 'observe':
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

        tw[n] = W1*U + W2*R + W3*L + W4*E

    # Clamp to valid range
    tw[n] = max(0.01, min(1.0, tw[n]))
    return tw[n]


def get_zone(tw_val):
    """Return the trust zone label for a given TW value."""
    if tw_val < ZONE_AVOID:
        return 'AVOID'
    elif tw_val < ZONE_TRUSTED:
        return 'MONITOR'
    else:
        return 'TRUSTED'


def print_tw_state(n, tw_val, event, tick):
    """Pretty print TW state for demo and debugging."""
    zone  = get_zone(tw_val)
    bar   = '█' * int(tw_val * 20) + '░' * (20 - int(tw_val * 20))
    print(f"  t={tick:03d} | event={event:<10} | "
          f"TW={tw_val:.4f} | [{bar}] | {zone}")


if __name__ == '__main__':
    print("\n" + "="*60)
    print("  STEP 2: Trust Weight Formula — Live Demo")
    print("="*60)

    # Demo with a single node — watch TW evolve through events
    nodes = [0]
    tw, uptime, failures, tx_count, lat_sum, battery, total_t = tw_initialise(nodes)

    print(f"\n  Node 0 initialised → TW = {tw[0]} (neutral prior)\n")

    # Sequence of events that a real IoT node might experience
    event_sequence = [
        'observe',   # normal tick — fresh data
        'observe',   # normal tick
        'success',   # packet delivered
        'success',   # packet delivered
        'success',   # packet delivered
        'failure',   # packet lost — penalty applied
        'failure',   # another loss
        'silent',    # node goes quiet — decay only
        'silent',    # still silent
        'recover',   # node comes back
        'observe',   # fresh observation after recovery
        'batt_low',  # battery critical — pre-emptive penalty
        'observe',   # final state
    ]

    for tick, event in enumerate(event_sequence):
        tw_update(0, event, tw, uptime, failures,
                  tx_count, lat_sum, battery, total_t, dt=1)
        print_tw_state(0, tw[0], event, tick + 1)

    print(f"\n  Final TW = {tw[0]:.4f} | Zone = {get_zone(tw[0])}")
    print(f"  Battery remaining = {battery[0]:.1f}%")
    print(f"  Packets sent = {tx_count[0]} | Failures = {failures[0]}")
    print(f"  Uptime ticks = {uptime[0]} / {total_t[0]}")

    print("\n  trust.py — DONE\n")