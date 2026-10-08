"""Stage Terminal-Bench's trajectory review of local trials as Harbor tasks.

Mirrors scripts/ci/stage_hosted_analysis.py from Terminal-Bench (commit in ci/tb3/SOURCE.md),
which CI runs after every /run and /cheat job: one task per trial, whose environment holds the
trial at /app/trial and the task it ran on at /app/task, and whose instruction is
trial-analysis.txt followed by each criterion of trial-analysis.toml. The reviewer writes
/app/analysis.json, which the verifier checks with CI's jq filter. Local changes:
  * the trial is copied from this checkout's jobs/ folder instead of downloaded from the Hub;
  * the image is python:3.13-slim-bookworm (pinned as the task's images are) with Claude
    Code preinstalled, as for the rubric review (tools/stage_review.py).

Usage: python tools/stage_analysis.py <out_dir> <task_dir> <job-name> [<job-name> ...]
<task_dir> holds the task files the trials ran on (e.g. archive/energy-centre-dispatch-v8).
"""

from __future__ import annotations

import json
import shutil
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI = ROOT / "ci" / "tb3"
IMAGE = "python:3.13-slim-bookworm@sha256:a1165e272e578941b84abc79e4ab38a0305cd12803a5c4247979ac7655f4d641"

# The verifier and its jq filter, as in stage_hosted_analysis.py.
VERIFIER = r"""#!/bin/sh
mkdir -p /logs/verifier
if test -f /app/analysis.json && jq -e -s --slurpfile criteria /tests/criteria.json -f /tests/validate.jq /app/analysis.json >/dev/null 2>&1; then
    echo 1
else
    echo 0
fi > /logs/verifier/reward.txt
"""

VALIDATE_JQ = r"""
length == 1 and (.[0] | type == "object" and
(.summary | type == "string" and test("\\S")) and
(.checks | type == "object" and (keys == ($criteria[0] | sort)) and
  all(.[]; type == "object" and
    (.outcome == "pass" or .outcome == "fail" or .outcome == "not_applicable") and
    (.explanation | type == "string" and test("\\S")))))
"""


def main() -> None:
    out, task, jobs = Path(sys.argv[1]).resolve(), (ROOT / sys.argv[2]).resolve(), sys.argv[3:]
    if out.exists():
        shutil.rmtree(out)
    criteria = tomllib.loads((CI / "trial-analysis.toml").read_text())["criteria"]
    names = [c["name"] for c in criteria]
    guidance = "\n\n".join(f"{c['name']}: {c['description']}\n{c['guidance']}" for c in criteria)
    instruction = (CI / "trial-analysis.txt").read_text() + "\n\n" + guidance
    count = 0
    for job in jobs:
        for result in sorted((ROOT / "jobs" / job).glob("*/result.json")):
            trial = result.parent
            dest = out / f"{job}__{trial.name.split('__')[-1]}"
            env, tests = dest / "environment", dest / "tests"
            tests.mkdir(parents=True)
            shutil.copytree(trial, env / "trial", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            shutil.copytree(task, env / "task", ignore=shutil.ignore_patterns(
                "__pycache__", "*.pyc", ".DS_Store", "build_energy_days.py"))
            (env / "Dockerfile").write_text(
                f"FROM {IMAGE}\n"
                "RUN apt-get update && apt-get install -y --no-install-recommends "
                "ca-certificates curl git jq nodejs npm procps && rm -rf /var/lib/apt/lists/*\n"
                "RUN npm install -g @anthropic-ai/claude-code\n"
                "COPY trial /app/trial\n"
                "COPY task /app/task\n"
                "WORKDIR /app\n"
            )
            (tests / "criteria.json").write_text(json.dumps(names))
            (tests / "validate.jq").write_text(VALIDATE_JQ)
            (tests / "test.sh").write_text(VERIFIER)
            (dest / "instruction.md").write_text(instruction)
            (dest / "task.toml").write_text(
                'schema_version = "1.3"\n'
                'artifacts = [{ source = "/app/analysis.json", '
                'destination = "analysis.json" }]\n\n'
                "[agent]\n"
                "timeout_sec = 600.0\n\n"
                "[verifier]\n"
                "timeout_sec = 30.0\n"
            )
            count += 1
    print(f"staged {count} analysis task(s) in {out}")


if __name__ == "__main__":
    main()
