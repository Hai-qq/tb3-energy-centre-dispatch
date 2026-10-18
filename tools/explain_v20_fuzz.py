"""Causal replay of the largest regrets in the already frozen 200-day suite."""
from pathlib import Path
import importlib.util
import json
import sys

import check_v18 as K

ROOT = K.ROOT
OUT = ROOT / "results/checks-v20"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def main():
    suite = OUT / "candidates/c1/fuzz-200"
    dest = OUT / "candidates/c1/fuzz-causal-controls"
    dest.mkdir(exist_ok=False)
    manifest = json.loads((suite / "manifest.json").read_text())
    records = [json.loads(p.read_text()) for p in (suite / "records").glob("*.json")]
    chosen = {a: max(records, key=lambda r: r["apps"][a].get("delta_gbp", -float("inf")))
              for a in ("strong-v16", "strong-v19")}
    ids = sorted({r["id"] for r in chosen.values()})
    ref = module("reference", OUT / "candidates/c1/task/tests/reference.py")
    tests = module("ecd_tests", OUT / "candidates/c1/task/tests/test_plans.py")
    days = {}
    for name in ids:
        day = ref.Day(suite / "days" / name)
        day.folder = suite / "days" / name
        day.optimum = json.loads((suite / "milp" / f"{name}.json").read_text())
        day.least_cost = lambda value=day.optimum: value
        days[name] = day
    matrix = {}
    for n in (16, 19):
        app = OUT / f"audit/arbitrage/diagnostic-direction-fixed/v{n}/app"
        matrix[f"fixed-v{n}"] = K.check_app(f"fixed-v{n}", app, days, tests, dest, 120)
    result = {"selection": "largest actual net-cost regret, selected after all original 200 inputs and replays were frozen",
              "original_worst": {a: {"id": r["id"], **r["apps"][a]} for a, r in chosen.items()},
              "input_specs": {x["id"]: x for x in manifest["accepted"] if x["id"] in ids},
              "direction_only_semantic_fix": matrix,
              "not_a_format_adapter": True}
    K.write_json(dest / "results.json", result)
    assert all(x["passed"] for x in matrix.values())
    print(json.dumps({a: {"id": r["id"], "regret_gbp": r["apps"][a]["delta_gbp"]} for a, r in chosen.items()}, indent=2))


if __name__ == "__main__":
    main()
