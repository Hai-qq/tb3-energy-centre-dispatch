"""Candidate-local mutation definitions; all original anchors remain mandatory."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'tools'))
import energy_mutants as M

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
    for name, patches in M.MUTANTS.items():
        texts = {}
        for rel, old, new in patches:
            s = texts.get(rel, (M.SOL / rel).read_text())
            count = s.count(old)
            assert count == 1, (name, rel, count)
            records.append({'mutant': name, 'file': rel, 'anchor_count': count})
            texts[rel] = s.replace(old, new)
    return records

if __name__ == '__main__':
    records = preflight()
    if sys.argv[1:] == ['--preflight']:
        print(json.dumps({'mutants': len(M.MUTANTS), 'patches': records}, indent=2))
    else:
        M.main()
