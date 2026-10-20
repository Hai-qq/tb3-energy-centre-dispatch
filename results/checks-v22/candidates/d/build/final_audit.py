"""Aggregate retained gate evidence; do not repeat completed evaluations."""
from pathlib import Path
from datetime import date
import ast
import hashlib
import json
import subprocess

B = Path(__file__).resolve().parent
ROOT = B.parents[4]
T = B.parent/'task'


def read(name):
    return json.loads((B/name).read_text())


def save(name, value):
    (B/name).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


for name in ('eval_solution', 'verify_candidate', 'fresh', 'mutants_1', 'mutants_2'):
    assert read(name+'.result.json')['exit_code'] == 0, name
assert read('traits_solution.result.json')['exit_code'] == 0
traits = read('traits_solution.json')
assert traits['all_passed']
assert set(traits['versions']) == {'D', 'no_stop_parts', 'no_new_parts', 'units_only'}
from candidate_mutants import M, preflight
anchors = preflight()
mutants = {}
for group in (1, 2):
    part = read(f'mutation_results_mutants_{group}.json')
    assert not set(part) & set(mutants)
    mutants.update(part)
assert len(mutants) == 48 and set(mutants) == set(M.MUTANTS)
required = {n: r for n, r in mutants.items() if n != 'diverter_ignored'}
assert all(r['status'] == 'CAUGHT' and r['hidden_days_caught'] and not r['skipped']
           for r in required.values())
assert all(not r['skipped'] for r in mutants.values())
assert all('timed out' not in error for n, r in mutants.items() if n != 'hangs_after_writing'
           for error in r['errors'].values())
assert read('gate_a.json')['passed']
assert read('task_sha256.json') == {str(p.relative_to(T)): hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in sorted(T.rglob('*')) if p.is_file()}
audit = read('README_audit.json')
assert audit['status'] == 'complete' and not audit['pending_claims']
assert audit['README_sha256'] == hashlib.sha256((B.parent/'README.md').read_bytes()).hexdigest()
assert all((B/x).is_file() for x in audit['source_of_claims'])
costs = read('costs.json')
assert all(abs(c['gap_gbp']) < 0.001 and max(c['solution_seconds'], c['milp_seconds']) < 120 for c in costs)
exhaust = read('exhaust_pressure.json')
assert exhaust['final']['pressure_a'] and exhaust['final']['pressure_b']

manifest = read('fresh/manifest.json')
assert manifest['input_hashes_unchanged_after_evaluation']
assert len(manifest['days']) == 16 and manifest['seed'] == 2026
assert not any(r['failed'] or r['errors'] for r in manifest['results'].values())
coverage = {'accepted_days': len(manifest['days']), 'draws': len(manifest['draws']),
            'seed': manifest['seed'], 'weekends': 0, 'outages': {k: [] for k in ('exhaust', 'jacket', 'phe', 'radiator')},
            'all_candidate_plants': True}
for name, info in manifest['days'].items():
    folder = B/'fresh/tests/days'/name
    assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()} == info['sha256']
    coverage['all_candidate_plants'] &= ((folder/'plant.json').read_bytes() == (T/'environment/data/plant.json').read_bytes())
    coverage['weekends'] += date.fromisoformat(info['spec']['date']).weekday() >= 5
    for outage in info['spec']['status']['outages']:
        for key, text in [('exhaust', 'exhaust heat exchanger'), ('jacket', 'jacket water heat exchanger'),
                          ('phe', 'LT PHE'), ('radiator', 'LT radiator')]:
            if text in outage['unit']:
                coverage['outages'][key].append({'day': name, **outage})
assert coverage['all_candidate_plants'] and all(coverage['outages'].values())
save('fresh_coverage.json', coverage)

categories = {
    'stop_intercooler': ['intercooler_outage_ignored'],
    'stop_jacket_water_exchanger': ['ht_source_outage_ignored'],
    'stop_primary_LT_PHE': ['lt_radiator_outage_ignored', 'parts_by_name_prefix'],
    'run_with_less_recovered_heat': ['exhaust_outage_stops_engine', 'exhaust_outage_ignored'],
    'share_remaining_radiator_capacity': ['lt_capacity_ignored', 'lt_capacity_ignores_outages', 'lt_radiator_outage_stops_engines'],
    'common_header': ['header_not_shared', 'absorber_cooling_water_ignored', 'absorber_needs_cold_weather'],
    'PHE1_maintenance': ['phe1_outage_ignored'],
    'electric_chiller_condenser': ['condenser_outage_ignored'],
    'absorption_generator': ['ac_generator_outage_ignored'],
    'absorption_parts': ['absorption_chiller_parts_ignored'],
    'tower_cell': ['tower_cell_outage_ignored'],
    'PV_array': ['pv_outage_ignored'],
    'free_diverter': ['diverter_ignored'],
}
category_evidence = {key: {n: {'hidden_days_caught': mutants[n]['hidden_days_caught'],
                             'failed': mutants[n]['failed'], 'errors': mutants[n]['errors']}
                           for n in names} for key, names in categories.items()}
for name in ('a16', 'a19'):
    r = read(f'traits_{name}.json')
    assert set(r['versions']) == set(traits['versions'])
    assert all(x['errors'] and x['failed'] for x in r['versions'].values())
    assert read(f'traits_{name}.result.json')['exit_code'] == 1
    # Gate E is the D section of the same single four-version example run.
    save(f'eval_{name}.json', r['versions']['D'])

for p in [*T.rglob('*.py'), *B.glob('*.py')]:
    ast.parse(p.read_text(), filename=str(p))
assert not list(B.parent.rglob('__pycache__'))
assert not [p for p in B.parent.rglob('*') if p.is_dir() and not any(p.iterdir())]
status = subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True)
assert status.strip() == '?? results/checks-v22/', status
branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip()
assert branch == 'v22-prechecks'
assert not subprocess.check_output(['git', 'diff', '--name-only', 'HEAD'], cwd=ROOT, text=True).strip()
pressure = {'mutant_count': len(mutants), 'required_caught_on_hidden_days': len(required),
            'all_caught': all(r['status'] == 'CAUGHT' for r in mutants.values()),
            'skipped': 0, 'patch_anchor_count': len(anchors), 'categories': category_evidence,
            'exhaust': exhaust, 'mutants': mutants}
save('rule_pressure.json', pressure)
summary = {'passed': True, 'gate_A': True, 'gate_B': True, 'gate_B_fresh': True, 'gate_C': True,
           'gate_E_executed': True, 'traits_solution_all_passed': True,
           'max_absolute_cost_gap_gbp': max(abs(c['gap_gbp']) for c in costs),
           'mutants_caught': sum(r['status'] == 'CAUGHT' for r in mutants.values()),
           'mutants_caught_hidden': sum(bool(r['hidden_days_caught']) for r in mutants.values()),
           'required_mutants_caught_hidden': len(required), 'mutation_skips': 0,
           'diverter_ignored': mutants['diverter_ignored']['status'],
           'git_status_porcelain': status, 'branch': branch, 'tracked_diff_empty': True,
           'no_candidate_pycache': True, 'no_empty_candidate_directories': True}
save('final_audit.json', summary)
print(json.dumps(summary, indent=2))
