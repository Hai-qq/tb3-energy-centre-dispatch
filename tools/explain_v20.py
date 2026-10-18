"""Preserve physical violations and a report-only causal control for v20.

The netted plans here are diagnostic counterfactuals, never adversary adapters.
They leave every unit output intact and change only grid/cost report fields.
"""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import sys
import traceback

import check_v18 as K

OUT = K.ROOT / "results/checks-v20"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def main():
    out = OUT / "causal-details"
    out.mkdir(exist_ok=False)
    details = {}
    for cid in ("c2", "c4"):
        task = OUT / "candidates" / cid / "task"
        ref = module("reference", task / "tests/reference.py")
        day = ref.Day(task / "tests/days/h2")
        details[cid] = {}
        for app in ("oracle", "strong-v16-claude", "strong-v19-claude"):
            source = OUT / "candidates" / cid / "gates-r1/apps" / app / "h2.json"
            plan = json.loads(source.read_text())
            f = day.true_flows(plan)
            if cid == "c2":
                entry = day.supply["gas"]["entry"]
                amount = f["gas_kwh"] * 2 * 3.6 / entry["gross_calorific_value_mj_per_standard_m3"]
                limit, unit = entry["maximum_standard_m3_per_hour"], "standard m3/h"
            else:
                hx = day.plant["heat_exchangers"][0]
                circuit = day.plant["heat_circuits"][hx["primary_circuit"]]
                amount = (f["engine_heat"] - f["ac_heat"]) / (hx["water_specific_heat_kj_per_kg_k"] * (circuit["flow_c"] - circuit["return_c"]))
                limit, unit = hx["primary_maximum_water_flow_kg_per_s"], "kg/s"
            peak = int(amount.argmax())
            details[cid][app] = {"source_plan": str(source.relative_to(K.ROOT)),
                "source_sha256": K.file_hash(source), "peak": float(amount[peak]),
                "limit": limit, "unit": unit, "peak_period": plan["periods"][peak],
                "violating_starts": [p["start"] for p, a in zip(plan["periods"], amount) if a > limit + .01]}
    task = OUT / "candidates/c1/task"
    ref = module("reference", task / "tests/reference.py")
    tests = module("ecd_tests", task / "tests/test_plans.py")
    day = ref.Day(task / "tests/days/h2")
    best = day.least_cost()
    day.least_cost = lambda: best
    details["c1_report_only_controls"] = {}
    for app in ("strong-v16-claude", "strong-v19-claude"):
        source = OUT / "candidates/c1/gates-r1/apps" / app / "h2.json"
        original = json.loads(source.read_text())
        plan = json.loads(source.read_text())
        for p in plan["periods"]:
            net = p["import_kw"] - p["export_kw"]
            p["import_kw"], p["export_kw"] = max(net, 0.), max(-net, 0.)
        flows = day.true_flows(plan)
        for p, cost in zip(plan["periods"], flows["cost"]):
            p["cost_gbp"] = float(cost)
        plan["summary"]["cost_gbp"] = float(flows["cost"].sum())
        plan["summary"]["import_kwh"] = .5 * sum(p["import_kw"] for p in plan["periods"])
        plan["summary"]["export_kwh"] = .5 * sum(p["export_kw"] for p in plan["periods"])
        assert all(all(a[k] == b[k] for k in ("engines_kwe", "boilers_kw", "chillers_kw", "pv_kw"))
                   for a, b in zip(original["periods"], plan["periods"]))
        failures = {}
        for name, func in vars(tests).items():
            if name.startswith("test_") and name != "test_same_plan_every_time" and callable(func):
                try:
                    func((day, plan, day.true_flows(plan)))
                except Exception:
                    failures[name] = traceback.format_exc()
        K.write_json(out / f"c1-h2-{app}-netted.json", plan)
        details["c1_report_only_controls"][app] = {"source_sha256": K.file_hash(source),
            "unit_outputs_unchanged": True, "cost_gbp": float(flows["cost"].sum()),
            "milp_gbp": best["cost"], "regret_gbp": float(flows["cost"].sum()) - best["cost"],
            "failures": failures, "note": "11 per-day tests; determinism belongs to the original two CLI runs"}
        assert set(failures) == {"test_least_cost"}, failures
    K.write_json(out / "results.json", details)
    print(json.dumps({"c1": {a: d["regret_gbp"] for a, d in details["c1_report_only_controls"].items()},
                      "report_only_control": "only least_cost fails for both; unit outputs unchanged"}, indent=2))


if __name__ == "__main__":
    main()
