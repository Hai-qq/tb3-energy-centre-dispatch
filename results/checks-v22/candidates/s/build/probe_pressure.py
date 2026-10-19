"""Retain initial unadjusted-day solutions and capacity/over-stopping probes."""
from pathlib import Path
import json
import shutil
import subprocess
import sys
import time

B = Path(__file__).resolve().parent
T = B.parent/'task'
sys.path.insert(0, str(T/'tests'))
from reference import Day
from candidate_mutants import M
plans = B/'initial-plans'
plans.mkdir(exist_ok=True)
apps = {'solution': T/'solution/app'}
for tag, name in [('ignored', 'lt_capacity_ignored'), ('stopped', 'lt_radiator_outage_stops_engines')]:
    app = B/(tag+'-app')
    shutil.copytree(T/'solution/app', app, ignore=shutil.ignore_patterns('__pycache__'), dirs_exist_ok=True)
    for rel, old, new in M.MUTANTS[name]:
        p = app/rel
        s = p.read_text()
        assert s.count(old) == 1
        p.write_text(s.replace(old, new))
    apps[tag] = app
rows = []
for name in ['visible', 'h1', 'h2', 'h3', 'h4']:
    folder = T/'tests/days'/name
    if name == 'h1':
        folder = B/'baseline-h1-data'
        shutil.copytree(T/'tests/days'/name, folder, dirs_exist_ok=True)
        status_path = folder/'status.json'
        status = json.loads(status_path.read_text())
        status['outages'] = [o for o in status['outages']
                             if o != {'unit': 'LT PHE 1', 'from': '18:10', 'to': '19:20'}]
        status_path.write_text(json.dumps(status, indent=2)+'\n')
    day = Day(folder)
    row = {'day': name, 'plans': {}}
    for tag, app in apps.items():
        out = plans/(name+'.'+tag+'.json')
        start = time.monotonic()
        r = subprocess.run([sys.executable, str(app/'dispatch.py'), '--data', str(folder),
                            '--output', str(out)], capture_output=True, text=True, timeout=120)
        if r.returncode:
            row['plans'][tag] = {'error': r.stderr.strip()}
            continue
        plan = json.loads(out.read_text())
        flows = day.true_flows(plan)
        row['plans'][tag] = {'cost': float(flows['cost'].sum()), 'seconds': time.monotonic()-start,
                            'periods': [{'start': p['start'], 'engines_kwe': p['engines_kwe'],
                                         'heat': float(flows['lt_heat']['lt_heat_rejection'][i]),
                                         'capacity': float(day.lt_capacity['lt_heat_rejection'][i])}
                                        for i, p in enumerate(plan['periods'])]}
    rows.append(row)
    print(name, {k: ({'cost': v['cost'], 'over': [p['start'] for p in v['periods'] if p['heat']>p['capacity']+0.5]}
                      if 'cost' in v else v) for k,v in row['plans'].items()}, flush=True)
(B/'initial-pressure.json').write_text(json.dumps(rows, indent=2)+'\n')
