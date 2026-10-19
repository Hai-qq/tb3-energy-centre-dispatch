"""Check completed gate artifacts, fresh coverage and final workspace scope."""
from pathlib import Path
from datetime import date
import hashlib
import json
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[5]
B=Path(__file__).resolve().parent
T=B.parent/'task'
sys.path.insert(0,str(B))
from candidate_mutants import M, preflight

def load(name):
    return json.loads((B/name).read_text())

def save(name,value):
    (B/name).write_text(json.dumps(value,indent=2)+'\n')

assert len(preflight())==len(load('mutation_preflight.json')['patches'])
for mode in ['pressure','verify_candidate','eval_solution','fresh','mutants_1','mutants_2','rules_solution']:
    assert load(mode+'.result.json')['exit_code']==0,mode
for mode in ['eval_a16','eval_a19','rules_a16','rules_a19']:
    assert load(mode+'.result.json')['exit_code']==1,mode
assert load('gate_a.json')['passed']
costs=load('costs.json')
assert len(costs)==5
assert all(abs(r['gap_gbp'])<.001 and max(r['solution_seconds'],r['milp_seconds'])<120 for r in costs)
mutants={}
for group in ['mutants_1','mutants_2']:
    part=load(group+'.json')
    assert not set(mutants)&part.keys()
    mutants.update(part)
assert mutants.keys()==M.MUTANTS.keys()
assert all(r['caught'] and r['failed'] for r in mutants.values())
save('mutants_all.json',{'count':len(mutants),'all_caught':True,'skipped':[],'mutants':mutants})
rules={'W':['grid_direction_ignored'],'P':['lt_pump_outage_ignored'],
       'C2':['shared_gas_limit_ignored','shared_gas_only_engines'],
       'C4':['phe_flow_limit_ignored','phe_counts_all_engine_ht'],
       'S':['lt_capacity_ignored','lt_capacity_ignores_outages','lt_radiator_outage_stops_engines']}
pressure=load('rule_pressure.json')
for rule,names in rules.items():
    rows=[]
    for name in names:
        result=mutants[name]
        caught={test:[d for d in days if d.startswith('h')] for test,days in result['failed'].items()}
        caught={t:days for t,days in caught.items() if days}
        assert caught,(rule,name)
        rows.append({'mutant':name,'caught_on_hidden_days':caught,'execution_errors':result['errors']})
    pressure['rules'][rule]=rows
save('rule_pressure.json',pressure)
m=load('fresh/manifest.json')
assert len(m['days'])==16 and m['seed']==2026
assert m['input_hashes_unchanged_after_evaluation']
assert all(not r['failed'] and not r['errors'] for r in m['results'].values())
coverage={'accepted_days':16,'draws':len(m['draws']),'seed':2026,'weekends':[], 'pump':[],'phe':[],'radiator':[], 'candidate_json_byte_identical':True}
for name,day in m['days'].items():
    spec=day['spec']
    if date.fromisoformat(spec['date']).weekday()>=5:
        coverage['weekends'].append({'day':name,'date':spec['date']})
    for key,pattern in [('pump',r'LT pump \d+'),('phe',r'LT PHE \d+'),('radiator',r'LT radiator \d+')]:
        coverage[key] += [{'day':name,**o} for o in spec['status']['outages'] if re.fullmatch(pattern,o['unit'])]
    for f in ['plant.json','supply.json']:
        assert (B/'fresh/tests/days'/name/f).read_bytes()==(T/'environment/data'/f).read_bytes(),(name,f)
assert all(coverage[k] for k in ['weekends','pump','phe','radiator'])
save('fresh_coverage.json',coverage)
solution=load('rules_solution/result.json')
assert all(v['passed'] and all(r['passed'] for r in v['rules'].values()) for v in solution['variants'].values())
# Each control is exactly the original task except the specified status filtering.
for mode in ['rules_solution','rules_a16','rules_a19']:
    control=B/mode/'without_old_component_outages'
    for source in T.rglob('*'):
        if not source.is_file():
            continue
        rel=source.relative_to(T)
        target=control/rel
        if str(rel) in {f'tests/days/h{n}/status.json' for n in range(1,5)}:
            status=json.loads(source.read_text())
            status['outages']=[o for o in status['outages'] if ' ' not in o['unit'] or re.fullmatch(r'LT (?:pump|PHE|radiator) \d+',o['unit'])]
            assert json.loads(target.read_text())==status
        else:
            assert target.read_bytes()==source.read_bytes(),(mode,str(rel))
cache=[str(p.relative_to(B.parent)) for p in B.parent.rglob('__pycache__')]
assert not cache,cache
status=subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)
assert status.strip()=='?? results/checks-v22/',status
branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
assert branch=='v22-prechecks',branch
assert not subprocess.check_output(['git','diff','--name-only'],cwd=ROOT,text=True).strip()
save('task_sha256.json',{str(p.relative_to(T)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(T.rglob('*')) if p.is_file()})
save('final_audit.json',{'passed':True,'mutants':51,'caught':51,'skipped':0,'patches_rewritten':[],
     'max_abs_cost_gap_gbp':max(abs(r['gap_gbp']) for r in costs),
     'max_fixed_solution_seconds':max(r['solution_seconds'] for r in costs),
     'fresh':coverage,'rules_solution_all_pass':True,'control_copies_exact':True,
     'git_status_porcelain':status,'branch':branch,'tracked_diff_empty':True,'pycache':cache,
     'harbor_run':False,'docker_run':False})
print('Final audit PASS: 51/51 caught, all gates complete, scope clean',flush=True)
