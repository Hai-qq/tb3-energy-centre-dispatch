"""Evidence-preserving B/C/E/F precheck runner for v20 experiments.

Canonical pytest is run separately. Each development matrix uses the actual
test functions, two timed subprocess executions, and one independently solved
whole-day MILP per day. No real-model trial is represented by this runner.
"""
from __future__ import annotations
import argparse
import importlib
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import time

import check_v18 as K
import energy_mutants as M

ROOT = K.ROOT
OUT = ROOT / "results/checks-v20"


def extras(cid):
    if cid == "c1":
        return {"simultaneous_grid_arbitrage": [("planner/optimize.py",
            'directions = (True, False) if tariff.import_rate(day.starts[t]) < tariff.export_rate else (None,)',
            'directions = (None,)')]}
    if cid == "c2":
        return {
            "shared_gas_limit_ignored": [("planner/optimize.py", '    if tariff.gas_entry is not None:', '    if False:')],
            "shared_gas_only_engines": [("planner/optimize.py",
                '            row[iB + j] = tariff.billed_gas(1.0 / b.efficiency, b.fuel_basis)',
                '            row[iB + j] = 0.0')],
        }
    if cid == "c4":
        return {
            "phe_flow_limit_ignored": [("planner/optimize.py", '    for hx in plant.heat_exchangers:', '    for hx in []:')],
            "phe_counts_all_engine_ht": [("planner/optimize.py",
                '''            for j, a in enumerate(absorbers):
                row[iA + j] = -1.0 / a.cop
            circ = plant.circuits[hx["primary_circuit"]]''',
                '''            for j, a in enumerate(absorbers):
                row[iA + j] = 0.0
            circ = plant.circuits[hx["primary_circuit"]]''')],
        }
    return {}


def applications(task, blind):
    apps = {"oracle": task / "solution/app",
            "strong-v16-claude": ROOT / "results/v16-trials/ecd16-run2-claude/app",
            "strong-v19-claude": ROOT / "results/v19-trials/ecd19-run2-claude/app"}
    for model in ("claude", "codex"):
        for run in range(1, 4):
            apps[f"v18-run{run}-{model}"] = ROOT / f"results/v18-trials/ecd18-run{run}-{model}/app"
    apps["v19-run1-claude"] = ROOT / "results/v19-trials/ecd19-run1-claude/app"
    if blind:
        apps["blind"] = blind
    return apps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", type=Path, default=ROOT / "tasks/energy-centre-dispatch")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--candidate", choices=["c1", "c2", "c4"], required=True)
    ap.add_argument("--blind", type=Path)
    ap.add_argument("--part", choices=["apps", "mutants", "all"], default="all")
    args = ap.parse_args()
    args.task, args.out = args.task.resolve(), args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.task / "tests"))
    ref = importlib.import_module("reference")
    tests = importlib.import_module("test_plans")
    import numpy as np
    import scipy
    meta = {"command": sys.argv, "python": platform.python_version(), "numpy": np.__version__,
            "scipy": scipy.__version__, "candidate": args.candidate,
            "task_hashes": K.tree_hash(args.task), "days": {}}
    days = {}
    for name in K.DAYS:
        folder = args.task / "tests/days" / name
        day = ref.Day(folder)
        start = time.monotonic()
        day.optimum = day.least_cost()
        day.folder = folder
        day.least_cost = lambda value=day.optimum: value
        meta["days"][name] = {"milp_cost": day.optimum["cost"], "seconds": time.monotonic()-start,
                              "input_hashes": K.tree_hash(folder)}
        K.write_json(args.out / "milp" / f"{name}.json", day.optimum)
        days[name] = day
        print(f"MILP {name}: {day.optimum['cost']:.9f}", flush=True)
    K.write_json(args.out / "metadata.json", meta)
    results, mutants = {}, {}
    if args.part in ("apps", "all"):
        for name, app in applications(args.task, args.blind.resolve() if args.blind else None).items():
            if not (app / "dispatch.py").exists():
                raise FileNotFoundError(app)
            results[name] = K.check_app(name, app, days, tests, args.out / "apps", 120)
            K.write_json(args.out / "apps.json", results)
    if args.part in ("mutants", "all"):
        mutations = {**M.MUTANTS, **extras(args.candidate)}
        for name, changes in mutations.items():
            app = args.out / "mutant_apps" / name
            shutil.copytree(args.task / "solution/app", app,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            for filename, old, new in changes:
                p = app / filename
                source = p.read_text()
                assert source.count(old) == 1, (name, filename, old)
                p.write_text(source.replace(old, new))
            mutants[name] = K.check_app(name, app, days, tests, args.out / "mutants",
                                        2 if name == "hangs_after_writing" else 120)
            K.write_json(args.out / "mutants.json", mutants)
            shutil.rmtree(app)
    gates = {}
    if results:
        oracle = results["oracle"]
        gates["B_five_days_and_milp_0.001"] = oracle["passed"] and all(abs(d["delta_gbp"]) < .001 for d in oracle["days"].values())
        gates["E_two_old_strong_fail"] = all(not results[k]["passed"] for k in ("strong-v16-claude", "strong-v19-claude"))
        gates["F_seven_old_failed_still_fail"] = all(not v["passed"] for k,v in results.items() if k.startswith(("v18-", "v19-run1")))
        if "blind" in results:
            gates["blind_observed_pass"] = results["blind"]["passed"]
    if mutants:
        gates["C_all_mutants_caught"] = all(not x["passed"] for x in mutants.values())
    K.write_json(args.out / "gates.json", gates)
    print("GATES", json.dumps(gates), flush=True)
    required = [v for k,v in gates.items() if k != "blind_observed_pass"]
    raise SystemExit(0 if all(required) else 1)


if __name__ == "__main__":
    main()
