"""T1-local mutations. Mandatory, exactly-once anchors; no skipped patches."""
from pathlib import Path
import json
import os
import shutil
import sys
import tempfile
import time

B = Path(__file__).resolve().parent
ROOT = B.parents[4]
T = B.parent/'task'
os.environ.update(ECD_TASK=str(T), PYTHONDONTWRITEBYTECODE='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
sys.path.insert(0, str(ROOT/'tools'))
import energy_mutants as M

M.SOL = T/'solution/app'
M.evaluate.__globals__['TASK'] = T
assert len(M.MUTANTS) == 42
OLD_RHS = 'b_eq.append(day.heat[t] + plant.lthw_loss_kw - sum(piece[4] for piece in pieces))'
NEW_RHS = 'b_eq.append(day.heat[t] + plant.lthw_loss_kw + day.ahu[t] - sum(piece[4] for piece in pieces))'
M.MUTANTS['no_lthw_loss'] = [('planner/optimize.py', NEW_RHS,
    'b_eq.append(day.heat[t] + day.ahu[t] - sum(piece[4] for piece in pieces))')]
BALANCE = '    row[iB:iB + nB] = 1.0\n    row[iR] = 1.0\n    A_eq.append(row)\n    '+NEW_RHS
M.MUTANTS['heat_can_be_dumped'] = [('planner/optimize.py', BALANCE,
    '    row[iB:iB + nB] = 1.0\n    row[iR] = 1.0\n    A_ub.append(-row)\n'
    '    b_ub.append(-(day.heat[t] + plant.lthw_loss_kw + day.ahu[t] - sum(piece[4] for piece in pieces)))')]
# lt_heat_counted's unchanged patch adds LT to the HT curve, hence counts it in LTHW.
FRACTION = 'return float(flow <= lt_flow_c - 5.0)'
M.MUTANTS['t1_energy_bus'] = [('planner/plant.py', FRACTION, 'return 1.0')]
M.MUTANTS['t1_never_recover'] = [('planner/plant.py', FRACTION, 'return 0.0')]
M.MUTANTS['t1_dry_bulb_utc'] = [('planner/data.py',
    'dry_bulb=np.array([float(r["dry_bulb_c"]) for r in wx]),',
    'dry_bulb=np.array([float(r["dry_bulb_c"]) for k, r in sorted(weather.items()) if k.date() == day]),')]


def preflight():
    records = []
    for name, patches in M.MUTANTS.items():
        texts = {}
        for rel, old, new in patches:
            s = texts.get(rel, (M.SOL/rel).read_text())
            count = s.count(old)
            assert count == 1, (name, rel, count)
            records.append({'mutant': name, 'file': rel, 'anchor_count': count})
            texts[rel] = s.replace(old, new)
    return records


def main():
    records = preflight()
    if sys.argv[1:] == ['--preflight']:
        print(json.dumps({'mutants': len(M.MUTANTS), 'overridden': ['no_lthw_loss', 'heat_can_be_dumped'],
                          'patches': records}, indent=2))
        return
    results, missed = {}, []
    for name in sys.argv[1:] or list(M.MUTANTS):
        start = time.monotonic()
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp)/'app'
            shutil.copytree(M.SOL, app, ignore=shutil.ignore_patterns('__pycache__'))
            for rel, old, new in M.MUTANTS[name]:
                p = app/rel
                s = p.read_text()
                assert s.count(old) == 1, (name, rel)
                p.write_text(s.replace(old, new))
            r = M.evaluate(app, quiet=True, timeout=M.RUN_TIMEOUT_S)
        hidden = sorted({d for days in r['failed'].values() for d in days if d.startswith('h')})
        caught = bool(r['failed']) and bool(hidden)
        results[name] = {**r, 'status': 'CAUGHT' if caught else 'MISSED',
                         'hidden_days_caught': hidden, 'skipped': False,
                         'elapsed_seconds': time.monotonic()-start}
        print(f'{name:36s} {results[name]["status"]} '+json.dumps(r), flush=True)
        if not caught and name != 't1_dry_bulb_utc':
            missed.append(name)
    label = os.environ.get('MUTANT_GROUP', 'all')
    (B/f'mutation_results_{label}.json').write_text(json.dumps(results, indent=2)+'\n')
    assert not missed, missed


if __name__ == '__main__':
    main()
