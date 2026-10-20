"""An exact dynamic programme for week_milp's problem (prototype).

The state before a half-hour is each engine's on/off state with its minimum up or down counter
(10 per engine, 100 joint) and the store's level, a continuous state. For every half-hour and
engine on/off pattern, the least cost of the half-hour is an exact piecewise-linear function of the
store's net flow: one parametric LP per part-load segment and header mode, each a convex function
of the flow found exactly by the sandwich method, and their lower envelope. The value functions of
the store's level are exact piecewise-linear functions, kept as lists of convex runs (the pieces
between the envelope's concave kinks and jumps) and carried backwards by min-plus convolution.

Usage: python exact_dp.py DAYS [--base visible|h3] [--store small|large]
"""

from __future__ import annotations

import argparse
import itertools
import math
import time

import numpy as np
from scipy.optimize import linprog

import week_milp as W

EPS_X = 1e-9   # kWh: grid points closer than this are one point
EPS_Y = 1e-7   # GBP: values closer than this are equal
EPS_S = 1e-8   # GBP per kWh: a fall in slope smaller than this is rounding, not a concave kink
EPS_V = 1e-9   # GBP: a point within this of the chord of its neighbours is dropped


# ---------------------------------------------------------------- piecewise-linear functions
# A convex run is (x, y): x strictly increasing (one point allowed), y convex, linear between.
# A function is a list of convex runs; its value at x is the least value of the runs holding x.

def simplify(x, y):
    """Drop the points that lie on the chord of their neighbours (never two neighbours at once)."""
    while len(x) > 2:
        dev = y[1:-1] - (y[:-2] + (y[2:] - y[:-2]) * (x[1:-1] - x[:-2]) / (x[2:] - x[:-2]))
        idx = np.nonzero(np.abs(dev) <= EPS_V)[0]
        if len(idx) == 0:
            break
        first = np.concatenate([[True], np.diff(idx) > 1])
        idx = idx[(idx - idx[first][np.cumsum(first) - 1]) % 2 == 0]
        keep = np.ones(len(x), bool)
        keep[idx + 1] = False
        x, y = x[keep], y[keep]
    return x, y


def clip(run, lo, hi):
    x, y = run
    if x[-1] < lo - EPS_X or x[0] > hi + EPS_X:
        return None
    a, b = max(x[0], lo), min(x[-1], hi)
    if b - a <= EPS_X:
        m = min(max(0.5 * (a + b), x[0]), x[-1])
        return np.array([m]), np.array([np.interp(m, x, y)])
    xs = np.concatenate([[a], x[(x > a) & (x < b)], [b]])
    return xs, np.interp(xs, x, y)


def conv(f, v):
    """Min-plus convolution of two convex runs: z -> min over x of f(x) + v(z - x)."""
    fx, fy = f
    vx, vy = v
    lengths = np.concatenate([np.diff(fx), np.diff(vx)])
    if len(lengths) == 0:
        return np.array([fx[0] + vx[0]]), np.array([fy[0] + vy[0]])
    slopes = np.concatenate([np.diff(fy) / np.diff(fx) if len(fx) > 1 else [],
                             np.diff(vy) / np.diff(vx) if len(vx) > 1 else []])
    o = np.argsort(slopes, kind="stable")
    x0, y0 = fx[0] + vx[0], fy[0] + vy[0]
    x = np.concatenate([[x0], x0 + np.cumsum(lengths[o])])
    y = np.concatenate([[y0], y0 + np.cumsum(lengths[o] * slopes[o])])
    return simplify(x, y)


def snap(X):
    X = np.unique(X)
    if len(X) > 1:
        X = X[np.concatenate([[True], np.diff(X) > EPS_X])]
    return X


def table(runs, X):
    """Values of each run on the grid X (inf outside the run)."""
    Y = np.full((len(runs), len(X)), np.inf)
    for i, (x, y) in enumerate(runs):
        lo = np.searchsorted(X, x[0] - EPS_X)
        hi = np.searchsorted(X, x[-1] + EPS_X, side="right")
        if hi > lo:
            Y[i, lo:hi] = np.interp(X[lo:hi], x, y)
    return Y


