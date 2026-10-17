"""Independent, self-generated validation of the visible dispatch specification.

No supplied test suite, reference solution, or external benchmark is used.
Run with the exact task interpreter from the ecd-blind directory.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import itertools
import json
import math
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "app"))
from planner.data import load_day
from planner.optimize import SOLVER_STATS, _available, _period, plan_day
from planner.plant import Plant
from planner.tariff import Tariff

BASE = load_day(ROOT / "app" / "data")
RAW_PLANT = copy.deepcopy(BASE.plant)
RAW_SUPPLY = copy.deepcopy(BASE.supply)


def scenario(*, n=1, elec=500, heat=500, cool=0, kvar=200, wb=18, pv=0,
             off=(), initial=("GE1",)):
    day = copy.deepcopy(BASE)
    day.starts = BASE.starts[:n]
    day.status["running_at_midnight"] = list(initial)
    day.status["outages"] = [
        {"unit": unit, "from": "00:00", "to": "24:00"} for unit in off
    ]
    for field, value in [
        ("elec", elec), ("heat", heat), ("cool", cool), ("kvar", kvar),
        ("wet_bulb", wb), ("pv", pv), ("dry_bulb", np.asarray(wb) + 5),
    ]:
        setattr(day, field, np.broadcast_to(value, (n,)).astype(float).copy())
    return day


def run(day):
    return plan_day(day, Plant(day.plant), Tariff(day.supply, day.first_start))


def raw_available(day, unit, start):
    # Independently compare explicit half-hour instants with daily intervals.
    h, m = map(int, start.split(":"))
    left, right = 60 * h + m, 60 * h + m + 30
    for outage in day.status.get("outages", []):
        if outage["unit"] != unit:
            continue
        a = sum(v * w for v, w in zip(map(int, outage["from"].split(":")), (60, 1)))
        b = sum(v * w for v, w in zip(map(int, outage["to"].split(":")), (60, 1)))
        intervals = [(a, b)] if a <= b else [(a, 1440), (0, b)]
        for begin, end in intervals:
            if max(left, begin) < min(right, end):
                return False
    return True


def validate(day, rows, starts, tolerance=3e-6):
    """Reconstruct balances, costs and unit limits directly from raw input data."""
    plant, supply = day.plant, day.supply
    previous = set(day.status.get("running_at_midnight", []))
    actual_starts = 0
    worst = {"electric_kw": 0.0, "heat_kw": 0.0, "cool_kw": 0.0,
             "gas_kwh": 0.0, "cost_gbp": 0.0, "grid_excess_kva": 0.0}
    for t, r in enumerate(rows):
        on = {unit for unit, value in r["engines_kwe"].items() if value > 1e-5}
        starts_now = on - previous
        actual_starts += len(starts_now)
        ht = lt = generated = auxiliary = gas_kw = maintenance = q_gen = 0.0
        start_cost = 0.0
        for engine in plant["engines"]:
            unit = engine["id"]
            p = r["engines_kwe"][unit]
            assert p >= -tolerance
            if p > 1e-5:
                assert engine["part_load"][0]["kwe"] - tolerance <= p <= engine["rated_kwe"] + tolerance
                assert raw_available(day, unit, r["start"])
                for circuit in plant["heat_circuits"].values():
                    if f"{unit} intercooler" in circuit.get("from", []):
                        assert any(raw_available(day, node, r["start"]) for node in circuit["to"])
                points = engine["part_load"]
                powers = [point["kwe"] for point in points]
                ht += float(np.interp(p, powers, [point["ht_heat_kw"] for point in points]))
                lt += float(np.interp(p, powers, [point["lt_heat_kw"] for point in points]))
                fuel = float(np.interp(p, powers, [point["fuel_kw"] for point in points]))
                if engine["fuel_basis"] == "net CV":
                    fuel *= supply["gas"]["gross_to_net_cv_ratio"]
                gas_kw += fuel
                auxiliary += engine["auxiliary_kwe"]
                assert p / engine["generator"]["power_factor"] <= engine["generator"]["rated_kva"] + tolerance
            generated += p
            q_gen += p * math.sqrt(1 / engine["generator"]["power_factor"]**2 - 1)
            maintenance += p * engine["maintenance_gbp_per_mwhe"] / 1000
            if unit in starts_now:
                start_cost += engine["start_cost_gbp"]
        boiler_heat = 0.0
        for boiler in plant["boilers"]:
            b = r["boilers_kw"][boiler["id"]]
            assert -tolerance <= b <= boiler["max_kw"] + tolerance
            if not raw_available(day, boiler["id"], r["start"]):
                assert abs(b) <= tolerance
            fuel = b / boiler["efficiency"]
            if boiler["efficiency_basis"] == "net CV":
                fuel *= supply["gas"]["gross_to_net_cv_ratio"]
            gas_kw += fuel
            boiler_heat += b
        towers = plant["cooling_towers"]
        temperature = max(float(day.wet_bulb[t]) + towers["approach_k"],
                          towers["min_leaving_water_c"])
        for absorber in plant["absorption_chillers"]:
            if r["chillers_kw"][absorber["id"]] > 1e-5:
                temperature = max(temperature, absorber["cooling_water_in_min_c"])
        absorbed_heat = cooling = chiller_power = rejected_heat = 0.0
        for chiller in plant["electric_chillers"]:
            value = r["chillers_kw"][chiller["id"]]
            assert -tolerance <= value <= chiller["max_kw"] + tolerance
            if not raw_available(day, chiller["id"], r["start"]):
                assert abs(value) <= tolerance
            table = chiller["cop_by_condenser_entering_c"]
            cop = float(np.interp(temperature, [p[0] for p in table], [p[1] for p in table]))
            chiller_power += value / cop
            cooling += value
            rejected_heat += value + value / cop
        for absorber in plant["absorption_chillers"]:
            value = r["chillers_kw"][absorber["id"]]
            assert -tolerance <= value <= absorber["max_kw"] + tolerance
            if not raw_available(day, absorber["id"], r["start"]):
                assert abs(value) <= tolerance
            if value > 1e-5:
                assert plant["heat_circuits"]["engine_ht"]["flow_c"] >= absorber["hot_water_in_min_c"]
            heat = value / absorber["cop"]
            power = value * absorber["auxiliary_kwe_per_kw"]
            chiller_power += power
            cooling += value
            absorbed_heat += heat
            rejected_heat += value + heat + power
        useful_heat = ht - absorbed_heat
        assert useful_heat >= -tolerance, "boiler or LT heat has driven absorption"
        if not raw_available(day, "PHE1", r["start"]):
            assert abs(useful_heat) <= tolerance
        table = towers["heat_rejection_kw_per_cell_by_wet_bulb_c"]
        capacity = sum(raw_available(day, unit, r["start"]) for unit in towers["cells"])
        capacity *= float(np.interp(day.wet_bulb[t], [p[0] for p in table], [p[1] for p in table]))
        assert rejected_heat <= capacity + tolerance, (t, rejected_heat, capacity)
        pv_cap = min(max(float(day.pv[t]), 0), plant["pv"]["inverter_ac_kw"])
        if not raw_available(day, plant["pv"]["id"], r["start"]):
            pv_cap = 0
        assert -tolerance <= r["pv_kw"] <= pv_cap + tolerance
        assert r["import_kw"] >= -tolerance and r["export_kw"] >= -tolerance
        assert min(r["import_kw"], r["export_kw"]) <= tolerance
        assert r["export_kw"] <= supply["electricity"]["export_limit_kw"] + tolerance
        apparent = math.hypot(r["import_kw"], day.kvar[t] - q_gen)
        assert apparent <= supply["electricity"]["import_capacity_kva"] + tolerance
        assert r["grid_ok"]
        e_err = abs(generated + r["pv_kw"] + r["import_kw"] - r["export_kw"]
                    - day.elec[t] - auxiliary - chiller_power)
        h_err = abs(useful_heat + boiler_heat - day.heat[t]
                    - plant["heat_circuits"]["lthw"]["loss_kw"])
        c_err = abs(cooling - day.cool[t])
        gas_err = abs(r["gas_kwh"] - gas_kw * 0.5)
        minute = int(r["start"][:2]) * 60 + int(r["start"][3:])
        bands = supply["electricity"]["import_rates_p_per_kwh"][
            "weekend" if day.first_start.weekday() >= 5 else "weekday"
        ]
        rate = next(band["rate"] / 100 for band in bands
                    if int(band["from"][:2]) * 60 + int(band["from"][3:]) <= minute
                    < int(band["to"][:2]) * 60 + int(band["to"][3:]))
        expected_cost = 0.5 * (gas_kw * supply["gas"]["rate_p_per_kwh"] / 100
                               + maintenance + rate * r["import_kw"]
                               - r["export_kw"] * supply["electricity"]["export_rate_p_per_kwh"] / 100)
        expected_cost += start_cost
        cost_err = abs(r["cost_gbp"] - expected_cost)
        for key, value in [("electric_kw", e_err), ("heat_kw", h_err),
                           ("cool_kw", c_err), ("gas_kwh", gas_err),
                           ("cost_gbp", cost_err),
                           ("grid_excess_kva", max(0, apparent - supply["electricity"]["import_capacity_kva"]))]:
            worst[key] = max(worst[key], value)
            assert value <= tolerance, (t, key, value)
        previous = on
    assert actual_starts == starts
    return worst


def expect_infeasible(day):
    try:
        run(day)
    except RuntimeError as exc:
        assert "no feasible" in str(exc), str(exc)
    else:
        raise AssertionError("an independently infeasible plant configuration was accepted")


def test_visible_and_determinism():
    started = time.perf_counter()
    rows, starts = run(BASE)
    elapsed = time.perf_counter() - started
    errors = validate(BASE, rows, starts)
    stats = SOLVER_STATS.copy()
    outputs = []
    with tempfile.TemporaryDirectory(prefix="selfcheck-", dir=ROOT) as folder:
        for j in range(2):
            output = Path(folder) / f"plan-{j}.json"
            subprocess.run([
                sys.executable, str(ROOT / "app" / "dispatch.py"), "--data",
                str(ROOT / "app" / "data"), "--output", str(output),
            ], check=True)
            outputs.append(output.read_bytes())
        assert outputs[0] == outputs[1]
        rounded = json.loads(outputs[0])
        rounded_errors = validate(BASE, rounded["periods"], rounded["summary"]["engine_starts"],
                                  tolerance=0.006)
    return {
        "elapsed_s": elapsed, "stats": stats, "raw_max_errors": errors,
        "serialized_max_errors": rounded_errors,
        "output_sha256": hashlib.sha256(outputs[0]).hexdigest(),
        "cost_gbp": sum(r["cost_gbp"] for r in rows),
        "gas_kwh": sum(r["gas_kwh"] for r in rows),
        "engine_starts": starts,
    }


def test_interpolation_and_billing():
    p, t = Plant(RAW_PLANT), Tariff(RAW_SUPPLY, BASE.first_start)
    e = p.engines[0]
    assert e.fuel(900) == 2275 and e.ht_heat(900) == 1110 and e.lt_heat(900) == 158
    assert e.fuel(750) == 1990 and e.ht_heat(750) == 972.5
    assert e.fuel(1050) == 2572.5 and e.ht_heat(1050) == 1200
    assert e.fuel(0) == e.ht_heat(0) == e.lt_heat(0) == 0
    assert e.fuel(1300) == 2870
    assert abs(t.billed_gas(1000, "net CV") - 1108) < 1e-10
    assert t.billed_gas(1000, "gross CV") == 1000


def test_local_calendar_and_weather():
    weather = list(csv.DictReader((ROOT / "app" / "data" / "weather.csv").open()))
    lookup = {datetime.fromisoformat(r["time_utc"].replace("Z", "+00:00")): r for r in weather}
    for t in range(48):
        key = (BASE.first_start + timedelta(minutes=30*t)).astimezone(timezone.utc)
        assert BASE.wet_bulb[t] == float(lookup[key]["wet_bulb_c"])
        assert BASE.pv[t] == float(lookup[key]["pv_kw"])
    saturday = datetime.fromisoformat("2026-07-25T00:00+01:00")
    monday = datetime.fromisoformat("2026-07-27T00:00+01:00")
    assert Tariff(RAW_SUPPLY, saturday).weekend
    assert not Tariff(RAW_SUPPLY, monday).weekend
    assert Tariff(RAW_SUPPLY, saturday).import_rate("16:00") == 0.226
    assert Tariff(RAW_SUPPLY, monday).import_rate("16:00") == 0.415
    with tempfile.TemporaryDirectory(prefix="selfcheck-", dir=ROOT) as folder:
        folder = Path(folder)
        for name in ("plant", "supply"):
            (folder / f"{name}.json").write_text(json.dumps(getattr(BASE, name)))
        (folder / "status.json").write_text(json.dumps({
            "date": "2026-07-25", "running_at_midnight": [], "outages": [],
        }))
        with (folder / "demand.csv").open("w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["period_start","electricity_kw","reactive_kvar","heat_kw","cooling_kw"])
            for i in reversed(range(48)):
                writer.writerow([(saturday + timedelta(minutes=30*i)).isoformat(), 100+i, 50, 100, 0])
        with (folder / "weather.csv").open("w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["time_utc","dry_bulb_c","wet_bulb_c","pv_kw"])
            for i in reversed(range(48)):
                instant = (saturday + timedelta(minutes=30*i)).astimezone(timezone.utc)
                writer.writerow([instant.isoformat(), 20+i/100, 15+i/100, i])
        day = load_day(folder)
        assert day.starts == BASE.starts
        assert day.elec[0] == 100 and day.elec[-1] == 147
        assert day.wet_bulb[0] == 15 and day.wet_bulb[-1] == 15.47
        assert day.pv[0] == 0 and day.pv[-1] == 47


def test_conic_root():
    day = scenario(elec=900, heat=1800, kvar=-950, off=("GE2",))
    rows, starts = run(day)
    validate(day, rows, starts)
    k = math.sqrt(1 / 0.95**2 - 1)
    roots = np.roots([1+k*k, -2*(932 + (-950)*k), 932**2 + 950**2 - 1220**2])
    expected = float(max(roots))
    assert 600 < expected < 900
    actual = rows[0]["engines_kwe"]["GE1"]
    assert abs(actual - expected) < 1e-5, (actual, expected)
    return {"closed_form_kwe": expected, "optimized_kwe": actual}


def test_startup_dynamic_program():
    day = scenario(n=3, elec=[2100,350,2100], heat=[800,100,800], cool=500, off=("GE2",))
    rows, starts = run(day)
    validate(day, rows, starts)
    p, tariff = Plant(day.plant), Tariff(day.supply, day.first_start)
    states = list(itertools.product((False, True), repeat=2))
    table = [[_period(day,p,tariff,t,on)[0] for on in states] for t in range(3)]
    assert table[1][states.index((False,False))] < table[1][states.index((True,False))]
    best = math.inf
    for path in itertools.product(range(4), repeat=3):
        cost, prev = 0.0, (True,False)
        for period,state in enumerate(path):
            cur = states[state]
            cost += table[period][state]
            cost += sum(e.start_cost for e,old,new in zip(p.engines,prev,cur) if new and not old)
            prev = cur
        best = min(best,cost)
    assert abs(sum(r["cost_gbp"] for r in rows) - best) < 1e-7
    assert starts == 0
    assert all(r["engines_kwe"]["GE1"] > 0 for r in rows)
    day.status["running_at_midnight"] = []
    new_rows, new_starts = run(day)
    validate(day,new_rows,new_starts)
    assert new_starts == 1
    assert abs(new_rows[0]["cost_gbp"] - rows[0]["cost_gbp"] - 38) < 1e-7
    return {"optimal_cost_gbp": best, "middle_period_penalty_gbp":
            table[1][states.index((True,False))] - table[1][states.index((False,False))]}


def test_condenser_regimes():
    day = scenario(elec=1400, heat=500, cool=1200, wb=10, off=("GE2",))
    rows, starts = run(day)
    validate(day, rows, starts)
    row = rows[0]
    assert row["chillers_kw"]["AC1"] > 0 and row["chillers_kw"]["EC1"] > 0
    expected = 1400 + 32 + row["chillers_kw"]["AC1"]*0.022 + row["chillers_kw"]["EC1"]/6.5 - row["engines_kwe"]["GE1"]
    assert abs(row["import_kw"] - expected) < 1e-7
    day = scenario(elec=500, heat=100, cool=100, wb=10, off=("GE1","GE2"), initial=())
    rows, starts = run(day)
    validate(day, rows, starts)
    assert abs(rows[0]["import_kw"] - (500 + 100/6.725)) < 1e-7


def test_outages_and_heat_routing():
    day = scenario(elec=500, heat=1000, off=("GE1","GE2","B1"), initial=())
    rows, starts = run(day)
    validate(day, rows, starts)
    assert rows[0]["boilers_kw"]["B1"] == 0
    assert abs(rows[0]["gas_kwh"] - 0.5*1075/0.83) < 1e-7
    day = scenario(cool=900, wb=22, off=("GE1","GE2","EC1"), initial=())
    rows, starts = run(day)
    validate(day, rows, starts)
    assert rows[0]["chillers_kw"]["EC1"] == 0
    assert rows[0]["chillers_kw"]["EC2"] == 900
    assert abs(rows[0]["import_kw"] - (500+900/4.6)) < 1e-7
    day = scenario(cool=1210, wb=22, off=("GE1","GE2","CT1"), initial=())
    expect_infeasible(day)
    day = scenario(elec=1800,heat=1800,cool=0,off=("CT1","CT2"))
    rows,starts = run(day)
    validate(day,rows,starts)
    assert any(v > 0 for v in rows[0]["engines_kwe"].values())
    day = scenario(elec=500,heat=1000,off=("PHE1",))
    rows,starts = run(day)
    validate(day,rows,starts)
    assert all(v == 0 for v in rows[0]["engines_kwe"].values())
    day = scenario(elec=500,heat=1800,off=("GE1 LT radiator",))
    rows,starts = run(day)
    validate(day,rows,starts)
    assert rows[0]["engines_kwe"]["GE1"] == 0
    expect_infeasible(scenario(elec=1400,heat=0,cool=0))
    expect_infeasible(scenario(elec=500,heat=1000,cool=2500,off=("GE1","GE2")))
    day = scenario()
    day.status["outages"] = [{"unit":"B1","from":"07:15","to":"08:15"}]
    assert not _available(day,"B1","07:00")
    assert not _available(day,"B1","08:00")
    assert _available(day,"B1","08:30")
    day.status["outages"] = [{"unit":"B1","from":"23:45","to":"00:15"}]
    assert not _available(day,"B1","23:30")
    assert not _available(day,"B1","00:00")
    assert _available(day,"B1","00:30")


def test_pv_and_export():
    day = scenario(elec=0,heat=100,pv=500,kvar=0,off=("GE1","GE2"),initial=())
    rows,starts = run(day)
    validate(day,rows,starts)
    assert rows[0]["pv_kw"] == rows[0]["export_kw"] == 250
    day = scenario(elec=500,heat=100,pv=500,kvar=0,off=("GE1","GE2"),initial=())
    rows,starts = run(day)
    validate(day,rows,starts)
    assert rows[0]["pv_kw"] == 280
    assert rows[0]["import_kw"] == 220
    day.status["outages"].append({"unit":"PV1","from":"00:00","to":"24:00"})
    rows,starts = run(day)
    validate(day,rows,starts)
    assert rows[0]["pv_kw"] == 0
    assert rows[0]["import_kw"] == 500


def test_constructed_feasible_cases():
    """Construct 96 feasible operating points, then demand a no-dearer optimum."""
    rng = np.random.default_rng(20260721)
    worst_time, maximum_lp_calls, maximum_conic_iterations = 0.0, 0, 0
    for case in range(96):
        powers = [float(rng.uniform(e["part_load"][0]["kwe"], e["rated_kwe"]))
                  if rng.random() < 0.65 else 0.0 for e in RAW_PLANT["engines"]]
        wet_bulb = float(rng.uniform(9, 27))
        ht, gas, aux, maintenance = 0.0, 0.0, 0.0, 0.0
        for e, p in zip(RAW_PLANT["engines"], powers):
            if p == 0:
                continue
            table = e["part_load"]
            xp = [point["kwe"] for point in table]
            ht += float(np.interp(p, xp, [point["ht_heat_kw"] for point in table]))
            gas += float(np.interp(p, xp, [point["fuel_kw"] for point in table])) * 1.108
            aux += e["auxiliary_kwe"]
            maintenance += p * e["maintenance_gbp_per_mwhe"] / 1000
        cells = 1 if rng.random() < 0.25 else 2
        table = RAW_PLANT["cooling_towers"]["heat_rejection_kw_per_cell_by_wet_bulb_c"]
        capacity = cells * float(np.interp(wet_bulb, [v[0] for v in table], [v[1] for v in table]))
        ac_coefficient = 1 + 1/0.71 + 0.022
        absorption = float(rng.uniform(0, min(800, ht*0.71, 0.5*capacity/ac_coefficient)))
        temperature = max(wet_bulb+4, 21, 22 if absorption > 0 else 21)
        remainder = capacity - ac_coefficient*absorption
        electric = []
        electric_power = 0.0
        for chiller in RAW_PLANT["electric_chillers"]:
            curve = chiller["cop_by_condenser_entering_c"]
            cop = float(np.interp(temperature, [p[0] for p in curve], [p[1] for p in curve]))
            value = float(rng.uniform(0, min(chiller["max_kw"], remainder/(1+1/cop))))
            electric.append(value)
            electric_power += value/cop
            remainder -= value*(1+1/cop)
        boiler = [float(rng.uniform(75, 1000)), float(rng.uniform(0, 300))]
        for b, value in zip(RAW_PLANT["boilers"], boiler):
            gas += value / b["efficiency"]
        pv = float(rng.uniform(0, 280))
        grid_import = float(rng.uniform(300, 1000))
        site_electric = sum(powers) + pv + grid_import - aux - electric_power - 0.022*absorption
        assert site_electric >= 0
        residual_kvar = float(rng.choice((-1, 1))*rng.uniform(0.70, 0.999999)
                              *math.sqrt(1220**2-grid_import**2))
        kvar = residual_kvar + sum(powers)*math.sqrt(1/0.95**2-1)
        site_heat = ht - absorption/0.71 + sum(boiler) - 75
        initial = tuple(e["id"] for e,p in zip(RAW_PLANT["engines"],powers) if p > 0)
        outages = ("CT1",) if cells == 1 else ()
        day = scenario(elec=site_electric, heat=site_heat, cool=sum(electric)+absorption,
                       kvar=kvar, wb=wet_bulb, pv=pv, initial=initial, off=outages)
        feasible_cost = 0.5*(gas*0.0435 + maintenance + grid_import*0.138)
        before = time.perf_counter()
        rows, starts = run(day)
        worst_time = max(worst_time, time.perf_counter()-before)
        validate(day, rows, starts)
        assert rows[0]["cost_gbp"] <= feasible_cost + 1e-5, (case, rows[0]["cost_gbp"], feasible_cost)
        maximum_lp_calls = max(maximum_lp_calls, SOLVER_STATS["lp_calls"])
        maximum_conic_iterations = max(maximum_conic_iterations, SOLVER_STATS["max_conic_iterations"])
    return {"constructed_cases": 96, "worst_period_s": worst_time,
            "maximum_lp_calls": maximum_lp_calls,
            "maximum_conic_iterations": maximum_conic_iterations}


def main():
    result = {}
    tests = [value for name,value in globals().items() if name.startswith("test_")]
    started = time.perf_counter()
    for test in tests:
        before = time.perf_counter()
        detail = test()
        result[test.__name__] = {"passed":True,"elapsed_s":time.perf_counter()-before,"detail":detail}
        print(test.__name__, "PASS", flush=True)
    result["total_elapsed_s"] = time.perf_counter()-started
    (ROOT / "SELF_CHECK_RESULTS.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))


if __name__ == "__main__":
    main()
