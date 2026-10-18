"""Independent whole-day MILP lower-bound oracle.

The production planner enumerates continuous segment subproblems and performs
dynamic programming. This reference instead uses one single mixed-integer model
for the entire horizon, with binary adjacent-segment selection and explicit
start variables. An outer polygon encloses the true grid circle, so its certified
dual bound is a valid lower bound on the physical least cost.

Only cases whose base tower water is already warm enough for every available
absorber are used here; cold-water operation is tested separately by witnesses.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import time
import warnings

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_array

from check_plan import available, interp, read_input

ROOT = Path(__file__).resolve().parents[1]


def plus(*terms):
    result = {}
    for expression, scale in terms:
        for index, value in expression.items():
            result[index] = result.get(index, 0.0) + scale * value
    return {index: value for index, value in result.items() if value != 0}


class Matrix:
    def __init__(self):
        self.c, self.lower, self.upper, self.integer = [], [], [], []
        self.rows, self.row_lower, self.row_upper = [], [], []
    def var(self, cost=0, upper=math.inf, integer=False):
        i = len(self.c)
        self.c.append(cost)
        self.lower.append(0)
        self.upper.append(upper)
        self.integer.append(int(integer))
        return {i: 1.0}
    def row(self, expression, lower=-math.inf, upper=math.inf):
        self.rows.append(expression)
        self.row_lower.append(lower)
        self.row_upper.append(upper)
    def solve(self):
        values, rows, columns = [], [], []
        for i, row in enumerate(self.rows):
            for j, value in row.items():
                rows.append(i)
                columns.append(j)
                values.append(value)
        matrix = coo_array((np.asarray(values), (np.asarray(rows, dtype=np.int32),
                           np.asarray(columns, dtype=np.int32))),
                           shape=(len(self.rows), len(self.c))).tocsc()
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Unrecognized options detected.*")
            result = milp(np.asarray(self.c), integrality=np.asarray(self.integer),
                          bounds=Bounds(np.asarray(self.lower), np.asarray(self.upper)),
                          constraints=LinearConstraint(matrix, np.asarray(self.row_lower),
                                                       np.asarray(self.row_upper)),
                          options={"time_limit": 90, "mip_rel_gap": 1e-9, "presolve": True,
                                   "threads": 1, "random_seed": 0})
        return result


def reference(folder, facets=128, periods=48):
    started = time.perf_counter()
    plant, supply, status, demand, wx = read_input(folder)
    model = Matrix()
    gas = supply["gas"]
    electricity = supply["electricity"]
    ratio = gas["gross_to_net_cv_ratio"]
    entry = gas.get("entry")
    gas_limit = entry["maximum_standard_m3_per_hour"] * entry["gross_calorific_value_mj_per_standard_m3"] / 3.6
    to_gross = lambda basis: ratio if basis == "net CV" else 1.0
    to_bill = lambda basis: to_gross(basis) / (1 if gas["billing_basis"] == "gross CV" else ratio)
    previous = [None] * len(plant["engines"])
    for t, row in enumerate(demand[:periods]):
        dt = datetime.fromisoformat(row["period_start"])
        local = dt.strftime("%H:%M")
        weather = wx[dt.astimezone(timezone.utc)]
        wb = float(weather["wet_bulb_c"])
        water = max(wb + plant["cooling_towers"]["approach_k"], plant["cooling_towers"]["min_leaving_water_c"])
        for a in plant["absorption_chillers"]:
            if available(status, a["id"], local) and water < a["cooling_water_in_min_c"]:
                raise ValueError("oracle case requires a separate cold-water mode")
        tariff_bands = electricity["import_rates_p_per_kwh"]["weekend" if dt.weekday() >= 5 else "weekday"]
        rate = next(b["rate"] / 100 for b in tariff_bands if b["from"] <= local < b["to"])
        powers, heat, gas_entry, q, electricity_balance = [], {}, {}, {}, {}
        for j, engine in enumerate(plant["engines"]):
            permitted = available(status, engine["id"], local) and available(status, "engine_ht", local)
            for circuit_id, circuit in plant["heat_circuits"].items():
                if engine["id"] + " intercooler" in circuit.get("from", []):
                    permitted &= available(status, circuit_id, local)
                    permitted &= all(available(status, radiator, local) for radiator in circuit["to"])
            on, power, hot, fuel = {}, {}, {}, {}
            table = engine["part_load"]
            maintenance = engine["maintenance_gbp_per_mwhe"] / 1000
            billed_fuel_price = .5 * to_bill(engine["fuel_basis"]) * gas["rate_p_per_kwh"] / 100
            for low, high in zip(table[:-1], table[1:]):
                y = model.var(billed_fuel_price * low["fuel_kw"] + .5 * maintenance * low["kwe"],
                              upper=int(permitted), integer=True)
                fraction = model.var(billed_fuel_price * (high["fuel_kw"] - low["fuel_kw"])
                                     + .5 * maintenance * (high["kwe"] - low["kwe"]), upper=int(permitted))
                model.row(plus((fraction, 1), (y, -1)), upper=0)
                on = plus((on, 1), (y, 1))
                power = plus((power, 1), (y, low["kwe"]), (fraction, high["kwe"] - low["kwe"]))
                hot = plus((hot, 1), (y, low["ht_heat_kw"]), (fraction, high["ht_heat_kw"] - low["ht_heat_kw"]))
                fuel = plus((fuel, 1), (y, low["fuel_kw"]), (fraction, high["fuel_kw"] - low["fuel_kw"]))
            model.row(on, upper=1)
            powers.append(power)
            heat = plus((heat, 1), (hot, 1))
            q = plus((q, 1), (power, -math.tan(math.acos(engine["generator"]["power_factor"]))))
            electricity_balance = plus((electricity_balance, 1), (power, 1), (on, -engine["auxiliary_kwe"]))
            if engine["id"] in entry["supplies"]:
                gas_entry = plus((gas_entry, 1), (fuel, to_gross(engine["fuel_basis"])))
            start = model.var(engine["start_cost_gbp"], upper=1)
            if previous[j] is None:
                model.row(plus((on, 1), (start, -1)), upper=int(engine["id"] in status["running_at_midnight"]))
            else:
                model.row(plus((on, 1), (previous[j], -1), (start, -1)), upper=0)
            previous[j] = on
        boiler_heat = {}
        for boiler in plant["boilers"]:
            b = model.var(.5 * to_bill(boiler["efficiency_basis"]) / boiler["efficiency"] * gas["rate_p_per_kwh"] / 100,
                          upper=boiler["max_kw"] if available(status, boiler["id"], local) else 0)
            boiler_heat = plus((boiler_heat, 1), (b, 1))
            if boiler["id"] in entry["supplies"]:
                gas_entry = plus((gas_entry, 1), (b, to_gross(boiler["efficiency_basis"]) / boiler["efficiency"]))
        cooling, rejection, absorption_heat = {}, {}, {}
        compressor = model.var()
        electricity_balance = plus((electricity_balance, 1), (compressor, -1))
        rejection = plus((rejection, 1), (compressor, 1))
        minimum_power, maximum_power = {}, {}
        highest_water = max([water] + [ch["cop_by_condenser_entering_c"][-1][0]
                                       for ch in plant["electric_chillers"]])
        if plant["cooling_towers"].get("fans") != "variable speed":
            highest_water = water
        for chiller in plant["electric_chillers"]:
            x = model.var(upper=chiller["max_kw"] if available(status, chiller["id"], local) else 0)
            cop = interp(chiller["cop_by_condenser_entering_c"], water)
            cooling = plus((cooling, 1), (x, 1))
            rejection = plus((rejection, 1), (x, 1))
            minimum_power = plus((minimum_power, 1), (x, 1/cop))
            worst_cop = interp(chiller["cop_by_condenser_entering_c"], highest_water)
            maximum_power = plus((maximum_power, 1), (x, 1/worst_cop))
        model.row(plus((minimum_power, 1), (compressor, -1)), upper=0)
        model.row(plus((compressor, 1), (maximum_power, -1)), upper=0)
        for absorber in plant["absorption_chillers"]:
            x = model.var(upper=absorber["max_kw"] if available(status, absorber["id"], local) else 0)
            electricity_balance = plus((electricity_balance, 1), (x, -absorber["auxiliary_kwe_per_kw"]))
            cooling = plus((cooling, 1), (x, 1))
            rejection = plus((rejection, 1), (x, 1+1/absorber["cop"]+absorber["auxiliary_kwe_per_kw"]))
            absorption_heat = plus((absorption_heat, 1), (x, 1/absorber["cop"]))
        pv = model.var(upper=min(float(weather["pv_kw"]), plant["pv"]["inverter_ac_kw"])
                       if available(status, plant["pv"]["id"], local) else 0)
        imported = model.var(.5 * rate, upper=electricity["import_capacity_kva"])
        exported = model.var(-.5 * electricity["export_rate_p_per_kwh"]/100, upper=electricity["export_limit_kw"])
        grid = plus((imported, 1), (exported, -1))
        electricity_balance = plus((electricity_balance, 1), (pv, 1), (grid, 1))
        model.row(electricity_balance, lower=float(row["electricity_kw"]), upper=float(row["electricity_kw"]))
        model.row(cooling, lower=float(row["cooling_kw"]), upper=float(row["cooling_kw"]))
        h = float(row["heat_kw"]) + plant["heat_circuits"]["lthw"]["loss_kw"]
        model.row(plus((heat, 1), (boiler_heat, 1), (absorption_heat, -1)), lower=h, upper=h)
        model.row(plus((absorption_heat, 1), (heat, -1)), upper=0)
        phe = set(plant["heat_circuits"]["engine_ht"]["to"]) & set(plant["heat_circuits"]["lthw"]["from"])
        if not any(available(status, unit, local) for unit in phe):
            model.row(plus((absorption_heat, 1), (heat, -1)), lower=0, upper=0)
        cells = sum(available(status, unit, local) for unit in plant["cooling_towers"]["cells"])
        tower = cells * interp(plant["cooling_towers"]["heat_rejection_kw_per_cell_by_wet_bulb_c"], wb)
        model.row(rejection, upper=tower)
        model.row(gas_entry, upper=gas_limit if available(status, entry["id"], local) else 0)
        for k in range(facets):
            theta = 2 * math.pi * k / facets
            nx, ny = math.cos(theta), math.sin(theta)
            model.row(plus((grid, nx), (q, ny)),
                      upper=electricity["import_capacity_kva"] - ny * float(row["reactive_kvar"]))
    result = model.solve()
    if not result.success:
        raise RuntimeError(f"reference MILP did not prove optimality: {result.message}")
    return {"cost_gbp": float(result.fun), "certified_lower_bound_gbp": float(result.mip_dual_bound),
            "mip_gap": float(result.mip_gap), "seconds": time.perf_counter() - started,
            "circle_outer_polygon_facets": facets, "periods": periods,
            "variables": len(model.c), "binary_variables": sum(model.integer), "constraints": len(model.rows)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", nargs="+", default=["visible", "gas_binding", "tower_binding",
                        "electric_chiller_out", "startup_bridge", "startup_midnight_off", "warmer_water_export"])
    parser.add_argument("--facets", type=int, default=128)
    args = parser.parse_args()
    rows = []
    for name in args.cases:
        folder = ROOT / "app" / "data" if name == "visible" else ROOT / "experiments" / "cases" / name
        ref = reference(folder, args.facets)
        plan = json.loads((ROOT / "experiments" / "plans" / f"{name}.json").read_text())
        cost = plan["summary"]["cost_gbp"]
        ref["plan_cost_gbp"], ref["plan_minus_lower_bound_gbp"] = cost, cost - ref["certified_lower_bound_gbp"]
        if not -1e-4 <= ref["plan_minus_lower_bound_gbp"] <= .002:
            raise AssertionError(f"{name}: discrepancy from independent bound: {ref}")
        rows.append({"name": name, **ref})
        print(json.dumps(rows[-1]), flush=True)
    (ROOT / "experiments" / "optimality-report.json").write_text(json.dumps(rows, indent=2) + "\n")


if __name__ == "__main__":
    main()
