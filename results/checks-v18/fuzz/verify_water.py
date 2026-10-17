"""Verify the warmer-water witness against all nine archived physical/report tests.

This does not change the task grader. It demonstrates what changes when the
known compressor input is matched to one common, attainable condenser-water
temperature instead of assuming its minimum. Run from the repository root with
the same Python/NumPy/SciPy versions as the task.
"""

import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
import fuzz_v18 as F

BASE = Path(__file__).resolve().parent / "water-probes"
records = []
for name in ("w0", "w1"):
    folder = BASE / "days" / name
    day = F.R.Day(folder)
    plan = json.loads((folder / "v17_codex_parts.plan.json").read_text())
    periods = []
    for t, p in enumerate(plan["periods"]):
        ac = float(p["chillers_kw"]["AC1"])
        mode = ac > 0.5
        aux = sum(e["auxiliary_kwe"] for e in day.plant["engines"]
                  if p["engines_kwe"][e["id"]] > 0.5) + 0.022 * ac
        compressor = (sum(p["engines_kwe"].values()) + p["pv_kw"]
                      + p["import_kw"] - p["export_kw"] - day.elec[t] - aux)
        lo = float(day.cewt[mode][t])
        hi = max(lo, 34.0)

        def power(temp):
            total = 0.0
            for c in day.plant["electric_chillers"]:
                curve = np.array(c["cop_by_condenser_entering_c"])
                total += p["chillers_kw"][c["id"]] / np.interp(temp, curve[:, 0], curve[:, 1])
            return total

        assert power(lo) - 1e-6 <= compressor <= power(hi) + 1e-6
        for _ in range(70):
            mid = (lo + hi) / 2
            if power(mid) < compressor:
                lo = mid
            else:
                hi = mid
        temp = (lo + hi) / 2
        for c in day.plant["electric_chillers"]:
            curve = np.array(c["cop_by_condenser_entering_c"])
            day.cop[c["id"]][mode][t] = np.interp(temp, curve[:, 0], curve[:, 1])
        if t == 32:
            periods.append({"period": p["start"], "required_compressor_kw": compressor,
                            "inferred_water_c": temp,
                            "electric_chiller_cop": p["chillers_kw"]["EC2"] / compressor,
                            "tower_rejection_kw": 700 + compressor,
                            "tower_capacity_kw": float(day.tower_max[t])})
    flows = day.true_flows(plan)
    fails = []
    for check in F.CHECKS:
        try:
            getattr(F.T, check)((day, plan, flows))
        except Exception as exc:
            fails.append({"check": check, "exception": repr(exc)})
    records.append({"case": name, "checks_passed": len(F.CHECKS) - len(fails),
                    "failures": fails, "periods": periods,
                    "cost_gbp": float(flows["cost"].sum())})
print(json.dumps(records, indent=2))
(BASE / "water-physics.json").write_text(json.dumps(records, indent=2) + "\n")
