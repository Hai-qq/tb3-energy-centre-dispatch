"""Self-generated daily inputs with unchanged plant.json and supply.json."""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import random
import shutil

from check_plan import available, interp, read_input

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "app" / "data"


def write_case(name, demands, weather, status, shuffle=False):
    folder = ROOT / "experiments" / "cases" / name
    folder.mkdir(parents=True, exist_ok=True)
    for filename in ("plant.json", "supply.json"):
        shutil.copyfile(DATA / filename, folder / filename)
    (folder / "status.json").write_text(json.dumps(status, indent=2) + "\n")
    if shuffle:
        random.Random(7701).shuffle(demands)
        random.Random(7702).shuffle(weather)
    for filename, rows in (("demand.csv", demands), ("weather.csv", weather)):
        with (folder / filename).open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    return folder


def clock(t):
    return f"{t // 2:02d}:{30 * (t % 2):02d}"


def constant_case(name, electricity=1000, reactive=300, heat=900, cooling=500,
                  wet_bulb=20, pv=0, outages=(), running=(), date="2026-07-27",
                  offset=1, shuffle=False):
    first = datetime.fromisoformat(date).replace(tzinfo=timezone(timedelta(hours=offset)))
    status = {"date": date, "running_at_midnight": list(running), "outages": list(outages)}
    demands, weather = [], []
    for t in range(48):
        dt = first + timedelta(minutes=30 * t)
        pick = lambda v: v(t) if callable(v) else v
        demands.append({"period_start": dt.isoformat(timespec="minutes"),
                        "electricity_kw": pick(electricity), "reactive_kvar": pick(reactive),
                        "heat_kw": pick(heat), "cooling_kw": pick(cooling)})
        wb, solar = pick(wet_bulb), pick(pv)
        weather.append({"time_utc": dt.astimezone(timezone.utc).isoformat(timespec="minutes"),
                        "dry_bulb_c": wb + 7, "wet_bulb_c": wb, "pv_kw": solar})
    # Additional times make a UTC-date slice incorrect even when its row count is 48.
    for t in (-2, -1, 48, 49):
        dt = first + timedelta(minutes=30 * t)
        weather.append({"time_utc": dt.astimezone(timezone.utc).isoformat(timespec="minutes"),
                        "dry_bulb_c": 50, "wet_bulb_c": 40, "pv_kw": 0})
    return write_case(name, demands, weather, status, shuffle)


def shifted_visible(name, date, offset):
    plant, supply, old_status, demand, weather = read_input(DATA)
    first = datetime.fromisoformat(date).replace(tzinfo=timezone(timedelta(hours=offset)))
    new_demand, new_weather = [], []
    for t, row in enumerate(demand):
        old = datetime.fromisoformat(row["period_start"])
        dt = first + timedelta(minutes=30 * t)
        new_demand.append({**row, "period_start": dt.isoformat(timespec="minutes")})
        wx = weather[old.astimezone(timezone.utc)]
        new_weather.append({**wx, "time_utc": dt.astimezone(timezone.utc).isoformat(timespec="minutes")})
    for t in (-4, -3, -2, -1, 48, 49, 50, 51):
        dt = first + timedelta(minutes=30 * t)
        new_weather.append({"time_utc": dt.astimezone(timezone.utc).isoformat(timespec="minutes"),
                            "dry_bulb_c": 45, "wet_bulb_c": 35, "pv_kw": 280})
    status = {**old_status, "date": date}
    return write_case(name, new_demand, new_weather, status, shuffle=True)


