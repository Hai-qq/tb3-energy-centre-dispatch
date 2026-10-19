"""Run checks with retained argv, status, duration and full output."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[5]
BUILD = Path(__file__).resolve().parent
TASK = BUILD.parent / 'task'
os.environ.update(PYTHONDONTWRITEBYTECODE='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1',
                  ECD_TASK=str(TASK))
mode = sys.argv[1]
if mode == 'eval_solution':
    cmd = [sys.executable, str(ROOT/'tools/eval_energy.py'), str(TASK/'solution/app')]
elif mode in ('eval_a16', 'eval_a19'):
    version = '16' if mode.endswith('16') else '19'
    cmd = [sys.executable, str(ROOT/'tools/eval_energy.py'),
           str(ROOT/f'results/v{version}-trials/ecd{version}-run2-claude/app')]
elif mode.startswith('mutants_'):
    from candidate_mutants import M, preflight
    preflight()
    names = list(M.MUTANTS)
    group = names[:23] if mode.endswith('1') else names[23:]
    tmp = BUILD / ('tmp-' + mode)
    tmp.mkdir(exist_ok=True)
    os.environ['TMPDIR'] = str(tmp)
    cmd = [sys.executable, str(BUILD/'candidate_mutants.py'), *group]
elif mode == 'fresh':
    cmd = [sys.executable, str(BUILD/'fresh_days.py'), '--days', '16', '--seed', '2026',
           '--output', str(BUILD/'fresh'), str(TASK/'solution/app')]
else:
    cmd = [sys.executable, str(BUILD/(mode+'.py'))]
start = time.monotonic()
with (BUILD/(mode+'.log')).open('w') as log:
    run = subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
record = {'argv': cmd, 'ECD_TASK': str(TASK), 'exit_code': run.returncode,
          'elapsed_seconds': time.monotonic()-start}
(BUILD/(mode+'.result.json')).write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps(record), flush=True)
raise SystemExit(run.returncode)
