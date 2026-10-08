"""Run a dispatch tool on every verifier day and run the task's tests on its plans.

Usage: python tools/eval_energy.py <app_root> [--quiet]
<app_root> holds dispatch.py and planner/ (e.g. tasks/energy-centre-dispatch/solution/app).
Runs the tool twice on each day, as the verifier does: a run that exits with an error or
takes longer than ECD_RUN_TIMEOUT seconds (150, as in the verifier) gives no plan, only the
reason. Prints one line per test with the days it failed on, and exits with status 1 if any
run or test failed.
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
RUN_TIMEOUT = float(os.environ.get("ECD_RUN_TIMEOUT", "150"))


def evaluate(app: Path, quiet: bool = False, timeout: float | None = None) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        plans = Path(tmp) / "plans"
        plans.mkdir()
        errors = {}
        for d in DAYS:
            for name in [d, f"{d}.rerun"]:
                out = plans / f"{name}.json"
                try:
                    r = subprocess.run([sys.executable, str(app / "dispatch.py"), "--data",
                                        str(TASK / "tests" / "days" / d), "--output", str(out)],
                                       capture_output=True, text=True, timeout=timeout or RUN_TIMEOUT,
                                       start_new_session=True)
                    if r.returncode != 0:
                        last = r.stderr.strip().splitlines()[-1] if r.stderr.strip() else ""
                        errors[name] = f"exit {r.returncode}" + (f": {last}" if last else "")
                except subprocess.TimeoutExpired:
                    errors[name] = "timed out"
                if name in errors:
                    out.unlink(missing_ok=True)
                    (plans / f"{name}.error").write_text(errors[name] + "\n")
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
    result = evaluate(Path(sys.argv[1]), quiet="--quiet" in sys.argv)
    sys.exit(1 if result["failed"] or result["errors"] else 0)
