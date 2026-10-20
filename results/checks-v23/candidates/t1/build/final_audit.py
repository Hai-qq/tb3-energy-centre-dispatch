"""Collect executable gate evidence, certify pressure, and freeze task hashes."""
from pathlib import Path
import ast
import hashlib
import json
import subprocess
import sys

B = Path(__file__).resolve().parent
ROOT = B.parents[4]
T = B.parent/'task'
sys.path.insert(0,str(B))
import candidate_mutants as M
sys.path.insert(0,str(T/'tests'))
from reference import Day


def load(name):
    return json.loads((B/name).read_text())


records = M.preflight()
mutants = {}
for group in ('mutants_1','mutants_2'):
    assert load(group+'.result.json')['exit_code']==0
    part = load('mutation_results_'+group+'.json')
    assert not (part.keys() & mutants.keys())
    mutants.update(part)
assert mutants.keys() == M.M.MUTANTS.keys()
assert len(mutants)==45 and all(not r['skipped'] for r in mutants.values())
missed = [n for n,r in mutants.items() if r['status']!='CAUGHT']
assert not (set(missed)-{'t1_dry_bulb_utc'}), missed
assert len(mutants['t1_energy_bus']['hidden_days_caught'])>=2
assert len(mutants['t1_never_recover']['hidden_days_caught'])>=1
(B/'mutation_results_all.json').write_text(json.dumps(mutants,indent=2)+'\n')
assert load('gate_a.json')['passed']
for action in ('verify_candidate','eval_solution','traits','fresh','costs_pressure','model_checks','probe_windows'):
    assert load(action+'.result.json')['exit_code']==0, action
assert load('traits_solution.json')['all_passed']
assert all(abs(r['gap_gbp'])<0.001 for r in load('costs.json').values())
assert load('visible_parity.json')['plans_identical']
coverage = load('fresh_coverage.json')
assert coverage['accepted']==16
assert set(coverage['season_counts'])=={'winter','spring_autumn','summer'}
assert all(not r['failed'] and not r['errors'] for r in coverage['results'].values())
assert load('fresh/manifest.json')['seed']==2026
fresh_certificates = {}
for folder in sorted((B/'fresh/tests/days').iterdir()):
    day = Day(folder)
    fresh_certificates[folder.name] = day.radiator_pressure
    assert 'ahu_heat_kw' in (folder/'demand.csv').read_text().splitlines()[0]
pressure = load('rule_pressure.json')
fixed_count = 0
for name in ('visible','h1','h2','h3','h4'):
    day = Day(T/'tests/days'/name)
    assert pressure[name]['radiator_certificates']==day.radiator_pressure
    fixed_count += len(day.radiator_pressure)
pressure['mutations'] = {n:mutants[n] for n in ('t1_energy_bus','t1_never_recover','t1_dry_bulb_utc',
    'heat_can_be_dumped','lt_radiator_outage_ignored','parts_by_name_prefix','intercooler_outage_ignored',
    'ht_source_outage_ignored','condenser_outage_ignored','ac_generator_outage_ignored',
    'absorption_chiller_parts_ignored','header_not_shared')}
pressure['fresh_radiator_certificates'] = fresh_certificates
(B/'rule_pressure.json').write_text(json.dumps(pressure,indent=2)+'\n')
assert fixed_count==15, fixed_count
assert load('eval_a16.result.json')['exit_code']==1
assert load('eval_a19.result.json')['exit_code']==1
assert not list((B.parent).rglob('__pycache__'))
assert not [p for p in B.parent.rglob('*') if p.is_dir() and not any(p.iterdir())]
python_files = sorted(B.parent.rglob('*.py'))
for p in python_files:
    ast.parse(p.read_text(),filename=str(p))
readme = (B.parent/'README.md').read_text()
assert 'after both groups finish' not in readme
subprocess.run(['git','diff','--exit-code'],cwd=ROOT,capture_output=True,check=True)
status=subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)
assert status.strip()=='?? results/checks-v23/', status
branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
assert branch=='v23-prechecks'
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
assert head=='5ae65f8cfb79209ce8a1c2959bc348d430fed23e'
hashes={str(p.relative_to(T)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(T.rglob('*')) if p.is_file()}
(B/'task_sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
summary={'passed':True,'gates':{'A':'PASS','B':'PASS','B_fresh':'PASS','C':'PASS with documented dry-bulb UTC exception' if missed else 'PASS',
    'traits':'PASS','E':'EXECUTED; historical apps fail'},
    'mutations':len(mutants),'caught':len(mutants)-len(missed),'missed':missed,'skipped':0,
    'patches_checked':len(records),'fixed_radiator_period_certificates':fixed_count,
    'fresh_radiator_period_certificates':sum(map(len,fresh_certificates.values())),
    'git_status':status,'branch':branch,'head':head,'candidate_has_no_pycache_or_empty_directories':True,
    'python_files_syntax_checked':len(python_files)}
(B/'final_audit.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
