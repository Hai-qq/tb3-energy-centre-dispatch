"""Mutation check for energy-centre-dispatch: each planted bug (and some likely
half-fixes and reporting faults) applied alone to the reference solution must fail the
tests. Exits with status 1 if any mutant passes them.

Usage: python tools/energy_mutants.py [name ...]
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from eval_energy import evaluate  # noqa: E402

SOL = Path(os.environ.get("ECD_TASK", ROOT / "tasks" / "energy-centre-dispatch")).resolve() / "solution" / "app"

# name: [(file, old, new), ...]
# the setpoint the shipped tool runs at: its design approach above the wet bulb, on the BMS's steps
_RULE = "min(max(21.0 + max(math.ceil((wb + {a} - 21.0) / 0.5 - 1e-9), 0) * 0.5, 21.0), 28.0)"
_Y = "        p.var(y, 0.0, 1.0, binary=True)\n"


def _setpoints_only(cond: str) -> list:
    """Restrict the program to the setpoints `cond` allows (an expression in sp and wb)."""
    return [("planner/optimize.py", _Y, f"        p.var(y, 0.0, 1.0 if {cond} else 0.0, binary=True)\n")]


MUTANTS = {
    # planted in the shipped tool
    "weather_by_utc_date": [("planner/data.py",
        "wx = [weather[s.astimezone(timezone.utc)] for s in starts]",
        "wx = [r for k, r in sorted(weather.items()) if k.date() == day]")],
    "two_point_curve": [("planner/plant.py",
        "        pts = d[\"part_load\"]\n", "        pts = [d[\"part_load\"][0], d[\"part_load\"][-1]]\n")],
    "gas_net_to_gross_divided": [("planner/tariff.py",
        "return kw * self.gross_per_net", "return kw / self.gross_per_net")],
    "starts_not_in_decision": [("planner/optimize.py",
        "            options = [best[j] + starts(prev, on) for j, prev in enumerate(combos)]",
        "            options = [best[j] for j, prev in enumerate(combos)]"),
        ("planner/optimize.py",
        "    best = np.array([cost[0, k] + starts(initial, on) for k, on in enumerate(combos)])",
        "    best = np.array([cost[0, k] for k, on in enumerate(combos)])")],
    "heat_can_be_dumped": [("planner/optimize.py",
        "constrained(dict(lthw), target, target)", "constrained(dict(lthw), target, np.inf)")],
    "lt_heat_counted": [("planner/plant.py",
        "self.heat_kw = np.array([p[\"ht_heat_kw\"] for p in pts], dtype=float)",
        "self.heat_kw = np.array([p[\"ht_heat_kw\"] + p[\"lt_heat_kw\"] for p in pts], dtype=float)")],
    "towers_take_cooling_only": [("planner/plant.py",
        "return kw * (1.0 + 1.0 / self.cop(condenser_entering_c))", "return kw"),
        ("planner/plant.py", "return kw * (1.0 + 1.0 / self.cop)", "return kw")],
    "kva_ignores_engines": [("planner/plant.py",
        "self.kvar_per_kwe = math.sqrt(1.0 - pf * pf) / pf", "self.kvar_per_kwe = 0.0")],
    "setpoint_fixed_approach": _setpoints_only("abs(sp - " + _RULE.format(a="4.0") + ") < 1e-9"),
    "absorber_at_its_best_rating": [("planner/plant.py",
        "return float(np.interp(cooling_water_in_c, self._cw, self._max))", "return float(self._max.max())")],
    "fans_at_cooling_load": [("planner/optimize.py",
        "{x: -cells * slope / full * r for x, r in rejected.items()}", "{x: -cells * slope / full for x in rejected}")],
    "weekend_from_utc_start": [("planner/tariff.py", "from datetime import date\n",
        "from datetime import date, timedelta\n"),
        ("planner/tariff.py", "self.weekend = day.weekday() >= 5", "self.weekend = (day - timedelta(days=1)).weekday() >= 5")],
    # likely half-fixes
    "setpoint_fixed_approach_header_held": _setpoints_only(
        "abs(sp - " + _RULE.format(a="4.0") + ") < 1e-9 or abs(sp - max(" + _RULE.format(a="4.0") + ", 22.0)) < 1e-9"),
    "setpoint_fixed_approach_5k_header_held": _setpoints_only(
        "abs(sp - " + _RULE.format(a="5.0") + ") < 1e-9 or abs(sp - max(" + _RULE.format(a="5.0") + ", 22.0)) < 1e-9"),
    "setpoint_at_22_or_coldest": _setpoints_only("sp <= 22.0 or sp <= wb + 4.0"),
    "fans_ignored": [("planner/optimize.py", "        el[f] = -1.0\n", "        el[f] = 0.0\n")],
    "fans_for_one_cell": [("planner/optimize.py",
        "{x: -cells * slope / full * r for x, r in rejected.items()}, y: -cells * icpt}",
        "{x: -slope / full * r for x, r in rejected.items()}, y: -icpt}")],
    "tower_capacity_at_design_approach": [("planner/optimize.py",
        "full = cells * plant.cell_capacity(wb, sp)", "full = cells * plant.cell_capacity(wb, wb + 4.0)")],
    "tower_table_by_setpoint": [("planner/plant.py",
        "        approach = setpoint_c - wet_bulb_c\n", "        approach = setpoint_c\n")],
    "setpoint_off_its_steps": [("planner/plant.py",
        "steps = round((sp[\"max\"] - sp[\"min\"]) / sp[\"step\"])",
        "steps = round((sp[\"max\"] - sp[\"min\"]) / (sp[\"step\"] / 2))"),
        ("planner/plant.py", "sp[\"min\"] + i * sp[\"step\"]", "sp[\"min\"] + i * sp[\"step\"] / 2")],
    "kva_as_kw": [("planner/optimize.py",
        "p.row(row, -np.inf, tariff.import_capacity_kva - math.sin(th) * (day.kvar[t] - gen_const))",
        "p.row(row, -np.inf, tariff.import_capacity_kva + 1e6 * abs(math.sin(th)))")],
    "kva_engines_absorb_kvar": [("planner/plant.py",
        "self.kvar_per_kwe = math.sqrt(1.0 - pf * pf) / pf", "self.kvar_per_kwe = -math.sqrt(1.0 - pf * pf) / pf")],
    "towers_absorber_only": [("planner/plant.py",
        "return kw * (1.0 + 1.0 / self.cop(condenser_entering_c))", "return kw")],
    "cop_at_dry_bulb": [("planner/optimize.py",
        "el[x] = -1.0 / ch.cop(sp)", "el[x] = -1.0 / ch.cop(day.dry_bulb[t])"),
        ("planner/optimize.py", "rejected[x] = ch.rejected(1.0, sp)", "rejected[x] = ch.rejected(1.0, day.dry_bulb[t])")],
    "header_not_shared": [("planner/optimize.py",
        "el[x] = -1.0 / ch.cop(sp)", "el[x] = -1.0 / ch.cop(min(sp, max(wb + 4.0, 21.0)))"),
        ("planner/optimize.py", "rejected[x] = ch.rejected(1.0, sp)",
         "rejected[x] = ch.rejected(1.0, min(sp, max(wb + 4.0, 21.0)))")],
    "no_engine_aux": [("planner/optimize.py",
        "el_const = e.min_kwe - e.aux_kwe", "el_const = e.min_kwe")],
    "no_lthw_loss": [("planner/optimize.py",
        "target = day.heat[t] + plant.lthw_loss_kw", "target = day.heat[t]")],
    "outages_ignored": [("planner/optimize.py",
        "            if any(o and not _engine_can_run(day, plant, e, day.starts[t])\n"
        "                   for e, o in zip(plant.engines, on)):",
        "            if False:")],
    "outage_by_period_start": [("planner/optimize.py",
        "if o[\"unit\"] == unit_id and m < _minutes(o[\"to\"]) and m + 30 > _minutes(o[\"from\"]):",
        "if o[\"unit\"] == unit_id and _minutes(o[\"from\"]) <= m < _minutes(o[\"to\"]):")],
    "phe1_outage_ignored": [("planner/optimize.py",
        "constrained(dict(absorb), 0.0, np.inf if _available(day, \"PHE1\", hhmm) else 0.0)",
        "constrained(dict(absorb), 0.0, np.inf)")],
    "lt_radiator_outage_ignored": [("planner/optimize.py",
        " and _available(day, f\"{engine.id} LT radiator\", hhmm)", "")],
    "outages_engines_only": [("planner/optimize.py",
        "        return kw if _available(day, unit_id, hhmm) else 0.0", "        return kw")],
    "tower_cell_outage_ignored": [("planner/optimize.py",
        "cells = sum(_available(day, cell, hhmm) for cell in plant.tower_cells)", "cells = len(plant.tower_cells)")],
    "pv_outage_ignored": [("planner/optimize.py",
        "pv = day.pv[t] if _available(day, plant.pv_id, hhmm) else 0.0", "pv = day.pv[t]")],
    "absorber_cooling_water_ignored": [("planner/plant.py",
        "        if cooling_water_in_c < self.cooling_water_in_min_c - 1e-9:\n            return 0.0\n", "")],
    "midnight_state_ignored": [("planner/optimize.py",
        "initial = tuple(e.id in running for e in plant.engines)",
        "initial = tuple(False for e in plant.engines)")],
    "saturday_is_weekday": [("planner/tariff.py",
        "self.weekend = day.weekday() >= 5", "self.weekend = day.weekday() > 5")],
    # reporting faults: the plant runs right, the plan reports it wrong
    "import_total_in_kw": [("dispatch.py",
        '"import_kwh": sum(p["import_kw"] for p in periods) * 0.5,',
        '"import_kwh": sum(p["import_kw"] for p in periods),')],
    "grid_flag_without_generators": [("planner/optimize.py",
        'p["grid_ok"] = math.hypot(p["import_kw"], kvar) <=',
        'p["grid_ok"] = math.hypot(p["import_kw"], day.kvar[t]) <=')],
    "plan_varies_between_runs": [("dispatch.py", "import json\n", "import json\nimport random\n"),
        ("dispatch.py",
        '"export_kwh": sum(p["export_kw"] for p in periods) * 0.5,',
        '"export_kwh": sum(p["export_kw"] for p in periods) * 0.5 + 0.01 * random.random(),')],
    # execution faults: the plan is right, the run is not
    "exits_with_error_after_writing": [("dispatch.py",
        'if __name__ == "__main__":\n    main()\n',
        'if __name__ == "__main__":\n    main()\n    raise SystemExit(77)\n')],
    "hangs_after_writing": [("dispatch.py",
        'if __name__ == "__main__":\n    main()\n',
        'if __name__ == "__main__":\n    main()\n    import time\n    time.sleep(3600)\n')],
}

# The solution plans a day in about a second; a short limit lets the hanging mutant fail fast.
RUN_TIMEOUT_S = 20


def main() -> None:
    names = sys.argv[1:] or list(MUTANTS)
    missed = 0
    for name in names:
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "app"
            shutil.copytree(SOL, app)
            for f, old, new in MUTANTS[name]:
                p = app / f
                s = p.read_text()
                assert s.count(old) == 1, (name, f, old)
                p.write_text(s.replace(old, new))
            r = evaluate(app, quiet=True, timeout=RUN_TIMEOUT_S)
        fails = "; ".join(f"{k.replace('test_', '')}:{','.join(v)}" for k, v in sorted(r["failed"].items()))
        errs = "; ".join(f"{d}:{e[:60]}" for d, e in r["errors"].items())
        print(f"{name:28s} {'CAUGHT' if r['failed'] else 'MISSED'}  {fails}  {errs}", flush=True)
        missed += not r["failed"]
    sys.exit(1 if missed else 0)


if __name__ == "__main__":
    main()
