"""Aggregate the requested executable gates without repeating completed runs."""
from pathlib import Path
from datetime import date
import ast
import json
import subprocess

B = Path(__file__).resolve().parent
ROOT = B.parents[4]
T = B.parent/'task'

def read(name):
    return json.loads((B/name).read_text())

for name in ['eval_solution', 'verify_candidate', 'fresh', 'mutants_1', 'mutants_2']:
    assert read(name+'.result.json')['exit_code'] == 0, name
from candidate_mutants import M, preflight
preflight()
rows = []
for group in (1, 2):
    for line in (B/f'mutants_{group}.log').read_text().splitlines():
        name, status, *detail = line.split(maxsplit=2)
        assert status == 'CAUGHT', (name, status)
        rows.append({'name': name, 'status': status, 'details': detail[0] if detail else ''})
assert len(rows) == 45 and len({r['name'] for r in rows}) == 45
assert {r['name'] for r in rows} == set(M.MUTANTS)
assert read('mutation_preflight.json')['mutants'] == 45
assert all(abs(r['gap_gbp']) < 0.001 and max(r['solution_seconds'], r['milp_seconds']) < 120
           for r in read('costs.json'))
assert read('visible_parity.json')['complete_json_equal']
assert read('fresh_coverage.json')['accepted_days'] == 16
assert read('fresh_coverage.json')['radiator_outages'] and read('fresh_coverage.json')['phe_outages']
manifest = read('fresh/manifest.json')
assert manifest['input_hashes_unchanged_after_evaluation']
assert not any(v['failed'] or v['errors'] for v in manifest['results'].values())
coverage = {'accepted_days': len(manifest['days']), 'draws': len(manifest['draws']),
            'weekends': 0, 'radiator_outages': [], 'phe_outages': [], 'all_candidate_plants': True}
for name, info in manifest['days'].items():
    spec = info['spec']
    coverage['weekends'] += date.fromisoformat(spec['date']).weekday() >= 5
    coverage['all_candidate_plants'] &= ((B/'fresh/tests/days'/name/'plant.json').read_bytes()
                                         == (T/'environment/data/plant.json').read_bytes())
    for outage in spec['status']['outages']:
        if outage['unit'].startswith('LT radiator'):
            coverage['radiator_outages'].append({'day': name, **outage})
        if outage['unit'].startswith('LT PHE'):
            coverage['phe_outages'].append({'day': name, **outage})
assert coverage == read('fresh_coverage.json')
assert coverage['all_candidate_plants']
for p in [*T.rglob('*.py'), *B.glob('*.py')]:
    ast.parse(p.read_text(), filename=str(p))
assert not list((B.parent).rglob('__pycache__'))
status = subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True)
assert status.strip() == '?? results/checks-v22/', status
assert subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip() == 'v22-prechecks'
assert not subprocess.check_output(['git', 'diff', '--name-only', 'HEAD'], cwd=ROOT, text=True).strip()
result = {'executable_acceptance_passed': True, 'mutants': rows,
          'original_mutants_caught': 42, 'new_mutants_caught': 3, 'skipped': 0,
          'git_status_porcelain': status, 'no_candidate_pycache': True,
          'finite_over_stopping_cost_premium_met': False,
          'optional_both_on_derated_optimum_observed': False,
          'overall_task_status': 'partial: requested finite cost pressure cannot be met by allowed outage-window edits'}
(B/'final_audit.json').write_text(json.dumps(result, indent=2)+'\n')
print('A/B/C executable gates passed; 45/45 CAUGHT, zero skipped; scope clean. Finite-premium condition unmet.')
