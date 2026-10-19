"""Check finite all-off feasibility before selecting a radiator window."""
from pathlib import Path
import itertools
import json
import math
import sys

B = Path(__file__).resolve().parent
T = B.parent/'task'
sys.path.insert(0, str(T/'solution/app'))
from planner.data import load_day
from planner.plant import Plant
from planner.tariff import Tariff
from planner.optimize import _period

rows = []
for name in ['h2', 'h3', 'h4']:
    day = load_day(T/'tests/days'/name)
    plant = Plant(day.plant)
    tariff = Tariff(day.supply, day.date)
    fixed = json.loads((B/'initial-plans'/f'{name}.solution.json').read_text())
    times = []
    periods = []
    for t in range(48):
        off = min(_period(day, plant, tariff, t, (None, None), a)[0] for a in (False, True))
        # Optimistic lower bound: no auxiliary load, unlimited best-COP EC,
        # all forecast PV, no cell or EC outage. With no engine heat AC must be off.
        cewt = plant.condenser_entering(day.wet_bulb[t])
        best_cop = max(c.cop(cewt) for c in plant.electric_chillers)
        import_lb = max(0.0, day.elec[t]-day.pv[t]+day.cool[t]/best_cop)
        kva_lb = math.hypot(import_lb, day.kvar[t])
        periods.append({'start': day.starts[t], 'all_off_feasible': math.isfinite(off),
                        'optimistic_all_off_import_kw': import_lb,
                        'optimistic_all_off_grid_kva': kva_lb,
                        'import_limit_kva': tariff.import_capacity_kva,
                        'grid_lower_bound_exceeds_limit': kva_lb > tariff.import_capacity_kva+0.5})
        if off < float('inf'):
            times.append({'start': day.starts[t], 'all_off_period_cost': off,
                          'initial_solution_period_cost': fixed['periods'][t]['cost_gbp']})
    rows.append({'day': name, 'finite_all_off': times, 'periods': periods,
                 'minimum_optimistic_all_off_grid_kva': min(p['optimistic_all_off_grid_kva'] for p in periods),
                 'all_period_grid_lower_bounds_exceed_limit': all(p['grid_lower_bound_exceeds_limit'] for p in periods)})
    print(name, times, flush=True)
(B/'window_scan.json').write_text(json.dumps(rows, indent=2)+'\n')
