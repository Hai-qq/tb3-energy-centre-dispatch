"""Independent costs, visible energy-bus parity and fixed-day rule certificates."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time
import shutil
import tempfile
import numpy as np

B = Path(__file__).resolve().parent
T = B.parent/'task'
sys.path.insert(0, str(T/'tests'))
from reference import Day

plans = B/'plans'
plans.mkdir(exist_ok=True)
costs, pressure = {}, {}
for name in ('visible','h1','h2','h3','h4'):
    day = Day(T/'tests/days'/name)
    output = plans/(name+'.solution.json')
    start = time.monotonic()
    subprocess.run([sys.executable, str(T/'solution/app/dispatch.py'), '--data', str(T/'tests/days'/name), '--output', str(output)], check=True, capture_output=True, text=True, timeout=120)
    solution_seconds = time.monotonic()-start
    solution = json.loads(output.read_text())
    f = day.true_flows(solution)
    start = time.monotonic()
    optimum = day.least_cost()
    milp_seconds = time.monotonic()-start
    (plans/(name+'.milp.json')).write_text(json.dumps(optimum, indent=2)+'\n')
    gap = float(f['cost'].sum()-optimum['cost'])
    costs[name] = {'true_cost_gbp':float(f['cost'].sum()), 'reported_cost_gbp':solution['summary']['cost_gbp'],
                   'milp_cost_gbp':optimum['cost'], 'gap_gbp':gap,
                   'solution_seconds':solution_seconds, 'milp_seconds':milp_seconds}
    assert abs(gap)<0.001, (name, gap)
    assert solution_seconds<120 and milp_seconds<120
    pressure[name] = {'radiator_certificates':day.radiator_pressure,
                      'bounds_equal_all_periods':bool(np.array_equal(day.ahu_len_cap, day.ahu_strict_cap)),
                      'dry_bulb_range_c':[float(day.dry_bulb.min()),float(day.dry_bulb.max())],
                      'periods':[{'start':day.starts[t].strftime('%H:%M'),
                                  'ahu_kw':float(day.ahu[t]), 'T_f':float(f['T_f'][t]), 'T_r':float(f['T_r'][t]),
                                  'lenient_temperature_cap_kw':float(day.ahu_len_cap[t]),
                                  'strict_temperature_cap_kw':float(day.ahu_strict_cap[t]),
                                  'lt_heat_kw':float(f['lt_heat'][t]),
                                  'R_len_kw':float(f['R_len'][t]), 'R_strict_kw':float(f['R_strict'][t])} for t in range(48)]}

# Compare only the new recovery interpretation; all old repairs stay identical.
with tempfile.TemporaryDirectory(prefix='t1-visible-energy-') as tmp:
    app = Path(tmp)/'app'
    shutil.copytree(T/'solution/app', app, ignore=shutil.ignore_patterns('__pycache__'))
    p = app/'planner/plant.py'
    text = p.read_text()
    old = 'return float(flow <= lt_flow_c - 5.0)'
    assert text.count(old)==1
    p.write_text(text.replace(old, 'return 1.0'))
    out = Path(tmp)/'visible.json'
    subprocess.run([sys.executable,str(app/'dispatch.py'),'--data',str(T/'tests/days/visible'),'--output',str(out)],check=True,capture_output=True,text=True,timeout=120)
    energy_bus = json.loads(out.read_text())
    strict = json.loads((plans/'visible.solution.json').read_text())
    parity = {'energy_bus_cost_gbp':energy_bus['summary']['cost_gbp'],
              'strict_cost_gbp':strict['summary']['cost_gbp'], 'plans_identical':energy_bus==strict,
              'temperature_caps_equal_all_periods':pressure['visible']['bounds_equal_all_periods']}
    assert parity['plans_identical'] and parity['temperature_caps_equal_all_periods']
(B/'visible_parity.json').write_text(json.dumps(parity,indent=2)+'\n')
(B/'costs.json').write_text(json.dumps(costs,indent=2)+'\n')
(B/'rule_pressure.json').write_text(json.dumps(pressure,indent=2)+'\n')
print(json.dumps({'costs':costs,'visible_parity':parity},indent=2))
