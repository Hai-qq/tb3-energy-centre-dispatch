"""Option A falsification test: does structure give a large, stable speed-up over a well-optimised
generic approach when one plant model is solved for a batch of scenarios? (prototype)

Scenarios: the visible day of the current task (v12) with its demand and PV perturbed half-hour by
half-hour (a forecast ensemble). Per scenario the solution plans the day with 768 small LPs (each
half-hour x engine combination x part-load piece x header mode) and a DP over the day.

Methods, all required to give the same least cost per scenario:
  naive      the solution's plan_day, one scenario after another
  batched    the same LPs, built once per slot and stacked into one sparse block LP per scenario
  structured an LP's matrix and costs do not change between scenarios, only its right-hand sides
             and bounds, so the optimal active set of one scenario is tried on all of them at once
             (one least-squares solve per slot for the whole batch); a scenario whose solution
             breaks a constraint falls back to HiGHS

Usage: python experiment.py [n_scenarios]
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import block_diag, csr_matrix

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "tasks" / "energy-centre-dispatch" / "solution" / "app"
DAY = ROOT / "tasks" / "energy-centre-dispatch" / "tests" / "days" / "visible"
sys.path.insert(0, str(APP))
from planner import optimize as O  # noqa: E402
from planner.data import load_day  # noqa: E402
from planner.plant import Plant  # noqa: E402
from planner.tariff import Tariff  # noqa: E402

TOL = 1e-6


def scenarios(day, n, seed=7):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        d = load_day(DAY)
        d.elec = day.elec * (1 + 0.04 * rng.standard_normal(48))
        d.kvar = day.kvar * d.elec / day.elec
        d.heat = day.heat * (1 + 0.08 * rng.standard_normal(48))
        d.cool = day.cool * (1 + 0.08 * rng.standard_normal(48))
        d.pv = day.pv * rng.uniform(0.7, 1.1, 48)
        out.append(d)
    return out


# ---------------------------------------------------------------- capture the LPs of a scenario
class Captured:
    status = 2
    fun = math.inf
    x = None


def capture(day, plant, tariff):
    """Every LP plan_day would solve, in its order: (key, c, A_ub, b_ub, A_eq, b_eq, bounds, const)."""
    lps = []
    real = O.linprog

    def fake(c, A_ub=None, b_ub=None, A_eq=None, b_eq=None, bounds=None, method=None):
        lps.append([np.asarray(c, float), np.asarray(A_ub, float), np.asarray(b_ub, float),
                    np.asarray(A_eq, float), np.asarray(b_eq, float), np.asarray(bounds, float)])
        return Captured()

    O.linprog = fake
    real_period = O._period
    consts = []

    def period(*a, **k):
        n0 = len(lps)
        value, out = real_period(*a, **k)
        consts.append((n0, a[3], a[4], a[5]))  # LP index, t, seg, absorbing
        return value, out

    O._period = period
    try:
        O.plan_day.__wrapped__ if hasattr(O.plan_day, "__wrapped__") else None
        try:
            O.plan_day(day, plant, tariff)
        except RuntimeError:
            pass  # every LP "failed": the DP finds nothing, which is fine for capturing
    finally:
        O.linprog = real
        O._period = real_period
    return lps, consts


def const_of(day, plant, tariff, t, seg):
    """The constant _period adds to the LP's value: the engines' fuel at zero output."""
    gas = tariff.gas_rate
    total = 0.0
    for e, s in zip(plant.engines, seg):
        if s is not None:
            f0 = e.segments()[s][2]
            total += O.DT_H * tariff.billed_gas(f0, e.fuel_basis) * gas
    return total


def dp(day, plant, costs):
    """costs[t][k]: cheapest cost of combination k in period t; returns the day's least cost."""
    import itertools
    combos = list(itertools.product((False, True), repeat=len(plant.engines)))

    def starts(prev, on):
        return sum(e.start_cost for e, a, b in zip(plant.engines, prev, on) if b and not a)

    running = set(day.status.get("running_at_midnight", []))
    initial = tuple(e.id in running for e in plant.engines)
    best = np.array([costs[0][k] + starts(initial, on) for k, on in enumerate(combos)])
    for t in range(1, 48):
        best = np.array([min(best[j] + starts(p, on) for j, p in enumerate(combos)) + costs[t][k]
                         for k, on in enumerate(combos)])
    return float(best.min())


