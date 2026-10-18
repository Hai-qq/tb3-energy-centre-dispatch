"""Derive the unreported heat flows, water setpoint and meter loading of a plan.

The established plan schema is unchanged. This review helper reconstructs these
quantities from its unit outputs, grid exchange and the supplied input data.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path

from check_plan import check_plan, interp, read_input, available


def explain(folder, path):
    check_plan(folder, path)
    plant, supply, status, demand, weather = read_input(folder)
    plan = json.loads(Path(path).read_text())
    details = []
    for row, p in zip(demand, plan["periods"]):
        date_time = datetime.fromisoformat(row["period_start"])
        wx = weather[date_time.astimezone(timezone.utc)]
        q_generation = sum(p["engines_kwe"][e["id"]] * math.tan(math.acos(e["generator"]["power_factor"]))
                           for e in plant["engines"])
        fixed_aux = sum(e["auxiliary_kwe"] for e in plant["engines"] if p["engines_kwe"][e["id"]] > 1e-8)
        abs_aux = sum(p["chillers_kw"][a["id"]] * a["auxiliary_kwe_per_kw"] for a in plant["absorption_chillers"])
        ac_heat = sum(p["chillers_kw"][a["id"]] / a["cop"] for a in plant["absorption_chillers"])
        compression = (sum(p["engines_kwe"].values()) + p["pv_kw"] + p["import_kw"] - p["export_kw"]
                       - float(row["electricity_kw"]) - fixed_aux - abs_aux)
        base = max(float(wx["wet_bulb_c"]) + plant["cooling_towers"]["approach_k"],
                   plant["cooling_towers"]["min_leaving_water_c"])
        required = max([base] + [a["cooling_water_in_min_c"] for a in plant["absorption_chillers"]
                                 if p["chillers_kw"][a["id"]] > 1e-8])
        low = required
        high = max([low] + [c["cop_by_condenser_entering_c"][-1][0] for c in plant["electric_chillers"]])
        power = lambda temp: sum(p["chillers_kw"][c["id"]] / interp(c["cop_by_condenser_entering_c"], temp)
                                 for c in plant["electric_chillers"])
        if compression > power(low) + 1e-8:
            for _ in range(75):
                middle = (low + high)/2
                if power(middle) < compression:
                    low = middle
                else:
                    high = middle
            selected = (low + high)/2
        else:
            selected = low
        ht = 0.0
        lt = {}
        gross = {}
        for e in plant["engines"]:
            value = p["engines_kwe"][e["id"]]
            recover = lambda key: interp([(point["kwe"], point[key]) for point in e["part_load"]], value) if value > 1e-8 else 0.0
            ht += recover("ht_heat_kw")
            lt[e["id"]] = recover("lt_heat_kw")
            gross[e["id"]] = recover("fuel_kw") * (supply["gas"]["gross_to_net_cv_ratio"] if e["fuel_basis"] == "net CV" else 1)
        for b in plant["boilers"]:
            gross[b["id"]] = p["boilers_kw"][b["id"]] / b["efficiency"] * (
                supply["gas"]["gross_to_net_cv_ratio"] if b["efficiency_basis"] == "net CV" else 1)
        entry = supply["gas"]["entry"]
        entry_kw = sum(gross[unit] for unit in entry["supplies"])
        cells = sum(available(status, cell, p["start"]) for cell in plant["cooling_towers"]["cells"])
        capacity = cells * interp(plant["cooling_towers"]["heat_rejection_kw_per_cell_by_wet_bulb_c"], float(wx["wet_bulb_c"]))
        details.append({
            "start": p["start"],
            "forecast_utc": date_time.astimezone(timezone.utc).isoformat(),
            "minimum_condenser_entering_c": required,
            "selected_condenser_entering_c": selected,
            "electric_chiller_power_kw": compression,
            "engine_ht_kw": ht,
            "absorption_generator_heat_kw": ac_heat,
            "phe_heat_to_lthw_kw": ht - ac_heat,
            "engine_lt_radiator_heat_kw": lt,
            "tower_rejection_kw": float(row["cooling_kw"]) + compression + ac_heat + abs_aux,
            "available_tower_rejection_kw": capacity,
            "net_grid_kvar": float(row["reactive_kvar"]) - q_generation,
            "grid_kva": math.hypot(p["import_kw"] - p["export_kw"], float(row["reactive_kvar"]) - q_generation),
            "gas_entry_gross_kw": entry_kw,
            "gas_entry_standard_m3_per_hour": entry_kw * 3.6 / entry["gross_calorific_value_mj_per_standard_m3"],
        })
    return {"date": plan["date"], "periods": details}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--plan", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(explain(args.data, args.plan), indent=2) + "\n")


if __name__ == "__main__":
    main()
