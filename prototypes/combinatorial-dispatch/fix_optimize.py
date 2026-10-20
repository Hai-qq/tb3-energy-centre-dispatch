"""The careful generic baseline the review asked for: a MIP heuristic anyone fluent in MILP would
write, without any insight specific to the store. (prototype)

1. HiGHS on the whole horizon for a short time gives a first plan.
2. Fix-and-optimise: a window of days slides over the horizon; every binary outside it is fixed
   to the current plan and HiGHS re-solves the window's binaries (with all continuous variables of
   the whole horizon free, so the store can still move heat across the window's edges). A better
   plan replaces the current one; passes repeat until the time budget runs out.

Usage: python fix_optimize.py DAYS [--base visible|h3] [--store small|large] [--budget 120]
"""

from __future__ import annotations

import argparse
import time

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

import week_milp as W


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("days", type=int)
    ap.add_argument("--base", default="visible")
    ap.add_argument("--store", default="large")
    ap.add_argument("--budget", type=float, default=120.0)
    ap.add_argument("--first", type=float, default=20.0, help="seconds for the first whole-horizon solve")
    ap.add_argument("--window", type=int, default=2, help="days per window")
    a = ap.parse_args()
    W.STORE.clear()
    W.STORE.update(W.STORES[a.store])
    base, h = W.horizon(a.days, base_name=a.base)
    c, A, rlo, rhi, lo, hi, integ = W.build(base, h)
    T = len(h["elec"])
    nv = len(c) // T
    period = np.arange(len(c)) // nv
    cons = LinearConstraint(A, rlo, rhi)
    t0 = time.perf_counter()
    first = milp(c, constraints=cons, integrality=integ, bounds=Bounds(lo, hi),
                 options={"mip_rel_gap": 1e-4, "time_limit": a.first})
    x = first.x
    best = float(first.fun)
    trail = [(time.perf_counter() - t0, best)]
    binary = integ > 0
    starts = list(range(0, max(a.days - a.window, 0) + 1)) or [0]
    while time.perf_counter() - t0 < a.budget:
        improved = False
        for d in starts:
            left = a.budget - (time.perf_counter() - t0)
            if left <= 1:
                break
            inside = (period >= 48 * d) & (period < 48 * (d + a.window))
            fix = binary & ~inside
            lo2, hi2 = lo.copy(), hi.copy()
            lo2[fix] = hi2[fix] = np.round(x[fix])
            r = milp(c, constraints=cons, integrality=integ, bounds=Bounds(lo2, hi2),
                     options={"mip_rel_gap": 1e-6, "time_limit": min(left, 60.0)})
            if r.x is not None and r.fun < best - 1e-6:
                best, x = float(r.fun), r.x
                improved = True
            trail.append((time.perf_counter() - t0, best))
        if not improved:
            break
    print(f"FIXOPT days={a.days} base={a.base} store={a.store} best={best:.2f} after {trail[-1][0]:.1f}s;"
          f" first plan {trail[0][1]:.2f} at {trail[0][0]:.1f}s; trail " +
          " ".join(f"{t:.0f}s:{v:.2f}" for t, v in trail), flush=True)


if __name__ == "__main__":
    main()