def slot_costs(day, plant, tariff, values, consts):
    """Fold LP values into costs[t][k] the way plan_day does."""
    import itertools
    combos = list(itertools.product((False, True), repeat=len(plant.engines)))
    costs = [[math.inf] * len(combos) for _ in range(48)]
    for (i, t, seg, _absorbing), v in zip(consts, values):
        on = tuple(s is not None for s in seg)
        k = combos.index(on)
        c = v + const_of(day, plant, tariff, t, seg)
        if c < costs[t][k]:
            costs[t][k] = c
    return costs


# ---------------------------------------------------------------- the three methods
def naive(days, plant, tariff):
    out = []
    for d in days:
        periods, _ = O.plan_day(d, plant, tariff)
        out.append(sum(p["cost_gbp"] for p in periods))
    return out


def solve_one(lp):
    c, A_ub, b_ub, A_eq, b_eq, bounds = lp
    r = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")
    return (r.fun if r.status == 0 else math.inf), r


PENALTY = 1e5  # GBP per kW of slack: far above any real cost, so slack only where an LP is infeasible


def elastic(lp):
    """The LP with a penalised slack on each equality row (both ways) and on each inequality row
    but the kVA tangents, so that it is always feasible; an LP is infeasible iff its slack is used."""
    c, A_ub, b_ub, A_eq, b_eq, bounds = lp
    nv, m_eq, m_ub = len(c), len(b_eq), len(b_ub)
    soft = [i for i in range(m_ub) if i < m_ub - len(O._ANGLES)]  # the rows before the kVA tangents
    n_new = 2 * m_eq + len(soft)
    c2 = np.concatenate([c, np.full(n_new, PENALTY)])
    A_eq2 = np.hstack([A_eq, np.eye(m_eq), -np.eye(m_eq), np.zeros((m_eq, len(soft)))])
    S = np.zeros((m_ub, len(soft)))
    for k, i in enumerate(soft):
        S[i, k] = -1.0
    A_ub2 = np.hstack([A_ub, np.zeros((m_ub, 2 * m_eq)), S])
    bounds2 = np.vstack([bounds, np.tile([0.0, np.inf], (n_new, 1))])
    return c2, A_ub2, b_ub, A_eq2, b_eq, bounds2, nv


def batched(day0, plant, tariff, captured):
    """All of a scenario's LPs, made elastic, stacked into one sparse block LP and solved at once."""
    out = []
    for d, (lps, consts) in captured:
        blocks = [elastic(lp) for lp in lps]
        c = np.concatenate([b[0] for b in blocks])
        A_ub = block_diag([csr_matrix(b[1]) for b in blocks], format="csr")
        b_ub = np.concatenate([b[2] for b in blocks])
        A_eq = block_diag([csr_matrix(b[3]) for b in blocks], format="csr")
        b_eq = np.concatenate([b[4] for b in blocks])
        bounds = np.vstack([b[5] for b in blocks])
        r = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")
        assert r.status == 0, r.message
        values, pos = [], 0
        for b, lp in zip(blocks, lps):
            n2, nv = len(b[0]), b[6]
            x = r.x[pos:pos + n2]
            values.append(math.inf if x[nv:].max(initial=0.0) > 1e-6 else float(lp[0] @ x[:nv]))
            pos += n2
        out.append(dp(d, plant, slot_costs(d, plant, tariff, values, consts)))
    return out


