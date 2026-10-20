"""Reproducible independent regression, adversarial and generated-witness checks.

Only the visible app data are used as the fixed plant/supply source. Every other
input is built here. No production module is imported. Run with the target Python:

    python checks/run_checks.py

All generated inputs, plans and reports stay in this delivery's experiments/ tree.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import random
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from audit import check_plan, interp, minutes, out_at
from oracle import solve_oracle

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
EXPERIMENTS = ROOT / "experiments"
PLANT = json.loads((APP / "data/plant.json").read_text())
SUPPLY = json.loads((APP / "data/supply.json").read_text())


def array(value):
    return [value(t) if callable(value) else (value[t] if isinstance(value, list) else value) for t in range(48)]


def create_day(name, *, date="2026-07-21", offset=60, running=(), outages=(), shuffled=False,
               elec=1000., q=220., heat=700., cool=750., wb=19., pv=0.):
    folder = EXPERIMENTS / name / "data"
    folder.mkdir(parents=True, exist_ok=True)
    for filename in ("plant.json", "supply.json"):
        shutil.copyfile(APP / "data" / filename, folder / filename)
    status = {"date": date, "running_at_midnight": list(running), "outages": list(outages)}
    (folder / "status.json").write_text(json.dumps(status, indent=2) + "\n")
    values = {k: array(v) for k, v in {"e": elec, "q": q, "h": heat, "c": cool, "wb": wb, "pv": pv}.items()}
    first = datetime.fromisoformat(date).replace(tzinfo=timezone(timedelta(minutes=offset)))
    demand, forecast = [], []
    for t in range(48):
        stamp = first + timedelta(minutes=30 * t)
        demand.append({"period_start": stamp.isoformat(timespec="minutes"),
                       "electricity_kw": values["e"][t], "reactive_kvar": values["q"][t],
                       "heat_kw": values["h"][t], "cooling_kw": values["c"][t]})
        forecast.append({"time_utc": stamp.astimezone(timezone.utc).isoformat(timespec="minutes").replace("+00:00", "Z"),
                         "dry_bulb_c": values["wb"][t] + 5., "wet_bulb_c": values["wb"][t], "pv_kw": values["pv"][t]})
    # Neighbouring dates have deliberately different forecasts. A positional or
    # calendar-date join cannot accidentally pass these fixtures.
    for t in list(range(-24, 0)) + list(range(48, 72)):
        stamp = first + timedelta(minutes=30 * t)
        forecast.append({"time_utc": stamp.astimezone(timezone.utc).isoformat(timespec="minutes").replace("+00:00", "Z"),
                         "dry_bulb_c": 36., "wet_bulb_c": 29., "pv_kw": 279.})
    if shuffled:
        random.Random(197).shuffle(demand)
        random.Random(613).shuffle(forecast)
    for filename, rows in (("demand.csv", demand), ("weather.csv", forecast)):
        with (folder / filename).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    return folder


def outage(unit, start="00:00", end="24:00"):
    return {"unit": unit, "from": start, "to": end}


def run_cli(folder, name, *, feasible=True, repeat=False):
    output = EXPERIMENTS / name / "plan.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "11"}
    begin = time.monotonic()
    result = subprocess.run([sys.executable, str(APP / "dispatch.py"), "--data", str(folder), "--output", str(output)],
                            text=True, capture_output=True, timeout=120, env=env)
    seconds = time.monotonic() - begin
    if not feasible:
        assert result.returncode != 0 and not output.exists(), (name, "infeasible input incorrectly accepted")
        assert "no feasible loading" in result.stderr, (name, result.stderr)
        return {"name": name, "passed": True, "expected_infeasible": True, "seconds": seconds, "diagnostic": result.stderr.strip()}
    assert result.returncode == 0, (name, result.stderr)
    report = check_plan(folder, output)
    report.update({"name": name, "seconds": seconds})
    if repeat:
        original = output.read_bytes()
        for seed in (37, 211):
            env["PYTHONHASHSEED"] = str(seed)
            again = subprocess.run([sys.executable, str(APP / "dispatch.py"), "--data", str(folder), "--output", str(output)],
                                   text=True, capture_output=True, timeout=120, env=env)
            assert again.returncode == 0 and output.read_bytes() == original, (name, "nondeterministic output", again.stderr)
        report["deterministic_across_three_fresh_processes"] = True
        report["plan_sha256"] = hashlib.sha256(original).hexdigest()
    return report


def oracle_compare(folder, name, report):
    certificate, oracle_plan = solve_oracle(folder)
    case_dir = EXPERIMENTS / name
    (case_dir / "oracle.json").write_text(json.dumps(certificate, indent=2) + "\n")
    assert certificate["feasible"] == (not report.get("expected_infeasible", False)), name
    if certificate["feasible"]:
        oracle_path = case_dir / "oracle-plan.json"
        oracle_path.write_text(json.dumps(oracle_plan, indent=1) + "\n")
        check_plan(folder, oracle_path)
        difference = abs(certificate["cost_gbp"] - report["cost_gbp"])
        assert difference < 2e-4, (name, "oracle objective disagreement", difference)
        report["oracle_cost_difference_gbp"] = difference
        report["oracle_relative_mip_gap"] = certificate["relative_mip_gap"]
        report["oracle_circle_cuts"] = certificate["circle_cuts"]
    else:
        report["independent_oracle_proved_infeasible"] = True


def create_witness_day(seed):
    """Construct a complete feasible dispatch first, then derive its demand.

    The optimizer must find an audited plan no more expensive than this witness.
    Outputs span engine segments, leading/lagging reactive power, solar clipping,
    warm/cold weather and cooling equipment outages. This exercises feasibility
    without presuming what the optimizer's commitment decisions should be.
    """
    rng = random.Random(seed)
    name = f"witness_{seed}"
    chosen = ["GE1", "GE2", "EC1", "EC2", "AC1", "CT2", "PV1", "B2"]
    outages = []
    for unit in chosen:
        if rng.random() < .65:
            start = rng.randrange(0, 40)
            end = min(48, start + rng.randrange(2, 9))
            outages.append(outage(unit, f"{start // 2:02d}:{30 * (start % 2):02d}",
                                 "24:00" if end == 48 else f"{end // 2:02d}:{30 * (end % 2):02d}"))
    initial = {e["id"] for e in PLANT["engines"] if rng.random() < .5}
    status = {"running_at_midnight": list(initial), "outages": outages}
    arrays = {key: [] for key in ("elec", "q", "heat", "cool", "wb", "pv")}
    periods = []
    previous, nstarts = initial, 0
    date = "2026-08-15" if seed % 2 else "2026-08-17"
    local_date = datetime.fromisoformat(date)
    for t in range(48):
        hhmm = f"{t // 2:02d}:{30 * (t % 2):02d}"
        up = lambda unit: not out_at(status, unit, hhmm)
        wb = rng.uniform(10., 29.)
        p, qgen, ht, fuel, aux, upkeep = {}, 0., 0., 0., 0., 0.
        running = set()
        startup = 0.
        for engine in PLANT["engines"]:
            power = rng.uniform(engine["part_load"][0]["kwe"], engine["rated_kwe"]) if up(engine["id"]) and rng.random() < .68 else 0.
            p[engine["id"]] = power
            if power:
                running.add(engine["id"])
                ht += interp(power, [(v["kwe"], v["ht_heat_kw"]) for v in engine["part_load"]])
                fuel += 1.108 * interp(power, [(v["kwe"], v["fuel_kw"]) for v in engine["part_load"]])
                aux += engine["auxiliary_kwe"]
                if engine["id"] not in previous:
                    nstarts += 1
                    startup += engine["start_cost_gbp"]
            qgen += power * math.sqrt(1 / engine["generator"]["power_factor"] ** 2 - 1)
            upkeep += power * engine["maintenance_gbp_per_mwhe"] / 1000
        previous = running
        absorber = rng.uniform(0., min(400., ht * .71)) if up("AC1") else 0.
        cools = {"EC1": rng.uniform(0., 350.) if up("EC1") else 0.,
                 "EC2": rng.uniform(0., 250.) if up("EC2") else 0., "AC1": absorber}
        cold = max(wb + 4., 21., 22. if absorber else 21.)
        temperature = rng.uniform(cold, max(cold, 34.))
        compressor = sum(cools[ch["id"]] / interp(temperature, ch["cop_by_condenser_entering_c"]) for ch in PLANT["electric_chillers"])
        rejection = sum(cools.values()) + compressor + absorber / .71
        tower_capacity = (1 + int(up("CT2"))) * interp(wb, PLANT["cooling_towers"]["heat_rejection_kw_per_cell_by_wet_bulb_c"])
        if rejection > .9 * tower_capacity:
            factor = .9 * tower_capacity / rejection
            cools = {key: amount * factor for key, amount in cools.items()}
            compressor *= factor
            absorber = cools["AC1"]
        b = {"B1": rng.uniform(150., 1500.), "B2": rng.uniform(0., 650.) if up("B2") else 0.}
        heat = ht - absorber / .71 + sum(b.values()) - 75.
        for boiler in PLANT["boilers"]:
            fuel += b[boiler["id"]] / boiler["efficiency"]
        forecast_pv = max(0., math.sin(math.pi * (t - 10) / 30)) * rng.uniform(250., 550.) if 10 <= t <= 40 else 0.
        pv = rng.uniform(.4, 1.) * min(forecast_pv, 280.) if up("PV1") else 0.
        qnet = rng.uniform(-1000., 1000.)
        import_limit = math.sqrt(1220. ** 2 - qnet ** 2)
        grid = rng.uniform(.15, .95) * import_limit
        if sum(p.values()) > 650 and rng.random() < .25:
            grid = -rng.uniform(0., 220.)
        demand = sum(p.values()) + pv + grid - aux - compressor - .022 * absorber
        if demand < 0:
            grid += 10. - demand
            demand = 10.
            assert grid <= import_limit
        imported, exported = max(grid, 0.), max(-grid, 0.)
        bands = SUPPLY["electricity"]["import_rates_p_per_kwh"]["weekend" if local_date.weekday() >= 5 else "weekday"]
        rate = next(v["rate"] for v in bands if minutes(v["from"]) <= minutes(hhmm) < minutes(v["to"])) / 100
        cost = .5 * (fuel * .0435 + upkeep + imported * rate - exported * .12) + startup
        periods.append({"start": hhmm, "engines_kwe": p, "boilers_kw": b, "chillers_kw": cools,
                        "pv_kw": pv, "import_kw": imported, "export_kw": exported,
                        "gas_kwh": fuel * .5, "cost_gbp": cost, "grid_ok": True})
        for key, val in {"elec": demand, "q": qnet + qgen, "heat": heat, "cool": sum(cools.values()), "wb": wb, "pv": forecast_pv}.items():
            arrays[key].append(val)
    folder = create_day(name, date=date, offset=[0, 60, 330, -420][seed % 4], running=sorted(initial), outages=outages,
                        shuffled=True, **arrays)
    summary = {"cost_gbp": math.fsum(p["cost_gbp"] for p in periods), "gas_kwh": math.fsum(p["gas_kwh"] for p in periods),
               "import_kwh": .5 * math.fsum(p["import_kw"] for p in periods),
               "export_kwh": .5 * math.fsum(p["export_kw"] for p in periods), "engine_starts": nstarts, "grid_ok": True}
    path = EXPERIMENTS / name / "witness-plan.json"
    path.write_text(json.dumps({"date": date, "periods": periods, "summary": summary}, indent=1) + "\n")
    check_plan(folder, path)
    return name, folder, summary["cost_gbp"]


def main():
    EXPERIMENTS.mkdir(exist_ok=True)
    report = []
    cases = []

    def case(name, **kwargs):
        cases.append((name, create_day(name, **kwargs), True))

    def infeasible(name, **kwargs):
        cases.append((name, create_day(name, **kwargs), False))

    case("saturday_east_utc", date="2026-08-15", offset=330, shuffled=True,
         wb=lambda t: 12 + 5 * math.sin(t / 10), elec=lambda t: 950 + 90 * math.sin(t / 7),
         heat=1000, cool=550, pv=lambda t: max(0, 420 * math.sin((t - 10) * math.pi / 28)),
         outages=[outage("B1", "12:15", "14:45"), outage("EC1", "08:15", "10:45"),
                  outage("CT2", "16:00", "19:00"), outage("PV1", "12:00", "14:00")])
    case("monday_east_utc", date="2026-08-17", offset=60, shuffled=True, heat=900, cool=600)
    case("sunday_west_utc", date="2026-08-16", offset=-420, shuffled=True, heat=800, cool=550)
    case("far_east_utc", date="2026-11-11", offset=840, shuffled=True, wb=10, heat=800, cool=450)
    case("boiler_priority", elec=500, heat=2700, cool=1000,
         outages=[outage("GE1"), outage("GE2")], running=["GE1"])
    case("no_arbitrage", elec=100, q=50, heat=0, cool=0,
         outages=[outage("GE1"), outage("GE2"), outage("CT1"), outage("CT2")])
    case("pv_surplus", elec=20, heat=0, cool=0, q=10,
         pv=lambda t: 450 if 10 <= t < 38 else 0, outages=[outage("GE1"), outage("GE2")])
    case("pv_inverter_cap", elec=500, cool=0, heat=200,
         pv=lambda t: 450 if 10 <= t < 38 else 0, outages=[outage("GE1"), outage("GE2")])
    case("boiler_outages", elec=1100, heat=1200, cool=700,
         outages=[outage("B1"), outage("B2", "10:00", "17:00")])
    case("chiller_outages", elec=1000, heat=150, cool=600,
         outages=[outage("EC1", "00:00", "06:00"), outage("EC2", "06:00", "14:00"), outage("EC1", "12:00", "14:00")])
    case("absorber_outage", elec=1100, heat=650, cool=900, outages=[outage("AC1")])
    case("tower_binding", elec=1000, heat=600, cool=1100, wb=22, outages=[outage("CT2")])
    case("grid_positive_q", elec=1600, q=900, heat=1000, cool=400, outages=[outage("GE1")])
    case("grid_positive_q_initial_on", elec=1600, q=900, heat=1000, cool=400,
         outages=[outage("GE1")], running=["GE2"])
    case("grid_negative_q", elec=1500, q=-600, heat=1000, cool=400, outages=[outage("GE1")])
    case("reactive_export", elec=100, q=1300, heat=700, cool=200, outages=[outage("GE1")], running=["GE2"])
    case("outage_overlap", running=["GE2"], outages=[
         outage("GE1", "07:15", "07:45"), outage("B1", "01:15", "01:45"),
         outage("EC1", "02:15", "02:45"), outage("AC1", "03:15", "03:45"),
         outage("CT1", "04:15", "04:45"), outage("PV1", "05:15", "05:45"),
         outage("PHE1", "14:15", "14:45"), outage("LT radiator 1", "16:15", "16:45"),
         outage("LT radiator 2", "17:15", "17:45"), outage("GE2", "23:15", "00:45")])
    case("cold_absorption_only", elec=1100, heat=400, cool=500, wb=8,
         outages=[outage("EC1"), outage("EC2")])
    case("warm_frontier", elec=300, heat=760, cool=100, wb=14, q=100, running=["GE1"],
         outages=[outage("GE2"), outage("AC1"), outage("EC2")])
    case("startup_continuity", elec=lambda t: (90 if t % 2 == 0 else 300) if t < 14 else 900,
         heat=500, cool=200, wb=18, q=120, running=["GE2"], outages=[outage("GE1"), outage("EC2")])
    case("ge1_segments", elec=1300, heat=lambda t: [760., 897.5, 1035., 1125., 1215.][t % 5], cool=300,
         wb=lambda t: [-5., 14., 16., 18., 20., 22., 30., 40.][t % 8], running=["GE1"],
         outages=[outage("GE2"), outage("B1"), outage("B2"), outage("AC1")])
    case("ge2_segments", elec=1000, heat=lambda t: [515., 610., 705., 765., 825.][t % 5], cool=500,
         running=["GE2"], outages=[outage("GE1"), outage("B1"), outage("B2"), outage("AC1")])
    case("phe_outage", elec=1000, heat=650, cool=800, outages=[outage("PHE1")])
    case("both_engines_forced", elec=2700, q=400, heat=1500, cool=1000, pv=150, running=["GE1", "GE2"])
    case("grid_corner_import", elec=math.sqrt(1220.**2 - 900.**2), q=900, heat=0, cool=0,
         outages=[outage("GE1"), outage("GE2")])
    case("grid_corner_reactive", elec=0, q=1220, heat=0, cool=0,
         outages=[outage("GE1"), outage("GE2"), outage("CT1"), outage("CT2")])
    infeasible("infeasible_heat_sink", elec=1400, q=100, heat=0, cool=0)
    infeasible("infeasible_cooling_capacity", elec=1000, heat=700, cool=801,
               outages=[outage("EC1"), outage("EC2")])
    infeasible("infeasible_towers", cool=1, outages=[outage("CT1"), outage("CT2")])
    infeasible("infeasible_boiler_capacity", elec=500, heat=2001, cool=0,
               outages=[outage("GE1"), outage("GE2"), outage("B2")])
    infeasible("infeasible_reactive_capacity", q=2000, heat=2000, cool=1000)
    infeasible("infeasible_just_above_connection", elec=math.sqrt(1220.**2 - 900.**2) + .001,
               q=900, heat=0, cool=0, outages=[outage("GE1"), outage("GE2")])

    visible = run_cli(APP / "data", "visible", repeat=True)
    oracle_compare(APP / "data", "visible", visible)
    report.append(visible)
    print(f"visible: PASS, {visible['seconds']:.3f} s, independent global optimum verified", flush=True)
    oracle_cases = {"saturday_east_utc", "grid_positive_q", "grid_negative_q", "warm_frontier",
                    "startup_continuity", "tower_binding", "infeasible_heat_sink", "infeasible_reactive_capacity"}
    repeat_cases = {"saturday_east_utc", "grid_positive_q", "warm_frontier", "startup_continuity"}
    for name, folder, feasible in cases:
        result = run_cli(folder, name, feasible=feasible, repeat=name in repeat_cases)
        if name in oracle_cases:
            oracle_compare(folder, name, result)
        report.append(result)
        print(f"{name}: PASS, {result['seconds']:.3f} s", flush=True)
    by_name = {r["name"]: r for r in report}
    assert abs(by_name["grid_positive_q"]["cost_gbp"] - by_name["grid_positive_q_initial_on"]["cost_gbp"] - 27.) < 1e-5
    assert by_name["grid_positive_q"]["engine_starts"] == 1
    assert by_name["grid_positive_q_initial_on"]["engine_starts"] == 0
    assert by_name["warm_frontier"]["maximum_warming_above_required_minimum_c"] > 4.
    assert by_name["startup_continuity"]["engine_starts"] == 0
    assert by_name["tower_binding"]["minimum_tower_margin_kw"] < 1e-5
    assert by_name["grid_positive_q"]["minimum_import_margin_kva"] < 1e-5
    assert by_name["grid_negative_q"]["minimum_import_margin_kva"] < 1e-5
    for name, engine, values in (("ge1_segments", "GE1", [600., 750., 900., 1050., 1200.]),
                                 ("ge2_segments", "GE2", [400., 500., 600., 700., 800.])):
        plan = json.loads((EXPERIMENTS / name / "plan.json").read_text())
        assert all(abs(p["engines_kwe"][engine] - values[t % 5]) < 1e-6 for t, p in enumerate(plan["periods"]))
    no_arb = json.loads((EXPERIMENTS / "no_arbitrage/plan.json").read_text())
    assert all(p["export_kw"] == 0 and abs(p["import_kw"] - 100) < 1e-7 for p in no_arb["periods"])
    bplan = json.loads((EXPERIMENTS / "boiler_priority/plan.json").read_text())
    assert all(abs(p["boilers_kw"]["B1"] - 2000.) < 1e-7 and abs(p["boilers_kw"]["B2"] - 775.) < 1e-7 for p in bplan["periods"])

    for seed in range(710, 722):
        name, folder, witness_cost = create_witness_day(seed)
        result = run_cli(folder, name, repeat=seed == 710)
        assert result["cost_gbp"] <= witness_cost + 1e-5, (name, "worse than feasible constructed witness")
        result["witness_cost_gbp"] = witness_cost
        result["improvement_over_witness_gbp"] = witness_cost - result["cost_gbp"]
        if seed == 710:
            oracle_compare(folder, name, result)
        report.append(result)
        print(f"{name}: PASS, {result['seconds']:.3f} s, witness beaten by GBP {witness_cost-result['cost_gbp']:.3f}", flush=True)
    total = {"passed": True, "cases": len(report), "feasible_cases": sum(not r.get("expected_infeasible", False) for r in report),
             "infeasible_cases": sum(r.get("expected_infeasible", False) for r in report),
             "maximum_cli_seconds": max(r["seconds"] for r in report),
             "minimum_cli_seconds": min(r["seconds"] for r in report),
             "global_oracle_comparisons": sum("oracle_cost_difference_gbp" in r for r in report),
             "global_infeasibility_proofs": sum(r.get("independent_oracle_proved_infeasible", False) for r in report),
             "results": report}
    (EXPERIMENTS / "check-results.json").write_text(json.dumps(total, indent=2) + "\n")
    print(json.dumps({k: v for k, v in total.items() if k != "results"}, indent=2), flush=True)


if __name__ == "__main__":
    main()
