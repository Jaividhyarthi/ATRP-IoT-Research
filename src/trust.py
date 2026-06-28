"""
trust.py — Trust Weight Formula + Decay Update
ATRP Research | Jai Vidhyarthi | Synthara | 2026

WHY THIS FILE:
This is the mathematical core of ATRP.
Standard routing sees all nodes as equal — only distance matters.
ATRP assigns every node a Trust Weight (TW) between 0.0 and 1.0
based on FIVE observable behavioural signals.

UPDATED PRIMARY FORMULA (v2 — with ETX component):
  TW(n,t) = w1*U(n,t) + w2*R(n,t) + w3*L(n,t) + w4*E(n,t) + w5*X(n,t)

  U = Uptime ratio        (w1=0.25) — was the node online?
  R = Packet reliability  (w2=0.25) — did packets get through?
  L = Latency score       (w3=0.15) — was it fast?
  E = Energy level        (w4=0.10) — how much battery remains?
  X = ETX score           (w5=0.25) — link quality (absorbs RPL's strength)

WHY ETX AS 5TH COMPONENT:
  RPL (IoT standard) uses ETX as its primary routing metric.
  By absorbing ETX into TW, ATRP becomes a superset of RPL —
  everything RPL does plus uptime, battery, and temporal decay.
  ETX_score = 1 - (etx(n) / max_etx) — normalised to [0,1]
  ETX=1.0 (perfect link) → X=0.9+ (high score)
  ETX=5.0 (terrible link) → X=0.0 (low score)

DECAY FORMULA (unchanged):
  TW(n,t) = TW(n,t-1) * exp(-k * dt) + bonus(n,t)
"""

import math
import random

# ── Weight Constants (v2) ───────────────────────────
W1 = 0.25   # Uptime
W2 = 0.25   # Packet reliability
W3 = 0.15   # Latency
W4 = 0.10   # Energy
W5 = 0.25   # ETX link quality — new component

# Verify weights sum to 1.0
assert round(W1 + W2 + W3 + W4 + W5, 10) == 1.0, "Weights must sum to 1.0"

K_DECAY     = 0.05
MAX_LAT     = 200.0
BATTERY_MAX = 100.0
MAX_ETX     = 5.0    # maximum ETX value in network (normalisation ceiling)

# Trust zone thresholds
ZONE_AVOID   = 0.4
ZONE_TRUSTED = 0.7


def tw_initialise(nodes):
    """
    Algorithm 1: TW_INITIALISE
    All nodes start at TW=0.5 — neutral Bayesian prior.
    ETX initialised at 1.0 — assume perfect link until observed otherwise.
    """
    tw       = {n: 0.5         for n in nodes}
    uptime   = {n: 0           for n in nodes}
    failures = {n: 0           for n in nodes}
    tx_count = {n: 0           for n in nodes}
    lat_sum  = {n: 0.0         for n in nodes}
    battery  = {n: BATTERY_MAX for n in nodes}
    total_t  = {n: 1           for n in nodes}
    etx      = {n: 1.0         for n in nodes}

    return tw, uptime, failures, tx_count, lat_sum, battery, total_t, etx


def tw_update(n, event, tw, uptime, failures, tx_count,
              lat_sum, battery, total_t, etx=None, dt=1, k=K_DECAY):
    """
    Algorithm 2: TW_UPDATE

    Stage 1 — Temporal decay
    Stage 2 — Event-specific update
    Stage 3 — Full recomputation from 5 components when fresh data available
    """
    if etx is None:
        etx = {}

    # Stage 1: Temporal decay
    tw_decayed = tw[n] * math.exp(-k * dt)

    # Stage 2: Event update
    if event == 'success':
        tw[n] = min(1.0, tw_decayed + 0.05)
        tx_count[n] += 1
        uptime[n]   += 1
        # Good delivery = ETX improves slightly
        if n in etx:
            etx[n] = max(1.0, etx[n] * 0.95)

    elif event == 'failure':
        tw[n] = tw_decayed * 0.70
        failures[n] += 1
        tx_count[n] += 1
        # Packet loss = ETX worsens
        if n in etx:
            etx[n] = min(MAX_ETX, etx[n] * 1.2)

    elif event == 'silent':
        tw[n] = tw_decayed

    elif event == 'recover':
        tw[n] = min(1.0, tw_decayed + 0.15)
        uptime[n] += 1
        if n in etx:
            etx[n] = max(1.0, etx[n] * 0.80)

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

        # Update ETX based on recent packet success rate
        loss_rate = failures[n] / max(1, tx_count[n])
        if loss_rate > 0:
            if n in etx:
                etx[n] = min(MAX_ETX, 1.0 / max(0.01, 1 - loss_rate))
        else:
            if n in etx:
                etx[n] = max(1.0, etx[n] * 0.98)

        # Compute all 5 components
        U = uptime[n]  / max(1, total_t[n])
        R = 1 - (failures[n] / max(1, tx_count[n]))
        L = 1 - ((lat_sum[n] / max(1, tx_count[n])) / MAX_LAT)
        E = battery[n] / BATTERY_MAX
        X = 1 - (etx.get(n, 1.0) / MAX_ETX)

        tw[n] = W1*U + W2*R + W3*L + W4*E + W5*X

    # Stage 3: Clamp
    tw[n] = max(0.01, min(1.0, tw[n]))
    return tw[n]


def get_zone(tw_val):
    if tw_val < ZONE_AVOID:     return 'AVOID'
    elif tw_val < ZONE_TRUSTED: return 'MONITOR'
    else:                       return 'TRUSTED'


def print_tw_state(n, tw_val, event, tick):
    zone = get_zone(tw_val)
    bar  = '█' * int(tw_val * 20) + '░' * (20 - int(tw_val * 20))
    print(f"  t={tick:03d} | event={event:<10} | "
          f"TW={tw_val:.4f} | [{bar}] | {zone}")


if __name__ == '__main__':
    print("\n" + "="*60)
    print("  TRUST v2 — 5-Component TW Formula Demo")
    print("="*60)
    print(f"\n  Weights: U={W1} R={W2} L={W3} E={W4} ETX={W5}")
    print(f"  Sum = {W1+W2+W3+W4+W5} (must be 1.0)")

    nodes = [0]
    tw, uptime, failures, tx_count, lat_sum, battery, total_t, etx = tw_initialise(nodes)

    print(f"\n  Node 0 init → TW={tw[0]} | ETX={etx[0]}\n")

    sequence = [
        'observe','observe','success','success',
        'failure','failure','silent','recover',
        'observe','batt_low','observe'
    ]

    for tick, event in enumerate(sequence):
        tw_update(0, event, tw, uptime, failures,
                  tx_count, lat_sum, battery, total_t, etx, dt=1)
        print_tw_state(0, tw[0], event, tick+1)
        print(f"         ETX={etx[0]:.3f}")

    print(f"\n  Final TW={tw[0]:.4f} | Zone={get_zone(tw[0])}")
    print(f"  Final ETX={etx[0]:.3f}")
    print("\n  trust.py v2 -- DONE\n")