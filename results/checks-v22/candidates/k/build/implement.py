"""Merge source edits relative to unchanged v19; no source tree is modified."""
from pathlib import Path
import difflib
import json

ROOT = Path(__file__).resolve().parents[5]
B = Path(__file__).resolve().parent
T = B.parent / 'task'
BASE = ROOT / 'tasks/energy-centre-dispatch'
SOURCES = {n: ROOT / p / 'task' for n, p in {
    'w': 'results/checks-v21/candidates/w', 'p': 'results/checks-v21/candidates/p',
    'c2': 'results/checks-v20/candidates/c2', 'c4': 'results/checks-v20/candidates/c4',
    's': 'results/checks-v22/candidates/s'}.items()}
records = {}
for rel in ['tests/reference.py', 'tests/test_plans.py', *[str(p.relative_to(BASE)) for p in (BASE/'solution/app').rglob('*.py')]]:
    original = (BASE/rel).read_text().splitlines(keepends=True)
    edits = {}
    for name, source in SOURCES.items():
        other = (source/rel).read_text().splitlines(keepends=True)
        for tag, a, z, c, d in difflib.SequenceMatcher(None, original, other, autojunk=False).get_opcodes():
            if tag != 'equal':
                replacement = ''.join(other[c:d])
                values = edits.setdefault((a,z), [])
                if replacement not in [v[1] for v in values]:
                    values.append((name, replacement))
    spans = sorted(edits)
    for (a,z), (c,d) in zip(spans, spans[1:]):
        assert z <= c, (rel, (a,z), (c,d))
    result = original[:]
    for a,z in reversed(spans):
        values = edits[(a,z)]
        assert a == z or len(values) == 1, (rel,a,z,values)
        result[a:z] = [''.join(v[1] for v in values)]
    (T/rel).write_text(''.join(result))
    if edits:
        records[rel] = [{'base_lines': [a+1,z], 'sources': [n for n,_ in edits[(a,z)]]} for a,z in spans]
for folder in [Path('environment/data'), *[Path('tests/days')/n for n in ['visible','h1','h2','h3','h4']]]:
    plant = json.loads((SOURCES['s']/folder/'plant.json').read_text())
    p = json.loads((SOURCES['p']/folder/'plant.json').read_text())
    for n in (1,2):
        plant['heat_circuits'][f'ge{n}_lt']['pump'] = p['heat_circuits'][f'ge{n}_lt']['pump']
    plant['heat_exchangers'] = json.loads((SOURCES['c4']/folder/'plant.json').read_text())['heat_exchangers']
    supply = json.loads((SOURCES['w']/folder/'supply.json').read_text())
    supply['gas']['entry'] = json.loads((SOURCES['c2']/folder/'supply.json').read_text())['gas']['entry']
    for name,obj in [('plant',plant),('supply',supply)]:
        (T/folder/(name+'.json')).write_text(json.dumps(obj,indent=2)+'\n')
for name in ['h1','h3']:
    (T/'tests/days'/name/'status.json').write_bytes((SOURCES['p']/'tests/days'/name/'status.json').read_bytes())
status_path = T/'tests/days/h1/status.json'
status = json.loads(status_path.read_text())
status['outages'].append({'unit': 'LT PHE 1', 'from': '20:10', 'to': '21:20'})
status_path.write_text(json.dumps(status,indent=2)+'\n')
(B/'merge_record.json').write_text(json.dumps(records,indent=2)+'\n')
print(json.dumps(records,indent=2))