def envelope(runs):
    """The lower envelope of a list of runs, as a list of maximal convex runs."""
    runs = [r for r in runs if r is not None]
    if len(runs) <= 1:
        return [simplify(*r) for r in runs]
    X = snap(np.concatenate([r[0] for r in runs]))
    for _ in range(100):
        Y = table(runs, X)
        if len(X) == 1:
            break
        cov = np.isfinite(Y[:, :-1]) & np.isfinite(Y[:, 1:])
        YL = np.where(cov, Y[:, :-1], np.inf)
        YR = np.where(cov, Y[:, 1:], np.inf)
        yl, yr = YL.min(0), YR.min(0)
        # the run lowest just right of the left end: lowest there, and of those the lowest at the right end
        aL = np.where(YL <= yl + EPS_Y, YR, np.inf).argmin(0)
        aR = YR.argmin(0)
        k = np.arange(len(X) - 1)
        bad = np.isfinite(yl) & (YR[aL, k] > yr + EPS_Y)
        if not bad.any():
            break
        k = k[bad]
        dl = YL[aL[k], k] - YL[aR[k], k]
        dr = YR[aL[k], k] - YR[aR[k], k]
        lam = np.clip(-dl / (dr - dl), 0.0, 1.0)
        X = snap(np.concatenate([X, X[k] + lam * (X[k + 1] - X[k])]))
    else:
        raise RuntimeError("envelope did not converge")
    P = Y.min(0)
    out = []
    if len(X) == 1:
        return [(X.copy(), P.copy())] if np.isfinite(P[0]) else []
    has = np.isfinite(yl)
    slope = np.where(has, (yr - yl) / np.diff(X), 0.0)
    cx, cy, cs = None, None, None
    for i in range(len(X) - 1):
        if not has[i]:
            if cx is not None:
                out.append((np.array(cx), np.array(cy)))
                cx = None
            continue
        if (cx is not None and cx[-1] == X[i] and abs(cy[-1] - yl[i]) <= EPS_Y
                and P[i] >= yl[i] - EPS_Y
                and (slope[i] >= cs - EPS_S or (cs - slope[i]) * min(X[i + 1] - X[i], cx[-1] - cx[-2]) <= EPS_V)):
            cx.append(X[i + 1]); cy.append(yr[i])
        else:
            if cx is not None:
                out.append((np.array(cx), np.array(cy)))
            cx, cy = [X[i], X[i + 1]], [yl[i], yr[i]]
        cs = slope[i]
    if cx is not None:
        out.append((np.array(cx), np.array(cy)))
    left = np.concatenate([[np.inf], np.where(has, yr, np.inf)])
    right = np.concatenate([np.where(has, yl, np.inf), [np.inf]])
    for i in np.nonzero(P < np.minimum(left, right) - EPS_Y)[0]:
        out.append((X[i:i + 1].copy(), P[i:i + 1].copy()))
    return [simplify(x, y) for x, y in out]


def value(runs, x):
    best = np.inf
    for rx, ry in runs:
        if rx[0] - EPS_X <= x <= rx[-1] + EPS_X:
            best = min(best, float(np.interp(x, rx, ry)))
    return best


def breakpoints(runs):
    return np.concatenate([r[0] for r in runs]) if runs else np.zeros(0)


