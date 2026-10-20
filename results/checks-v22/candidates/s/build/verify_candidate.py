"""Byte boundary, independent costs, visible parity and per-period rule pressure."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[5]
B = Path(__file__).resolve().parent
T = B.parent/'task'
BASE = ROOT/'tasks/energy-centre-dispatch'
SOURCE = Path('/private/tmp/claude-501/-Users-haiy-qq-Desktop----klavis/a70e7eab-ed43-4fbc-8c31-1d0858956a32/scratchpad/v22-prechecks/s/visible/app/data/plant.json')
sys.path.insert(0, str(T/'tests'))
from reference import Day

def save(name, value):
    (B/name).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')

def contents(folder):
    return {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob('*')
            if p.is_file() and '__pycache__' not in p.parts}

a, b = contents(BASE), contents(T)
assert a.keys() == b.keys()
diff = sorted(p for p in a if a[p] != b[p])
allowed = {'environment/data/plant.json', 'tests/reference.py', 'tests/test_plans.py',
           'solution/app/planner/plant.py', 'solution/app/planner/optimize.py',
           'tests/days/h1/status.json'}
allowed |= {f'tests/days/{name}/plant.json' for name in ['visible', 'h1', 'h2', 'h3', 'h4']}
assert set(diff) == allowed, (set(diff)-allowed, allowed-set(diff))
for rel in [p for p in allowed if p.endswith('plant.json')]:
    assert b[rel] == SOURCE.read_bytes(), rel
    expected = json.loads(a[rel])
    for n in (1, 2):
        expected['heat_circuits'][f'ge{n}_lt']['to'] = [f'LT PHE {n}']
    expected['heat_circuits']['lt_heat_rejection'] = {
        'flow_c': 37, 'return_c': 32, 'from': ['LT PHE 1', 'LT PHE 2'],
        'to': ['LT radiator 1', 'LT radiator 2']}
    expected['lt_radiators'] = [{'id': f'LT radiator {n}', 'max_kw': 220} for n in (1, 2)]
    assert json.loads(b[rel]) == expected
for rel in ['instruction.md', 'task.toml', 'environment/Dockerfile', 'tests/Dockerfile', 'tests/test.sh']:
    assert a[rel] == b[rel], rel
status = json.loads(a['tests/days/h1/status.json'])
status['outages'].append({'unit': 'LT PHE 1', 'from': '18:10', 'to': '19:20'})
assert json.loads(b['tests/days/h1/status.json']) == status
original_tests = a['tests/test_plans.py'].decode()
assert b['tests/test_plans.py'].decode().startswith(original_tests)
save('gate_a.json', {'passed': True, 'changed_files': diff,
                    'environment_changes': [p for p in diff if p.startswith('environment/')],
                    'protected_files_unchanged': True,
                    'all_original_plants_identical': len({a[p] for p in a if p.endswith('/plant.json')}) == 1,
                    'supplied_plant_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest()})
print('gate A passed', flush=True)
plans = B/'plans'
plans.mkdir(exist_ok=True)

def run_plan(app, folder, name):
    out = plans/(name+'.json')
    start = time.monotonic()
    r = subprocess.run([sys.executable, str(app/'dispatch.py'), '--data', str(folder), '--output', str(out)],
                       capture_output=True, text=True, timeout=120)
    seconds = time.monotonic()-start
    if r.returncode:
        return None, seconds, r.stderr.strip()
    return json.loads(out.read_text()), seconds, None

costs, pressure = [], []
for name in ['visible', 'h1', 'h2', 'h3', 'h4']:
    folder = T/'tests/days'/name
    day = Day(folder)
    fixed, seconds, error = run_plan(T/'solution/app', folder, name)
    assert not error, (name, error)
    start = time.monotonic()
    best = day.least_cost()
    milp_s = time.monotonic()-start
    assert milp_s < 120 and seconds < 120, (name, milp_s, seconds)
    flows = day.true_flows(fixed)
    total = float(flows['cost'].sum())
    gap = total-best['cost']
    assert abs(gap) < 0.001, (name, gap)
    costs.append({'day': name, 'date': str(day.date), 'least_cost_gbp': best['cost'],
                  'true_flows_cost_gbp': total, 'gap_gbp': gap,
                  'solution_seconds': seconds, 'milp_seconds': milp_s})
    assert all((heat <= flows['lt_capacity'][c]+0.5).all() for c, heat in flows['lt_heat'].items())
    ignored, _, error = run_plan(B/'ignored-app', folder, name+'.ignored')
    assert not error, error
    relaxed = day.true_flows(ignored)
    stopped, stop_s, stop_error = run_plan(B/'stopped-app', folder, name+'.stopped')
    row = {'day': name, 'date': str(day.date), 'radiator_outages': [o for o in day.status['outages']
            if o['unit'] in {r['id'] for r in day.plant['lt_radiators']}],
           'solution_cost_gbp': total, 'ignored_cost_gbp': float(relaxed['cost'].sum()),
           'stopped_plan_feasible': stopped is not None, 'stopped_seconds': stop_s,
           'stopped_error': stop_error,
           'stopped_cost_premium_gbp': float(day.true_flows(stopped)['cost'].sum()-total) if stopped else None,
           'stopped_cost_interpretation': 'finite premium' if stopped else 'infeasible; no finite cost premium',
           'periods': []}
    for i, p in enumerate(fixed['periods']):
        for circuit, heat in flows['lt_heat'].items():
            cap = float(flows['lt_capacity'][circuit][i])
            q = float(heat[i])
            ignored_q = float(relaxed['lt_heat'][circuit][i])
            row['periods'].append({'start': p['start'], 'circuit': circuit,
                                   'engines_kwe': p['engines_kwe'], 'lt_heat_kw': q,
                                   'capacity_kw': cap, 'ignored_lt_heat_kw': ignored_q,
                                   'ignored_exceeds_capacity': ignored_q > cap+0.5,
                                   'both_on_with_reduced_capacity': min(p['engines_kwe'].values()) > 0.5 and cap < 440})
    pressure.append(row)
    print('cost', costs[-1], flush=True)

baseline, _, error = run_plan(BASE/'solution/app', BASE/'environment/data', 'v19-visible')
assert not error, error
visible = json.loads((plans/'visible.json').read_text())
assert visible == baseline
vflows = Day(T/'tests/days/visible').true_flows(visible)
save('visible_parity.json', {'passed': True, 'complete_json_equal': True, 'all_48_periods_equal': True,
                            'reported_cost_gbp': visible['summary']['cost_gbp'],
                            'max_lt_heat_kw': max(float(x.max()) for x in vflows['lt_heat'].values()),
                            'minimum_spare_capacity_kw': min(float((vflows['lt_capacity'][c]-q).min())
                                                           for c,q in vflows['lt_heat'].items()),
                            'periods': [{'start': p['start'], 'equal': p == baseline['periods'][i]}
                                        for i,p in enumerate(visible['periods'])]})
initial = json.loads((B/'initial-plans/h1.solution.json').read_text())
final = json.loads((plans/'h1.json').read_text())
phe_periods = [{'start': p['start'], 'before_kwe': p['engines_kwe']['GE1'],
                'after_kwe': final['periods'][i]['engines_kwe']['GE1']}
               for i,p in enumerate(initial['periods']) if p['start'] in ('18:00', '18:30', '19:00')]
assert all(p['before_kwe']>0.5 and p['after_kwe']==0 for p in phe_periods)
save('phe_outage_pressure.json', {'day': 'h1', 'date': '2026-08-08', 'unit': 'LT PHE 1',
                                 'outage': ['18:10', '19:20'], 'other_engine_outages_overlap': False,
                                 'periods': phe_periods})
assert any(p['ignored_exceeds_capacity'] for d in pressure for p in d['periods'])
save('costs.json', costs)
save('rule_pressure.json', {'days': pressure, 'radiator_windows_changed': False,
                           'capacity_violation_pressure': True,
                           'over_stopping_caught_by_infeasibility': True,
                           'finite_over_stopping_cost_premium_requirement_met': False,
                           'both_on_derated_optimum_observed': any(p['both_on_with_reduced_capacity']
                                                                 for d in pressure for p in d['periods']),
                           'limitation': 'All-off is infeasible in every period of h2-h4; see window_scan.json. '
                                         'Changing only radiator outage windows cannot create a finite premium.'})
print('cost agreement, visible parity and pressure records passed; finite over-stopping premium unavailable', flush=True)
