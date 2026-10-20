"""Test a candidate thermodynamic extension; this is NOT the v17 reference rule.

The fixed data names an LT radiator on a 40/35 C circuit. We test the consequence
IF that means dry-air heat rejection at those fixed water temperatures. The data
does not explicitly state dry versus spray/evaporative assist or whether those
temperatures are absolute limits. Consequently this probe supplies measurements
for a fairness decision and does not assert that the extension is a valid trap.
"""

import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
import fuzz_v18 as F

OUT = Path(__file__).resolve().parent / "radiator-probe"
DAY = OUT / "day"
OUT.mkdir(exist_ok=True)
spec = dict(date="2026-07-27", offset=1, seed=180042,
            elec=[(0, 1000)], heat=[(0, 1200)], cool=[(0, 700)],
            dry=[(0, 27), (6, 26), (10, 35), (12, 39), (14, 42), (16, 41), (18, 36), (23, 29)],
            wet=[(0, 18), (6, 17.5), (10, 20), (12, 22), (14, 23), (16, 23), (18, 21), (23, 19)],
            sun=(5.2, 20.8), pv_peak=0, cloud=0,
            status={"running_at_midnight": ["GE1"], "outages": []})
(OUT / "spec.json").write_text(json.dumps(spec, indent=2) + "\n")
F.B.write_day(DAY, spec)
day = F.R.Day(DAY)
wx = {datetime.fromisoformat(r["time_utc"].replace("Z", "+00:00")): r
      for r in csv.DictReader((DAY / "weather.csv").open())}
dry = np.array([float(wx[t.astimezone(timezone.utc)]["dry_bulb_c"]) for t in day.starts])
record = {"input_problems": F.check_inputs(DAY), "dry_bulb_c": dry.tolist(),
          "candidate_status": "conditional model extension pending fairness assessment", "apps": {}}
plans = {}
for app in F.APPS:
    start = time.monotonic()
    plan = F.run_app(app, DAY)
    plans[app] = plan
    (OUT / (app + ".plan.json")).write_text(json.dumps(plan, indent=1) + "\n")
    flows = day.true_flows(plan)
    failed = []
    for check in F.CHECKS:
        try:
            getattr(F.T, check)((day, plan, flows))
        except Exception as exc:
            failed.append({"check": check, "exception": repr(exc)})
    record["apps"][app] = {"elapsed_seconds": time.monotonic() - start,
                            "original_v17_cheap_failures": failed,
                            "cost_gbp": float(flows["cost"].sum())}
    print(app, record["apps"][app], flush=True)

# Explicit witness independent of all three app algorithms: keep both engines off,
# use efficient boiler B1 and electric chiller EC1, and import the needed power.
periods = []
for t in range(48):
    boiler = float(day.heat[t] + day.lthw_loss)
    cooling = float(day.cool[t])
    imp = float(day.elec[t] + cooling / day.cop["EC1"][False][t])
    gas = .5 * boiler / .905
    cost = gas * day.gas_rate + .5 * imp * day.import_rate[t]
    periods.append({"start": f"{day.clock[t] // 60:02d}:{day.clock[t] % 60:02d}",
                    "engines_kwe": {"GE1": 0.0, "GE2": 0.0},
                    "boilers_kw": {"B1": boiler, "B2": 0.0},
                    "chillers_kw": {"EC1": cooling, "EC2": 0.0, "AC1": 0.0},
                    "pv_kw": 0.0, "import_kw": imp, "export_kw": 0.0,
                    "gas_kwh": gas, "cost_gbp": cost, "grid_ok": True})
witness = {"date": day.date.isoformat(), "periods": periods,
           "summary": {"cost_gbp": sum(p["cost_gbp"] for p in periods),
                       "gas_kwh": sum(p["gas_kwh"] for p in periods),
                       "import_kwh": .5 * sum(p["import_kw"] for p in periods),
                       "export_kwh": 0.0, "engine_starts": 0, "grid_ok": True}}
(OUT / "engines-off-witness.json").write_text(json.dumps(witness, indent=1) + "\n")
wflows = day.true_flows(witness)
for check in F.CHECKS:
    getattr(F.T, check)((day, witness, wflows))
record["engines_off_witness"] = {"physical_report_checks_passed": len(F.CHECKS),
                                  **F.details(day, witness, wflows)}
record["conditional_extensions"] = {}
for threshold, description in [(40., "ambient at least fixed LT flow temperature"),
                               (35., "ambient at least fixed LT return temperature")]:
    alternative = F.R.Day(DAY)
    hot = dry >= threshold
    for engine in alternative.engines:
        alternative.available[engine["id"]] &= ~hot
    start = time.monotonic()
    best = alternative.least_cost()
    checks = {}
    for app, plan in plans.items():
        flows = alternative.true_flows(plan)
        checks[app] = {"failed_test": "test_units_within_ratings_and_availability",
                       "failed_periods": np.where(~flows["running_ok"])[0].tolist()}
    record["conditional_extensions"][str(threshold)] = {
        "meaning": description, "hot_periods": np.where(hot)[0].tolist(),
        "reference_milp_cost_gbp": float(best["cost"]),
        "reference_milp_seconds": time.monotonic() - start, "apps": checks}
    for check in F.CHECKS:
        getattr(F.T, check)((alternative, witness, alternative.true_flows(witness)))
(OUT / "results.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(record, indent=2), flush=True)