def structured(plant, tariff, captured):
    """Active-set reuse across the whole batch, slot by slot, with HiGHS as the fallback."""
    n_s = len(captured)

    def lp(si, j):
        return captured[si][1][0][j]

    n_lp = len(captured[0][1][0])
    values = np.full((n_s, n_lp), math.inf)
    fallbacks = 0
    for j in range(n_lp):
        c, A_ub, _, A_eq, _, _ = lp(0, j)
        nv = len(c)
        B_ub = np.array([lp(si, j)[2] for si in range(n_s)])  # (n_s, m_ub)
        B_eq = np.array([lp(si, j)[4] for si in range(n_s)])
        LO = np.array([lp(si, j)[5][:, 0] for si in range(n_s)])
        HI = np.array([lp(si, j)[5][:, 1] for si in range(n_s)])
        todo = np.arange(n_s)
        tried = 0
        while len(todo) and tried < 4:
            # solve one pending scenario with HiGHS and take its active set
            s0 = todo[0]
            v, r = solve_one(lp(s0, j))
            fallbacks += 1
            if r.status != 0:
                todo = todo[1:]
                continue
            values[s0, j] = v
            x = r.x
            act_ub = np.where(np.abs(A_ub @ x - B_ub[s0]) < 1e-7)[0]
            at_lo = np.where(np.abs(x - LO[s0]) < 1e-9)[0]
            at_hi = np.where(np.abs(x - HI[s0]) < 1e-9)[0]
            rows = [A_eq, A_ub[act_ub], np.eye(nv)[at_lo], np.eye(nv)[at_hi]]
            M = np.vstack(rows)
            rest = todo[1:]
            if len(rest) == 0:
                todo = rest
                break
            R = np.hstack([B_eq[rest], B_ub[rest][:, act_ub], LO[rest][:, at_lo], HI[rest][:, at_hi]])
            X, *_ = np.linalg.lstsq(M, R.T, rcond=None)  # (nv, n_rest)
            X = X.T
            ok = (np.abs(X @ M.T - R).max(axis=1) < 1e-6)
            ok &= ((X @ A_ub.T - B_ub[rest]).max(axis=1) < 1e-6) if len(A_ub) else ok
            ok &= ((LO[rest] - X).max(axis=1) < 1e-7) & ((X - HI[rest]).max(axis=1) < 1e-7)
            values[rest[ok], j] = X[ok] @ c  # same matrix and costs: the old duals still certify it
            todo = rest[~ok]
            tried += 1
        for s in todo:  # whatever is left: HiGHS one by one
            values[s, j] = solve_one(lp(s, j))[0]
            fallbacks += 1
    out = []
    for s, (d, (lps, consts)) in enumerate(captured):
        out.append(dp(d, plant, slot_costs(d, plant, tariff, list(values[s]), consts)))
    return out, fallbacks


def strip_kva(lp):
    """The LP without the kVA tangents (the 2,600 kVA connection never binds on this day; a careful
    generic code would add them only where an import breaks the limit, which the run checks)."""
    c, A_ub, b_ub, A_eq, b_eq, bounds = lp
    k = len(O._ANGLES)
    return [c, A_ub[:-k], b_ub[:-k], A_eq, b_eq, bounds]


