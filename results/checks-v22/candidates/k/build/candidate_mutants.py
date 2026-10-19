"""K mutation wrapper: original 42 plus the nine source mutations."""
from pathlib import Path
import json
import os
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[5]
B = Path(__file__).resolve().parent
T = B.parent / 'task'
os.environ['ECD_TASK'] = str(T)
sys.path.insert(0, str(ROOT/'tools'))
import energy_mutants as M
from check_v20 import extras

M.MUTANTS.update(extras('c2'))
M.MUTANTS.update(extras('c4'))
M.MUTANTS['grid_direction_ignored'] = [('planner/optimize.py', 'directions = (True, False) if tariff.import_rate(day.starts[t]) < tariff.export_rate else (None,)', 'directions = (None,)')]
M.MUTANTS['lt_pump_outage_ignored'] = [('planner/plant.py', 'for item in c["to"] + ([c["pump"]] if "pump" in c else []))', 'for item in c["to"])')]
CAPACITY = '    for sources, sinks in plant.lt_rejection.values():'
IGNORE = ('planner/optimize.py', CAPACITY, '    for sources, sinks in ():')
M.MUTANTS['lt_capacity_ignored'] = [IGNORE]
M.MUTANTS['lt_radiator_outage_stops_engines'] = [IGNORE, ('planner/optimize.py',
    '    return all(_available(day, item, hhmm)',
    '''    if any(engine.id in sources and any(not _available(day, item, hhmm) for item in sinks)
           for sources, sinks in plant.lt_rejection.values()):
        return False
    return all(_available(day, item, hhmm)''')]
M.MUTANTS['lt_capacity_ignores_outages'] = [('planner/optimize.py',
    '        capacity = sum(kw for item, kw in sinks.items()\n'
    '                       if _available(day, item, day.starts[t]))',
    '        capacity = sum(sinks.values())')]

def preflight():
    records = []
    assert len(M.MUTANTS) == 51
    for name, patches in M.MUTANTS.items():
        texts = {}
        for rel, old, new in patches:
            source = texts.get(rel, (M.SOL/rel).read_text())
            count = source.count(old)
            assert count == 1, (name, rel, count)
            records.append({'mutant': name, 'file': rel, 'anchor_count': count})
            texts[rel] = source.replace(old,new)
    return records

def main():
    records = preflight()
    if sys.argv[1:] == ['--preflight']:
        print(json.dumps({'mutants': 51, 'patches': records, 'rewritten_patches': []},indent=2))
        return
    names = sys.argv[1:] or list(M.MUTANTS)
    results = {}
    for name in names:
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp)/'app'
            shutil.copytree(M.SOL,app)
            for rel,old,new in M.MUTANTS[name]:
                p = app/rel
                source = p.read_text()
                assert source.count(old) == 1, (name,rel)
                p.write_text(source.replace(old,new))
            result = M.evaluate(app, quiet=True, timeout=2 if name == 'hangs_after_writing' else 120)
        results[name] = {'caught': bool(result['failed']), **result}
        print(name, 'CAUGHT' if result['failed'] else 'MISSED', json.dumps(result),flush=True)
        if os.environ.get('K_MUTATION_OUTPUT'):
            Path(os.environ['K_MUTATION_OUTPUT']).write_text(json.dumps(results,indent=2)+'\n')
    raise SystemExit(0 if all(r['caught'] for r in results.values()) else 1)

if __name__ == '__main__':
    main()
