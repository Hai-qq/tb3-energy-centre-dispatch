"""Probe timestamp identity and existing reference row-order dependence.

Recovered from the original conversation after the workspace cleanup. Running
this file creates a new, explicitly labelled recovery execution record; it does
not reconstruct the lost original stdout or JSON output.

No task data is changed. The state-cost example is an isolated chronology
calculation, not a complete feasible hospital dispatch plan.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

import numpy as np
import scipy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TASK = ROOT / "tasks/energy-centre-dispatch"
spec = importlib.util.spec_from_file_location("order_contract_reference", TASK / "tests/reference.py")
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)


def copy_variant(name, which):
    target = HERE / "order-contract-fixtures-recovery" / name
    shutil.copytree(TASK / "tests/days/visible", target, dirs_exist_ok=True)
    if which:
        path = target / which
        lines = path.read_text().splitlines()
        old = lines[1:]
        new = list(reversed(old)) if which == "weather.csv" else old[24:] + old[:24]
        assert sorted(new) == sorted(old)
        path.write_text("\n".join([lines[0]] + new) + "\n")
    return R.Day(target)


base = copy_variant("original", None)
weather = copy_variant("weather_reversed", "weather.csv")
demand = copy_variant("demand_noon_first", "demand.csv")
assert np.array_equal(base.wet_bulb, weather.wet_bulb)
assert np.array_equal(base.pv, weather.pv)
assert base.clock == weather.clock
ix = np.argsort(demand.clock)
for key in ["elec", "kvar", "heat", "cool", "wet_bulb", "pv"]:
    assert np.array_equal(getattr(base, key), getattr(demand, key)[ix]), key


def state_example(day):
    day.running0 = {"GE1"}
    periods = []
    for clock in day.clock:
        periods.append({"start": f"{clock // 60:02d}:{clock % 60:02d}",
                        "engines_kwe": {"GE1": 600.0 if clock >= 720 else 0.0, "GE2": 0.0},
                        "boilers_kw": {"B1": 0.0, "B2": 0.0},
                        "chillers_kw": {"EC1": 0.0, "EC2": 0.0, "AC1": 0.0},
                        "pv_kw": 0.0, "import_kw": 0.0, "export_kw": 0.0})
    flows = day.true_flows({"periods": periods})
    return {"starts_reported_by_current_reference": flows["starts"],
            "cost_reported_by_current_reference": float(flows["cost"].sum())}


natural, permuted = state_example(base), state_example(demand)
assert natural["starts_reported_by_current_reference"] == 1
assert permuted["starts_reported_by_current_reference"] == 0
assert abs(natural["cost_reported_by_current_reference"] - permuted["cost_reported_by_current_reference"] - 38) < 1e-8
result = {"provenance": {"kind": "post-cleanup recovery rerun",
                         "executed_utc": datetime.now(timezone.utc).isoformat(),
                         "python": sys.version.split()[0], "numpy": np.__version__, "scipy": scipy.__version__,
                         "reference_sha256": hashlib.sha256((TASK / "tests/reference.py").read_bytes()).hexdigest(),
                         "source": "Script recovered from the conversation; this output was newly executed, not recreated from the lost original log."},
          "weather_permutation_changes_current_reference_inputs": False,
          "demand_permutation_preserves_all_timestamp_keyed_values": True,
          "current_reference_preserves_demand_row_order": {"original_first_clock": base.clock[0],
                                                            "permuted_first_clock": demand.clock[0]},
          "isolated_identical_physical_engine_schedule": {"running_at_midnight": ["GE1"],
                                                           "GE1_on_local_times": "12:00 to 24:00", "GE2": "off"},
          "chronological_order": natural, "noon_first_row_order": permuted,
          "limitation": "This proves reference chronology dependence; it does not decide whether unordered input is within the promised production schema, nor evaluate an opponent or a complete feasible plan."}
(HERE / "order_contract.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
