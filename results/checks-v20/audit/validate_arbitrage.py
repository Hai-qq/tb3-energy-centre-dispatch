"""Recompute saved probes and show that a diagnostic direction fix removes the defect.

The fixed copies are diagnostic model corrections, NOT minimal format adapters.
"""
from __future__ import annotations
import difflib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
from probe_arbitrage import HERE, OUT, ROOT, load_ref


def physical(Day, directory, plan_path):
    day = Day(directory / "data")
    plan = json.loads(plan_path.read_text())
    flows = day.true_flows(plan)
    p = plan["periods"]
    engines = np.array([sum(r["engines_kwe"].values()) for r in p])
    boilers = np.array([sum(r["boilers_kw"].values()) for r in p])
    cooling = np.array([sum(r["chillers_kw"].values()) for r in p])
    imp = np.array([r["import_kw"] for r in p]); exp = np.array([r["export_kw"] for r in p])
    pv = np.array([r["pv_kw"] for r in p])
    overlaps = np.minimum(imp, exp)
    cost = float(flows["cost"].sum() + np.sum(0.5 * overlaps * (day.export_rate - day.import_rate)))
    checks = {
        "unit_ratings_and_outages": bool(flows["running_ok"].all()),
        "electricity_balance_max_abs_kw": float(np.abs(engines + pv + imp - exp - day.elec - flows["aux"] - flows["ec_elec"]).max()),
        "heat_balance_max_abs_kw": float(np.abs(flows["engine_heat"] - flows["ac_heat"] + boilers - day.heat - day.lthw_loss).max()),
        "cooling_balance_max_abs_kw": float(np.abs(cooling - day.cool).max()),
        "tower_excess_max_kw": float(np.max(flows["rejected"] - day.tower_max)),
        "net_connection_kva_max": float(np.max(np.hypot(imp-exp, day.kvar-flows["engine_kvar"]))),
        "net_export_max_kw": float(np.max(exp - imp)),
        "directional_overlap_periods": int(np.sum(overlaps > 0.5)),
        "physical_netted_cost": cost,
        "reported_cost": plan.get("summary", {}).get("cost_gbp"),
    }
    return checks


def corrected_app(version):
    base = ROOT / f"results/v{version}-trials/ecd{version}-run2-claude/app"
    dest = OUT / "diagnostic-direction-fixed" / f"v{version}" / "app"
    if dest.exists(): shutil.rmtree(dest)
    shutil.copytree(base, dest)
    target = dest / "planner/optimize.py"
    before = target.read_text()
    s = before
    if version == 16:
        old = '    def _solve(self, segs: list[Segment | None], water: _Water) -> Loading | None:'
        new = '''    def _solve(self, segs: list[Segment | None], water: _Water) -> Loading | None:
        best = None
        for direction in ("import", "export"):
            candidate = self._solve_direction(segs, water, direction)
            if candidate is not None and (best is None or _better((candidate.excess_kva, candidate.cost), (best.excess_kva, best.cost))):
                best = candidate
        return best

    def _solve_direction(self, segs: list[Segment | None], water: _Water, direction: str) -> Loading | None:'''
        assert old in s; s = s.replace(old, new)
        s = s.replace('bounds[self.iI] = (0.0, None)', 'bounds[self.iI] = (0.0, None if direction == "import" else 0.0)')
        s = s.replace('bounds[self.iX] = (0.0, tariff.export_limit_kw)', 'bounds[self.iX] = (0.0, tariff.export_limit_kw if direction == "export" else 0.0)')
    else:
        old = '''def _solve(h: _Half, plant: Plant, tariff: Tariff, run: list[tuple[Engine, Stretch]],
           condenser_c: float, absorbers: list[AbsorptionChiller], excess: bool) -> _Loading | None:'''
        new = '''def _solve(h: _Half, plant: Plant, tariff: Tariff, run: list[tuple[Engine, Stretch]],
           condenser_c: float, absorbers: list[AbsorptionChiller], excess: bool) -> _Loading | None:
    best = None
    for direction in ("import", "export"):
        candidate = _solve_direction(h, plant, tariff, run, condenser_c, absorbers, excess, direction)
        if candidate is not None and (best is None or candidate.rank < best.rank - 1e-9):
            best = candidate
    return best


def _solve_direction(h: _Half, plant: Plant, tariff: Tariff, run: list[tuple[Engine, Stretch]],
           condenser_c: float, absorbers: list[AbsorptionChiller], excess: bool, direction: str) -> _Loading | None:'''
        assert old in s; s = s.replace(old, new)
        s = s.replace('bounds[iI] = (0.0, math.inf if excess else tariff.import_capacity_kva)', 'bounds[iI] = (0.0, (math.inf if excess else tariff.import_capacity_kva) if direction == "import" else 0.0)')
        s = s.replace('bounds[iX] = (0.0, tariff.export_limit_kw)', 'bounds[iX] = (0.0, tariff.export_limit_kw if direction == "export" else 0.0)')
    target.write_text(s)
    (dest.parent / "model-correction.diff").write_text("".join(difflib.unified_diff(before.splitlines(True), s.splitlines(True), fromfile=f"v{version}/original-optimize.py", tofile=f"v{version}/direction-corrected-optimize.py")))
    return dest


if __name__ == "__main__":
    Day = load_ref()
    result = {}
    for directory in sorted(OUT.iterdir()):
        if not (directory / "result.json").exists(): continue
        item = {}
        for version in (16, 19):
            item[f"v{version}"] = physical(Day, directory, directory / f"v{version}-plan.json")
        item["MILP"] = physical(Day, directory, directory / "directional-milp-plan.json")
        result[directory.name] = item
    for version in (16, 19):
        app = corrected_app(version)
        directory = OUT / "flat-1250-heat2000"
        output = directory / f"v{version}-direction-corrected-plan.json"
        cmd = [sys.executable, str(app / "dispatch.py"), "--data", str(directory / "data"), "--output", str(output)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1"))
        (directory / f"v{version}-direction-corrected.log").write_text(r.stdout + r.stderr)
        item = {"returncode": r.returncode, "command": cmd}
        if r.returncode == 0: item.update(physical(Day, directory, output))
        result["flat-1250-heat2000"][f"v{version}-direction-corrected"] = item
    (OUT / "physical-validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
