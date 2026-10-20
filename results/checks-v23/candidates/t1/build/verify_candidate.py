"""Gate A: exact supplied bytes, complete package and tightly scoped differences."""
from pathlib import Path
import csv
import hashlib
import json
import subprocess

B = Path(__file__).resolve().parent
ROOT = B.parents[4]
T = B.parent/'task'
BASE = ROOT/'tasks/energy-centre-dispatch'
SOURCE = Path('/private/tmp/claude-501/-Users-haiy-qq-Desktop----klavis/a70e7eab-ed43-4fbc-8c31-1d0858956a32/scratchpad/v23-t1/visible')


def inventory(folder):
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}


original, candidate = inventory(BASE/'environment'), inventory(T/'environment')
assert original.keys() == candidate.keys()
changed = sorted(k for k in original if original[k] != candidate[k])
allow = sorted(['data/plant.json', 'data/demand.csv', 'planner/data.py', 'planner/plant.py', 'planner/optimize.py'])
assert changed == allow, changed
source_hashes = {}
for rel in allow:
    src = SOURCE/'app'/rel
    assert (T/'environment'/rel).read_bytes() == src.read_bytes(), rel
    source_hashes[rel] = hashlib.sha256(src.read_bytes()).hexdigest()
assert (T/'instruction.md').read_bytes() == (SOURCE/'instruction.md').read_bytes()
old = (BASE/'instruction.md').read_bytes()
needle = b'heat at the buildings and chilled water'
assert old.count(needle) == 1
assert old.replace(needle, b"heat at the buildings, heat at the air handling units' heating coils and chilled water") == (T/'instruction.md').read_bytes()
all_original, all_candidate = inventory(BASE), inventory(T)
assert all_original.keys() == all_candidate.keys(), (all_original.keys() ^ all_candidate.keys())
all_changes = sorted(k for k in all_original if all_original[k] != all_candidate[k])
allowed = {'instruction.md', 'README.md', 'tests/reference.py', 'tests/test_plans.py',
           'solution/app/planner/data.py','solution/app/planner/plant.py','solution/app/planner/optimize.py',
           'tests/days/h3/status.json'}
allowed |= {'environment/'+k for k in allow}
allowed |= {'tests/days/'+name+'/plant.json' for name in ('visible','h1','h2','h3','h4')}
allowed |= {'tests/days/'+name+'/demand.csv' for name in ('visible','h1','h2','h3','h4')}
assert set(all_changes) == allowed, (set(all_changes)^allowed)
for name in ('visible','h1','h2','h3','h4'):
    p = T/'tests/days'/name/'plant.json'
    assert p.read_bytes() == (SOURCE/'app/data/plant.json').read_bytes()
    new = list(csv.DictReader(open(T/'tests/days'/name/'demand.csv')))
    prior = list(csv.DictReader(open(BASE/'tests/days'/name/'demand.csv')))
    assert [{k:v for k,v in row.items() if k!='ahu_heat_kw'} for row in new] == prior
    assert list(new[0]).index('ahu_heat_kw') == list(new[0]).index('heat_kw')+1
assert (T/'tests/days/visible/demand.csv').read_bytes() == (SOURCE/'app/data/demand.csv').read_bytes()
# Only the heat-balance assertion changes; no existing test was dropped.
s = (BASE/'tests/test_plans.py').read_text()
old = '    assert np.abs(lthw - day.heat - day.lthw_loss).max() <= KW'
new = '''    upper = day.heat + day.lthw_loss + day.ahu
    assert (lthw <= upper + KW).all()  # no HT dump
    assert (lthw >= upper - flows["R_len"] - KW).all()'''
assert s.replace(old, new) == (T/'tests/test_plans.py').read_text()
assert not list(T.rglob('__pycache__'))
subprocess.run(['git','diff','--exit-code'],cwd=ROOT,check=True,capture_output=True)
record = {'passed':True,'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
          'environment_changed_files':changed, 'all_task_changed_files':all_changes,
          'source_sha256':source_hashes,'instruction_only_named_sentence_changed':True,
          'all_six_original_plants_byte_identical':len(set(json.loads((B/'baseline_plants.json').read_text()).values()))==1,
          'existing_tests_preserved_except_heat_assertion':True, 'new_tests':0,
          'complete_file_inventory_preserved':True}
(B/'gate_a.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
