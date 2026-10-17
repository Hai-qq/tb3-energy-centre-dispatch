"""Record a NEW execution after the uncommitted original outputs were lost.

run.py was recovered from the conversation's exact source. Old run logs/results
were not recreated. This wrapper records current code hashes, runtime, UTC times
and elapsed time, then runs that one combined reversal probe once.
"""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

os.environ.update(PYTHONDONTWRITEBYTECODE="1", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
sys.dont_write_bytecode = True
import numpy
import scipy
import pytest

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
paths = [OUT / "run.py", OUT / "rerun.py", ROOT / "tools/fuzz_v18.py",
         ROOT / "archive/energy-centre-dispatch-v17/tests/reference.py",
         ROOT / "archive/energy-centre-dispatch-v17/tests/test_plans.py"]
for app in ("results/v16-trials/ecd16-run2-claude/app",
            "results/checks-v18/opponents/ecd17-run2-codex-parts/app",
            "results/checks-v18/opponents/ecd17-run2-claude-parts/app"):
    paths.extend(sorted((ROOT / app).rglob("*.py")))
record = {
    "execution_kind": "new_rerun_after_environment_cleanup",
    "original_uncommitted_outputs_lost": True,
    "old_logs_reconstructed": False,
    "probe_script_recovered_from": "complete source in the earlier conversation apply_patch",
    "python_executable": sys.executable,
    "versions": {"python": sys.version, "numpy": numpy.__version__,
                 "scipy": scipy.__version__, "pytest": pytest.__version__},
    "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
    "started_utc": datetime.now(timezone.utc).isoformat(),
    "command": [sys.executable, str(OUT / "run.py")],
}
(OUT / "rerun-metadata.json").write_text(json.dumps(record, indent=2) + "\n")
start = time.monotonic()
with (OUT / "run.log").open("w") as stream:
    completed = subprocess.run(record["command"], cwd=ROOT, env=os.environ.copy(),
                               stdout=stream, stderr=subprocess.STDOUT, timeout=600)
record.update(finished_utc=datetime.now(timezone.utc).isoformat(),
              elapsed_seconds=time.monotonic() - start, exit_code=completed.returncode)
(OUT / "rerun-metadata.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps({k: v for k, v in record.items() if k != "source_sha256"}, indent=2))
raise SystemExit(completed.returncode)