def batched_lazy(plant, tariff, captured, chunk=50):
    """Generic, done carefully: no kVA rows, elastic blocks, many scenarios in one sparse LP."""
    out = []
    for c0 in range(0, len(captured), chunk):
        part = captured[c0:c0 + chunk]
        blocks, owners = [], []
        for si, (d, (lps, consts)) in enumerate(part):
            for lp in lps:
                c, A_ub, b_ub, A_eq, b_eq, bounds = strip_kva(lp)
                nv, m_eq, m_ub = len(c), len(b_eq), len(b_ub)
                n_new = 2 * m_eq + m_ub
                blocks.append((np.concatenate([c, np.full(n_new, PENALTY)]),
                               np.hstack([A_ub, np.zeros((m_ub, 2 * m_eq)), -np.eye(m_ub)]), b_ub,
                               np.hstack([A_eq, np.eye(m_eq), -np.eye(m_eq), np.zeros((m_eq, m_ub))]), b_eq,
                               np.vstack([bounds, np.tile([0.0, np.inf], (n_new, 1))]), nv, c))
        r = linprog(np.concatenate([b[0] for b in blocks]),
                    A_ub=block_diag([csr_matrix(b[1]) for b in blocks], format="csr"),
                    b_ub=np.concatenate([b[2] for b in blocks]),
                    A_eq=block_diag([csr_matrix(b[3]) for b in blocks], format="csr"),
                    b_eq=np.concatenate([b[4] for b in blocks]),
                    bounds=np.vstack([b[5] for b in blocks]), method="highs")
        assert r.status == 0, r.message
        pos, values = 0, []
        for b in blocks:
            n2, nv = len(b[0]), b[6]
            x = r.x[pos:pos + n2]
            values.append(math.inf if x[nv:].max(initial=0.0) > 1e-6 else float(b[7] @ x[:nv]))
            pos += n2
        n_lp = len(part[0][1][0])
        for si, (d, (lps, consts)) in enumerate(part):
            out.append(dp(d, plant, slot_costs(d, plant, tariff, values[si * n_lp:(si + 1) * n_lp], consts)))
    return out


def basis_rows(lp, r):
    """A basis of the optimum r: every row and bound with a nonzero dual, completed to full rank
    with the other tight ones. Returns the row matrix and, per row, where its right-hand side is."""
    c, A_ub, b_ub, A_eq, b_eq, bounds = lp
    nv = len(c)
    rows, src = [], []
    for i in range(len(b_eq)):
        rows.append(A_eq[i]); src.append(("eq", i))
    tight_ub = [i for i in range(len(b_ub)) if abs(A_ub[i] @ r.x - b_ub[i]) < 1e-7]
    lo = [i for i in range(nv) if abs(r.x[i] - bounds[i, 0]) < 1e-9]
    hi = [i for i in range(nv) if abs(r.x[i] - bounds[i, 1]) < 1e-9]
    duals_ub = r.ineqlin.marginals
    first = [("ub", i) for i in tight_ub if abs(duals_ub[i]) > 1e-9]
    first += [("lo", i) for i in lo if abs(r.lower.marginals[i]) > 1e-9]
    first += [("hi", i) for i in hi if abs(r.upper.marginals[i]) > 1e-9]
    rest = [("ub", i) for i in tight_ub if abs(duals_ub[i]) <= 1e-9]
    rest += [("lo", i) for i in lo if abs(r.lower.marginals[i]) <= 1e-9]
    rest += [("hi", i) for i in hi if abs(r.upper.marginals[i]) <= 1e-9]

    def row_of(k):
        kind, i = k
        return A_ub[i] if kind == "ub" else np.eye(nv)[i]

    for k in first + rest:
        cand = np.vstack(rows + [row_of(k)])
        if np.linalg.matrix_rank(cand) > np.linalg.matrix_rank(np.vstack(rows)) if rows else True:
            rows.append(row_of(k)); src.append(k)
        if len(rows) == nv:
            break
    if len(rows) < nv or np.linalg.matrix_rank(np.vstack(rows)) < nv:
        return None
    return np.vstack(rows), src


