"""Diagnostic existing-field counterexample, with a directional whole-day MILP.

This writes only under checks-v20/audit. It never changes the archived apps or task.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
# The archive is read-only; it matches the 9db5808 baseline, while the root task
# may be changed concurrently during v20 construction.
TASK = ROOT / "archive/energy-centre-dispatch-v19"
OUT = HERE / "arbitrage"
OUT.mkdir(exist_ok=True)


def load_ref():
    src = (TASK / "tests/reference.py").read_text()
    src = src.replace('["Z", "I", "X"]', '["Z", "I", "X", "DIR"]')
    old = '            hi[v(t, "I")], hi[v(t, "X")] = self.import_kva, self.export_max'
    new = old + '''
            hi[v(t, "DIR")], integ[v(t, "DIR")] = 1.0, 1
            add({v(t, "I"): 1.0, v(t, "DIR"): -self.import_kva}, -np.inf, 0.0)
            add({v(t, "X"): 1.0, v(t, "DIR"): self.export_max}, -np.inf, self.export_max)'''
    assert old in src
    src = src.replace(old, new)
    p = OUT / "reference_directional.py"
    p.write_text(src)
    spec = importlib.util.spec_from_file_location("reference_directional", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Day


def scenario(name, demand=None, import_night=13.8, export=15.0, gas=4.35):
    data = OUT / name / "data"
    if data.exists():
        shutil.rmtree(data)
    shutil.copytree(TASK / "environment/data", data)
    supply = json.loads((data / "supply.json").read_text())
    for kind in ("weekday", "weekend"):
        supply["electricity"]["import_rates_p_per_kwh"][kind][0]["rate"] = import_night
    supply["electricity"]["export_rate_p_per_kwh"] = export
    supply["gas"]["rate_p_per_kwh"] = gas
    (data / "supply.json").write_text(json.dumps(supply, indent=2) + "\n")
    if demand is not None:
        rows = list(csv.DictReader((data / "demand.csv").open()))
        for row in rows:
            row.update({k: str(v) for k, v in demand.items()})
        with (data / "demand.csv").open("w") as fh:
            w = csv.DictWriter(fh, fieldnames=rows[0]); w.writeheader(); w.writerows(rows)
        status = json.loads((data / "status.json").read_text())
        status["outages"] = []
        status["running_at_midnight"] = []
        (data / "status.json").write_text(json.dumps(status, indent=2) + "\n")
        rows = list(csv.DictReader((data / "weather.csv").open()))
        for row in rows:
            row["pv_kw"] = "0"
            row["wet_bulb_c"] = "18"
            row["dry_bulb_c"] = "24"
        with (data / "weather.csv").open("w") as fh:
            w = csv.DictWriter(fh, fieldnames=rows[0]); w.writeheader(); w.writerows(rows)
    return data


def run(name, data, Day):
    d = Day(data)
    t0 = time.monotonic(); optimum = d.least_cost()
    (data.parent / "directional-milp-plan.json").write_text(json.dumps(optimum, indent=2) + "\n")
    out = {"name": name, "directional_milp_cost": optimum["cost"], "milp_seconds": time.monotonic() - t0, "apps": {}}
    for version in (16, 19):
        app = ROOT / f"results/v{version}-trials/ecd{version}-run2-claude/app"
        p = data.parent / f"v{version}-plan.json"
        command = [sys.executable, str(app / "dispatch.py"), "--data", str(data), "--output", str(p)]
        t0 = time.monotonic()
        result = subprocess.run(command, capture_output=True, text=True, timeout=120, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1"))
        (data.parent / f"v{version}-stdout.log").write_text(result.stdout)
        (data.parent / f"v{version}-stderr.log").write_text(result.stderr)
        info = {"returncode": result.returncode, "seconds": time.monotonic() - t0, "command": command}
        if result.returncode == 0:
            plan = json.loads(p.read_text())
            flows = d.true_flows(plan)
            imp_exp = [{"t": r["start"], "import_kw": r["import_kw"], "export_kw": r["export_kw"]} for r in plan["periods"] if min(r["import_kw"], r["export_kw"]) > 0.5]
            netted_cost = float(flows["cost"].sum())
            for t, r in enumerate(plan["periods"]):
                netted_cost += 0.5 * min(r["import_kw"], r["export_kw"]) * (d.export_rate - d.import_rate[t])
            info.update({"reported_cost": plan["summary"]["cost_gbp"], "true_cost_as_reported": float(flows["cost"].sum()), "physical_netted_cost": netted_cost, "physical_regret_gbp": netted_cost - optimum["cost"], "simultaneous_count": len(imp_exp), "simultaneous_examples": imp_exp[:4]})
        out["apps"][str(version)] = info
    (data.parent / "result.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out), flush=True)
    return out


if __name__ == "__main__":
    Day = load_ref()
    cases = [
        ("visible-export15", None, 13.8, 15.0, 4.35),
        ("visible-night7-export12", None, 7.0, 12.0, 4.35),
        ("flat-1250-heat1600", dict(electricity_kw=1250, reactive_kvar=450, heat_kw=1600, cooling_kw=500), 7.0, 12.0, 4.35),
        ("flat-1500-heat1600", dict(electricity_kw=1500, reactive_kvar=450, heat_kw=1600, cooling_kw=500), 7.0, 12.0, 4.35),
        ("flat-1250-heat2000", dict(electricity_kw=1250, reactive_kvar=450, heat_kw=2000, cooling_kw=500), 7.0, 12.0, 4.35),
    ]
    outputs=[]
    for name, demand, imp, exp, gas in cases:
        try:
            outputs.append(run(name, scenario(name, demand, imp, exp, gas), Day))
        except Exception as exc:
            outputs.append({"name": name, "error": repr(exc)})
            print(json.dumps(outputs[-1]), flush=True)
    (OUT / "summary.json").write_text(json.dumps(outputs, indent=2) + "\n")
