"""Independent, reproducible checks of the frozen v17 verifier's requirements.

Only this directory is written. Deliberately tests reference gaps as gaps, not as
candidate unfair failures of model submissions. Run with the project Python 3.13.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import shutil
import sys

import numpy as np
from scipy.stats import beta

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = ROOT / "archive/energy-centre-dispatch-v17"
spec = importlib.util.spec_from_file_location("fairness_frozen_reference", BASE / "tests/reference.py")
ref = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ref)
Day = ref.Day


def copied(name: str, day="visible", *, outages=None):
    target = HERE / "fixtures" / name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(BASE / "tests/days" / day, target)
    if outages is not None:
        status = json.loads((target / "status.json").read_text())
        status["outages"] = outages
        (target / "status.json").write_text(json.dumps(status, indent=2) + "\n")
    return target


def check_visibility():
    old = ROOT / "archive/energy-centre-dispatch-v8.1"
    paths = [Path("instruction.md")] + [p.relative_to(BASE) for p in (BASE / "environment").rglob("*")
                                       if p.is_file() and "__pycache__" not in p.parts]
    mismatches = [str(p) for p in paths if (BASE / p).read_bytes() != (old / p).read_bytes()]
    assert not mismatches
    comparison = {}
    for version in ("v8", "v8.1", "v16", "v17"):
        source = ROOT / "archive" / f"energy-centre-dispatch-{version}"
        comparison[version] = [str(p) for p in paths if (BASE/p).read_bytes() != (source/p).read_bytes()]
    return {"files_compared": len(paths), "mismatches": mismatches,
            "other_version_mismatches": comparison,
            "v17_reference_sha256": hashlib.sha256((BASE / "tests/reference.py").read_bytes()).hexdigest()}


def check_names():
    day = Day(BASE / "tests/days/visible")
    names = {p for c in day.plant["heat_circuits"].values() for p in c["from"] + c["to"]}
    missing = sorted(names - day.available.keys())
    assert missing == ["GE1 jacket water and exhaust", "GE2 jacket water and exhaust", "hospital buildings"]
    failures = {}
    for name in missing[:2]:
        folder = copied("named_" + name[:3], outages=[{"unit": name, "from": "10:00", "to": "11:00"}])
        try:
            Day(folder)
        except KeyError as ex:
            failures[name] = type(ex).__name__ + ": " + str(ex)
        else:
            raise AssertionError(name)
    return {"all_named_endpoints": sorted(names), "missing_from_v17_availability": missing,
            "literal_component_outage_failures": failures,
            "interpretation": "Do not treat hospital buildings as a component outage without specifying the changed demand."}


def check_outage_overlap_and_topology():
    dependencies = {"GE1": ["GE1 intercooler", "GE1 LT radiator"],
                    "GE2": ["GE2 intercooler", "GE2 LT radiator"],
                    "EC1": ["EC1 condenser"], "EC2": ["EC2 condenser"],
                    "AC1": ["AC1 generator", "AC1 absorber and condenser"]}
    rows = []
    for unit, parts in dependencies.items():
        for part in parts:
            folder = copied("part_" + part.replace(" ", "_"), outages=[
                {"unit": part, "from": "10:10", "to": "10:20"},
                {"unit": part, "from": "12:30", "to": "13:00"},
                {"unit": part, "from": "14:20", "to": "14:40"}])
            d = Day(folder)
            off = [d.clock[t] for t in np.flatnonzero(~d.available[unit])]
            assert off == [600, 750, 840, 870], (part, off)
            rows.append({"unit": unit, "part": part, "off_period_starts_minutes": off})
    folder = copied("union_idempotence", outages=[
        {"unit": "GE1", "from": "10:10", "to": "11:10"},
        {"unit": "GE1", "from": "10:50", "to": "11:20"}])
    d = Day(folder)
    assert [d.clock[t] for t in np.flatnonzero(~d.available["GE1"])] == [600, 630, 660]
    return {"dependency_cases": rows, "multi_interval_union": "PASS",
            "period_boundaries": "Outage end 13:00 leaves the 13:00 period available; a 10-minute outage disables the full containing period."}


def check_pv_overlap():
    folder = copied("pv_overlap", outages=[
        {"unit": "PV1", "from": "12:05", "to": "12:15"},
        {"unit": "PV1", "from": "12:10", "to": "12:20"}])
    d = Day(folder)
    with (folder / "weather.csv").open() as f:
        weather = {r["time_utc"]: r for r in csv.DictReader(f)}
    # On visible July date 12:00 local equals 11:00 UTC.
    forecast = float(weather[f"{d.date.isoformat()}T11:00Z"]["pv_kw"])
    actual = float(d.pv_max[24])
    correct_union = forecast * 15.0 / 30.0
    assert abs(actual - forecast / 3) < 1e-9
    assert correct_union > actual
    return {"forecast_kw": forecast, "unavailable_union_minutes": 15, "v17_added_minutes": 20,
            "v17_pv_max_kw": actual, "union_based_pv_max_kw": correct_union,
            "false_rejection_potential_kw": correct_union - actual,
            "finding": "Confirmed v17 verifier bug: overlapping PV outages are summed instead of unioned. All-off interpretation still passes."}


def empty_plan(d):
    p = {"date": d.date.isoformat(), "periods": []}
    for c in d.clock:
        p["periods"].append({"start": f"{c // 60:02d}:{c % 60:02d}",
                             "engines_kwe": {"GE1": 0.0, "GE2": 0.0},
                             "boilers_kw": {"B1": 0.0, "B2": 0.0},
                             "chillers_kw": {"EC1": 0.0, "EC2": 0.0, "AC1": 0.0},
                             "pv_kw": 0.0, "import_kw": 0.0, "export_kw": 0.0})
    return p


def check_arithmetic():
    folder = copied("arithmetic", outages=[])
    d = Day(folder)
    d.running0 = {"GE1"}
    p = empty_plan(d)
    row = p["periods"][0]
    row["engines_kwe"] = {"GE1": 750.0, "GE2": 400.0}
    row["boilers_kw"] = {"B1": 905.0, "B2": 830.0}
    row["chillers_kw"] = {"EC1": 650.0, "EC2": 520.0, "AC1": 355.0}
    row["import_kw"] = 100.0
    d.wet_bulb[0] = 14.0
    for ch in d.plant["electric_chillers"]:
        pts = np.array(ch["cop_by_condenser_entering_c"])
        d.cop[ch["id"]][True][0] = np.interp(22, pts[:, 0], pts[:, 1])
    f = d.true_flows(p)
    expected_gas = 0.5 * ((1990 + 1180) * 1.108 + 1000 + 1000)
    expected_cost = expected_gas * .0435 + .5 * (.750 * 11 + .400 * 12.5) + .5 * 100 * .138 + 27
    assert abs(f["gas_kwh"][0] - expected_gas) < 1e-9
    assert abs(f["cost"][0] - expected_cost) < 1e-9
    assert abs(f["engine_heat"][0] - (972.5 + 590)) < 1e-9
    assert abs(f["aux"][0] - (32 + 24 + 355 * .022)) < 1e-9
    assert abs(f["ec_elec"][0] - 200) < 1e-9
    assert abs(f["ac_heat"][0] - 500) < 1e-9
    assert abs(f["rejected"][0] - (650 + 100 + 520 + 100 + 355 + 500)) < 1e-9
    assert f["starts"] == 1
    return {"manual_case": "GE1 750kWe (mid-segment, already running), GE2 400kWe (new start), B1 905kW, B2 830kW, EC1 650kW, EC2 520kW, AC1 355kW, grid import100kW at 22C",
            "gas_kwh": expected_gas, "cost_gbp": expected_cost, "engine_ht_kw": f["engine_heat"][0],
            "aux_kw": f["aux"][0], "electric_chiller_power_kw": f["ec_elec"][0],
            "absorption_drive_kw": f["ac_heat"][0], "tower_rejection_kw_excluding_absorber_aux": f["rejected"][0],
            "starts": f["starts"], "status": "PASS"}


def check_limits_and_temperature():
    d = Day(BASE / "tests/days/visible")
    ratings = {e["id"]: {"at_rated_kva": e["rated_kwe"] / e["generator"]["power_factor"],
                         "rated_kva": e["generator"]["rated_kva"]} for e in d.engines}
    assert all(v["at_rated_kva"] < v["rated_kva"] for v in ratings.values())
    pf = .95
    q_per_kw = math.sqrt(1 - pf * pf) / pf
    negative_q = 50 - (1200 + 800) * q_per_kw
    max_p = math.sqrt(1220 ** 2 - negative_q ** 2)
    positive_only_capacity_error = 1220 - max_p
    assert negative_q < 0 and positive_only_capacity_error > 100
    q_ranges = {}
    for name in ("visible", "h1", "h2", "h3", "h4"):
        case = Day(BASE / "tests/days" / name)
        q_ranges[name] = [float(case.kvar.min()), float(case.kvar.max())]
    qmin = min(x[0] for x in q_ranges.values())
    qmax = max(x[1] for x in q_ranges.values())
    net_q_bound = max(qmax, 2000 * q_per_kw - qmin)
    return {"generator_rating_redundant_with_current_fixed_plant": ratings,
            "ac_hot_water_satisfied_c": {"engine_ht_flow": 90, "ac_required_minimum": 85},
            "lt_not_usable_for_ac_c": {"lt_flow": 40, "ac_required_minimum": 85},
            "negative_net_kvar_at_site50_and_engines2000kwe": negative_q,
            "connection_pmax_kw_at_negative_q": max_p,
            "overestimate_if_negative_q_ignored_kw": positive_only_capacity_error,
            "actual_v17_site_kvar_ranges": q_ranges,
            "actual_v17_absolute_net_kvar_bound": net_q_bound,
            "actual_v17_apparent_export_bound_kva": math.hypot(250, net_q_bound),
            "181_tangent_max_radial_excess_kva": 1220 * (1 / math.cos(math.pi / 360) - 1),
            "connection_test_allowance_kva": .5}


def check_absorber_mode_threshold():
    d = Day(BASE / "tests/days/h3")
    t = int(np.flatnonzero(d.cewt[False] < 22)[0])
    p = empty_plan(d)
    p["periods"][t]["chillers_kw"] = {"EC1": 1000.0, "EC2": 0.0, "AC1": 0.4}
    f = d.true_flows(p)
    correct_ec = 1000.0 / d.cop["EC1"][True][t]
    gap = correct_ec - f["ec_elec"][t]
    assert gap > 1.0
    return {"local_time": p["periods"][t]["start"], "ac_output_kw": .4,
            "ec1_output_kw": 1000.0, "physical_header_floor_c": 22,
            "v17_recomputed_ec_power_kw": float(f["ec_elec"][t]),
            "ec_power_with_positive_absorber_kw": float(correct_ec),
            "difference_kw": float(gap),
            "finding": "A >0.5 kW mode threshold can reject a plan whose small positive AC output correctly needs the warm header. Numerical-boundary issue, inadmissible as a hardness trap."}


def check_probability():
    rows = []
    for version in ("v8", "v8-rerun", "v9", "v10", "v11", "v12", "v13", "v14", "v15", "v16", "v17"):
        base = ROOT / "results" / (version + "-trials")
        if not base.exists():
            continue
        for p in sorted(base.glob("*/trial.json")):
            if "cheat" in p.parent.name:
                continue
            j = json.loads(p.read_text())
            # Deliberately only copy non-sensitive result fields.
            agent = j.get("agent") or {}
            rows.append({"version": version, "trial": p.parent.name,
                         "agent": {k: agent.get(k) for k in ("name", "model")}, "minutes": j.get("agent_minutes"),
                         "exception": j.get("exception"), "reward": j.get("reward")})
    frequentist_upper = 1 - .05 ** (1/3)
    models = {}
    for name, a, b in (("uniform_beta_1_1_prior", 1, 4), ("jeffreys_beta_half_half_prior", .5, 3.5)):
        next_three_fail = math.prod((b + i)/(a + b + i) for i in range(3))
        models[name] = {"posterior_mean_single_trial_pass": a/(a+b),
                        "posterior_95_percent_interval": [float(beta.ppf(.025, a, b)), float(beta.ppf(.975, a, b))],
                        "next_three_all_fail": next_three_fail,
                        "next_three_each_model_all_fail_assuming_independent_models": next_three_fail**2}
    return {"recovered_historical_rows": rows, "v17_zero_of_three_exact_one_sided_95_percent_upper_bound": frequentist_upper,
            "illustrative_bayesian_sensitivity_each_model_v17_0_of_3": models,
            "fixed_pass_rate_scenarios": [{"opus_p": a, "gpt_p": b, "probability_next_six_all_fail": (1-a)**3*(1-b)**3}
                                          for a,b in ((.05,.02),(.10,.05),(.15,.05),(.20,.10),(.25,.15),(.30,.10))],
            "warning": "Probabilities assume independent fresh runs at a fixed version. Historical versions, adaptive stop-on-pass, visible cues, verifier corrections and selection invalidate naive pooling."}


def main():
    result = {"runtime": {"python": platform.python_version(), "numpy": np.__version__},
              "visibility": check_visibility(), "names": check_names(),
              "outages": check_outage_overlap_and_topology(), "pv_overlap": check_pv_overlap(),
              "arithmetic": check_arithmetic(), "limits": check_limits_and_temperature(),
              "absorber_mode_threshold": check_absorber_mode_threshold(),
              "statistics": check_probability()}
    path = HERE / "audit_checks.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k,v in result.items() if k != "statistics"}, indent=2))
    print("Statistics saved with non-sensitive historical outcome fields in", path)


if __name__ == "__main__":
    main()
