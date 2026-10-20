"""Verify exact merge scope and independent full-day cost agreement."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[5]
B = Path(__file__).resolve().parent
T = B.parent/'task'
BASE = ROOT/'tasks/energy-centre-dispatch'
sys.path.insert(0,str(T/'tests'))
from reference import Day

def save(name,obj):
    (B/name).write_text(json.dumps(obj,indent=2)+'\n')

def tree(folder):
    return {str(p.relative_to(folder)):p.read_bytes() for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts}

a,b = tree(BASE),tree(T)
assert a.keys()==b.keys()
changed = sorted(p for p in a if a[p]!=b[p])
expected = {'environment/data/plant.json','environment/data/supply.json',
            'tests/reference.py','tests/test_plans.py','solution/app/planner/plant.py',
            'solution/app/planner/optimize.py','solution/app/planner/tariff.py',
            'tests/days/h1/status.json','tests/days/h3/status.json'}
expected |= {f'tests/days/{d}/{f}.json' for d in ['visible','h1','h2','h3','h4'] for f in ['plant','supply']}
assert set(changed)==expected,(set(changed)-expected,expected-set(changed))
for folder in ['environment/data',*[f'tests/days/{d}' for d in ['visible','h1','h2','h3','h4']]]:
    plant = json.loads((ROOT/'results/checks-v22/candidates/s/task'/folder/'plant.json').read_text())
    pumps = json.loads((ROOT/'results/checks-v21/candidates/p/task'/folder/'plant.json').read_text())
    for n in (1,2):
        plant['heat_circuits'][f'ge{n}_lt']['pump']=pumps['heat_circuits'][f'ge{n}_lt']['pump']
        assert list(plant['heat_circuits'][f'ge{n}_lt'])[-1]=='pump'
    plant['heat_exchangers']=json.loads((ROOT/'results/checks-v20/candidates/c4/task'/folder/'plant.json').read_text())['heat_exchangers']
    supply=json.loads((ROOT/'results/checks-v21/candidates/w/task'/folder/'supply.json').read_text())
    supply['gas']['entry']=json.loads((ROOT/'results/checks-v20/candidates/c2/task'/folder/'supply.json').read_text())['gas']['entry']
    for name,obj in [('plant',plant),('supply',supply)]:
        assert b[f'{folder}/{name}.json']==(json.dumps(obj,indent=2)+'\n').encode()
for rel in ['instruction.md','task.toml','environment/Dockerfile','tests/Dockerfile','tests/test.sh']:
    assert a[rel]==b[rel],rel
for day in ['visible','h1','h2','h3','h4']:
    status=json.loads(a[f'tests/days/{day}/status.json'])
    if day=='h1':
        status['outages'] += [{'unit':'LT pump 1','from':'18:10','to':'19:20'}, {'unit':'LT PHE 1','from':'20:10','to':'21:20'}]
    if day=='h3':
        status['outages'] += [{'unit':'LT pump 2','from':'17:10','to':'17:20'}]
    assert json.loads(b[f'tests/days/{day}/status.json'])==status
original=a['tests/test_plans.py'].decode()
assert b['tests/test_plans.py'].decode().startswith(original)
for c in ['w','p','c2','c4','s']:
    version = 'v22' if c=='s' else 'v20' if c.startswith('c') else 'v21'
    tests=(ROOT/f'results/checks-{version}/candidates/{c}/task/tests/test_plans.py').read_text()
    assert tests.startswith(original)
    assert tests[len(original):] in b['tests/test_plans.py'].decode()
save('gate_a.json',{'passed':True,'changed_files':changed,'environment_changes':[p for p in changed if p.startswith('environment/')], 'protected_files_unchanged':True,'exact_json_merge':True,'source_tests_preserved':True})
print('Gate A PASS',flush=True)
(B/'plans').mkdir(exist_ok=True)
rows=[]
for name in ['visible','h1','h2','h3','h4']:
    folder=T/'tests/days'/name
    out=B/'plans'/(name+'.json')
    start=time.monotonic()
    run=subprocess.run([sys.executable,str(T/'solution/app/dispatch.py'),'--data',str(folder),'--output',str(out)],capture_output=True,text=True,timeout=120)
    seconds=time.monotonic()-start
    assert run.returncode==0,(name,run.stderr)
    day=Day(folder)
    start=time.monotonic()
    best=day.least_cost()
    milp_s=time.monotonic()-start
    cost=float(day.true_flows(json.loads(out.read_text()))['cost'].sum())
    gap=cost-best['cost']
    rows.append({'day':name,'least_cost_gbp':best['cost'],'true_flows_cost_gbp':cost,'gap_gbp':gap,'solution_seconds':seconds,'milp_seconds':milp_s})
    save('costs.json',rows)
    assert abs(gap)<.001,(name,gap)
    assert seconds<120 and milp_s<120,(name,seconds,milp_s)
    print(name,rows[-1],flush=True)
print('Independent costs PASS',flush=True)
