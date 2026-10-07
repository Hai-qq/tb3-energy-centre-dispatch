"""Run a dispatch tool on every verifier day and run the task's tests on its plans.

Usage: python tools/eval_energy.py <app_root> [--quiet]
<app_root> holds dispatch.py and planner/ (e.g. tasks/energy-centre-dispatch/solution/app).
Prints one line per test with the days it failed on.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK = Path(os.environ.get("ECD_TASK", ROOT / "tasks" / "energy-centre-dispatch")).resolve()
DAYS = ["visible", "h1", "h2", "h3", "h4"]


def evaluate(app: Path, quiet: bool = False) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        plans = Path(tmp) / "plans"
        plans.mkdir()
        errors = {}
        for d in DAYS:
            r = subprocess.run([sys.executable, str(app / "dispatch.py"), "--data", str(TASK / "tests" / "days" / d),
                                "--output", str(plans / f"{d}.json")], capture_output=True, text=True, timeout=600)
            if r.returncode != 0:
                errors[d] = r.stderr.strip().splitlines()[-1] if r.stderr.strip() else f"exit {r.returncode}"
        report = Path(tmp) / "report.xml"
        env = dict(os.environ, PLANS_DIR=str(plans))
        subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={report}",
                        str(TASK / "tests" / "test_plans.py")], cwd=TASK / "tests", env=env,
                       capture_output=True, text=True)
        root = ET.parse(report).getroot()
        cases = list(root.iter("testcase"))
        if not cases:
            raise RuntimeError("pytest collected no tests")
    failed: dict[str, list[str]] = {}
    for t in cases:
        base, _, day = t.get("name").partition("[")
        day = day.rstrip("]")
        if t.find("failure") is not None or t.find("error") is not None:
            failed.setdefault(base, []).append(day)
    if not quiet:
        for d, e in errors.items():
            print(f"  planner failed on {d}: {e}")
        for base, days in sorted(failed.items()):
            print(f"  FAIL {base}: {','.join(days)}")
        if not failed:
            print("  all tests pass")
    return {"errors": errors, "failed": failed}


if __name__ == "__main__":
    evaluate(Path(sys.argv[1]), quiet="--quiet" in sys.argv)
