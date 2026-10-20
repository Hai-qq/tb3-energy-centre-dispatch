#!/usr/bin/env python3
"""Run 3+3 batches of the official v19 task until one batch fails all six, or a batch cap is hit.

Usage: driver2.py <repo-root> [first-batch=1] [max-batch=4]

Pre-flight: one oracle trial must score 1 (an existing ecd19-batches-oracle that scored 1 is
reused). Each batch runs three Opus trials one after another and, alongside them, three GPT
trials one after another, with the settings of scripts/run_trials.sh; only one Opus trial runs
at a time. Every attempt stays in jobs/ and gets a line in jobs/logs/ecd19-batches.status.

An attempt counts when it has a reward and ended without an exception or with an agent timeout;
a reward of 1 always counts. An attempt that ends in an infrastructure error (rate limit,
overload, network, environment or agent setup) without a reward of 1 is not counted and its slot
is rerun, at most twice, after a pause (30 minutes after a rate limit). Any other outcome halts
the driver for a human look, so that no attempt is dropped by rule.

The driver resumes from jobs/: an attempt that already exists is judged by the same rules
instead of being run again, and one that is still running is waited for.
"""

from __future__ import annotations

import json
import os
import re
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
INFRA = ("RateLimit", "Overloaded", "Network", "Connection", "Setup", "Environment", "Build", "Docker")
LOCK = threading.Lock()


def note(line: str) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with LOCK, STATUS.open("a") as fh:
        fh.write(f"{stamp} {line}\n")


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


def judge(reward: float | None, exc: str | None) -> str:
    if reward == 1.0 or (reward is not None and exc in (None, "AgentTimeoutError")):
        return "counted"
    if exc and any(word in exc for word in INFRA):
        return "infra"
    return "review"


def running(job: str) -> bool:
    ps = subprocess.run(["ps", "-ax", "-o", "command"], capture_output=True, text=True).stdout
    return any(re.search(rf"--job-name {re.escape(job)}(\s|$)", ln) for ln in ps.splitlines())


def harbor(cmd: list[str], job: str) -> None:
    with (LOGS / f"{job}.log").open("w") as fh:
        rc = subprocess.run(cmd, cwd=ROOT, env={**os.environ, "TASK_NAME": TASK},
                            stdout=fh, stderr=subprocess.STDOUT).returncode
        fh.write(f"exit {rc}\n")


def attempt(agent: str, b: int, job: str) -> tuple[float | None, str | None, str]:
    earlier = (JOBS / job).exists()
    if earlier:
        while not list((JOBS / job).glob("*__*/result.json")) and running(job):
            time.sleep(60)
        time.sleep(5)
    else:
        harbor(["bash", str(ROOT / "scripts" / "run_trials.sh"), agent, "run", "1", job,
                "--agent-setup-timeout-multiplier", "5"], job)
    reward, exc, mins = outcome(job)
    verdict = judge(reward, exc)
    tag = {"counted": "counted", "infra": "NOT COUNTED, rerun", "review": "NEEDS REVIEW"}[verdict]
    note(f"batch {b} {job} reward={reward} exception={exc} minutes={mins} {tag}"
         + (" (from an earlier driver)" if earlier else ""))
    return reward, exc, verdict


def slot(agent: str, b: int, i: int, results: dict) -> None:
    base = f"ecd19-b{b}-run{i}-{agent}"
    names = [base, f"{base}-r1", f"{base}-r2"]
    for k, job in enumerate(names):
        reward, exc, verdict = attempt(agent, b, job)
        if verdict != "infra":
            results[(agent, i)] = reward if verdict == "counted" else "review"
            return
        if k < 2 and not (JOBS / names[k + 1]).exists():
            time.sleep(1800 if "RateLimit" in (exc or "") else 120)
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
    note(f"DRIVER2 START batches {FIRST}-{LAST} task {TASK} pid {os.getpid()}")
    if FIRST == 1:
        job = "ecd19-batches-oracle"
        if not (JOBS / job).exists():
            harbor(["harbor", "run", "-p", str(ROOT / "tasks" / TASK), "--agent", "oracle", "--env", "docker",
                    "--yes", "-o", str(JOBS), "--job-name", job], job)
        reward, exc, _ = outcome(job)
        if reward != 1.0:
            note(f"HALT oracle {job} reward={reward} exception={exc}")
            return 1
    for b in range(FIRST, LAST + 1):
        resumed = any(JOBS.glob(f"ecd19-b{b}-run*"))
        note(f"BATCH {b} {'RESUME' if resumed else 'START'}")
        results: dict = {}
        lanes = [threading.Thread(target=lane, args=("claude", b, results, 0)),
                 threading.Thread(target=lane, args=("codex", b, results, 0 if resumed else 180))]
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
