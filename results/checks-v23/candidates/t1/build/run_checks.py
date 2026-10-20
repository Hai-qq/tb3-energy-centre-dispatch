"""Retain exact commands, output, environment subset, timing and exit status."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time

B = Path(__file__).resolve().parent
ROOT = B.parents[4]
T = B.parent/'task'
D = Path('/private/tmp/claude-501/-Users-haiy-qq-Desktop----klavis/a70e7eab-ed43-4fbc-8c31-1d0858956a32/scratchpad/codex-v23-t1')
env = dict(os.environ, ECD_TASK=str(T), PYTHONDONTWRITEBYTECODE='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
action = sys.argv[1]
python = sys.executable
if action.startswith('eval_'):
    apps = {'solution': T/'solution/app', 'a16': ROOT/'results/v16-trials/ecd16-run2-claude/app',
            'a19': ROOT/'results/v19-trials/ecd19-run2-claude/app'}
    cmd = [python, str(ROOT/'tools/eval_energy.py'), str(apps[action[5:]])]
elif action == 'traits':
    cmd = [python, str(B/'eval_traits.py'), str(T/'solution/app'), '--output', str(B/'traits_solution.json')]
elif action == 'fresh':
    cmd = [python, str(B/'fresh_days.py'), '--days', '16', '--seed', '2026', '--output', str(B/'fresh'), str(T/'solution/app')]
elif action.startswith('mutants_'):
    sys.path.insert(0, str(B))
    import candidate_mutants as M
    names = list(M.M.MUTANTS)
    names = names[:23] if action == 'mutants_1' else names[23:]
    tmp = D/action
    tmp.mkdir(exist_ok=True)
    env.update(TMPDIR=str(tmp), MUTANT_GROUP=action)
    cmd = [python, str(B/'candidate_mutants.py'), *names]
else:
    cmd = [python, str(B/(action+'.py'))]
start = time.monotonic()
with (B/(action+'.log')).open('w') as log:
    r = subprocess.run(cmd, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
record = {'argv':cmd, 'cwd':str(ROOT), 'environment':{k:env[k] for k in ('ECD_TASK','PYTHONDONTWRITEBYTECODE','OPENBLAS_NUM_THREADS','OMP_NUM_THREADS')},
          'exit_code':r.returncode, 'elapsed_seconds':time.monotonic()-start}
if action.startswith('mutants_'):
    record['environment'].update({k:env[k] for k in ('TMPDIR','MUTANT_GROUP')})
    if not any(tmp.iterdir()):
        tmp.rmdir()
(B/(action+'.result.json')).write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps(record), flush=True)
raise SystemExit(r.returncode)