def structured_lib(plant, tariff, captured):
    """Basis reuse done properly: per LP slot a growing library of optimal bases, each tried on all
    pending scenarios at once (one solve with a square basis matrix), HiGHS only for the rest."""
    n_s = len(captured)
    n_lp = len(captured[0][1][0])
    values = np.full((n_s, n_lp), math.inf)
    highs = 0
    for j in range(n_lp):
        lps = [strip_kva(captured[si][1][0][j]) for si in range(n_s)]
        c, A_ub, _, A_eq, _, _ = lps[0]
        B = {"eq": np.array([lp[4] for lp in lps]), "ub": np.array([lp[2] for lp in lps]),
             "lo": np.array([lp[5][:, 0] for lp in lps]), "hi": np.array([lp[5][:, 1] for lp in lps])}
        todo = np.arange(n_s)
        library = []
        while len(todo):
            for M, src in library:
                R = np.column_stack([B[kind][todo, i] for kind, i in src])
                X = np.linalg.solve(M, R.T).T
                ok = np.ones(len(todo), bool)
                if len(A_ub):
                    ok &= (X @ A_ub.T - B["ub"][todo]).max(axis=1) < 1e-6
                ok &= ((B["lo"][todo] - X).max(axis=1) < 1e-7) & ((X - B["hi"][todo]).max(axis=1) < 1e-7)
                values[todo[ok], j] = X[ok] @ c
                todo = todo[~ok]
                if not len(todo):
                    break
            if not len(todo):
                break
            s0 = todo[0]
            c0, A_ub0, b_ub0, A_eq0, b_eq0, bounds0 = lps[s0]
            r = linprog(c0, A_ub=A_ub0 if len(b_ub0) else None, b_ub=b_ub0 if len(b_ub0) else None,
                        A_eq=A_eq0, b_eq=b_eq0, bounds=bounds0, method="highs")
            highs += 1
            todo = todo[1:]
            if r.status != 0:
                continue
            values[s0, j] = r.fun
            basis = basis_rows(lps[s0], r)
            if basis is not None:
                library.append(basis)
    out = [dp(d, plant, slot_costs(d, plant, tariff, list(values[si]), consts))
           for si, (d, (lps, consts)) in enumerate(captured)]
    return out, highs


def elastic_nokva(lp):
    """strip_kva, then a penalised slack on every row, so the LP is always feasible."""
    c, A_ub, b_ub, A_eq, b_eq, bounds = strip_kva(lp)
    nv, m_eq, m_ub = len(c), len(b_eq), len(b_ub)
    n_new = 2 * m_eq + m_ub
    return [np.concatenate([c, np.full(n_new, PENALTY)]),
            np.hstack([A_ub, np.zeros((m_ub, 2 * m_eq)), -np.eye(m_ub)]), b_ub,
            np.hstack([A_eq, np.eye(m_eq), -np.eye(m_eq), np.zeros((m_eq, m_ub))]), b_eq,
            np.vstack([bounds, np.tile([0.0, np.inf], (n_new, 1))])], nv


def structured_elastic(plant, tariff, captured):
    """Basis reuse on the elastic LPs: infeasibility is just a used slack, so every LP of every
    scenario is a candidate for a basis found on another scenario."""
    n_s = len(captured)
    n_lp = len(captured[0][1][0])
    values = np.full((n_s, n_lp), math.inf)
    highs = 0
    for j in range(n_lp):
        pairs = [elastic_nokva(captured[si][1][0][j]) for si in range(n_s)]
        lps = [p[0] for p in pairs]
        nv = pairs[0][1]
        c, A_ub, _, A_eq, _, _ = lps[0]
        B = {"eq": np.array([lp[4] for lp in lps]), "ub": np.array([lp[2] for lp in lps]),
             "lo": np.array([lp[5][:, 0] for lp in lps]), "hi": np.array([lp[5][:, 1] for lp in lps])}
        todo = np.arange(n_s)
        library = []
        while len(todo):
            for M, src in library:
                R = np.column_stack([B[kind][todo, i] for kind, i in src])
                X = np.linalg.solve(M, R.T).T
                ok = (X @ A_ub.T - B["ub"][todo]).max(axis=1) < 1e-6 if len(A_ub) else np.ones(len(todo), bool)
                ok &= ((B["lo"][todo] - X).max(axis=1) < 1e-7) & ((X - B["hi"][todo]).max(axis=1) < 1e-7)
                done = todo[ok]
                used = X[ok][:, nv:].max(axis=1, initial=0.0) > 1e-6
                values[done, j] = np.where(used, math.inf, X[ok][:, :nv] @ c[:nv])
                todo = todo[~ok]
                if not len(todo):
                    break
            if not len(todo):
                break
            s0 = todo[0]
            c0, A_ub0, b_ub0, A_eq0, b_eq0, bounds0 = lps[s0]
            r = linprog(c0, A_ub=A_ub0, b_ub=b_ub0, A_eq=A_eq0, b_eq=b_eq0, bounds=bounds0, method="highs")
            highs += 1
            todo = todo[1:]
            values[s0, j] = math.inf if r.x[nv:].max(initial=0.0) > 1e-6 else float(c0[:nv] @ r.x[:nv])
            basis = basis_rows(lps[s0], r)
            if basis is not None:
                library.append(basis)
    out = [dp(d, plant, slot_costs(d, plant, tariff, list(values[si]), consts))
           for si, (d, (lps, consts)) in enumerate(captured)]
    return out, highs


