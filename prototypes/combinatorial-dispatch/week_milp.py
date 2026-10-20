"""Third falsification test: can the optimisation itself be made hard to solve exactly in two
minutes? (prototype)

The current task's plant (v12), planned over several days at once, with a hot-water thermal store
on the LTHW circuit (couples the half-hours, so the per-half-hour LPs plus a DP no longer work)
and minimum up and down times for the engines. One MILP over the whole horizon, built as a careful
generic code would build it (the standard tight minimum up/down constraints, the part-load
segments and the header modes of the task's reference), solved with SciPy's HiGHS.

Usage: python week_milp.py DAYS [time_limit_s]
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tasks" / "energy-centre-dispatch" / "tests"))
import reference as R  # noqa: E402

DT_H = 0.5
STORES = {"small": dict(kwh=1500.0, kw=750.0), "large": dict(kwh=3000.0, kw=1500.0)}
LOSS_PER_H = 0.005  # standing loss of the store; it has no round-trip loss
STORE = dict(STORES["large"])
MIN_UP, MIN_DOWN = 6, 4  # half-hours
import os
OFF = set(filter(None, os.environ.get("ECD_NO", "").split(",")))  # parts left out, for the diagnosis


def horizon(days: int, seed: int = 3, base_name: str = "visible"):
    """Per half-hour arrays for `days` days: the visible day perturbed day by day; days 6 and 7 of
    each week at weekend rates."""
    base = R.Day(ROOT / "tasks" / "energy-centre-dispatch" / "tests" / "days" / base_name)
    rng = np.random.default_rng(seed)
    el = base.supply["electricity"]["import_rates_p_per_kwh"]
    def rates(weekend):
        bands = el["weekend" if weekend else "weekday"]
        return np.array([next(b["rate"] for b in bands if R._hm(b["from"]) <= c < R._hm(b["to"]))
                         for c in base.clock]) / 100.0
    cols = {k: [] for k in ("elec", "kvar", "heat", "cool", "pv", "rate", "cop0", "cop1", "tower")}
    for d in range(days):
        f = 1 + 0.05 * rng.standard_normal()
        cols["elec"].append(base.elec * f * (1 + 0.02 * rng.standard_normal(48)))
        cols["kvar"].append(base.kvar * f)
        cols["heat"].append(base.heat * (1 + 0.15 * rng.standard_normal()) * (1 + 0.04 * rng.standard_normal(48)))
        cols["cool"].append(base.cool * (1 + 0.1 * rng.standard_normal()) * (1 + 0.04 * rng.standard_normal(48)))
        cols["pv"].append(base.pv * rng.uniform(0.5, 1.1))
        cols["rate"].append(rates(d % 7 >= 5))
        cols["cop0"].append({ch["id"]: base.cop[ch["id"]][False] for ch in base.plant["electric_chillers"]})
        cols["cop1"].append({ch["id"]: base.cop[ch["id"]][True] for ch in base.plant["electric_chillers"]})
        cols["tower"].append(base.tower_max)
    out = {k: np.concatenate(v) for k, v in cols.items() if k not in ("cop0", "cop1")}
    out["cop"] = {m: {ch["id"]: np.concatenate([c[ch["id"]] for c in cols["cop1" if m else "cop0"]])
                      for ch in base.plant["electric_chillers"]} for m in (False, True)}
    return base, out


def build(base, h):
    eng, boil = base.engines, base.plant["boilers"]
    ecs, acs = base.plant["electric_chillers"], base.plant["absorption_chillers"]
    T = len(h["elec"])
    names = []
    for g, e in enumerate(eng):
        nseg = len(e["part_load"]) - 1
        names += [f"U{g}", f"S{g}"] + [f"D{g}_{s}" for s in range(nseg)] + [f"W{g}_{s}" for s in range(1, nseg)]
    names += [f"B{b}" for b in range(len(boil))] + [f"E{i}" for i in range(len(ecs))] + [f"H{i}" for i in range(len(ecs))]
    names += [f"A{a}" for a in range(len(acs))] + ["Z", "I", "X", "F", "L"]
    k = {n: i for i, n in enumerate(names)}
    nv = len(names)
    total = nv * T
    c, lo, hi, integ = np.zeros(total), np.zeros(total), np.zeros(total), np.zeros(total)
    ri, ci, vals, rlo, rhi = [], [], [], [], []

    def v(t, n):
        return t * nv + k[n]

    def add(coefs, lb, ub):
        r = len(rlo)
        for i, x in coefs.items():
            ri.append(r); ci.append(i); vals.append(x)
        rlo.append(lb); rhi.append(ub)

    st = STORE
    keep = (1 - LOSS_PER_H) ** DT_H
    start = st["kwh"] / 2
    for t in range(T):
        el = {v(t, "I"): 1.0, v(t, "X"): -1.0}
        heat_terms = {}
        for g, e in enumerate(eng):
            kw, fuel, heat = base.curve[e["id"]]
            nseg = len(kw) - 1
            hi[v(t, f"U{g}")], integ[v(t, f"U{g}")] = 1.0, 1
            hi[v(t, f"S{g}")] = 1.0
            c[v(t, f"S{g}")] = e["start_cost_gbp"]
            c[v(t, f"U{g}")] = DT_H * (fuel[0] * base.gross_net * base.gas_rate + kw[0] * e["maintenance_gbp_per_mwhe"] / 1000.0)
            el[v(t, f"U{g}")] = kw[0] - e["auxiliary_kwe"]
            heat_terms[v(t, f"U{g}")] = heat[0]
            for s in range(nseg):
                length = kw[s + 1] - kw[s]
                d = v(t, f"D{g}_{s}")
                hi[d] = length
                c[d] = DT_H * ((fuel[s + 1] - fuel[s]) / length * base.gross_net * base.gas_rate
                               + e["maintenance_gbp_per_mwhe"] / 1000.0)
                el[d] = 1.0
                heat_terms[d] = (heat[s + 1] - heat[s]) / length
                gate = v(t, f"U{g}") if s == 0 else v(t, f"W{g}_{s}")
                add({d: 1.0, gate: -length}, -np.inf, 0.0)
                if s > 0:
                    w = v(t, f"W{g}_{s}")
                    hi[w], integ[w] = 1.0, (0 if "segbin" in OFF else 1)
                    add({v(t, f"D{g}_{s - 1}"): 1.0, w: -(kw[s] - kw[s - 1])}, 0.0, np.inf)
                    add({w: 1.0, (v(t, f"U{g}") if s == 1 else v(t, f"W{g}_{s - 1}")): -1.0}, -np.inf, 0.0)
            # start: S >= U(t) - U(t-1); minimum up and down times, the standard tight form
            if t == 0:
                add({v(t, f"S{g}"): 1.0, v(t, f"U{g}"): -1.0}, -1.0 if e["id"] in base.running0 else 0.0, np.inf)
            else:
                add({v(t, f"S{g}"): 1.0, v(t, f"U{g}"): -1.0, v(t - 1, f"U{g}"): 1.0}, 0.0, np.inf)
            if "minupdown" not in OFF:
                add({**{v(tau, f"S{g}"): 1.0 for tau in range(max(0, t - MIN_UP + 1), t + 1)}, v(t, f"U{g}"): -1.0},
                    -np.inf, 0.0)
            if t >= MIN_DOWN and "minupdown" not in OFF:
                add({**{v(tau, f"S{g}"): 1.0 for tau in range(t - MIN_DOWN + 1, t + 1)}, v(t - MIN_DOWN, f"U{g}"): 1.0},
                    -np.inf, 1.0)
        for b, bl in enumerate(boil):
            hi[v(t, f"B{b}")] = bl["max_kw"]
            c[v(t, f"B{b}")] = DT_H * base.gas_rate / bl["efficiency"]
        z = v(t, "Z")
        hi[z], integ[z] = 1.0, (0 if "header" in OFF else 1)
        rejection = {}
        for i, ch in enumerate(ecs):
            cap = ch["max_kw"]
            for name, mode in ((f"E{i}", False), (f"H{i}", True)):
                hi[v(t, name)] = cap
                cop = h["cop"][mode][ch["id"]][t]
                el[v(t, name)] = -1.0 / cop
                rejection[v(t, name)] = 1.0 + 1.0 / cop
            add({v(t, f"E{i}"): 1.0, z: cap}, -np.inf, cap)
            add({v(t, f"H{i}"): 1.0, z: -cap}, -np.inf, 0.0)
        for a, ac in enumerate(acs):
            hi[v(t, f"A{a}")] = ac["max_kw"]
            el[v(t, f"A{a}")] = -ac["auxiliary_kwe_per_kw"]
            rejection[v(t, f"A{a}")] = 1.0 + 1.0 / ac["cop"]
            add({v(t, f"A{a}"): 1.0, z: -ac["max_kw"]}, -np.inf, 0.0)
        hi[v(t, "I")] = math.sqrt(max(base.import_kva ** 2 - h["kvar"][t] ** 2, 0.0))
        hi[v(t, "X")] = base.export_max
        c[v(t, "I")] = DT_H * h["rate"][t]
        c[v(t, "X")] = -DT_H * base.export_rate
        add(el, h["elec"][t] - h["pv"][t], h["elec"][t] - h["pv"][t])
        # LTHW: engine heat after the absorbers, the boilers and the store's discharge, less its charge
        lthw = dict(heat_terms)
        absorb = dict(heat_terms)
        for a, ac in enumerate(acs):
            lthw[v(t, f"A{a}")] = -1.0 / ac["cop"]
            absorb[v(t, f"A{a}")] = -1.0 / ac["cop"]
        for b in range(len(boil)):
            lthw[v(t, f"B{b}")] = 1.0
        lthw[v(t, "F")] = -1.0  # F > 0 charges the store from the LTHW header
        add(lthw, h["heat"][t] + base.lthw_loss, h["heat"][t] + base.lthw_loss)
        add(absorb, 0.0, np.inf)
        add({**{v(t, f"{m}{i}"): 1.0 for i in range(len(ecs)) for m in "EH"},
             **{v(t, f"A{a}"): 1.0 for a in range(len(acs))}}, h["cool"][t], h["cool"][t])
        add(rejection, -np.inf, h["tower"][t])
        # the store: L(t) = keep * L(t-1) + F(t) * 0.5 h
        lo[v(t, "F")] = 0.0 if "store" in OFF else -st["kw"]
        hi[v(t, "F")] = 0.0 if "store" in OFF else st["kw"]
        hi[v(t, "L")] = st["kwh"]
        prev = {v(t - 1, "L"): -keep} if t > 0 else {}
        rhs = keep * start if t == 0 else 0.0
        add({v(t, "L"): 1.0, **prev, v(t, "F"): -DT_H}, rhs, rhs)
    lo[v(T - 1, "L")] = 0.0 if "store" in OFF else start  # back where it started
    A = coo_matrix((vals, (ri, ci)), shape=(len(rlo), total)).tocsr()
    return c, A, np.array(rlo), np.array(rhi), lo, hi, integ


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("days", type=int)
    ap.add_argument("limit", type=float, nargs="?", default=600.0)
    ap.add_argument("--base", default="visible")
    ap.add_argument("--store", default="large")
    ap.add_argument("--disp", action="store_true")
    a = ap.parse_args()
    STORE.clear()
    STORE.update(STORES[a.store])
    base, h = horizon(a.days, base_name=a.base)
    t0 = time.perf_counter()
    c, A, rlo, rhi, lo, hi, integ = build(base, h)
    t1 = time.perf_counter()
    res = milp(c, constraints=LinearConstraint(A, rlo, rhi), integrality=integ, bounds=Bounds(lo, hi),
               options={"mip_rel_gap": 1e-4, "time_limit": a.limit, "disp": a.disp})
    t2 = time.perf_counter()
    print(f"SUMMARY days={a.days} base={a.base} store={a.store} vars={A.shape[1]} binaries={int(integ.sum())}"
          f" rows={A.shape[0]} nnz={A.nnz} build={t1 - t0:.2f}s solve={t2 - t1:.1f}s status={res.status}"
          f" cost={res.fun if res.x is not None else float('nan'):.2f}"
          f" bound={getattr(res, 'mip_dual_bound', float('nan')):.2f} gap={getattr(res, 'mip_gap', float('nan'))}", flush=True)


if __name__ == "__main__":
    main()
