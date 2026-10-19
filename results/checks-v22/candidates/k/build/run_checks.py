"""Retain exact command, duration, exit status and logs for K gates."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time
ROOT = Path(__file__).resolve().parents[5]
B = Path(__file__).resolve().parent
T = B.parent/'task'
os.environ.update(PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',ECD_TASK=str(T),ECD_RUN_TIMEOUT='120')
mode = sys.argv[1]
if mode.startswith('eval_'):
    version = mode.removeprefix('eval_')
    app = T/'solution/app' if version == 'solution' else ROOT/f'results/v{version[1:]}-trials/ecd{version[1:]}-run2-claude/app'
    cmd = [sys.executable,str(ROOT/'tools/eval_energy.py'),str(app)]
elif mode.startswith('mutants_'):
    from candidate_mutants import M, preflight
    preflight()
    names = list(M.MUTANTS)
    group = names[:26] if mode.endswith('1') else names[26:]
    tmp = B/('tmp-'+mode)
    tmp.mkdir(exist_ok=True)
    os.environ.update(TMPDIR=str(tmp),K_MUTATION_OUTPUT=str(B/(mode+'.json')))
    cmd = [sys.executable,str(B/'candidate_mutants.py'),*group]
elif mode == 'pressure':
    os.environ['K_MUTATION_OUTPUT'] = str(B/'pressure_mutants.json')
    cmd = [sys.executable,str(B/'candidate_mutants.py'),'grid_direction_ignored','lt_pump_outage_ignored','shared_gas_limit_ignored','phe_flow_limit_ignored','lt_capacity_ignored']
elif mode == 'fresh':
    cmd = [sys.executable,str(B/'fresh_days.py'),'--days','16','--seed','2026','--output',str(B/'fresh'),str(T/'solution/app')]
elif mode.startswith('rules_'):
    version = mode.removeprefix('rules_')
    app = T/'solution/app' if version == 'solution' else ROOT/f'results/v{version[1:]}-trials/ecd{version[1:]}-run2-claude/app'
    cmd = [sys.executable,str(B/'eval_rules.py'),str(app),'--output',str(B/mode)]
else:
    cmd = [sys.executable,str(B/(mode+'.py'))]
start = time.monotonic()
with (B/(mode+'.log')).open('w') as log:
    run = subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
r = {'argv':cmd,'ECD_TASK':str(T),'exit_code':run.returncode,'elapsed_seconds':time.monotonic()-start}
(B/(mode+'.result.json')).write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r),flush=True)
raise SystemExit(run.returncode)
