"""Summarize energy-centre-dispatch trials and measure what each agent's tool got wrong.

For every trial directory under the given jobs, prints the reward, exception, agent time and
failing tests, then reruns the agent's tool (artifacts/app) on every verifier day and reports,
per day: the largest HT/LTHW heat imbalance, the largest cooling-tower and connection excess,
and the gap between the plan's true cost and the least cost.

Usage: python tools/analyze_ecd_trials.py <job-name> [<job-name> ...]
"""

from __future__ import annotations

import json
import os
import math
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TASK = Path(os.environ.get("ECD_TASK", ROOT / "tasks" / "energy-centre-dispatch")).resolve()
sys.path.insert(0, str(TASK / "tests"))
from reference import Day  # noqa: E402

DAYS = ["visible", "h1", "h2", "h3", "h4"]
_best: dict[str, float] = {}


def minutes(a: str | None, b: str | None) -> float | None:
    if not a or not b:
        return None
    f = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))  # noqa: E731
    return round((f(b) - f(a)).total_seconds() / 60, 1)


def measure(app: Path) -> list[str]:
    lines = []
    with tempfile.TemporaryDirectory() as tmp:
        for name in DAYS:
            folder = TASK / "tests" / "days" / name
            out = Path(tmp) / f"{name}.json"
            r = subprocess.run([sys.executable, str(app / "dispatch.py"), "--data", str(folder), "--output", str(out)],
                               capture_output=True, text=True, timeout=900)
            if r.returncode != 0 or not out.exists():
                tail = (r.stderr.strip().splitlines() or ["no output"])[-1]
                lines.append(f"    {name}: tool failed: {tail[:120]}")
                continue
            day = Day(folder)
            plan = json.loads(out.read_text())
            f = day.true_flows(plan)
            boilers = sum(np.array([p["boilers_kw"][b["id"]] for p in plan["periods"]], dtype=float)
                          for b in day.plant["boilers"])
            heat_gap = f["engine_heat"] - f["ac_heat"] + boilers - day.heat - day.lthw_loss
            tower = f["rejected"] - day.tower_max
            imp = np.array([p["import_kw"] for p in plan["periods"]], dtype=float)
            kva = np.hypot(imp, day.kvar - f["engine_kvar"]) - day.import_kva
            if name not in _best:
                _best[name] = day.least_cost()["cost"]
            best = _best[name]
            lines.append(f"    {name}: heat surplus max {heat_gap.max():7.1f} kW in {int((np.abs(heat_gap) > 1).sum()):2d} periods"
                         f" | tower excess {max(tower.max(), 0):6.1f} | kVA excess {max(kva.max(), 0):6.1f}"
                         f" | cost {f['cost'].sum():8.2f} vs least {best:8.2f} ({f['cost'].sum() - best:+.2f})")
    return lines


def main() -> None:
    for job in sys.argv[1:]:
        for trial in sorted((ROOT / "jobs" / job).glob("*__*")):
            res = json.loads((trial / "result.json").read_text()) if (trial / "result.json").exists() else {}
            exc = (res.get("exception_info") or {}).get("exception_type")
            ae = res.get("agent_execution") or {}
            reward = (trial / "verifier" / "reward.txt").read_text().strip() if (trial / "verifier" / "reward.txt").exists() else "-"
            stdout = (trial / "verifier" / "test-stdout.txt")
            failed = []
            summary = ""
            if stdout.exists():
                text = stdout.read_text()
                failed = [ln.split("::")[1].split(" ")[0] for ln in text.splitlines() if ln.startswith("FAILED ")]
                summary = next((ln.strip("= ") for ln in reversed(text.splitlines()) if " passed" in ln or " failed" in ln), "")
            print(f"{job}/{trial.name}: reward={reward} exception={exc} agent_min={minutes(ae.get('started_at'), ae.get('finished_at'))} | {summary}")
            for name in failed:
                print(f"    FAILED {name}")
            app = trial / "artifacts" / "app"
            if (app / "dispatch.py").exists():
                for ln in measure(app):
                    print(ln)


if __name__ == "__main__":
    main()
