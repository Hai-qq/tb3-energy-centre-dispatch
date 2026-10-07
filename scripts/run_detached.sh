#!/usr/bin/env bash
# Start one single-attempt trial in a session of its own, so that it outlives the shell that
# started it (a shell killed on a timeout takes its whole process group with it). The settings
# are those of run_trials.sh; the log is jobs/logs/<job-name>.log and ends with "exit <code>".
#
#   scripts/run_detached.sh <task> <claude|codex> <run|cheat> <job-name>
#
# <task> is a folder name under tasks/ (or a path relative to tasks/, e.g. ../staging/<task>).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TASK="$1"; AGENT="$2"; KIND="$3"; NAME="$4"
mkdir -p "$ROOT/jobs/logs"
LOG="$ROOT/jobs/logs/$NAME.log"
nohup python3 -c '
import os, subprocess, sys
root, task, agent, kind, name, log = sys.argv[1:]
os.setsid()
with open(log, "w") as fh:
    r = subprocess.run(["bash", f"{root}/scripts/run_trials.sh", agent, kind, "1", name,
                        "--agent-setup-timeout-multiplier", "5"],
                       env={**os.environ, "TASK_NAME": task}, stdout=fh, stderr=subprocess.STDOUT)
    fh.write(f"exit {r.returncode}\n")
' "$ROOT" "$TASK" "$AGENT" "$KIND" "$NAME" "$LOG" > /dev/null 2>&1 &
echo "$(date '+%H:%M:%S') started $NAME (log: jobs/logs/$NAME.log)"