def random_witness_case(seed):
    plant, supply, _, _, _ = read_input(DATA)
    rng = random.Random(seed)
    first = datetime(2026, 8, 3, tzinfo=timezone(timedelta(hours=1)))
    demands, weather, outages, witnesses = [], [], [], []
    for t in range(48):
        wb = rng.uniform(5, 28)
        pv = rng.uniform(0, 280) if 10 <= t <= 39 else 0.0
        off = set()
        if rng.random() < .28:
            off.add(rng.choice(["GE1", "GE2", "B1", "B2", "EC1", "EC2", "AC1", "CT1", "PV1"]))
        for unit in sorted(off):
            outages.append({"unit": unit, "from": clock(t), "to": clock(t + 1)})
        p = []
        for e in plant["engines"]:
            value = 0.0 if e["id"] in off or rng.random() < .3 else rng.uniform(e["part_load"][0]["kwe"], e["rated_kwe"])
            p.append(value)
        ht = gross = aux = qgen = 0.0
        for e, value in zip(plant["engines"], p):
            if value:
                ht += interp([(a["kwe"], a["ht_heat_kw"]) for a in e["part_load"]], value)
                gross += interp([(a["kwe"], a["fuel_kw"]) for a in e["part_load"]], value) * supply["gas"]["gross_to_net_cv_ratio"]
                aux += e["auxiliary_kwe"]
                qgen += value * math.tan(math.acos(e["generator"]["power_factor"]))
        a = 0.0 if "AC1" in off else min(rng.uniform(0, 650), max(0, ht - 150) * .71)
        water = max(wb + 4, 21, 22 if a > 0 else 0)
        towers = (1 if "CT1" in off else 2) * interp(plant["cooling_towers"]["heat_rejection_kw_per_cell_by_wet_bulb_c"], wb)
        abs_duty = a * (1 + 1 / .71 + .022)
        if abs_duty > .6 * towers:
            a *= .6 * towers / abs_duty
        remaining = .9 * towers - a * (1 + 1 / .71 + .022)
        ec = []
        power = 0.0
        for ch in plant["electric_chillers"]:
            cop = interp(ch["cop_by_condenser_entering_c"], water)
            cap = min(ch["max_kw"], max(0, remaining) / (1 + 1 / cop))
            value = 0 if ch["id"] in off else rng.uniform(0, max(0, cap))
            ec.append(value)
            remaining -= value * (1 + 1 / cop)
            power += value / cop
        b = []
        gas_left = 5900 - gross
        for boiler in plant["boilers"]:
            cap = min(boiler["max_kw"], max(0, gas_left) * boiler["efficiency"])
            value = 0 if boiler["id"] in off else rng.uniform(0, min(1400, cap))
            b.append(value)
            gas_left -= value / boiler["efficiency"]
        if ht + sum(b) - a / .71 < 130:
            # A boiler can supply this small shortfall; at most one unit is out.
            k = 0 if "B1" not in off else 1
            extra = 150 - (ht + sum(b) - a / .71)
            b[k] += extra
        if "PV1" in off:
            actual_pv = 0.0
        else:
            actual_pv = pv
        power += .022 * a
        qgrid = rng.uniform(max(-100, -qgen), 700)
        upper = min(1000, math.sqrt(1220**2 - qgrid**2) - 35)
        lower = max(200, 70 + aux + power - sum(p) - actual_pv)
        grid = rng.uniform(lower, upper)
        site_e = sum(p) + actual_pv + grid - aux - power
        site_h = ht + sum(b) - a / .71 - 75
        dt = first + timedelta(minutes=30 * t)
        demands.append({"period_start": dt.isoformat(timespec="minutes"),
                        "electricity_kw": round(site_e, 7), "reactive_kvar": round(qgrid + qgen, 7),
                        "heat_kw": round(site_h, 7), "cooling_kw": round(sum(ec) + a, 7)})
        weather.append({"time_utc": dt.astimezone(timezone.utc).isoformat(timespec="minutes"),
                        "dry_bulb_c": wb + 5, "wet_bulb_c": wb, "pv_kw": pv})
        witnesses.append({"start": clock(t), "engines_kwe": p, "boilers_kw": b,
                          "electric_chillers_kw": ec, "absorption_kw": a,
                          "grid_kw": grid, "grid_kvar": qgrid, "pv_kw": actual_pv,
                          "condenser_entering_c": water})
    status = {"date": first.date().isoformat(), "running_at_midnight": ["GE1"], "outages": outages}
    folder = write_case(f"random_witness_{seed}", demands, weather, status, True)
    (folder / "feasible-witness.json").write_text(json.dumps(witnesses, indent=2) + "\n")
    return folder


