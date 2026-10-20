"""Independent check of the v11 reference: per half-hour, every engine combination and setpoint,
the fans exactly on their curve (segment binaries), then a DP over the day for the starts."""
import math, sys
from multiprocessing import Pool
from pathlib import Path
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

TASK = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(TASK / "tests"))
import reference as R  # noqa: E402

DT_H, N, CUTS = R.DT_H, R.N, R.CUTS


def period(day, t, combo, sp):
    eng, boil = day.engines, day.plant["boilers"]
    ecs, ac = day.plant["electric_chillers"], day.plant["absorption_chillers"][0]
    fx, fk = day._fan_x, day._fan_kw
    names = []
    for g in combo:
        nseg = len(eng[g]["part_load"]) - 1
        names += [f"D{g}_{s}" for s in range(nseg)] + [f"W{g}_{s}" for s in range(1, nseg)]
    names += [f"B{b}" for b in range(len(boil))] + [f"E{i}" for i in range(len(ecs))] + ["A", "I", "X", "F"]
    names += [f"L{j}" for j in range(len(fx))] + [f"Z{j}" for j in range(len(fx) - 1)]
    k = {n: i for i, n in enumerate(names)}
    nv = len(names)
    c, lo, hi, integ = np.zeros(nv), np.zeros(nv), np.zeros(nv), np.zeros(nv)
    rows, rlo, rhi = [], [], []

    def add(coefs, lb, ub):
        r = np.zeros(nv)
        for n, x in coefs.items():
            r[k[n]] += x
        rows.append(r); rlo.append(lb); rhi.append(ub)

    cc = ce = ch_ = cg = 0.0
    el, heat, gen = {}, {}, {}
    for g in combo:
        e = eng[g]
        kw, fuel, ht = day.curve[e["id"]]
        cc += DT_H * (fuel[0] * day.gross_net * day.gas_rate + kw[0] * e["maintenance_gbp_per_mwhe"] / 1000.0)
        ce += kw[0] - e["auxiliary_kwe"]; ch_ += ht[0]; cg += kw[0] * day.q_per_kw[e["id"]]
        for s in range(len(kw) - 1):
            L = kw[s + 1] - kw[s]; d = f"D{g}_{s}"
            hi[k[d]] = L
            c[k[d]] = DT_H * ((fuel[s + 1] - fuel[s]) / L * day.gross_net * day.gas_rate + e["maintenance_gbp_per_mwhe"] / 1000.0)
            el[d] = 1.0; heat[d] = (ht[s + 1] - ht[s]) / L; gen[d] = day.q_per_kw[e["id"]]
            if s > 0:
                w = f"W{g}_{s}"; hi[k[w]], integ[k[w]] = 1, 1
                add({d: 1.0, w: -L}, -np.inf, 0.0)
                add({f"D{g}_{s - 1}": 1.0, w: -(kw[s] - kw[s - 1])}, 0.0, np.inf)
    for b, bl in enumerate(boil):
        hi[k[f"B{b}"]] = bl["max_kw"] if day.available[bl["id"]][t] else 0.0
        c[k[f"B{b}"]] = DT_H * day.gas_rate / bl["efficiency"]
    rej = {}
    for i, chl in enumerate(ecs):
        hi[k[f"E{i}"]] = chl["max_kw"] if day.available[chl["id"]][t] else 0.0
        cop = day.ec_cop(chl, sp); el[f"E{i}"] = -1.0 / cop; rej[f"E{i}"] = 1.0 + 1.0 / cop
    hi[k["A"]] = day.ac_max(ac, sp) if day.available[ac["id"]][t] else 0.0
    el["A"] = -ac["auxiliary_kwe_per_kw"]; rej["A"] = 1.0 + 1.0 / ac["cop"]
    hi[k["I"]], hi[k["X"]] = day.import_kva, day.export_max
    c[k["I"]] = DT_H * day.import_rate[t]; c[k["X"]] = -DT_H * day.export_rate
    el["I"], el["X"], el["F"] = 1.0, -1.0, -1.0
    full, n = day.towers_max(t, sp), day.cells[t]
    hi[k["F"]] = np.inf
    for j in range(len(fx)):
        hi[k[f"L{j}"]] = 1.0
    for j in range(len(fx) - 1):
        hi[k[f"Z{j}"]], integ[k[f"Z{j}"]] = 1, 1
    add({f"L{j}": 1.0 for j in range(len(fx))}, 1.0, 1.0)
    add({f"Z{j}": 1.0 for j in range(len(fx) - 1)}, 1.0, 1.0)
    for j in range(len(fx)):
        adj = {f"L{j}": 1.0}
        if j > 0: adj[f"Z{j - 1}"] = -1.0
        if j < len(fx) - 1: adj[f"Z{j}"] = -1.0
        add(adj, -np.inf, 0.0)
    add({**rej, **{f"L{j}": -full * fx[j] for j in range(len(fx))}}, 0.0, 0.0)
    add({"F": 1.0, **{f"L{j}": -n * fk[j] for j in range(len(fx))}}, 0.0, 0.0)
    add(el, day.elec[t] - day.pv[t] - ce, day.elec[t] - day.pv[t] - ce)
    lthw = dict(heat); lthw["A"] = -1.0 / ac["cop"]
    for b in range(len(boil)): lthw[f"B{b}"] = 1.0
    add(lthw, day.heat[t] + day.lthw_loss - ch_, day.heat[t] + day.lthw_loss - ch_)
    ab = dict(heat); ab["A"] = -1.0 / ac["cop"]
    add(ab, -ch_, np.inf if day.available["PHE1"][t] else -ch_)
    add({**{f"E{i}": 1.0 for i in range(len(ecs))}, "A": 1.0}, day.cool[t], day.cool[t])
    for th in np.linspace(-np.pi / 2, np.pi / 2, CUTS):
        cut = {"I": math.cos(th)}
        for d, x in gen.items(): cut[d] = cut.get(d, 0.0) - math.sin(th) * x
        add(cut, -np.inf, day.import_kva - math.sin(th) * day.kvar[t] + math.sin(th) * cg)
    res = milp(c, constraints=LinearConstraint(np.array(rows), rlo, rhi), integrality=integ,
               bounds=Bounds(lo, hi), options={"mip_rel_gap": 1e-9})
    return (float(res.fun) + cc) if res.status == 0 else math.inf


