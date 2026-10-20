"""Cross-check the development matrix through the original pytest harness."""
from pathlib import Path
import hashlib
import json
import os
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
os.environ["ECD_RUN_TIMEOUT"] = "120"
sys.path.insert(0, str(ROOT / "tools"))
import eval_energy as E

apps = {
    "oracle": "tasks/energy-centre-dispatch/solution/app",
    "strong-v16-claude": "results/v16-trials/ecd16-run2-claude/app",
    "patched-v17-claude": "results/checks-v18/opponents/ecd17-run2-claude-parts/app",
    "patched-v17-codex": "results/checks-v18/opponents/ecd17-run2-codex-parts/app",
}
output = Path(__file__).with_suffix(".json")
result = {
    "command": sys.argv,
    "reference_sha256": hashlib.sha256((ROOT / "tasks/energy-centre-dispatch/tests/reference.py").read_bytes()).hexdigest(),
    "apps": {},
}
for name, path in apps.items():
    start = time.monotonic()
    print(name, path, flush=True)
    row = E.evaluate(ROOT / path)
    row["elapsed_seconds"] = time.monotonic() - start
    result["apps"][name] = row
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(row), flush=True)
assert all(not r["errors"] and not r["failed"] for r in result["apps"].values()), result
