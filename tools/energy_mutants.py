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
        "    row[iB:iB + nB] = 1.0\n    A_eq.append(row)\n    b_eq.append(day.heat[t] + plant.lthw_loss_kw - sum(piece[4] for piece in pieces))",
        "    row[iB:iB + nB] = 1.0\n    A_ub.append(-row)\n    b_ub.append(-(day.heat[t] + plant.lthw_loss_kw - sum(piece[4] for piece in pieces)))")],
    "lt_heat_counted": [("planner/plant.py",
        "self.heat_kw = np.array([p[\"ht_heat_kw\"] for p in pts], dtype=float)",
        "self.heat_kw = np.array([p[\"ht_heat_kw\"] + p[\"lt_heat_kw\"] for p in pts], dtype=float)")],
    "towers_take_cooling_only": [("planner/plant.py",
        "return kw * (1.0 + 1.0 / self.cop(condenser_entering_c))", "return kw"),
        ("planner/plant.py", "return kw * (1.0 + 1.0 / self.cop)", "return kw")],
    "kva_ignores_engines": [("planner/plant.py",
        "self.kvar_per_kwe = math.sqrt(1.0 - pf * pf) / pf", "self.kvar_per_kwe = 0.0")],
    "absorber_needs_cold_weather": [("planner/plant.py",
        "return max(wet_bulb_c + self.tower_approach, self.tower_min_leaving, at_least_c)",
        "return max(wet_bulb_c + self.tower_approach, self.tower_min_leaving)"),
        ("planner/optimize.py",
        'bounds[iA + j] = (0.0, cap(a, a.max_kw, _CHILLER_PARTS["absorption"]) if absorbing else 0.0)',
        'bounds[iA + j] = (0.0, cap(a, a.max_kw, _CHILLER_PARTS["absorption"])'
        ' if cewt >= a.cooling_water_in_min_c else 0.0)')],
    "weekend_from_utc_start": [("planner/tariff.py", "from datetime import date\n",
        "from datetime import date, timedelta\n"),
        ("planner/tariff.py", "self.weekend = day.weekday() >= 5", "self.weekend = (day - timedelta(days=1)).weekday() >= 5")],
    # likely half-fixes
    "kva_as_kw": [("planner/optimize.py",
        "        b_ub.append(tariff.import_capacity_kva - math.sin(th) * day.kvar[t])",
        "        b_ub.append(tariff.import_capacity_kva + 1e6 * abs(math.sin(th)))")],
    "kva_engines_absorb_kvar": [("planner/plant.py",
        "self.kvar_per_kwe = math.sqrt(1.0 - pf * pf) / pf", "self.kvar_per_kwe = -math.sqrt(1.0 - pf * pf) / pf")],
    "towers_absorber_only": [("planner/plant.py",
        "return kw * (1.0 + 1.0 / self.cop(condenser_entering_c))", "return kw")],
    "cop_at_dry_bulb": [("planner/optimize.py",
        "cewt = plant.condenser_entering(day.wet_bulb[t], floor)", "cewt = max(day.dry_bulb[t], floor)")],
    "cewt_without_minimum": [("planner/plant.py",
        "return max(wet_bulb_c + self.tower_approach, self.tower_min_leaving, at_least_c)",
        "return max(wet_bulb_c + self.tower_approach, at_least_c)")],
    "no_engine_aux": [("planner/optimize.py",
        "b_eq.append(day.elec[t] - pv + sum(e.aux_kwe for e in engines))",
        "b_eq.append(day.elec[t] - pv)")],
    "no_lthw_loss": [("planner/optimize.py",
        "b_eq.append(day.heat[t] + plant.lthw_loss_kw - sum(piece[4] for piece in pieces))",
        "b_eq.append(day.heat[t] - sum(piece[4] for piece in pieces))")],
    "outages_ignored": [("planner/optimize.py",
        "            if any(o and not _engine_can_run(day, plant, e, day.starts[t])\n"
        "                   for e, o in zip(plant.engines, on)):",
        "            if False:")],
    "outage_by_period_start": [("planner/optimize.py",
        "if o[\"unit\"] == unit_id and m < _minutes(o[\"to\"]) and m + 30 > _minutes(o[\"from\"]):",
        "if o[\"unit\"] == unit_id and _minutes(o[\"from\"]) <= m < _minutes(o[\"to\"]):")],
    "phe1_outage_ignored": [("planner/optimize.py",
        "    if _available(day, \"PHE1\", day.starts[t]):", "    if True:")],
    "lt_radiator_outage_ignored": [("planner/optimize.py",
        '               + plant.engine_lt_sinks[engine.id])',
        '               + ())')],
    "intercooler_outage_ignored": [("planner/optimize.py",
        'for item in (engine.id, f"{engine.id} intercooler", f"{engine.id} jacket water and exhaust")',
        'for item in (engine.id, f"{engine.id} jacket water and exhaust")')],
    "ht_source_outage_ignored": [("planner/optimize.py",
        'for item in (engine.id, f"{engine.id} intercooler", f"{engine.id} jacket water and exhaust")',
        'for item in (engine.id, f"{engine.id} intercooler")')],
    "parts_by_name_prefix": [("planner/optimize.py",
        'for item in (engine.id, f"{engine.id} intercooler", f"{engine.id} jacket water and exhaust")\n'
        '               + plant.engine_lt_sinks[engine.id])',
        'for item in (engine.id,) + tuple(o["unit"] for o in day.status.get("outages", [])\n'
        '                                               if o["unit"].startswith(engine.id + " ")))')],
    "ac_generator_outage_ignored": [("planner/optimize.py",
        '"absorption": ("generator", "absorber and condenser")}',
        '"absorption": ("absorber and condenser",)}')],
    "condenser_outage_ignored": [("planner/optimize.py",
        '_CHILLER_PARTS = {"electric": ("condenser",),', '_CHILLER_PARTS = {"electric": (),')],
    "absorption_chiller_parts_ignored": [("planner/optimize.py",
        '"absorption": ("generator", "absorber and condenser")}', '"absorption": ()}')],
    "outages_engines_only": [("planner/optimize.py",
        "        return kw if all(_available(day, item, day.starts[t]) for item in items) else 0.0",
        "        return kw")],
    "tower_cell_outage_ignored": [("planner/optimize.py",
        "cells = sum(_available(day, cell, day.starts[t]) for cell in plant.tower_cells)",
        "cells = len(plant.tower_cells)")],
    "pv_outage_ignored": [("planner/optimize.py",
        "pv = day.pv[t] if _available(day, plant.pv_id, day.starts[t]) else 0.0",
        "pv = day.pv[t]")],
    "kva_positive_reactive_only": [("planner/optimize.py",
        "_ANGLES = np.radians(np.arange(-90.0, 90.5, 1.0))", "_ANGLES = np.radians(np.arange(0.0, 90.5, 1.0))")],
    "outages_one_per_unit": [("planner/optimize.py",
        '    for o in day.status.get("outages", []):\n        if o["unit"] == unit_id and',
        '    for o in {x["unit"]: x for x in day.status.get("outages", [])}.values():\n        if o["unit"] == unit_id and')],
    "outage_capacity_prorated": [("planner/optimize.py",
        """    def cap(unit, kw, parts=()):
        items = [unit.id] + [f"{unit.id} {part}" for part in parts]
        return kw if all(_available(day, item, day.starts[t]) for item in items) else 0.0
""", """    def cap(unit, kw, parts=()):
        items = [unit.id] + [f"{unit.id} {part}" for part in parts]
        m, share = _minutes(day.starts[t]), 1.0
        for o in day.status.get("outages", []):
            if o["unit"] in items:
                share -= max(0, min(_minutes(o["to"]), m + 30) - max(_minutes(o["from"]), m)) / 30.0
        return kw * max(share, 0.0)
""")],
    "absorber_cooling_water_ignored": [("planner/plant.py",
        "return max(wet_bulb_c + self.tower_approach, self.tower_min_leaving, at_least_c)",
        "return max(wet_bulb_c + self.tower_approach, self.tower_min_leaving)")],
    "header_not_shared": [("planner/optimize.py",
        "        row[iE + j] = -1.0 / ch.cop(cewt)",
        "        row[iE + j] = -1.0 / ch.cop(plant.condenser_entering(day.wet_bulb[t]))"),
        ("planner/optimize.py",
        "        row[iE + j] = ch.rejected(1.0, cewt)",
        "        row[iE + j] = ch.rejected(1.0, plant.condenser_entering(day.wet_bulb[t]))")],
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
