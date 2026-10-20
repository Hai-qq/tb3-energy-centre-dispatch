"""Run every test on T1 and three hidden-data ablations; recompute each bound."""
from pathlib import Path
import argparse
import csv
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
sys.path.insert(0, str(T/'tests'))
import eval_energy as E
from reference import Day


def evaluate(app):
    result = {'app': str(app), 'versions': {}}
    for variant in ('T1', 'no_part_outages', 'no_t1', 'header_only'):
        with tempfile.TemporaryDirectory(prefix='t1-traits-') as tmp:
            task = Path(tmp)/'task'
            shutil.copytree(T/'tests', task/'tests', ignore=shutil.ignore_patterns('__pycache__'))
            edits = {}
            for folder in sorted((task/'tests/days').glob('h*')):
                edits[folder.name] = {'removed_outages': [], 'zeroed_ahu_periods': []}
                if variant in ('no_part_outages', 'header_only'):
                    p = folder/'status.json'
                    status = json.loads(p.read_text())
                    edits[folder.name]['removed_outages'] = [o for o in status['outages'] if ' ' in o['unit']]
                    status['outages'] = [o for o in status['outages'] if ' ' not in o['unit']]
                    p.write_text(json.dumps(status, indent=2)+'\n')
                if variant in ('no_t1', 'header_only'):
                    day = Day(folder)
                    p = folder/'demand.csv'
                    rows = list(csv.DictReader(open(p)))
                    for t, row in enumerate(rows):
                        if day.ahu_len_fraction[t] < 1.0:
                            row['ahu_heat_kw'] = '0.000'
                            edits[folder.name]['zeroed_ahu_periods'].append(day.starts[t].strftime('%H:%M'))
                    with p.open('w', newline='') as f:
                        w = csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows)
            E.TASK = task
            start = time.monotonic()
            evaluated = E.evaluate(app, quiet=True)
            result['versions'][variant] = {**evaluated, 'edits': edits,
                                          'elapsed_seconds': time.monotonic()-start}
            print(f"{variant}: {'PASS' if not evaluated['errors'] and not evaluated['failed'] else 'FAIL'}", file=sys.stderr, flush=True)
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
