"""Full CLI + checker validation of the two uniquely reconstructed accepted days."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TASK = ROOT / "tasks/energy-centre-dispatch"
sys.path.insert(0, str(TASK / "tests"))
import reference as R
spec = importlib.util.spec_from_file_location("reconstructed_oracle_checks", TASK / "tests/test_plans.py")
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)


def hashes(folder):
    return {name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
            for name in ["plant.json", "supply.json", "status.json", "demand.csv", "weather.csv"]}


rows = []
for seed, name in [(2026, "f4"), (2403, "f7")]:
    folder = HERE / "fresh-reconstructed" / f"seed-{seed}" / name
    out = HERE / "reconstructed-oracle" / f"seed-{seed}-{name}"
    out.mkdir(parents=True, exist_ok=True)
    before = hashes(folder)
    plans, runtimes = [], []
    for run in [1, 2]:
        path = out / f"plan-{run}.json"
        start = time.monotonic()
        res = subprocess.run([sys.executable, str(TASK / "solution/app/dispatch.py"),
                              "--data", str(folder), "--output", str(path)],
                             capture_output=True, text=True, timeout=120)
        runtimes.append(time.monotonic() - start)
        (out / f"run-{run}.txt").write_text(res.stdout + res.stderr)
        assert res.returncode == 0, res.stderr
        plans.append(json.loads(path.read_text()))
        assert hashes(folder) == before
    assert plans[0] == plans[1]
    day = R.Day(folder)
    best = day.least_cost()
    day.least_cost = lambda: best
    flows = day.true_flows(plans[0])
    passed = []
    for check, fn in vars(T).items():
        if check.startswith("test_") and check != "test_same_plan_every_time":
            fn((day, plans[0], flows))
            passed.append(check)
    delta = float(flows["cost"].sum()) - best["cost"]
    assert abs(delta) < .001
    row = {"seed": seed, "name": name, "date": day.date.isoformat(), "input_sha256": before,
           "cost_gbp": float(flows["cost"].sum()), "reference_cost_gbp": best["cost"],
           "cost_delta_gbp": delta, "cli_runtimes_s": runtimes, "deterministic": True,
           "passed_case_checks": passed, "inputs_unchanged_after_both_runs": True}
    rows.append(row)
    print(json.dumps(row, indent=2), flush=True)
    (HERE / "check_reconstructed_oracle.json").write_text(json.dumps(rows, indent=2) + "\n")