def generic_split(plant, tariff, captured, chunk=50):
    """batched_lazy with its time split: building the block LP (Python) and HiGHS's solve."""
    t_build = t_solve = 0.0
    for c0 in range(0, len(captured), chunk):
        part = captured[c0:c0 + chunk]
        t0 = time.perf_counter()
        blocks = [elastic_nokva(lp)[0] for d, (lps, consts) in part for lp in lps]
        args = dict(A_ub=block_diag([csr_matrix(b[1]) for b in blocks], format="csr"),
                    b_ub=np.concatenate([b[2] for b in blocks]),
                    A_eq=block_diag([csr_matrix(b[3]) for b in blocks], format="csr"),
                    b_eq=np.concatenate([b[4] for b in blocks]),
                    bounds=np.vstack([b[5] for b in blocks]), method="highs")
        cc = np.concatenate([b[0] for b in blocks])
        t1 = time.perf_counter()
        r = linprog(cc, **args)
        t2 = time.perf_counter()
        t_build += t1 - t0
        t_solve += t2 - t1
    return t_build, t_solve


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    check = int(sys.argv[2]) if len(sys.argv) > 2 else n
    day0 = load_day(DAY)
    plant = Plant(day0.plant)
    tariff = Tariff(day0.supply, day0.date)
    days = scenarios(day0, n)

    t0 = time.perf_counter()
    ref = naive(days[:check], plant, tariff)
    t_naive = (time.perf_counter() - t0) / check

    t0 = time.perf_counter()
    captured = [(d, capture(d, plant, tariff)) for d in days]
    t_capture = (time.perf_counter() - t0) / n

    t_build, t_solve = generic_split(plant, tariff, captured)

    t0 = time.perf_counter()
    st, highs = structured_elastic(plant, tariff, captured)
    t_struct = time.perf_counter() - t0

    n_lp = len(captured[0][1][0])
    print(f"{n} scenarios, {n_lp} LPs each (naive and the exactness check on the first {check})")
    print(f"naive                {1000 * t_naive:8.1f} ms per scenario")
    print(f"building the LPs     {1000 * t_capture:8.1f} ms per scenario (the solution's code)")
    print(f"generic, build       {1000 * t_build / n:8.1f} ms per scenario (stacking the blocks)")
    print(f"generic, HiGHS       {1000 * t_solve / n:8.1f} ms per scenario")
    print(f"structured, total    {t_struct:8.2f} s for all {n}: {1000 * t_struct / n:.1f} ms per scenario;"
          f" {highs} HiGHS solves of {n * n_lp} LPs")
    print(f"largest difference from naive: {max(abs(a - b) for a, b in zip(ref, st[:check])):.6f} GBP")


if __name__ == "__main__":
    main()