def table(args):
    folder, t = args
    day = R.Day(folder)
    out = {}
    for m in range(1 << len(day.engines)):
        cmb = tuple(g for g in range(len(day.engines)) if m >> g & 1)
        if all(day.available[day.engines[g]["id"]][t] for g in cmb):
            out[cmb] = min(period(day, t, cmb, sp) for sp in day.setpoints)
    return t, out


def main():
    with Pool(16) as pool:
        for d in sys.argv[2:] or ["visible", "h1", "h2", "h3", "h4"]:
            folder = TASK / "tests" / "days" / d
            day = R.Day(folder)
            tabs = dict(pool.map(table, [(folder, t) for t in range(N)]))
            prev = {tuple(g for g, e in enumerate(day.engines) if e["id"] in day.running0): 0.0}
            for t in range(N):
                cur = {}
                for cmb, pc in tabs[t].items():
                    if not math.isfinite(pc): continue
                    best = min((v + sum(day.engines[g]["start_cost_gbp"] for g in cmb if g not in p) for p, v in prev.items()), default=math.inf)
                    if math.isfinite(best): cur[cmb] = best + pc
                prev = cur
            dp = min(prev.values()) if prev else math.inf
            try:
                ref = day.least_cost()["cost"]
            except RuntimeError as e:
                ref = str(e)
            print(f"{d}: decomposition {dp:.4f}   reference MILP {ref if isinstance(ref, str) else f'{ref:.4f}'}")


if __name__ == "__main__":
    main()
