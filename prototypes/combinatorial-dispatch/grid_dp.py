"""The careful approximate method an expert might try first (prototype): a DP over the engines'
states and the store's level on a grid, with the exact half-hour costs at each grid move, then a
polish of its engine schedule (HiGHS on the whole horizon with the engines' on/off fixed).
Optionally, rounds of refinement: the same DP on a fine grid in a corridor around the last
polished plan's store levels, and a polish of its schedule.

Usage: python grid_dp.py DAYS [--base visible|h3] [--store small|large] [--step 10 5]
       python grid_dp.py DAYS --step 10 --refine 30 1 --rounds 2
"""

from __future__ import annotations

import argparse
import itertools
import time

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

import exact_dp as X
import week_milp as W


def evaluate(runs, d):
    out = np.full(d.shape, np.inf)
    for x, y in runs:
        inside = (d >= x[0] - X.EPS_X) & (d <= x[-1] + X.EPS_X)
        if inside.any():
            out[inside] = np.minimum(out[inside], np.interp(d[inside], x, y))
    return out


def setup(base, h, store):
    T = len(h["elec"])
    eng = base.engines
    s0 = tuple(X.ON_FREE if e["id"] in base.running0 else X.OFF_FREE for e in eng)
    succ, reach = {}, [{s0}]
    for t in range(T):
        nxt = set()
        for s in reach[t]:
            out = []
            for combo in itertools.product(*[X.moves(k, t == 0) for k in s]):
                s2 = tuple(m[0] for m in combo)
                out.append((s2, sum(e["start_cost_gbp"] for e, m in zip(eng, combo) if m[1])))
                nxt.add(s2)
            succ[t, s] = out
        reach.append(nxt)
    st = X.Stage(base, h, store)
    G = {}
    for t in range(T):
        for u in itertools.product((False, True), repeat=len(eng)):
            if any(tuple(X.is_on(k) for k in s) == u for s in reach[t + 1]):
                G[t, u] = st.cost_function(t, u)
    return s0, succ, reach, G


def schedule(h, store, levels, s0, succ, reach, G):
    """DP over the engines' states and the store levels levels[t] (levels[0]: the start level;
    levels[t + 1]: the level after half-hour t). Returns its cost, the engines' on/off and the levels."""
    T = len(h["elec"])
    keep = (1 - W.LOSS_PER_H) ** W.DT_H
    start = store["kwh"] / 2
    V = {s: np.where(levels[T] >= start - 1e-9, 0.0, np.inf) for s in reach[T]}
    arg = {}
    for t in range(T - 1, -1, -1):
        D = levels[t + 1][None, :] - keep * levels[t][:, None]
        n = len(levels[t])
        Gm = {u: evaluate(g, D) for (tt, u), g in G.items() if tt == t}
        M = {}
        for s2, v in V.items():
            u = tuple(X.is_on(k) for k in s2)
            if u not in Gm:
                continue
            tot = Gm[u] + v[None, :]
            j = tot.argmin(1)
            M[s2] = (tot[np.arange(n), j], j)
        Vn = {}
        for s in reach[t]:
            opts = [(s2, sc) for s2, sc in succ[t, s] if s2 in M]
            if not opts:
                continue
            vals = np.array([M[s2][0] + sc for s2, sc in opts])
            k = vals.argmin(0)
            Vn[s] = vals[k, np.arange(n)]
            arg[t, s] = ([o[0] for o in opts], k, np.array([M[o[0]][1] for o in opts]))
        V = Vn
    cost = V[s0][0]
    s, i, U, L = s0, 0, [], []
    for t in range(T):
        names2, k, js = arg[t, s]
        s, i = names2[k[i]], js[k[i], i]
        U.append(tuple(X.is_on(q) for q in s))
        L.append(levels[t + 1][i])
    return cost, U, np.array(L)


def polish(base, h, U, limit):
    """HiGHS on the whole horizon with the engines' on/off fixed: cost, gap and the store levels."""
    T = len(h["elec"])
    eng = base.engines
    c, A, rlo, rhi, lo, hi, integ = W.build(base, h)
    nv = len(c) // T
    lo, hi = lo.copy(), hi.copy()
    names = []
    for g, e in enumerate(eng):
        nseg = len(e["part_load"]) - 1
        names += [f"U{g}", f"S{g}"] + [f"D{g}_{q}" for q in range(nseg)] + [f"W{g}_{q}" for q in range(1, nseg)]
    for t in range(T):
        for g in range(len(eng)):
            k = t * nv + names.index(f"U{g}")
            lo[k] = hi[k] = float(U[t][g])
    r = milp(c, constraints=LinearConstraint(A, rlo, rhi), integrality=integ, bounds=Bounds(lo, hi),
             options={"mip_rel_gap": 1e-9, "time_limit": limit})
    return float(r.fun), float(r.mip_gap), r.x[nv - 1::nv]  # L is the last variable of each half-hour


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("days", type=int)
    ap.add_argument("--base", default="visible")
    ap.add_argument("--store", default="large")
    ap.add_argument("--step", type=float, nargs="+", default=[50.0])
    ap.add_argument("--refine", type=float, nargs=2, default=None, metavar=("HALF_WIDTH", "STEP"))
    ap.add_argument("--rounds", type=int, default=1)
    ap.add_argument("--polish", type=float, default=60.0, help="time limit of each polish, s")
    a = ap.parse_args()
    store = W.STORES[a.store]
    W.STORE.clear()
    W.STORE.update(store)
    base, h = W.horizon(a.days, base_name=a.base)
    T = len(h["elec"])
    cap, start = store["kwh"], store["kwh"] / 2
    t0 = time.perf_counter()
    s0, succ, reach, G = setup(base, h, store)
    print(f"stage functions {time.perf_counter() - t0:.1f}s", flush=True)
    for step in a.step:
        t1 = time.perf_counter()
        lev = np.arange(0.0, cap + 1e-9, step)
        levels = [np.array([start])] + [lev] * T
        cost, U, L = schedule(h, store, levels, s0, succ, reach, G)
        t2 = time.perf_counter()
        best, gap, L = polish(base, h, U, a.polish)
        t3 = time.perf_counter()
        print(f"GRID step={step} levels={len(lev)} dp={t2 - t1:.1f}s polish={t3 - t2:.1f}s"
              f" grid_cost={cost:.4f} polished={best:.4f} (polish gap {gap:.1e})", flush=True)
        if a.refine:
            w, d = a.refine
            for rnd in range(a.rounds):
                t1 = time.perf_counter()
                levels = [np.array([start])]
                for t in range(T):
                    lv = np.arange(np.floor((L[t] - w) / d) * d, L[t] + w + d / 2, d)
                    lv = lv[(lv >= 0) & (lv <= cap)]
                    if t == T - 1:
                        lv = np.unique(np.concatenate([lv[lv >= start], [start]]))
                    levels.append(lv)
                cost, U, _ = schedule(h, store, levels, s0, succ, reach, G)
                t2 = time.perf_counter()
                best, gap, L = polish(base, h, U, a.polish)
                t3 = time.perf_counter()
                print(f"  refine {rnd + 1}: corridor +-{w} step {d} dp={t2 - t1:.1f}s polish={t3 - t2:.1f}s"
                      f" grid_cost={cost:.4f} polished={best:.4f} (polish gap {gap:.1e})", flush=True)


if __name__ == "__main__":
    main()