# ---------------------------------------------------------------- the half-hour's LPs
class Stage:
    """The least cost of one half-hour, given which engines run, as a function of the store's
    net flow F (kW, > 0 charges), exactly as week_milp.build models the half-hour."""

    def __init__(self, base, h, store):
        self.base, self.h, self.kw = base, h, store["kw"]
        self.eng = base.engines
        self.boil = base.plant["boilers"]
        self.ecs = base.plant["electric_chillers"]
        self.ac = base.plant["absorption_chillers"][0]
        self.lp_calls = 0

    def combos(self, u):
        segs = [range(len(self.base.curve[e["id"]][0]) - 1) if on else [None] for on, e in zip(u, self.eng)]
        for s in itertools.product(*segs):
            for z in (0, 1):
                yield s, z

    def lp(self, t, segs, z, F=None, sense=0):
        """F given: least cost and its slope in F. F None: least (sense 1) or greatest (sense -1) F."""
        b, h = self.base, self.h
        gn, gas = b.gross_net, b.gas_rate
        c, el, ht, ab, cl, tw, lo, hi = [], [], [], [], [], [], [], []
        const = 0.0
        e_rhs = h["elec"][t] - h["pv"][t]
        h_rhs = h["heat"][t] + b.lthw_loss
        ab_rhs = 0.0
        for e, s in zip(self.eng, segs):
            if s is None:
                continue
            kw, fuel, heat = b.curve[e["id"]]
            ln = kw[s + 1] - kw[s]
            m = e["maintenance_gbp_per_mwhe"] / 1000.0
            hs = (heat[s + 1] - heat[s]) / ln
            c.append(W.DT_H * ((fuel[s + 1] - fuel[s]) / ln * gn * gas + m))
            el.append(1.0); ht.append(hs); ab.append(-hs); cl.append(0.0); tw.append(0.0)
            lo.append(0.0); hi.append(ln)
            const += W.DT_H * (fuel[s] * gn * gas + kw[s] * m)
            e_rhs -= kw[s] - e["auxiliary_kwe"]
            h_rhs -= heat[s]
            ab_rhs += heat[s]
        for bl in self.boil:
            c.append(W.DT_H * gas / bl["efficiency"])
            el.append(0.0); ht.append(1.0); ab.append(0.0); cl.append(0.0); tw.append(0.0)
            lo.append(0.0); hi.append(bl["max_kw"])
        for ch in self.ecs:
            cop = h["cop"][bool(z)][ch["id"]][t]
            c.append(0.0)
            el.append(-1.0 / cop); ht.append(0.0); ab.append(0.0); cl.append(1.0); tw.append(1.0 + 1.0 / cop)
            lo.append(0.0); hi.append(ch["max_kw"])
        ac = self.ac
        c.append(0.0)
        el.append(-ac["auxiliary_kwe_per_kw"]); ht.append(-1.0 / ac["cop"]); ab.append(1.0 / ac["cop"])
        cl.append(1.0); tw.append(1.0 + 1.0 / ac["cop"])
        lo.append(0.0); hi.append(ac["max_kw"] * z)
        c += [W.DT_H * h["rate"][t], -W.DT_H * b.export_rate]
        el += [1.0, -1.0]; ht += [0.0, 0.0]; ab += [0.0, 0.0]; cl += [0.0, 0.0]; tw += [0.0, 0.0]
        lo += [0.0, 0.0]
        hi += [math.sqrt(max(b.import_kva ** 2 - h["kvar"][t] ** 2, 0.0)), b.export_max]
        A_eq = [el, ht, cl]
        b_eq = [e_rhs, h_rhs, h["cool"][t]]
        A_ub = [ab, tw]
        b_ub = [ab_rhs, h["tower"][t]]
        self.lp_calls += 1
        if F is None:
            n = len(c)
            A_eq = [r + [0.0] for r in A_eq]
            A_eq[1][-1] = -1.0
            A_ub = [r + [0.0] for r in A_ub]
            obj = [0.0] * n + [float(sense)]
            r = linprog(obj, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                        bounds=list(zip(lo, hi)) + [(-self.kw, self.kw)], method="highs")
            return None if r.status != 0 else float(r.x[-1])
        b_eq[1] += F
        r = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=list(zip(lo, hi)), method="highs")
        if r.status != 0:
            raise RuntimeError(f"stage LP t={t} segs={segs} z={z} F={F}: {r.message}")
        return float(r.fun) + const, float(r.eqlin.marginals[1])

    def curve(self, t, segs, z):
        """The convex least cost in F of one segment and header choice, exactly (sandwich method)."""
        a = self.lp(t, segs, z, sense=1)
        if a is None:
            return None
        b = self.lp(t, segs, z, sense=-1)
        ga, sa = self.lp(t, segs, z, a)
        if b - a <= EPS_X:
            return np.array([a]), np.array([ga])
        gb, sb = self.lp(t, segs, z, b)
        pts = {a: ga, b: gb}
        stack = [(a, ga, sa, b, gb, sb)]
        while stack:
            a, ga, sa, b, gb, sb = stack.pop()
            if sb - sa <= EPS_S or b - a <= 1e-6:
                continue
            m = (gb - ga + sa * a - sb * b) / (sa - sb)
            if not (a + 1e-7 < m < b - 1e-7):
                continue
            gm, sm = self.lp(t, segs, z, m)
            pts[m] = gm
            if gm - (ga + sa * (m - a)) <= EPS_Y:
                continue
            stack.append((a, ga, sa, m, gm, sm))
            stack.append((m, gm, sm, b, gb, sb))
        x = np.array(sorted(pts))
        return simplify(x, np.array([pts[v] for v in x]))

    def cost_function(self, t, u):
        """Least cost of half-hour t with engines u, as a function of d = 0.5 h * F (kWh into the store)."""
        runs = []
        for segs, z in self.combos(u):
            r = self.curve(t, segs, z)
            if r is not None:
                runs.append((r[0] * W.DT_H, r[1]))
        return envelope(runs)


# ---------------------------------------------------------------- engine states
# per engine: 0..5 on for 1..6 half-hours (5: may stop), 6..9 off for 1..4 half-hours (9: may start)
ON_FREE, OFF_FREE = W.MIN_UP - 1, W.MIN_UP + W.MIN_DOWN - 1


def moves(k, t0):
    """(next state, started) for one engine. t0: the first half-hour, when a running engine that
    stops owes no minimum down time (week_milp counts down time only after a half-hour on)."""
    if k < ON_FREE:
        return [(k + 1, False)]
    if k == ON_FREE:
        return [(ON_FREE, False), (OFF_FREE if t0 else W.MIN_UP, False)]
    if k < OFF_FREE:
        return [(k + 1, False)]
    return [(OFF_FREE, False), (0, True)]


