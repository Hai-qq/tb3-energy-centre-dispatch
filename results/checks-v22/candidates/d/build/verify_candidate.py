"""Check byte boundaries, independent cost agreement and exhaust pressure."""
from pathlib import Path
import ast
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import numpy as np

B = Path(__file__).resolve().parent
ROOT = B.parents[4]
T = B.parent/'task'
BASE = ROOT/'tasks/energy-centre-dispatch'
S = ROOT/'results/checks-v22/candidates/s/task'
SUPPLIED = Path('/private/tmp/claude-501/-Users-haiy-qq-Desktop----klavis/a70e7eab-ed43-4fbc-8c31-1d0858956a32/scratchpad/v22-prechecks/d/visible/app')
sys.path.insert(0, str(T/'tests'))
from reference import Day


def save(name, value):
    (B/name).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def contents(folder):
    return {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob('*')
            if p.is_file() and '__pycache__' not in p.parts}


a, b, s = contents(BASE), contents(T), contents(S)
assert a.keys() == b.keys() == s.keys()
diff = sorted(p for p in a if a[p] != b[p])
assert [p for p in diff if p.startswith('environment/')] == ['environment/data/plant.json', 'environment/planner/plant.py']
allowed = {'environment/data/plant.json', 'environment/planner/plant.py', 'tests/reference.py',
           'tests/test_plans.py', 'solution/app/planner/plant.py', 'solution/app/planner/optimize.py',
           'tests/days/h1/status.json', 'tests/days/h2/status.json'}
allowed |= {f'tests/days/{d}/plant.json' for d in ('visible', 'h1', 'h2', 'h3', 'h4')}
assert set(diff) == allowed, (diff, allowed)
for rel in ['instruction.md', 'task.toml', 'environment/Dockerfile', 'tests/Dockerfile', 'tests/test.sh']:
    assert a[rel] == b[rel] == s[rel], rel
for p in [T/'environment/data/plant.json', *(T/'tests/days').glob('*/plant.json')]:
    assert p.read_bytes() == (SUPPLIED/'data/plant.json').read_bytes()
assert b['environment/planner/plant.py'] == (SUPPLIED/'planner/plant.py').read_bytes()
for rel in ['tests/days/h1/status.json', 'tests/days/h3/status.json', 'tests/days/h4/status.json']:
    assert s[rel] == b[rel], rel
expected = json.loads(s['tests/days/h2/status.json'])
for o in expected['outages']:
    if o['unit'] == 'GE2 jacket water and exhaust':
        o['unit'] = 'GE2 jacket water heat exchanger'
expected['outages'].append({'unit': 'GE1 exhaust heat exchanger', 'from': '12:00', 'to': '14:50'})
assert json.loads(b['tests/days/h2/status.json']) == expected
# All pre-existing tests survive, and only heat_balance changes its body.
def test_functions(data):
    return {n.name: ast.dump(n) for n in ast.parse(data).body if isinstance(n, ast.FunctionDef)}
old, new = test_functions(s['tests/test_plans.py']), test_functions(b['tests/test_plans.py'])
assert old.keys() == new.keys()
assert [n for n in old if old[n] != new[n]] == ['test_heat_balance']
save('gate_a.json', {'passed': True, 'changed_files': diff,
                    'environment_changes': [p for p in diff if p.startswith('environment/')],
                    'protected_files_unchanged': True,
                    'supplied_sha256': {rel: hashlib.sha256((SUPPLIED/rel).read_bytes()).hexdigest()
                                        for rel in ['data/plant.json', 'planner/plant.py']}})
print('gate A passed', flush=True)
plans = B/'plans'
plans.mkdir(exist_ok=True)


def run_plan(app, folder, name):
    out = plans/(name+'.json')
    start = time.monotonic()
    r = subprocess.run([sys.executable, str(app/'dispatch.py'), '--data', str(folder), '--output', str(out)],
                       capture_output=True, text=True, timeout=120)
    seconds = time.monotonic()-start
    assert not r.returncode, (name, r.stderr)
    return json.loads(out.read_text()), seconds


costs = []
for name in ['visible', 'h1', 'h2', 'h3', 'h4']:
    folder = T/'tests/days'/name
    day = Day(folder)
    fixed, seconds = run_plan(T/'solution/app', folder, name)
    start = time.monotonic()
    best = day.least_cost()
    milp_s = time.monotonic()-start
    total = float(day.true_flows(fixed)['cost'].sum())
    gap = total-best['cost']
    assert abs(gap) < 0.001 and seconds < 120 and milp_s < 120, (name, gap, seconds, milp_s)
    costs.append({'day': name, 'least_cost_gbp': best['cost'], 'true_flows_cost_gbp': total,
                  'gap_gbp': gap, 'solution_seconds': seconds, 'milp_seconds': milp_s})
    print(costs[-1], flush=True)
