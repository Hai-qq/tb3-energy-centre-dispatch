"""Local read-only diagnosis of the r1 oracle's two fresh-day failures."""
from __future__ import annotations

import argparse
import importlib.util
import itertools
import json
import math
from pathlib import Path
import sys
import time

import numpy as np
from scipy.optimize import linprog

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TASK = ROOT / "tasks/energy-centre-dispatch"
sys.path.insert(0, str(TASK / "solution/app"))
from planner import optimize as O
from planner.data import load_day
from planner.plant import Plant
from planner.tariff import Tariff

spec = importlib.util.spec_from_file_location("oracle_lp_reference", TASK / "tests/reference.py")
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
parser = argparse.ArgumentParser()
parser.add_argument("--reconstructed", action="store_true")
args = parser.parse_args()
suffix = "_reconstructed" if args.reconstructed else "_original"

results = []
for name, path in [("seed2026_f4", "seed-2026/tests/days/f4"),
                   ("seed2403_f7", "seed-2403/tests/days/f7")]:
    if args.reconstructed:
        folder = HERE / "fresh-reconstructed" / path.replace("tests/days/", "")
    else:
        folder = ROOT / "results/checks-v18/final-fresh" / path
    day, ref = load_day(folder), R.Day(folder)
    plant, tariff = Plant(day.plant), Tariff(day.supply, day.date)
    start = time.monotonic()
    try:
        O.plan_day(day, plant, tariff)
        outcome = "returned a plan"
    except Exception as exc:
        outcome = repr(exc)
    result = {"day": name, "oracle_baseline_outcome": outcome, "oracle_seconds": time.monotonic() - start,
              "reference_cost_gbp": None, "reference_state_LP_disagreements": []}
    try:
        best = ref.least_cost()
    except RuntimeError as exc:
        result["reference_error"] = str(exc)
        result["status"] = day.status
        results.append(result)
        (HERE / ("diagnose_oracle_lp" + suffix + ".json")).write_text(json.dumps(results, indent=2) + "\n")
        print(json.dumps(result, indent=2), flush=True)
        continue
    result["reference_cost_gbp"] = best["cost"]
    for t, p in enumerate(best["periods"]):
        segments = []
        for engine in plant.engines:
            power = p["engines_kwe"][engine.id]
            if power < 1e-5:
                segments.append(None)
            else:
                matches = [k for k, piece in enumerate(engine.segments())
                           if piece[0] - 1e-5 <= power <= piece[1] + 1e-5]
                assert matches, (name, t, power)
                segments.append(matches[0])
        absorbing = any(p["chillers_kw"][a.id] > 1e-7 for a in plant.absorption_chillers)
        captured = {}
        def probe(c, **kwargs):
            captured.update(c=np.array(c), **kwargs)
            res = linprog(c, **kwargs)
            captured["result"] = res
            return res
        O.linprog = probe
        value, output = O._period(day, plant, tariff, t, tuple(segments), absorbing)
        O.linprog = linprog
        if not math.isinf(value):
            continue
        kwargs = {k: v for k, v in captured.items() if k not in ["c", "result"]}
        x = [p["engines_kwe"][e.id] for e, s in zip(plant.engines, segments) if s is not None]
        x += [p["boilers_kw"][b.id] for b in plant.boilers]
        x += [p["chillers_kw"][ch.id] for ch in plant.electric_chillers + plant.absorption_chillers]
        x += [p["import_kw"], p["export_kw"]]
        x = np.array(x)
        eq = np.array(captured["A_eq"]) @ x - np.array(captured["b_eq"])
        ub = np.array(captured["A_ub"]) @ x - np.array(captured["b_ub"])
        bounds_error = max(max(a - value, value - b) for value, (a, b) in zip(x, captured["bounds"]))
        variants = {}
        for label, method, options in [("highs_no_presolve", "highs", {"presolve": False}),
                                        ("highs_ipm", "highs-ipm", {}),
                                        ("highs_ds_no_presolve", "highs-ds", {"presolve": False})]:
            variant = linprog(captured["c"], **{**kwargs, "method": method, "options": options})
            variants[label] = {"status": int(variant.status), "message": variant.message,
                               "fun": float(variant.fun) if variant.fun is not None else None}
        entry = {"period": t, "start": p["start"], "segments": segments, "absorbing": absorbing,
                 "baseline_status": int(captured["result"].status), "baseline_message": captured["result"].message,
                 "reference_solution_max_eq_residual": float(abs(eq).max()),
                 "reference_solution_max_ub_excess": float(ub.max()),
                 "reference_solution_max_bound_excess": float(bounds_error),
                 "equality_residuals": eq.tolist(), "positive_ub_rows": np.flatnonzero(ub > 1e-6).tolist(),
                 "solver_variants": variants}
        result["reference_state_LP_disagreements"].append(entry)
        fixture = HERE / "lp-probes"
        fixture.mkdir(exist_ok=True)
        np.savez(fixture / (name + "_" + p["start"].replace(":", "") + ".npz"),
                 c=captured["c"], A_eq=captured["A_eq"], b_eq=captured["b_eq"],
                 A_ub=captured["A_ub"], b_ub=captured["b_ub"], bounds=captured["bounds"], reference_x=x)
    results.append(result)
    (HERE / ("diagnose_oracle_lp" + suffix + ".json")).write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(result, indent=2), flush=True)
