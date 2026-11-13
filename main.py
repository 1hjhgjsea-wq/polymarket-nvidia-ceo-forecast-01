#!/usr/bin/env python3
"""Quantile forecaster for Polymarket's "Next CEO of NVIDIA?" 4-hour price paths.

Conditional empirical quantiles of the h-minute move, estimated per market over the
trailing 18 hours, scaled by the ratio of short-run to day-long volatility (volatility
clusters: a quiet half hour followed by a jump is what the plain empirical window misses),
plus a mild pull back to the trailing median (prices are bounded and mean-reverting) and
a small shrink of the 5%/95% tails, whose empirical estimates are the noisiest.

Standard library only, deterministic, ~0.3 s per case.
"""
import json
import math
import os
import sys

QS = [0.05, 0.25, 0.5, 0.75, 0.95]
H = 240
HGRID = [1, 2, 3, 4, 6, 8, 11, 15, 20, 27, 36, 48, 64, 85, 110, 140, 175, 210, 240]
STRIDE = 3
WINDOW = 1080        # trailing minutes the quantile grid is estimated on
VOL_SHORT = 60       # short volatility lookback
VOL_LONG = 1440      # long volatility lookback
VOL_EXP = 0.4        # how hard to lean on the short/long ratio
VOL_MIN, VOL_MAX = 0.5, 2.0
OU = 0.15            # pull toward the trailing median, in half-squares of the horizon
TS = (0.85, 0.9, 1.0, 0.9, 0.85)
SIG_DEFAULT = 0.0025  # hourly sigma for a market too short to estimate one
SIG_MIN, SIG_MAX = 0.0008, 0.02
Z = (-1.6448536269514729, -0.6744897501960817, 0.0, 0.6744897501960817, 1.6448536269514729)


def quant(vals, q):
    n = len(vals)
    if n == 1:
        return vals[0]
    pos = q * (n - 1)
    lo = int(pos)
    hi = lo + 1 if lo + 1 < n else lo
    return vals[lo] + (vals[hi] - vals[lo]) * (pos - lo)


def rms(seg, w):
    d = [abs(seg[i] - seg[i - 1]) for i in range(max(1, len(seg) - w), len(seg))]
    return math.sqrt(sum(v * v for v in d) / len(d)) if d else 0.0


def cross_sigma(markets):
    """Median hourly sigma of the case's markets, for the ones too short to fit."""
    vals = sorted(v for v in (rms(m['prices'], VOL_SHORT) for m in markets) if v > 0)
    if not vals:
        return SIG_DEFAULT
    return min(SIG_MAX, max(SIG_MIN, vals[len(vals) // 2] * math.sqrt(60)))


def grid_of(seg):
    n = len(seg)
    g = []
    for h in HGRID:
        if n - h < 30:
            continue
        ds = sorted(seg[t + h] - seg[t] for t in range(0, n - h, STRIDE))
        g.append((h, [quant(ds, t) for t in QS]))
    return g


def interp(g, h):
    if h <= g[0][0]:
        return g[0][1][:]
    for i in range(len(g) - 1):
        h0, q0 = g[i]
        h1, q1 = g[i + 1]
        if h <= h1:
            w = (math.log(h) - math.log(h0)) / (math.log(h1) - math.log(h0))
            return [a + (b - a) * w for a, b in zip(q0, q1)]
    return g[-1][1][:]


def forecast(prices, sig=SIG_DEFAULT):
    x = prices[-1]
    seg = prices[-WINDOW:] if len(prices) > WINDOW else prices
    g = grid_of(seg)
    k = 1.0
    if len(g) >= 2:
        a, b = rms(prices, VOL_SHORT), rms(prices, VOL_LONG)
        if a > 0 and b > 0:
            k = min(VOL_MAX, max(VOL_MIN, (a / b) ** VOL_EXP))
    mu = quant(sorted(prices[-VOL_LONG:]), 0.5)
    rows = []
    for h in range(1, H + 1):
        if len(g) < 2:
            d = [z * sig * math.sqrt(h) for z in Z]
        else:
            d = [v * k for v in interp(g, h)]
            if OU:
                pull = OU * (mu - x) * math.sqrt(h / H)
                d = [v + pull for v in d]
            d = [v * t for v, t in zip(d, TS)]
        row = []
        prev = 0.0
        for v in d:
            qv = min(1.0, max(0.0, x + v))
            if qv < prev:
                qv = prev
            row.append(round(qv, 6))
            prev = qv
        rows.append(row)
    return rows


def main():
    ind = os.environ.get('MAKEFUN_INPUT_DIR') or '/input/'
    outd = os.environ.get('MAKEFUN_OUTPUT_DIR') or '/output/'
    for name in sorted(os.listdir(ind)):
        if not name.endswith('.in'):
            continue
        with open(os.path.join(ind, name), 'r', encoding='utf-8') as f:
            case = json.load(f)
        sig = cross_sigma(case['markets'])
        forecasts = [{'id': m['id'], 'q': forecast(m['prices'], sig)} for m in case['markets']]
        os.makedirs(outd, exist_ok=True)
        with open(os.path.join(outd, name[:-3] + '.out'), 'w', encoding='utf-8') as f:
            json.dump({'forecasts': forecasts}, f, separators=(',', ':'))


if __name__ == '__main__':
    main()
