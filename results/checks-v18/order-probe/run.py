"""One equivalent visible-day probe: reverse both CSV data-row orders.

No timestamps, fields, JSON files or row bytes are changed. The archived
reference sees a time-normalized copy; all three saved apps see reversed rows.
This is an order-invariance investigation, not a new E success claim.
"""

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

os.environ.update(PYTHONDONTWRITEBYTECODE="1", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import fuzz_v18 as F
import numpy as np

SOURCE = ROOT / "tasks/energy-centre-dispatch/environment/data"
REVERSED = OUT / "reversed"
NORMALIZED = OUT / "normalized"
FILES = ("plant.json", "supply.json", "status.json", "demand.csv", "weather.csv")
for folder in (REVERSED, NORMALIZED):
    folder.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        shutil.copyfile(SOURCE / name, folder / name)

integrity = {}
for name, time_key in (("demand.csv", "period_start"), ("weather.csv", "time_utc")):
    original = (SOURCE / name).read_bytes().splitlines(keepends=True)
    changed = [original[0], *reversed(original[1:])]
    (REVERSED / name).write_bytes(b"".join(changed))
    normalized_rows = sorted(changed[1:], key=lambda b: datetime.fromisoformat(
        b.decode().split(",", 1)[0].replace("Z", "+00:00")).astimezone(timezone.utc))
    (NORMALIZED / name).write_bytes(b"".join([changed[0], *normalized_rows]))
    integrity[name] = {
        "data_rows": len(original) - 1,
        "header_unchanged": original[0] == changed[0],
        "row_bytes_multiset_unchanged": Counter(original[1:]) == Counter(changed[1:]),
        "timestamps_and_values_unchanged": True,
        "reversal_changes_file": b"".join(original) != b"".join(changed),
        "normalized_matches_original_bytes": (NORMALIZED / name).read_bytes() == (SOURCE / name).read_bytes(),
    }
    assert all(integrity[name][k] for k in integrity[name] if k != "data_rows")

report = {
    "kind": "single_equivalent_day_csv_order_probe",
    "source": str(SOURCE.relative_to(ROOT)),
    "reference": "archived v17, applied to time-normalized input",
    "semantics_changed": False,
    "csv_integrity": integrity,
    "json_inputs_byte_identical": all((SOURCE / n).read_bytes() == (REVERSED / n).read_bytes()
                                      for n in FILES if n.endswith(".json")),
    "source_sha256": {n: hashlib.sha256((SOURCE / n).read_bytes()).hexdigest() for n in FILES},
    "apps": {},
}
day = F.R.Day(NORMALIZED)
best = float(day.least_cost()["cost"])
report["reference_milp_cost_gbp"] = best
for name, app in F.APPS.items():
    data, *_ = F.load_app(name)
    standard = data.load_day(NORMALIZED)
    permuted = data.load_day(REVERSED)
    same = {field: np.array_equal(getattr(standard, field), getattr(permuted, field))
            for field in ("elec", "kvar", "heat", "cool", "dry_bulb", "wet_bulb", "pv")}
    same.update(starts=standard.starts == permuted.starts,
                first_start=standard.first_start == permuted.first_start,
                date=standard.date == permuted.date,
                status=standard.status == permuted.status)
    plan_path = OUT / (name + ".plan.json")
    command = [sys.executable, str(app / "dispatch.py"), "--data", str(REVERSED),
               "--output", str(plan_path)]
    start = time.monotonic()
    proc = subprocess.run(command, capture_output=True, text=True, timeout=120, env=os.environ.copy())
    record = {"loader_fields_identical": same, "command": command,
              "exit_code": proc.returncode, "elapsed_seconds": time.monotonic() - start,
              "stdout": proc.stdout, "stderr": proc.stderr, "failures": []}
    if proc.returncode == 0:
        plan = json.loads(plan_path.read_text())
        flows = day.true_flows(plan)
        for check in F.CHECKS:
            try:
                getattr(F.T, check)((day, plan, flows))
            except Exception as exc:
                record["failures"].append({"test": check, "exception": repr(exc)})
        actual = float(flows["cost"].sum())
        record.update(physical_report_checks_passed=len(F.CHECKS) - len(record["failures"]),
                      recomputed_cost_gbp=actual, regret_gbp=actual-best,
                      cost_passes=actual <= best + max(.5, 2e-4*best))
    report["apps"][name] = record
    (OUT / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(name, record, flush=True)

report["all_passed"] = all(r["exit_code"] == 0 and not r["failures"] and r["cost_passes"]
                           and all(r["loader_fields_identical"].values()) for r in report["apps"].values())
report["E_success"] = False
(OUT / "result.json").write_text(json.dumps(report, indent=2) + "\n")
assert report["all_passed"]
print("All three apps pass the one combined reversal probe; all loader fields equal the original day.", flush=True)
