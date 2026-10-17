"""Replace the isolated v17 midnight reactive-power spike with a smooth profile.

This is a coverage/realism experiment, not a claim of a new reasoning trap.
All candidate inputs and the exact failed connection margins are retained.
"""
from __future__ import annotations

import copy
import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "archive/energy-centre-dispatch-v17/tests"))
from reference import Day

_builder_spec = importlib.util.spec_from_file_location(
    "frozen_v17_negative_q_builder", ROOT / "archive/energy-centre-dispatch-v17/build_energy_days.py")
B = importlib.util.module_from_spec(_builder_spec)
_builder_spec.loader.exec_module(B)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec-dir", type=Path, help="Replay saved q*/spec.json from any of the four rounds")
    ap.add_argument("--case", help="One saved case, for example q02")
    ap.add_argument("--out", type=Path, default=ROOT / "results/checks-v18/candidates/negative-q-replay")
    args = ap.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    mutant = out / "positive-only-app"
    shutil.copytree(ROOT / "archive/energy-centre-dispatch-v17/solution/app", mutant,
                    dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    file = mutant / "planner/optimize.py"
    src = file.read_text()
    old = "_ANGLES = np.radians(np.arange(-90.0, 90.5, 1.0))"
    assert src.count(old) == 1
    file.write_text(src.replace(old, "_ANGLES = np.radians(np.arange(0.0, 90.5, 1.0))"))
    results = []
    specifications = []
    if args.spec_dir:
        for file in sorted(args.spec_dir.glob("q*/spec.json")):
            if args.case is None or file.parent.name == args.case:
                specifications.append((file.parent.name, json.loads(file.read_text())))
        assert specifications, "No saved specifications matched"
    else:
        parameters = [
            (2360, 190, 1800, .10), (2370, 190, 1800, .10),
            (2380, 190, 1800, .10), (2390, 190, 1800, .10),
            (2400, 190, 1800, .10), (2410, 190, 1800, .10),
            (2360, 190, 1800, .12), (2370, 190, 1800, .12),
            (2380, 190, 1800, .12), (2390, 190, 1800, .12),
            (2400, 190, 1800, .12), (2410, 190, 1800, .12)]
        for index, (peak, cooling, heat, pf_ratio) in enumerate(parameters):
            spec = copy.deepcopy(B.DAYS["h2"])
            spec.pop("overrides", None)
            spec["elec"] = [(0, peak), (1, peak), (2, 1750), (3, 1300)] + spec["elec"][1:]
            spec["heat"] = [(0, heat), (1, heat), (2, 2050), (3, 2250)] + spec["heat"][1:]
            spec["cool"] = [(0, cooling), (2, cooling)] + spec["cool"][1:]
            spec["kvar_per_kw"] = pf_ratio
            spec["status"]["outages"][0]["from"] = "00:00"
            # Return the radiator before the smooth late-evening load rise.
            spec["status"]["outages"][-1]["to"] = "23:00"
            if args.case is None or f"q{index:02d}" == args.case:
                specifications.append((f"q{index:02d}", spec))
    for case_id, spec in specifications:
        folder = out / case_id
        B.write_day(folder, spec)
        (folder / "spec.json").write_text(json.dumps(spec, indent=2) + "\n")
        dr = {"id": folder.name, "peak_kw": spec["elec"][0][1],
              "night_cooling_kw": spec["cool"][0][1], "night_heat_kw": spec["heat"][0][1],
              "site_q_per_p": spec["kvar_per_kw"]}
        try:
            day = Day(folder)
            best = day.least_cost()
            dr["reference_cost"] = best["cost"]
            ppath = folder / "positive-only-plan.json"
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
            run = subprocess.run([sys.executable, str(mutant / "dispatch.py"), "--data", str(folder),
                                  "--output", str(ppath)], capture_output=True, text=True,
                                 timeout=120, env=env)
            dr["returncode"] = run.returncode
            (folder / "mutant.log").write_text(run.stdout + run.stderr)
            if run.returncode == 0:
                plan = json.loads(ppath.read_text())
                f = day.true_flows(plan)
                imp = np.array([p["import_kw"] for p in plan["periods"]])
                reactive = day.kvar - f["engine_kvar"]
                excess = np.hypot(imp, reactive) - day.import_kva
                dr["violations"] = [{"period": p["start"], "excess_kva": float(excess[t]),
                                     "net_kvar": float(reactive[t]), "import_kw": float(imp[t])}
                                    for t, p in enumerate(plan["periods"]) if excess[t] > .5]
                dr["mutant_cost"] = float(f["cost"].sum())
                dr["max_excess_kva"] = float(excess.max())
        except Exception as exc:
            dr["exception"] = repr(exc)
        results.append(dr)
        (out / "results.json").write_text(json.dumps(results, indent=2) + "\n")
        print(json.dumps(dr), flush=True)


if __name__ == "__main__":
    main()
