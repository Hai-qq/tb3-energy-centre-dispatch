"""Independent physical and billing audit of a published dispatch JSON.

This module deliberately does not import planner or use the optimizer's matrices.
It reconstructs interpolation, UTC joins, heat routes, generator vars, gas
metering, startup transitions and invoice totals directly from the input files.
"""

from __future__ import annotations

import argparse
import bisect
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path


TOL = 2e-5


def interp(points, value):
    if value <= points[0][0]:
        return float(points[0][1])
    if value >= points[-1][0]:
        return float(points[-1][1])
    i = bisect.bisect_right([p[0] for p in points], value) - 1
    x0, y0 = points[i]
    x1, y1 = points[i + 1]
    return y0 + (y1 - y0) * (value - x0) / (x1 - x0)


def minute(s):
    h, m = map(int, s.split(":"))
    return 60 * h + m


def available(status, unit, start):
    lo = minute(start)
    for o in status.get("outages", []):
        if o["unit"] != unit:
            continue
        a, b = minute(o["from"]), minute(o["to"])
        intervals = [(a, b)] if a <= b else [(a, 1440), (0, b)]
        for x, y in intervals:
            if x < lo + 30 and y > lo:
                return False
    return True


def read_input(folder):
    folder = Path(folder)
    plant = json.loads((folder / "plant.json").read_text())
    supply = json.loads((folder / "supply.json").read_text())
    status = json.loads((folder / "status.json").read_text())
    with (folder / "demand.csv").open() as fh:
        demand = sorted(csv.DictReader(fh), key=lambda r: datetime.fromisoformat(r["period_start"]))
    with (folder / "weather.csv").open() as fh:
        weather = {datetime.fromisoformat(r["time_utc"]).astimezone(timezone.utc): r
                   for r in csv.DictReader(fh)}
    return plant, supply, status, demand, weather