save('costs.json', costs)

visible = json.loads((plans/'visible.json').read_text())
day = Day(T/'tests/days/visible')
f = day.true_flows(visible)
baselines = {}
for label, task in [('v19', BASE), ('S', S)]:
    p, _ = run_plan(task/'solution/app', task/'environment/data', label+'-visible')
    baselines[label] = {'reported_cost_gbp': p['summary']['cost_gbp'],
                        'D_minus_baseline_gbp': visible['summary']['cost_gbp']-p['summary']['cost_gbp']}
periods = []
for i, p in enumerate(visible['periods']):
    generated = {e['id']: float(np.interp(p['engines_kwe'][e['id']], day.curve[e['id']][0], day.curve[e['id']][3]))
                 if p['engines_kwe'][e['id']] > 0.5 else 0.0 for e in day.engines}
    recovered = day.heat[i]+day.lthw_loss-sum(p['boilers_kw'].values())+f['ac_heat'][i]
    stack = float(f['jacket'][i]+sum(generated.values())-recovered)
    assert stack >= -0.01
    periods.append({'start': p['start'], 'exhaust_generated_kw': generated,
                    'stack_exhaust_kw': max(0.0, stack)})
save('visible_comparison.json', {'reported_cost_gbp': visible['summary']['cost_gbp'],
     'true_cost_gbp': float(f['cost'].sum()), 'baselines': baselines,
     'stack_exhaust_kwh': 0.5*sum(p['stack_exhaust_kw'] for p in periods),
     'stack_kw_max': max(p['stack_exhaust_kw'] for p in periods), 'periods': periods,
     'allocation_note': 'Total stack duty is inferred uniquely from the unchanged plan schema; allocation between engines is not reported.'})


def pressure(folder, window):
    day = Day(folder)
    fixed = day.least_cost()
    cost = fixed['cost']
    stopped = copy.deepcopy(day)
    stopped.available['GE1'] &= stopped.exhaust_ok['GE1']
    try:
        stop = stopped.least_cost()
        stop_result = {'feasible': True, 'cost_gbp': stop['cost'], 'premium_gbp': stop['cost']-cost}
    except RuntimeError as e:
        stop_result = {'feasible': False, 'error': str(e)}
    ignored = copy.deepcopy(day)
    ignored.exhaust_ok['GE1'] = np.ones(48, dtype=bool)
    bad = ignored.least_cost()
    flows = day.true_flows(bad)
    violations = []
    for i, p in enumerate(bad['periods']):
        recovered = day.heat[i]+day.lthw_loss-sum(p['boilers_kw'].values())+flows['ac_heat'][i]
        excess = float(recovered-flows['jacket'][i]-flows['exhaust'][i])
        if excess > 1.0:
            violations.append({'start': p['start'], 'recovered_exceeds_upper_kw': excess})
    row = {'day': 'h2', 'window': window, 'cost_gbp': cost, 'stopped': stop_result,
           'ignored': {'cost_gbp': bad['cost'], 'cost_difference_gbp': bad['cost']-cost,
                       'heat_violations': violations}}
    row['pressure_a'] = not stop_result['feasible'] or stop_result['premium_gbp'] > max(0.5, 2e-4*cost)
    row['pressure_b'] = bool(violations) or bad['cost'] < cost-max(0.5, 2e-4*cost)
    return row

with tempfile.TemporaryDirectory(prefix='d-first-window-') as tmp:
    folder = Path(tmp)/'h2'
    shutil.copytree(T/'tests/days/h2', folder)
    p = folder/'status.json'
    st = json.loads(p.read_text())
    st['outages'][-1].update({'from': '09:20', 'to': '14:50'})
    p.write_text(json.dumps(st, indent=2)+'\n')
    initial = pressure(folder, ['09:20', '14:50'])
    initial['overlaps_existing_GE1_intercooler'] = ['09:20', '11:50']
final = pressure(T/'tests/days/h2', ['12:00', '14:50'])
final['other_GE1_outages_overlap'] = False
assert final['pressure_a'] and final['pressure_b'], final
save('exhaust_pressure.json', {'initial_v15_window': initial, 'final': final,
     'reason_for_change': 'The v15 window overlaps existing GE1 intercooler maintenance 09:20-11:50. Move the start to 12:00; no other input is changed.'})
print('cost agreement, visible comparison and both exhaust pressures passed', flush=True)
