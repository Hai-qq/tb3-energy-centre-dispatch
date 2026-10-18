"""Evaluate the v19 witness after fixing only its reporting by netting I/X.

No dispatch output is changed. All existing physical/reporting checks pass and
the existing least-cost assertion fails against the directional whole-day MILP.
"""
import importlib.util
import json
from pathlib import Path
import sys
import types

from probe_arbitrage import OUT, TASK, load_ref

Day = load_ref()
alias = types.ModuleType("reference")
alias.Day = Day
sys.modules["reference"] = alias
spec = importlib.util.spec_from_file_location("baseline_test_plans", TASK / "tests/test_plans.py")
tests = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tests)

directory = OUT / "flat-1250-heat2000"
day = Day(directory / "data")
plan = json.loads((directory / "v19-plan.json").read_text())
for t, p in enumerate(plan["periods"]):
    overlap = min(p["import_kw"], p["export_kw"])
    p["import_kw"] -= overlap
    p["export_kw"] -= overlap
    p["cost_gbp"] += 0.5 * overlap * (day.export_rate - day.import_rate[t])
plan["summary"]["cost_gbp"] = sum(p["cost_gbp"] for p in plan["periods"])
plan["summary"]["import_kwh"] = 0.5 * sum(p["import_kw"] for p in plan["periods"])
plan["summary"]["export_kwh"] = 0.5 * sum(p["export_kw"] for p in plan["periods"])
(directory / "v19-netted-reporting-plan.json").write_text(json.dumps(plan, indent=2) + "\n")
case = day, plan, day.true_flows(plan)
results = {}
for name in sorted(dir(tests)):
    if not name.startswith("test_") or name == "test_same_plan_every_time":
        continue
    try:
        getattr(tests, name)(case)
        results[name] = {"passed": True}
    except AssertionError as exc:
        results[name] = {"passed": False, "error": repr(exc)}
best = day.least_cost()["cost"]
results["cost_detail"] = {"true_netted_cost": float(case[2]["cost"].sum()), "directional_milp": best, "tolerance": max(0.5, 2e-4 * best), "regret": float(case[2]["cost"].sum()) - best}
results["note"] = "All original test functions except rerun executed directly; only Day.least_cost uses added direction binaries. No physical dispatch variable was adapted. Determinism not re-tested in this diagnostic."
(directory / "v19-netted-test-results.json").write_text(json.dumps(results, indent=2) + "\n")
print(json.dumps(results, indent=2))
