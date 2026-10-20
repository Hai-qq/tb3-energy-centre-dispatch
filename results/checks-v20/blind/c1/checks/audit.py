"""Independent plan checker: this file imports no part of the repaired planner.

Reconstructs timestamp matching, all physical balances, a common attainable
condenser-water temperature, connection limits, metered gas and every cash flow.

    python checks/audit.py --data app/data --plan experiments/visible-plan.json
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

EPS = 1e-5


def interp(value, points):
    if value <= points[0][0]:
        return float(points[0][1])
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if value <= x1:
            return y0 + (y1 - y0) * (value - x0) / (x1 - x0)
    return float(points[-1][1])


def minutes(value):
    h, m = map(int, value.split(":"))
    return 60 * h + m


def out_at(status, unit, hhmm):
    # Minute sampling is exact here because the input intervals have HH:MM ends.
    for outage in status.get("outages", []):
        if outage["unit"] == unit:
            left, right = minutes(outage["from"]), minutes(outage["to"])
            for m in range(minutes(hhmm), minutes(hhmm) + 30):
                if (left <= m < right) if left <= right else (m >= left or m < right):
                    return True
    return False


def read_inputs(folder):
    folder = Path(folder)
    plant = json.loads((folder / "plant.json").read_text())
    supply = json.loads((folder / "supply.json").read_text())
    status = json.loads((folder / "status.json").read_text())
    with (folder / "demand.csv").open(newline="") as stream:
        demand = sorted(csv.DictReader(stream), key=lambda r: datetime.fromisoformat(r["period_start"]))
    with (folder / "weather.csv").open(newline="") as stream:
        weather = {datetime.fromisoformat(r["time_utc"]).astimezone(timezone.utc): r
                   for r in csv.DictReader(stream)}
    return plant, supply, status, demand, weather


def check_plan(folder, plan_path):
    plant, supply, status, demand, weather = read_inputs(folder)
    plan = json.loads(Path(plan_path).read_text())
    failures = []

    def need(condition, explanation):
        if not condition:
            failures.append(explanation)

    need(set(plan) == {"date", "periods", "summary"}, "top-level schema")
    need(plan["date"] == status["date"], "plan date")
    need(len(plan["periods"]) == len(demand) == 48, "48-period coverage")
    period_keys = {"start", "engines_kwe", "boilers_kw", "chillers_kw", "pv_kw", "import_kw",
                   "export_kw", "gas_kwh", "cost_gbp", "grid_ok"}
    circuits = plant["heat_circuits"]
    tower = plant["cooling_towers"]
    gas_tariff, electricity = supply["gas"], supply["electricity"]
    initial = set(status["running_at_midnight"])
    previous = initial
    starts = 0
    period_costs, period_gas = [], []
    temperatures, tower_margins, grid_margins = [], [], []
    heat_errors, electric_errors, cost_errors, gas_errors = [], [], [], []
    pv_curtailed = 0.0
    warm_extra = []

    def billed(quantity, basis):
        if gas_tariff["billing_basis"] == basis:
            return quantity
        if basis == "net CV" and gas_tariff["billing_basis"] == "gross CV":
            return quantity * gas_tariff["gross_to_net_cv_ratio"]
        if basis == "gross CV" and gas_tariff["billing_basis"] == "net CV":
            return quantity / gas_tariff["gross_to_net_cv_ratio"]
        raise ValueError("unsupported gas bases in test input")

    for t, (row, period) in enumerate(zip(demand, plan["periods"])):
        stamp = datetime.fromisoformat(row["period_start"])
        hhmm = stamp.strftime("%H:%M")
        wx = weather[stamp.astimezone(timezone.utc)]
        wb = float(wx["wet_bulb_c"])
        need(set(period) == period_keys, f"{hhmm}: period schema")
        need(period["start"] == hhmm, f"{hhmm}: period order")
        need(set(period["engines_kwe"]) == {e["id"] for e in plant["engines"]}, f"{hhmm}: engine keys")
        need(set(period["boilers_kw"]) == {b["id"] for b in plant["boilers"]}, f"{hhmm}: boiler keys")
        need(set(period["chillers_kw"]) == {c["id"] for c in plant["electric_chillers"] + plant["absorption_chillers"]},
             f"{hhmm}: chiller keys")
        running, gross_power, ht, gas, upkeep, start_cost, gen_aux = set(), 0., 0., 0., 0., 0., 0.
        reactive = float(row["reactive_kvar"])
        for engine in plant["engines"]:
            power = period["engines_kwe"][engine["id"]]
            need(math.isfinite(power) and power >= -EPS, f"{hhmm}: {engine['id']} finite nonnegative")
            if power > EPS:
                running.add(engine["id"])
                need(engine["part_load"][0]["kwe"] - EPS <= power <= engine["rated_kwe"] + EPS,
                     f"{hhmm}: {engine['id']} running range")
                need(not out_at(status, engine["id"], hhmm), f"{hhmm}: {engine['id']} outage")
                need(not out_at(status, "engine_ht", hhmm), f"{hhmm}: HT circuit outage")
                for name, circuit in circuits.items():
                    if any(s.startswith(engine["id"] + " ") and "intercooler" in s for s in circuit.get("from", [])):
                        need(not out_at(status, name, hhmm) and any(not out_at(status, sink, hhmm) for sink in circuit["to"]),
                             f"{hhmm}: {engine['id']} LT cooling path")
                ht += interp(power, [(p["kwe"], p["ht_heat_kw"]) for p in engine["part_load"]])
                fuel = interp(power, [(p["kwe"], p["fuel_kw"]) for p in engine["part_load"]])
                gas += billed(fuel, engine["fuel_basis"])
                gen_aux += engine["auxiliary_kwe"]
                if engine["id"] not in previous:
                    starts += 1
                    start_cost += engine["start_cost_gbp"]
            q = power * math.sqrt(1 / engine["generator"]["power_factor"] ** 2 - 1)
            need(math.hypot(power, q) <= engine["generator"]["rated_kva"] + EPS,
                 f"{hhmm}: {engine['id']} generator kVA")
            reactive -= q
            gross_power += power
            upkeep += power * engine["maintenance_gbp_per_mwhe"] / 1000
        previous = running
        boiler_heat = 0.
        for boiler in plant["boilers"]:
            output = period["boilers_kw"][boiler["id"]]
            limit = 0.0 if out_at(status, boiler["id"], hhmm) else boiler["max_kw"]
            need(math.isfinite(output) and -EPS <= output <= limit + EPS, f"{hhmm}: {boiler['id']} rating/outage")
            boiler_heat += output
            gas += billed(output / boiler["efficiency"], boiler["efficiency_basis"])
        absorption_heat, ac_aux = 0., 0.
        base = max(wb + tower["approach_k"], tower["min_leaving_water_c"])
        cold = base
        for absorber in plant["absorption_chillers"]:
            output = period["chillers_kw"][absorber["id"]]
            limit = 0.0 if out_at(status, absorber["id"], hhmm) else absorber["max_kw"]
            need(math.isfinite(output) and -EPS <= output <= limit + EPS, f"{hhmm}: {absorber['id']} rating/outage")
            if output > EPS:
                cold = max(cold, absorber["cooling_water_in_min_c"])
                need(circuits["engine_ht"]["flow_c"] >= absorber["hot_water_in_min_c"], f"{hhmm}: absorber source temperature")
                need(absorber["id"] + " generator" in circuits["engine_ht"]["to"], f"{hhmm}: absorber source connection")
                need(not out_at(status, "condenser_water", hhmm), f"{hhmm}: condenser circuit outage")
            absorption_heat += output / absorber["cop"]
            ac_aux += output * absorber["auxiliary_kwe_per_kw"]
        phe = ht - absorption_heat
        need(phe >= -EPS, f"{hhmm}: absorber cannot burn boiler heat or LT heat")
        phe_units = set(circuits["engine_ht"]["to"]) & set(circuits["lthw"]["from"])
        if not any(not out_at(status, u, hhmm) for u in phe_units):
            need(abs(phe) <= EPS, f"{hhmm}: PHE unavailable")
        balance = phe + boiler_heat - float(row["heat_kw"]) - circuits["lthw"]["loss_kw"]
        heat_errors.append(abs(balance))
        need(abs(balance) <= EPS, f"{hhmm}: HT/LTHW equality, residual {balance}")
        need(not out_at(status, "lthw", hhmm), f"{hhmm}: LTHW outage")
        need(abs(sum(period["chillers_kw"].values()) - float(row["cooling_kw"])) <= EPS, f"{hhmm}: cooling balance")
        for chiller in plant["electric_chillers"]:
            output = period["chillers_kw"][chiller["id"]]
            limit = 0.0 if out_at(status, chiller["id"], hhmm) else chiller["max_kw"]
            need(math.isfinite(output) and -EPS <= output <= limit + EPS, f"{hhmm}: {chiller['id']} rating/outage")
        imported, exported, pv = (period[key] for key in ("import_kw", "export_kw", "pv_kw"))
        need(all(math.isfinite(x) and x >= -EPS for x in (imported, exported, pv)), f"{hhmm}: finite nonnegative exchanges")
        need(min(imported, exported) <= EPS, f"{hhmm}: simultaneous import and export")
        need(exported <= electricity["export_limit_kw"] + EPS, f"{hhmm}: export capacity")
        pv_limit = min(float(wx["pv_kw"]), plant["pv"]["inverter_ac_kw"])
        if out_at(status, plant["pv"]["id"], hhmm):
            pv_limit = 0.
        need(pv <= pv_limit + EPS, f"{hhmm}: PV forecast, inverter and outage")
        pv_curtailed += max(0., pv_limit - pv) * 0.5
        compressor = gross_power + pv + imported - exported - float(row["electricity_kw"]) - gen_aux - ac_aux

        def compressor_at(temp):
            return sum(period["chillers_kw"][ch["id"]] / interp(temp, ch["cop_by_condenser_entering_c"])
                       for ch in plant["electric_chillers"])

        warm = max([cold] + [ch["cop_by_condenser_entering_c"][-1][0] for ch in plant["electric_chillers"]])
        if "variable speed" not in tower["fans"]:
            need(cold <= base + EPS, f"{hhmm}: cannot warm fixed-fan tower")
            warm = cold
        low_w, high_w = compressor_at(cold), compressor_at(warm)
        need(low_w - EPS <= compressor <= high_w + EPS,
             f"{hhmm}: shared condenser COP/electric balance {compressor} outside [{low_w},{high_w}]")
        left, right = cold, warm
        for _ in range(70):
            mid = (left + right) / 2
            if compressor_at(mid) < compressor:
                left = mid
            else:
                right = mid
        temperature = cold if abs(compressor - low_w) <= EPS else (left + right) / 2
        electric_errors.append(abs(compressor - compressor_at(temperature)))
        temperatures.append(temperature)
        warm_extra.append(max(0., temperature - cold))
        cells = sum(not out_at(status, cell, hhmm) for cell in tower["cells"])
        if out_at(status, "condenser_water", hhmm):
            cells = 0
        rejection = float(row["cooling_kw"]) + compressor + absorption_heat
        tower_margin = cells * interp(wb, tower["heat_rejection_kw_per_cell_by_wet_bulb_c"]) - rejection
        tower_margins.append(tower_margin)
        need(tower_margin >= -EPS, f"{hhmm}: tower rejection overload {-tower_margin}")
        grid_margin = electricity["import_capacity_kva"] - math.hypot(imported, reactive)
        grid_margins.append(grid_margin)
        need(grid_margin >= -EPS, f"{hhmm}: import kVA overload {-grid_margin}")
        need(period["grid_ok"] is True, f"{hhmm}: grid_ok must agree with feasible dispatch")
        bands = electricity["import_rates_p_per_kwh"]["weekend" if stamp.weekday() in (5, 6) else "weekday"]
        rate = next(b["rate"] for b in bands if minutes(b["from"]) <= minutes(hhmm) < minutes(b["to"])) / 100
        cost = 0.5 * (gas * gas_tariff["rate_p_per_kwh"] / 100 + upkeep + imported * rate
                      - exported * electricity["export_rate_p_per_kwh"] / 100) + start_cost
        cost_errors.append(abs(cost - period["cost_gbp"]))
        gas_errors.append(abs(0.5 * gas - period["gas_kwh"]))
        need(cost_errors[-1] <= EPS, f"{hhmm}: independently reconstructed bill")
        need(gas_errors[-1] <= EPS, f"{hhmm}: independently reconstructed billed gas")
        period_costs.append(cost)
        period_gas.append(0.5 * gas)

    summary = plan["summary"]
    need(set(summary) == {"cost_gbp", "gas_kwh", "import_kwh", "export_kwh", "engine_starts", "grid_ok"}, "summary schema")
    need(abs(summary["cost_gbp"] - math.fsum(period_costs)) <= EPS, "summary cost")
    need(abs(summary["gas_kwh"] - math.fsum(period_gas)) <= EPS, "summary gas")
    for kind in ("import", "export"):
        need(abs(summary[kind + "_kwh"] - 0.5 * math.fsum(p[kind + "_kw"] for p in plan["periods"])) <= EPS,
             f"summary {kind}")
    need(summary["engine_starts"] == starts, "summary starts including midnight")
    need(summary["grid_ok"] is True, "summary grid flag")
    if failures:
        raise AssertionError("\n".join(failures))
    return {
        "passed": True, "periods": len(plan["periods"]), "cost_gbp": math.fsum(period_costs),
        "gas_kwh": math.fsum(period_gas), "engine_starts": starts,
        "max_heat_balance_error_kw": max(heat_errors),
        "max_electric_balance_error_kw": max(electric_errors),
        "max_period_cost_error_gbp": max(cost_errors),
        "max_period_gas_error_kwh": max(gas_errors),
        "minimum_tower_margin_kw": min(tower_margins),
        "minimum_import_margin_kva": min(grid_margins),
        "condenser_temperature_range_c": [min(temperatures), max(temperatures)],
        "maximum_warming_above_required_minimum_c": max(warm_extra),
        "pv_curtailed_kwh": pv_curtailed,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    report = check_plan(args.data, args.plan)
    serialized = json.dumps(report, indent=2) + "\n"
    if args.report:
        Path(args.report).write_text(serialized)
    print(serialized, end="")


if __name__ == "__main__":
    main()
