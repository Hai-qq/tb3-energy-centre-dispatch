#!/usr/bin/env python3
"""Run 3+3 batches of the official v19 task until one batch fails all six, or a batch cap is hit.

Usage: driver.py <repo-root> [first-batch=1] [max-batch=4]

Pre-flight: one oracle trial must score 1. Each batch then runs three Opus trials one after
another and, alongside them, three GPT trials one after another, with the settings of
scripts/run_trials.sh. Every attempt stays in jobs/ and gets a line in
jobs/logs/ecd19-batches.status. An attempt counts when it has a reward and ended without an
exception or with an agent timeout; a reward of 1 always counts. An attempt that ends in an
infrastructure error (rate limit, overload, environment or agent setup) without a reward of 1
is not counted and its slot is rerun, at most twice. Any other outcome halts the driver for a
human look, so that no attempt is dropped by rule.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
FIRST = int(sys.argv[2]) if len(sys.argv) > 2 else 1
LAST = int(sys.argv[3]) if len(sys.argv) > 3 else 4
TASK = "../staging/energy-centre-dispatch-v19"  # byte-identical to tasks/energy-centre-dispatch
JOBS = ROOT / "jobs"
LOGS = JOBS / "logs"
STATUS = LOGS / "ecd19-batches.status"
INFRA = ("RateLimit", "Overloaded", "Setup", "Environment", "Build", "Docker")
LOCK = threading.Lock()


def note(line: str) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with LOCK, STATUS.open("a") as fh:
        fh.write(f"{stamp} {line}\n")


def fresh(name: str) -> str:
    n, job = 1, name
    while (JOBS / job).exists():
        n += 1
        job = f"{name}-dup{n}"
    return job


def outcome(job: str) -> tuple[float | None, str | None, float | None]:
    found = sorted((JOBS / job).glob("*__*/result.json"))
    if not found:
        return None, "NoResult", None
    r = json.loads(found[0].read_text())
    reward = ((r.get("verifier_result") or {}).get("rewards") or {}).get("reward")
    exc = (r.get("exception_info") or {}).get("exception_type")
    ae = r.get("agent_execution") or {}
    mins = None
    if ae.get("started_at") and ae.get("finished_at"):
        t0 = datetime.fromisoformat(ae["started_at"].replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(ae["finished_at"].replace("Z", "+00:00"))
        mins = round((t1 - t0).total_seconds() / 60, 1)
    return reward, exc, mins


def harbor(cmd: list[str], job: str) -> None:
    with (LOGS / f"{job}.log").open("w") as fh:
        rc = subprocess.run(cmd, cwd=ROOT, env={**os.environ, "TASK_NAME": TASK},
                            stdout=fh, stderr=subprocess.STDOUT).returncode
        fh.write(f"exit {rc}\n")


def slot(agent: str, b: int, i: int, results: dict) -> None:
    base = f"ecd19-b{b}-run{i}-{agent}"
    for k in range(3):
        job = fresh(base if k == 0 else f"{base}-r{k}")
        harbor(["bash", str(ROOT / "scripts" / "run_trials.sh"), agent, "run", "1", job,
                "--agent-setup-timeout-multiplier", "5"], job)
        reward, exc, mins = outcome(job)
        if reward == 1.0 or (reward is not None and exc in (None, "AgentTimeoutError")):
            note(f"batch {b} {job} reward={reward} exception={exc} minutes={mins} counted")
            results[(agent, i)] = reward
            return
        if exc and any(word in exc for word in INFRA):
            note(f"batch {b} {job} reward={reward} exception={exc} minutes={mins} NOT COUNTED, rerun")
            continue
        note(f"batch {b} {job} reward={reward} exception={exc} minutes={mins} NEEDS REVIEW")
        results[(agent, i)] = "review"
        return
    note(f"batch {b} {base}: three infrastructure errors in a row")
    results[(agent, i)] = "review"


def lane(agent: str, b: int, results: dict, delay: int) -> None:
    time.sleep(delay)
    for i in (1, 2, 3):
        slot(agent, b, i, results)
        if results[(agent, i)] == "review":
            return


def main() -> int:
    try:
        os.setsid()
    except OSError:
        pass
    LOGS.mkdir(parents=True, exist_ok=True)
    note(f"DRIVER START batches {FIRST}-{LAST} task {TASK} pid {os.getpid()}")
    if FIRST == 1:
        job = fresh("ecd19-batches-oracle")
        harbor(["harbor", "run", "-p", str(ROOT / "tasks" / TASK), "--agent", "oracle", "--env", "docker",
                "--yes", "-o", str(JOBS), "--job-name", job], job)
        reward, exc, _ = outcome(job)
        note(f"oracle {job} reward={reward} exception={exc}")
        if reward != 1.0:
            note("HALT oracle did not score 1")
            return 1
    for b in range(FIRST, LAST + 1):
        note(f"BATCH {b} START")
        results: dict = {}
        lanes = [threading.Thread(target=lane, args=("claude", b, results, 0)),
                 threading.Thread(target=lane, args=("codex", b, results, 180))]
        for t in lanes:
            t.start()
        for t in lanes:
            t.join()
        if "review" in results.values() or len(results) < 6:
            note(f"HALT batch {b}: an attempt needs review")
            return 1
        opus = sum(results[("claude", i)] == 1.0 for i in (1, 2, 3))
        gpt = sum(results[("codex", i)] == 1.0 for i in (1, 2, 3))
        all_fail = opus == 0 and gpt == 0
        note(f"BATCH {b} DONE opus_pass={opus}/3 gpt_pass={gpt}/3 all_fail={'yes' if all_fail else 'no'}")
        if all_fail:
            note(f"FINISHED all-fail batch {b}")
            return 0
    note(f"FINISHED cap: no all-fail batch in batches {FIRST}-{LAST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
