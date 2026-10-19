"""Retain one four-version evaluation invocation per example app."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time

B = Path(__file__).resolve().parent
ROOT = B.parents[4]
name = sys.argv[1]
app = B.parent/'task/solution/app' if name == 'solution' else ROOT/f'results/v{name[1:]}-trials/ecd{name[1:]}-run2-claude/app'
os.environ.update(PYTHONDONTWRITEBYTECODE='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
cmd = [sys.executable, str(B/'eval_traits.py'), str(app), '--output', str(B/f'traits_{name}.json')]
start = time.monotonic()
with (B/f'traits_{name}.log').open('w') as f:
    r = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=ROOT)
record = {'argv': cmd, 'exit_code': r.returncode, 'elapsed_seconds': time.monotonic()-start}
(B/f'traits_{name}.result.json').write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps(record))
raise SystemExit(r.returncode)