def is_on(k):
    return k <= ON_FREE


# ---------------------------------------------------------------- the DP
def solve(base, h, store, verbose=True):
    T = len(h["elec"])
    keep = (1 - W.LOSS_PER_H) ** W.DT_H
    cap, start = store["kwh"], store["kwh"] / 2
    st = Stage(base, h, store)
    eng = base.engines
    s0 = tuple(ON_FREE if e["id"] in base.running0 else OFF_FREE for e in eng)
    succ = {}
    reach = [{s0}]
    for t in range(T):
        nxt = set()
        for s in reach[t]:
            out = []
            for combo in itertools.product(*[moves(k, t == 0) for k in s]):
                s2 = tuple(m[0] for m in combo)
                sc = sum(e["start_cost_gbp"] for e, m in zip(eng, combo) if m[1])
                out.append((s2, sc))
                nxt.add(s2)
            succ[t, s] = out
        reach.append(nxt)
    t0 = time.perf_counter()
    G = {}
    for t in range(T):
        for u in itertools.product((False, True), repeat=len(eng)):
            if any(tuple(is_on(k) for k in s) == u for s in reach[t + 1]):
                G[t, u] = st.cost_function(t, u)
    t1 = time.perf_counter()
    if verbose:
        sizes = [len(r[0]) for g in G.values() for r in g]
        print(f"stage functions: {len(G)} in {t1 - t0:.1f}s, {st.lp_calls} LPs;"
              f" runs per function {np.mean([len(g) for g in G.values()]):.2f}, points per run {np.mean(sizes):.1f}",
              flush=True)
    V = {s: [(np.array([start, cap]), np.array([0.0, 0.0]))] for s in reach[T]}
    Vs = [None] * (T + 1)
    Vs[T] = V
    stats = []
    for t in range(T - 1, -1, -1):
        tt = time.perf_counter()
        Wf = {}
        zhi = keep * cap
        for s2, v in V.items():
            g = G.get((t, tuple(is_on(k) for k in s2)), [])
            pairs = []
            for gr in g:
                f = (-gr[0][::-1], gr[1][::-1])
                for vr in v:
                    pairs.append(clip(conv(f, vr), 0.0, zhi))
            Wf[s2] = envelope(pairs)
        Vn = {}
        for s in reach[t]:
            cands = []
            for s2, sc in succ[t, s]:
                for x, y in Wf.get(s2, []):
                    cands.append(clip((x / keep, y + sc), 0.0, cap))
            Vn[s] = envelope(cands)
        V = Vn
        Vs[t] = V
        stats.append((t, max(len(v) for v in V.values()), max(sum(len(r[0]) for r in v) for v in V.values())))
        if verbose > 1:
            print(f"  t={t:3d} runs {stats[-1][1]:4d} points {stats[-1][2]:5d} {time.perf_counter() - tt:6.2f}s", flush=True)
    t2 = time.perf_counter()
    best = value(V[s0], start)
    if verbose:
        print(f"DP: {t2 - t1:.1f}s; largest value function: {max(s[1] for s in stats)} runs,"
              f" {max(s[2] for s in stats)} points; least cost {best:.4f}", flush=True)
    # forward pass: the plan
    plan, s, lev, total = [], s0, start, 0.0
    for t in range(T):
        z = keep * lev
        choice = None
        for s2, sc in succ[t, s]:
            g = G.get((t, tuple(is_on(k) for k in s2)), [])
            v = Vs[t + 1].get(s2, [])
            if not g or not v:
                continue
            ds = np.concatenate([breakpoints(g), breakpoints(v) - z])
            for d in np.unique(ds):
                y = z + d
                if y < -EPS_X or y > cap + EPS_X:
                    continue
                c1, c2 = value(g, d), value(v, y)
                if c1 + c2 + sc < (choice[0] if choice else np.inf):
                    choice = (c1 + c2 + sc, s2, d, c1 + sc)
        _, s, d, stage_cost = choice
        lev = z + d
        total += stage_cost
        plan.append((tuple(is_on(k) for k in s), d / W.DT_H, lev))
    return best, total, plan, (t1 - t0, t2 - t1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("days", type=int)
    ap.add_argument("--base", default="visible")
    ap.add_argument("--store", default="large")
    a = ap.parse_args()
    store = W.STORES[a.store]
    W.STORE.clear()
    W.STORE.update(store)
    base, h = W.horizon(a.days, base_name=a.base)
    best, total, plan, times = solve(base, h, store)
    print(f"EXACT days={a.days} base={a.base} store={a.store} least_cost={best:.4f}"
          f" plan_cost={total:.4f} stage={times[0]:.1f}s dp={times[1]:.1f}s", flush=True)


if __name__ == "__main__":
    main()
