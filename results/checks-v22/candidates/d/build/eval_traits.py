"""Evaluate an unchanged app on D and three status-only ablations; recalculate all tests."""
from pathlib import Path
import argparse
import json
import os
import shutil
import sys
import tempfile
import time

B = Path(__file__).resolve().parent
ROOT = B.parents[4]
T = B.parent/'task'
os.environ.update(PYTHONDONTWRITEBYTECODE='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
sys.path.insert(0, str(ROOT/'tools'))
import eval_energy as E


def stop_parts(plant):
    sources = {x for c in plant['heat_circuits'].values() for x in c['from']}
    names = {x for e in plant['engines'] for x in sources
             if x in (f"{e['id']} intercooler", f"{e['id']} jacket water heat exchanger")}
    names |= {x for e in plant['engines'] for c in plant['heat_circuits'].values()
              if f"{e['id']} intercooler" in c['from'] for x in c['to']}
    names |= {f"{e['id']} condenser" for e in plant['electric_chillers']}
    names |= {f"{a['id']} {part}" for a in plant['absorption_chillers']
              for part in ('generator', 'absorber and condenser')}
    return names


def evaluate(app):
    plant = json.loads((T/'environment/data/plant.json').read_text())
    stopped = stop_parts(plant)
    new = {r['id'] for r in plant['lt_radiators']}
    new |= {x for e in plant['engines'] for c in plant['heat_circuits'].values() for x in c['from']
            if x == f"{e['id']} exhaust heat exchanger" and e.get('exhaust_heat_exchanger')}
    result = {'app': str(app), 'versions': {}}
    for variant in ('D', 'no_stop_parts', 'no_new_parts', 'units_only'):
        with tempfile.TemporaryDirectory(prefix='d-traits-') as tmp:
            task = Path(tmp)/'task'
            shutil.copytree(T/'tests', task/'tests', ignore=shutil.ignore_patterns('__pycache__'))
            removed = {}
            for p in sorted((task/'tests/days').glob('h*/status.json')):
                status = json.loads(p.read_text())
                def remove(name):
                    return ((variant == 'no_stop_parts' and name in stopped)
                            or (variant == 'no_new_parts' and name in new)
                            or (variant == 'units_only' and ' ' in name))
                removed[p.parent.name] = [o for o in status['outages'] if remove(o['unit'])]
                status['outages'] = [o for o in status['outages'] if not remove(o['unit'])]
                p.write_text(json.dumps(status, indent=2)+'\n')
            E.TASK = task
            start = time.monotonic()
            evaluated = E.evaluate(app, quiet=True)
            result['versions'][variant] = {**evaluated, 'removed_outages': removed,
                                          'elapsed_seconds': time.monotonic()-start}
    result['all_passed'] = all(not r['failed'] and not r['errors'] for r in result['versions'].values())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('app', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = evaluate(args.app.resolve())
    data = json.dumps(result, indent=2)+'\n'
    if args.output:
        args.output.write_text(data)
    print(data, end='')
    print('\nReadable summary:')
    for name, r in result['versions'].items():
        print(f"{name}: {'PASS' if not r['failed'] and not r['errors'] else 'FAIL'}")
        for test, days in sorted(r['failed'].items()):
            print(f"  {test}: {', '.join(days)}")
        for day, error in r['errors'].items():
            print(f'  execution {day}: {error}')
    return 0 if result['all_passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
