"""Independent whole-day mixed-integer optimality oracle (no planner imports).

Unlike the production enumerated LP + shortest-path method, this uses one SciPy
MILP for the entire day. Adjacent engine-table endpoint weights are selected by
binaries, commitment and starts are explicit, and buy/sell exclusivity is binary.
Any circle cuts are globally valid, so a feasible final optimum certifies the
whole-day objective, subject to the reported MILP and numerical tolerances.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_array

from audit import interp, minutes, out_at, read_inputs


class Model:
    def __init__(self):
        self.cost, self.lower, self.upper, self.integer = [], [], [], []
        self.rows, self.rlo, self.rhi = [], [], []

    def var(self, lower=0., upper=math.inf, cost=0., integer=0):
        i = len(self.cost)
        self.cost.append(cost)
        self.lower.append(lower)
        self.upper.append(upper)
        self.integer.append(integer)
        return i

    def row(self, terms, lower=-math.inf, upper=math.inf):
        self.rows.append(dict(terms))
        self.rlo.append(lower)
        self.rhi.append(upper)

    def solve(self, time_limit):
        ri, ci, values = [], [], []
        for r, row in enumerate(self.rows):
            for c, coefficient in row.items():
                if coefficient:
                    ri.append(r)
                    ci.append(c)
                    values.append(coefficient)
        matrix = coo_array((values, (np.asarray(ri, dtype=np.int32), np.asarray(ci, dtype=np.int32))),
                           shape=(len(self.rows), len(self.cost))).tocsc()
        return milp(np.asarray(self.cost), integrality=np.asarray(self.integer),
                    bounds=Bounds(self.lower, self.upper),
                    constraints=LinearConstraint(matrix, self.rlo, self.rhi),
                    options={"mip_rel_gap": 1e-10, "time_limit": time_limit})


def add(target, source, scale=1.):
    for variable, coefficient in source.items():
        target[variable] = target.get(variable, 0.) + coefficient * scale


def value(expression, vector):
    return math.fsum(coefficient * vector[i] for i, coefficient in expression.items())


def solve_oracle(folder, *, timeout=180.):
    plant, supply, status, demand, weather = read_inputs(folder)
    model = Model()
    el, gas = supply["electricity"], supply["gas"]
    circuits, towers = plant["heat_circuits"], plant["cooling_towers"]
    records = []
    previous = None
    start_time = time.monotonic()

    def billed(v, basis):
        if basis == gas["billing_basis"]:
            return v
        return v * gas["gross_to_net_cv_ratio"] if basis == "net CV" else v / gas["gross_to_net_cv_ratio"]

    for row in demand:
        first_var = len(model.cost)
        stamp = datetime.fromisoformat(row["period_start"])
        hhmm = stamp.strftime("%H:%M")
        wx = weather[stamp.astimezone(timezone.utc)]
        wb = float(wx["wet_bulb_c"])
        unavailable = lambda unit: out_at(status, unit, hhmm)
        record = {"start": hhmm, "p": {}, "u": {}, "b": {}, "e": {}, "a": {}, "gas": {}, "starts": []}
        electric, heat, reactive = {}, {}, {}
        for engine in plant["engines"]:
            eid = engine["id"]
            up = not unavailable(eid) and not unavailable("engine_ht")
            for name, circuit in circuits.items():
                if any(s.startswith(eid + " ") and "intercooler" in s for s in circuit.get("from", [])):
                    up = up and not unavailable(name) and any(not unavailable(sink) for sink in circuit["to"])
            pexpr, uexpr = {}, {}
            for p0, p1 in zip(engine["part_load"], engine["part_load"][1:]):
                selector = model.var(upper=float(up), integer=1)
                uexpr[selector] = 1.
                summation = {selector: -1.}
                for point in (p0, p1):
                    fuel = billed(point["fuel_kw"], engine["fuel_basis"])
                    rate = .5 * (fuel * gas["rate_p_per_kwh"] / 100
                                 + point["kwe"] * engine["maintenance_gbp_per_mwhe"] / 1000)
                    lam = model.var(upper=1., cost=rate)
                    summation[lam] = 1.
                    pexpr[lam] = point["kwe"]
                    heat[lam] = point["ht_heat_kw"]
                    record["gas"][lam] = fuel
                model.row(summation, 0., 0.)
            model.row(uexpr, upper=1.)
            model.row(pexpr, upper=min(engine["rated_kwe"], engine["generator"]["rated_kva"] * engine["generator"]["power_factor"]))
            add(electric, pexpr)
            add(electric, uexpr, -engine["auxiliary_kwe"])
            add(reactive, pexpr, -math.sqrt(1 / engine["generator"]["power_factor"] ** 2 - 1))
            record["p"][eid], record["u"][eid] = pexpr, uexpr
            start = model.var(upper=1., cost=engine["start_cost_gbp"])
            record["starts"].append(start)
            transition = {start: 1.}
            add(transition, uexpr, -1.)
            if previous is None:
                initial = float(eid in status["running_at_midnight"])
                model.row(transition, lower=-initial)
            else:
                add(transition, previous["u"][eid])
                model.row(transition, lower=0.)
        heat_load = float(row["heat_kw"]) + circuits["lthw"]["loss_kw"]
        phe_ids = set(circuits["engine_ht"]["to"]) & set(circuits["lthw"]["from"])
        phe_up = not unavailable("lthw") and not unavailable("engine_ht") and any(not unavailable(u) for u in phe_ids)
        phe = model.var(upper=heat_load if phe_up else 0.)
        heat[phe] = -1.
        lthw = {phe: 1.}
        for boiler in plant["boilers"]:
            fuel = billed(1 / boiler["efficiency"], boiler["efficiency_basis"])
            b = model.var(upper=0. if unavailable(boiler["id"]) or unavailable("lthw") else boiler["max_kw"],
                          cost=.5 * fuel * gas["rate_p_per_kwh"] / 100)
            lthw[b] = 1.
            record["b"][boiler["id"]] = b
            record["gas"][b] = fuel
        model.row(lthw, heat_load, heat_load)
        cooling, rejected = {}, {}
        for chiller in plant["electric_chillers"]:
            ch = model.var(upper=0. if unavailable(chiller["id"]) or unavailable("condenser_water") else chiller["max_kw"])
            record["e"][chiller["id"]] = ch
            cooling[ch], rejected[ch] = 1., 1.
        for absorber in plant["absorption_chillers"]:
            up = (not unavailable(absorber["id"]) and not unavailable("engine_ht") and not unavailable("condenser_water")
                  and circuits["engine_ht"]["flow_c"] >= absorber["hot_water_in_min_c"])
            ac = model.var(upper=absorber["max_kw"] if up else 0.)
            record["a"][absorber["id"]] = ac
            cooling[ac] = 1.
            heat[ac] = -1 / absorber["cop"]
            rejected[ac] = 1 + 1 / absorber["cop"]
            electric[ac] = -absorber["auxiliary_kwe_per_kw"]
        model.row(heat, 0., 0.)
        model.row(cooling, float(row["cooling_kw"]), float(row["cooling_kw"]))
        compressor = model.var()
        record["w"] = compressor
        electric[compressor], rejected[compressor] = -1., 1.
        cold = max(wb + towers["approach_k"], towers["min_leaving_water_c"])
        warm = max([cold] + [c["cop_by_condenser_entering_c"][-1][0] for c in plant["electric_chillers"]])
        low_e, high_e = {compressor: -1.}, {compressor: 1.}
        for chiller in plant["electric_chillers"]:
            ch = record["e"][chiller["id"]]
            low_e[ch] = 1 / interp(cold, chiller["cop_by_condenser_entering_c"])
            high_e[ch] = -1 / interp(warm, chiller["cop_by_condenser_entering_c"])
        model.row(low_e, upper=0.)
        model.row(high_e, upper=0.)
        for absorber in plant["absorption_chillers"]:
            if cold < absorber["cooling_water_in_min_c"]:
                warm_mode = model.var(upper=1., integer=1)
                model.row({record["a"][absorber["id"]]: 1., warm_mode: -absorber["max_kw"]}, upper=0.)
                minimum = absorber["cooling_water_in_min_c"]
                big_m = sum(ch["max_kw"] * (1 / interp(minimum, ch["cop_by_condenser_entering_c"])
                                           - 1 / interp(cold, ch["cop_by_condenser_entering_c"]))
                            for ch in plant["electric_chillers"])
                constraint = {compressor: -1., warm_mode: big_m}
                for chiller in plant["electric_chillers"]:
                    constraint[record["e"][chiller["id"]]] = 1 / interp(minimum, chiller["cop_by_condenser_entering_c"])
                model.row(constraint, upper=big_m)
        cells = sum(not unavailable(cell) for cell in towers["cells"]) if not unavailable("condenser_water") else 0
        model.row(rejected, upper=cells * interp(wb, towers["heat_rejection_kw_per_cell_by_wet_bulb_c"]))
        pv_limit = min(float(wx["pv_kw"]), plant["pv"]["inverter_ac_kw"]) if not unavailable(plant["pv"]["id"]) else 0.
        pv = model.var(upper=pv_limit)
        bands = el["import_rates_p_per_kwh"]["weekend" if stamp.weekday() >= 5 else "weekday"]
        import_rate = next(b["rate"] for b in bands if minutes(b["from"]) <= minutes(hhmm) < minutes(b["to"])) / 100
        imported = model.var(upper=el["import_capacity_kva"], cost=.5 * import_rate)
        exported = model.var(upper=el["export_limit_kw"], cost=-.5 * el["export_rate_p_per_kwh"] / 100)
        direction = model.var(upper=1., integer=1)
        model.row({imported: 1., direction: -el["import_capacity_kva"]}, upper=0.)
        model.row({exported: 1., direction: el["export_limit_kw"]}, upper=el["export_limit_kw"])
        electric[pv], electric[imported], electric[exported] = 1., 1., -1.
        model.row(electric, float(row["electricity_kw"]), float(row["electricity_kw"]))
        record.update({"pv": pv, "i": imported, "x": exported, "q": reactive,
                       "qd": float(row["reactive_kvar"]), "cost_vars": (first_var, len(model.cost))})
        for angle in np.linspace(-math.pi / 2, math.pi / 2, 17):
            tangent = {imported: math.cos(float(angle))}
            add(tangent, reactive, math.sin(float(angle)))
            model.row(tangent, upper=el["import_capacity_kva"] - record["qd"] * math.sin(float(angle)))
        records.append(record)
        previous = record

    iterations, cuts = 0, 0
    while True:
        remaining = timeout - (time.monotonic() - start_time)
        if remaining <= 0:
            raise RuntimeError("independent MILP oracle timeout")
        result = model.solve(remaining)
        iterations += 1
        if not result.success:
            if result.status == 2:
                return {"feasible": False, "status": "proven infeasible", "seconds": time.monotonic() - start_time}, None
            raise RuntimeError(result.message)
        violations = []
        for r in records:
            imp, q = result.x[r["i"]], r["qd"] + value(r["q"], result.x)
            norm = math.hypot(imp, q)
            if norm > el["import_capacity_kva"] + 2e-7:
                violations.append((r, imp / norm, q / norm))
        if not violations:
            break
        for r, ca, cq in violations:
            tangent = {r["i"]: ca}
            add(tangent, r["q"], cq)
            model.row(tangent, upper=el["import_capacity_kva"] - cq * r["qd"])
            cuts += 1
    x = result.x
    periods = []

    def zero(v):
        return 0. if abs(v) < 1e-7 else float(v)

    for r in records:
        begin, end = r["cost_vars"]
        periods.append({
            "start": r["start"],
            "engines_kwe": {eid: zero(value(expr, x)) for eid, expr in r["p"].items()},
            "boilers_kw": {bid: zero(x[j]) for bid, j in r["b"].items()},
            "chillers_kw": {**{eid: zero(x[j]) for eid, j in r["e"].items()},
                            **{aid: zero(x[j]) for aid, j in r["a"].items()}},
            "pv_kw": zero(x[r["pv"]]), "import_kw": zero(x[r["i"]]), "export_kw": zero(x[r["x"]]),
            "gas_kwh": .5 * value(r["gas"], x),
            "cost_gbp": float(np.asarray(model.cost[begin:end]) @ x[begin:end]), "grid_ok": True,
        })
    summary = {"cost_gbp": math.fsum(p["cost_gbp"] for p in periods),
               "gas_kwh": math.fsum(p["gas_kwh"] for p in periods),
               "import_kwh": .5 * math.fsum(p["import_kw"] for p in periods),
               "export_kwh": .5 * math.fsum(p["export_kw"] for p in periods),
               "engine_starts": round(sum(x[i] for r in records for i in r["starts"])), "grid_ok": True}
    report = {"feasible": True, "cost_gbp": float(result.fun), "dual_bound_gbp": float(result.mip_dual_bound),
              "relative_mip_gap": float(result.mip_gap), "iterations": iterations, "circle_cuts": cuts,
              "variables": len(model.cost), "binary_variables": sum(model.integer),
              "constraints": len(model.rows), "seconds": time.monotonic() - start_time}
    return report, {"date": status["date"], "periods": periods, "summary": summary}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--plan")
    args = parser.parse_args()
    report, plan = solve_oracle(args.data)
    Path(args.report).write_text(json.dumps(report, indent=2) + "\n")
    if args.plan and plan is not None:
        Path(args.plan).write_text(json.dumps(plan, indent=1) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