def create_cases():
    outage = lambda unit, a="00:00", b="24:00": {"unit": unit, "from": a, "to": b}
    cases = {
        "visible": DATA,
        "monday_plus_one": shifted_visible("monday_plus_one", "2026-07-27", 1),
        "monday_plus_five_half": shifted_visible("monday_plus_five_half", "2026-07-27", 5.5),
        "saturday_plus_one": shifted_visible("saturday_plus_one", "2026-07-25", 1),
        "sunday_minus_five": shifted_visible("sunday_minus_five", "2026-07-26", -5),
        "winter_zero_offset": shifted_visible("winter_zero_offset", "2026-12-07", 0),
        "all_engines_out": constant_case("all_engines_out", electricity=800, reactive=400, heat=1200,
            cooling=700, wet_bulb=10, pv=lambda t: 200 if 14 <= t < 34 else 0,
            outages=[outage("GE1"), outage("GE2"), outage("CT1"), outage("EC1", "12:00", "14:00"),
                     outage("B1", "12:00", "14:00"), outage("PV1", "06:00", "07:00")]),
        "no_ht_dump": constant_case("no_ht_dump", electricity=900, heat=100, cooling=0,
            wet_bulb=15, running=["GE1"]),
        "high_reactive": constant_case("high_reactive", electricity=2260, reactive=1820,
            heat=1650, cooling=450, wet_bulb=22, running=["GE1", "GE2"]),
        "grid_circle": constant_case("grid_circle", electricity=1850, reactive=600, heat=900,
            cooling=1000, wet_bulb=22, running=["GE2"], outages=[outage("GE1")]),
        "negative_reactive": constant_case("negative_reactive", electricity=100, reactive=-1210,
            heat=1300, cooling=0, wet_bulb=20),
        "gas_binding": constant_case("gas_binding", electricity=2650, reactive=600, heat=3400,
            cooling=200, wet_bulb=20, pv=50, running=["GE1", "GE2"]),
        "tower_binding": constant_case("tower_binding", electricity=1500, reactive=250, heat=1000,
            cooling=1200, wet_bulb=22, running=["GE1"], outages=[outage("CT1")]),
        "electric_chiller_out": constant_case("electric_chiller_out", electricity=2000, reactive=300,
            heat=400, cooling=1600, wet_bulb=22, outages=[outage("EC1")]),
        "cold_absorption": constant_case("cold_absorption", electricity=1850, reactive=250, heat=350,
            cooling=800, wet_bulb=5, outages=[outage("GE2")]),
        "warmer_water_export": constant_case("warmer_water_export", electricity=10, reactive=50, heat=515,
            cooling=500, wet_bulb=10, running=["GE2"], outages=[outage("GE1"), outage("AC1")]),
        "phe_radiator_outages": constant_case("phe_radiator_outages", electricity=1850, reactive=200,
            heat=650, cooling=700, wet_bulb=15, outages=[outage("PHE1"),
            outage("LT radiator 2", "12:00", "14:00")]),
        "pv_curtailment": constant_case("pv_curtailment", electricity=10, reactive=20, heat=0,
            cooling=0, wet_bulb=14, pv=lambda t: 280 if 20 <= t < 30 else 0),
        "table_clamping": constant_case("table_clamping", electricity=800, reactive=100, heat=900,
            cooling=1000, wet_bulb=lambda t: -10 if t < 24 else 40,
            outages=[outage("GE1"), outage("GE2")]),
        "startup_bridge": constant_case("startup_bridge", electricity=lambda t: 140 if t % 2 == 0 else 180,
            reactive=100, heat=900, cooling=0, wet_bulb=20, running=["GE2"], outages=[outage("GE1")]),
        "startup_midnight_off": constant_case("startup_midnight_off", electricity=lambda t: 140 if t % 2 == 0 else 180,
            reactive=100, heat=900, cooling=0, wet_bulb=20, running=[], outages=[outage("GE1")]),
        "partial_and_overnight_outages": constant_case("partial_and_overnight_outages", electricity=850,
            heat=1200, cooling=500, wet_bulb=20, outages=[outage("GE1", "03:15", "04:15"),
            outage("EC1", "09:15", "10:15"), outage("B1", "23:00", "01:00"),
            outage("ge1_lt", "16:00", "17:00")]),
    }
    for seed in (307, 891, 2026):
        cases[f"random_witness_{seed}"] = random_witness_case(seed)
    infeasible = {
        "gas_capacity_infeasible": constant_case("gas_capacity_infeasible", electricity=2800,
            reactive=400, heat=3700, cooling=200, wet_bulb=20, running=["GE1", "GE2"]),
        "gas_entry_out": constant_case("gas_entry_out", electricity=800, heat=1000, cooling=0,
            outages=[outage("GAS-IN")]),
        "all_towers_out": constant_case("all_towers_out", electricity=800, heat=900, cooling=500,
            outages=[outage("CT1"), outage("CT2")]),
        "reactive_unrecoverable": constant_case("reactive_unrecoverable", electricity=800, reactive=1300,
            heat=900, cooling=0, outages=[outage("GE1"), outage("GE2")]),
    }
    return cases, infeasible
