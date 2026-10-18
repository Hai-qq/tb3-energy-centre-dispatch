"""Post-freeze external replay of the C2 author's already frozen binding case.

This diagnostic is separate from the five evaluation days. It checks whether
the new gas rule was actually implemented even when old port-name validation
prevents the blind application from producing hidden-day plans.
"""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import sys

import check_v18 as K

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/checks-v20"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    task = OUT / "candidates/c2/task"
    blind = OUT / "blind/c2"
    dest = args.out.resolve()
    dest.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(task / "tests"))
    ref = importlib.import_module("reference")
    tests = importlib.import_module("test_plans")
    source = blind / "experiments/cases/gas_binding"
    source_plan = blind / "experiments/plans/gas_binding.json"
    before = K.tree_hash(blind)
    day = ref.Day(source)
    day.folder = source
    day.optimum = day.least_cost()
    day.least_cost = lambda value=day.optimum: value
    K.write_json(dest / "milp.json", day.optimum)
    scored = K.check_app("blind", blind / "app", {"gas_binding": day}, tests, dest, 120)
    plan = json.loads(source_plan.read_text())
    f = day.true_flows(plan)
    supply = json.loads((source / "supply.json").read_text())
    entry = supply["gas"]["entry"]
    vph = f["gas_kwh"] * 2.0 * 3.6 / entry["gross_calorific_value_mj_per_standard_m3"]
    cap = entry["maximum_standard_m3_per_hour"]
    result = {
        "candidate": "c2",
        "source_case": str(source.relative_to(ROOT)),
        "source_case_sha256": K.tree_hash(source),
        "source_plan_sha256": K.file_hash(source_plan),
        "source_was_frozen_before_external_evaluation": True,
        "diagnostic_is_not_a_hidden_day_pass": True,
        "external_replay": scored,
        "frozen_plan_peak_standard_m3_per_hour": float(vph.max()),
        "frozen_plan_binding_periods": int((abs(vph - cap) < 1e-5).sum()),
        "frozen_plan_exceeding_periods": int((vph > cap + .01).sum()),
        "frozen_plan_gas_gross_kwh": float(f["gas_kwh"].sum()),
        "frozen_files_unchanged": before == K.tree_hash(blind),
    }
    K.write_json(dest / "result.json", result)
    print(json.dumps({k: v for k, v in result.items() if k not in (
        "external_replay", "source_case_sha256")}, indent=2))
    assert result["frozen_files_unchanged"]
    assert result["frozen_plan_binding_periods"] == 48
    assert result["frozen_plan_exceeding_periods"] == 0
    assert scored["passed"], "Inspect retained external assertions"


if __name__ == "__main__":
    main()