def check_plan(folder, plan_path):
    plant, supply, status, demand, weather = read_input(folder)
    plan = json.loads(Path(plan_path).read_text()) if not isinstance(plan_path, dict) else plan_path
    errors = []
    metrics = {"max_electricity_residual_kw": 0.0, "max_heat_residual_kw": 0.0,
               "max_cooling_residual_kw": 0.0, "max_gas_residual_kwh": 0.0,
               "max_cost_residual_gbp": 0.0, "max_grid_kva": 0.0,
               "max_gas_standard_m3_per_hour": 0.0, "min_tower_headroom_kw": math.inf,
               "pv_curtailment_kwh": 0.0, "warm_water_periods": 0,
               "water_above_absorber_minimum_periods": 0, "maximum_condenser_entering_c": 0.0}
    def require(condition, message):
        if not condition:
            errors.append(message)
    def close(observed, expected, label, metric=None):
        residual = abs(observed - expected)
        if metric:
            metrics[metric] = max(metrics[metric], residual)
        require(residual <= TOL, f"{label}: {observed:.12g} != {expected:.12g}")
    def finite_nonnegative(value, label):
        require(isinstance(value, (int, float)) and math.isfinite(value) and value >= -TOL,
                f"{label}: invalid/non-finite/negative output {value!r}")

    require(set(plan) == {"date", "periods", "summary"}, "top-level schema changed")
    require(plan["date"] == status["date"], "wrong plan date")
    require(len(plan["periods"]) == len(demand) == 48, "wrong number of periods")
    gas_supply = supply["gas"]
    ratio = gas_supply["gross_to_net_cv_ratio"]
    electricity = supply["electricity"]
    initial = set(status.get("running_at_midnight", []))
    total_gas = total_cost = total_import = total_export = 0.0
    total_starts = 0
    for index, (row, p) in enumerate(zip(demand, plan["periods"])):
        instant = datetime.fromisoformat(row["period_start"])
        start = instant.strftime("%H:%M")
        label = f"{start}"
        require(p["start"] == start, f"{label}: wrong local start")
        require(set(p) == {"start", "engines_kwe", "boilers_kw", "chillers_kw", "pv_kw",
                           "import_kw", "export_kw", "gas_kwh", "cost_gbp", "grid_ok"},
                f"{label}: period schema changed")
        require(set(p["engines_kwe"]) == {e["id"] for e in plant["engines"]}, f"{label}: engine IDs")
        require(set(p["boilers_kw"]) == {b["id"] for b in plant["boilers"]}, f"{label}: boiler IDs")
        require(set(p["chillers_kw"]) == {c["id"] for c in plant["electric_chillers"] + plant["absorption_chillers"]},
                f"{label}: chiller IDs")
        for key in ("engines_kwe", "boilers_kw", "chillers_kw"):
            for unit, value in p[key].items():
                finite_nonnegative(value, f"{label} {unit}")
                require(available(status, unit, start) or value <= TOL, f"{label}: {unit} during outage")
        for key in ("pv_kw", "import_kw", "export_kw", "gas_kwh"):
            finite_nonnegative(p[key], f"{label} {key}")
        require(math.isfinite(p["cost_gbp"]), f"{label}: non-finite cost")

        wx = weather[instant.astimezone(timezone.utc)]
        tower = plant["cooling_towers"]
        base_temp = max(float(wx["wet_bulb_c"]) + tower["approach_k"], tower["min_leaving_water_c"])
        water_temp = base_temp
        for a in plant["absorption_chillers"]:
            if p["chillers_kw"][a["id"]] > 1e-8:
                water_temp = max(water_temp, a["cooling_water_in_min_c"])
                require(plant["heat_circuits"]["engine_ht"]["flow_c"] >= a["hot_water_in_min_c"],
                        f"{label}: insufficient absorption driving temperature")
        if water_temp > base_temp:
            metrics["warm_water_periods"] += 1
            require(tower.get("fans") == "variable speed", f"{label}: cannot regulate warmer tower water")
        current, engine_kw, reactive_generation, ht, aux, maintenance = set(), 0.0, 0.0, 0.0, 0.0, 0.0
        gross_by_unit = {}
        for e in plant["engines"]:
            value = p["engines_kwe"][e["id"]]
            if value <= TOL:
                gross_by_unit[e["id"]] = 0.0
                continue
            current.add(e["id"])
            require(e["part_load"][0]["kwe"] - TOL <= value <= e["rated_kwe"] + TOL,
                    f"{label}: {e['id']} outside minimum/rated output")
            pf = e["generator"]["power_factor"]
            require(value / pf <= e["generator"]["rated_kva"] + TOL,
                    f"{label}: generator kVA rating")
            reactive_generation += value * math.tan(math.acos(pf))
            engine_kw += value
            aux += e["auxiliary_kwe"]
            maintenance += value * e["maintenance_gbp_per_mwhe"] / 1000
            points = e["part_load"]
            fuel = interp([(x["kwe"], x["fuel_kw"]) for x in points], value)
            ht += interp([(x["kwe"], x["ht_heat_kw"]) for x in points], value)
            gross_by_unit[e["id"]] = fuel * ratio if e["fuel_basis"] == "net CV" else fuel
            require(available(status, "engine_ht", start), f"{label}: HT circuit out")
            for circuit_id, circuit in plant["heat_circuits"].items():
                if e["id"] + " intercooler" in circuit.get("from", []):
                    require(available(status, circuit_id, start), f"{label}: LT circuit out")
                    for radiator in circuit.get("to", []):
                        require(available(status, radiator, start), f"{label}: LT radiator out")
        boiler_heat = 0.0
        for b in plant["boilers"]:
            value = p["boilers_kw"][b["id"]]
            require(value <= b["max_kw"] + TOL, f"{label}: boiler rating")
            boiler_heat += value
            fuel = value / b["efficiency"]
            gross_by_unit[b["id"]] = fuel * ratio if b["efficiency_basis"] == "net CV" else fuel
        cooling = 0.0
        abs_heat = 0.0
        abs_power = 0.0
        for ch in plant["electric_chillers"]:
            value = p["chillers_kw"][ch["id"]]
            require(value <= ch["max_kw"] + TOL, f"{label}: electric chiller rating")
            cooling += value
        for ch in plant["absorption_chillers"]:
            value = p["chillers_kw"][ch["id"]]
            require(value <= ch["max_kw"] + TOL, f"{label}: absorption chiller rating")
            abs_heat += value / ch["cop"]
            abs_power += value * ch["auxiliary_kwe_per_kw"]
            cooling += value
        # Reconstruct compressor electricity from the published meter balance,
        # then independently find a *single* shared condenser-water temperature.
        # The variable-speed towers may run warmer when the export limit binds.
        observed_compressor = (engine_kw + p["pv_kw"] + p["import_kw"] - p["export_kw"]
                               - float(row["electricity_kw"]) - aux - abs_power)
        min_water = water_temp
        high_water = max([min_water] + [ch["cop_by_condenser_entering_c"][-1][0]
                                       for ch in plant["electric_chillers"]])
        if tower.get("fans") != "variable speed":
            high_water = min_water
        power_at = lambda temperature: sum(p["chillers_kw"][ch["id"]]
                            / interp(ch["cop_by_condenser_entering_c"], temperature)
                            for ch in plant["electric_chillers"])
        require(power_at(min_water) - TOL <= observed_compressor <= power_at(high_water) + TOL,
                f"{label}: compressor power cannot be attained at a common water temperature")
        if observed_compressor > power_at(min_water) + 1e-8:
            low_water = min_water
            for _ in range(75):
                mid_water = (low_water + high_water) / 2
                if power_at(mid_water) < observed_compressor:
                    low_water = mid_water
                else:
                    high_water = mid_water
            water_temp = (low_water + high_water) / 2
        ec_power = power_at(water_temp)
        if water_temp > min_water + 1e-6:
            metrics["water_above_absorber_minimum_periods"] += 1
        metrics["maximum_condenser_entering_c"] = max(metrics["maximum_condenser_entering_c"], water_temp)
        close(cooling, float(row["cooling_kw"]), label + " cooling", "max_cooling_residual_kw")
        close(ht + boiler_heat, float(row["heat_kw"]) + plant["heat_circuits"]["lthw"]["loss_kw"] + abs_heat,
              label + " HT and building heat", "max_heat_residual_kw")
        require(ht >= abs_heat - TOL, f"{label}: boiler or LT heat routed to absorber")
        phe_ids = set(plant["heat_circuits"]["engine_ht"]["to"]) & set(plant["heat_circuits"]["lthw"]["from"])
        if not any(available(status, unit, start) for unit in phe_ids):
            close(ht, abs_heat, label + " PHE outage")
        if not available(status, "lthw", start):
            require(float(row["heat_kw"]) + plant["heat_circuits"]["lthw"]["loss_kw"] <= TOL,
                    f"{label}: building heat circuit unavailable")
        cells = sum(available(status, unit, start) for unit in tower["cells"])
        capacity = cells * interp(tower["heat_rejection_kw_per_cell_by_wet_bulb_c"], float(wx["wet_bulb_c"]))
        if not available(status, "condenser_water", start):
            capacity = 0.0
        rejection = cooling + ec_power + abs_heat + abs_power
        metrics["min_tower_headroom_kw"] = min(metrics["min_tower_headroom_kw"], capacity - rejection)
        require(rejection <= capacity + TOL, f"{label}: tower heat rejection exceeds available cells")
        pv_available = min(float(wx["pv_kw"]), plant["pv"]["inverter_ac_kw"])
        if not available(status, plant["pv"]["id"], start):
            pv_available = 0.0
        require(p["pv_kw"] <= pv_available + TOL, f"{label}: excessive PV or PV outage")
        metrics["pv_curtailment_kwh"] += 0.5 * (pv_available - p["pv_kw"])
        close(engine_kw + p["pv_kw"] + p["import_kw"] - p["export_kw"],
              float(row["electricity_kw"]) + aux + ec_power + abs_power,
              label + " electricity", "max_electricity_residual_kw")
        require(min(p["import_kw"], p["export_kw"]) <= TOL, f"{label}: simultaneous import/export")
        require(p["export_kw"] <= electricity["export_limit_kw"] + TOL, f"{label}: export limit")
        apparent = math.hypot(p["import_kw"] - p["export_kw"], float(row["reactive_kvar"]) - reactive_generation)
        metrics["max_grid_kva"] = max(metrics["max_grid_kva"], apparent)
        require(apparent <= electricity["import_capacity_kva"] + TOL, f"{label}: connection kVA limit")
        require(p["grid_ok"] is True, f"{label}: grid_ok inconsistent")
        gross_kw = sum(gross_by_unit.values())
        billed_kw = gross_kw if gas_supply["billing_basis"] == "gross CV" else gross_kw / ratio
        close(p["gas_kwh"], billed_kw * 0.5, label + " metered gas", "max_gas_residual_kwh")
        entry = gas_supply.get("entry")
        if entry:
            entry_kw = sum(gross_by_unit.get(unit, 0.0) for unit in entry["supplies"])
            volume = entry_kw * 3.6 / entry["gross_calorific_value_mj_per_standard_m3"]
            metrics["max_gas_standard_m3_per_hour"] = max(metrics["max_gas_standard_m3_per_hour"], volume)
            limit = entry["maximum_standard_m3_per_hour"] if available(status, entry["id"], start) else 0.0
            require(volume <= limit + TOL, f"{label}: gas entry standard-volume rate exceeded")
        bands = electricity["import_rates_p_per_kwh"]["weekend" if instant.weekday() >= 5 else "weekday"]
        matching = [b for b in bands if minute(b["from"]) <= minute(start) < minute(b["to"])]
        require(len(matching) == 1, f"{label}: tariff band")
        rate = matching[0]["rate"] / 100
        started = current - initial
        start_cost = sum(e["start_cost_gbp"] for e in plant["engines"] if e["id"] in started)
        cost = 0.5 * (billed_kw * gas_supply["rate_p_per_kwh"] / 100 + maintenance
                      + p["import_kw"] * rate - p["export_kw"] * electricity["export_rate_p_per_kwh"] / 100) + start_cost
        close(p["cost_gbp"], cost, label + " bill", "max_cost_residual_gbp")
        initial = current
        total_starts += len(started)
        total_cost += p["cost_gbp"]
        total_gas += p["gas_kwh"]
        total_import += p["import_kw"] * 0.5
        total_export += p["export_kw"] * 0.5
    summary = plan["summary"]
    require(set(summary) == {"cost_gbp", "gas_kwh", "import_kwh", "export_kwh", "engine_starts", "grid_ok"},
            "summary schema changed")
    for key, value in (("cost_gbp", total_cost), ("gas_kwh", total_gas),
                       ("import_kwh", total_import), ("export_kwh", total_export)):
        close(summary[key], value, "summary " + key)
    require(summary["engine_starts"] == total_starts, "summary startup count")
    require(summary["grid_ok"] is True, "summary grid flag")
    if errors:
        raise AssertionError("\n".join(errors))
    return {"valid": True, "periods": len(plan["periods"]), "summary": summary, "metrics": metrics}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--plan", type=Path, required=True)
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()
    result = check_plan(args.data, args.plan)
    serialized = json.dumps(result, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(serialized)
    print(serialized, end="")


if __name__ == "__main__":
    main()
