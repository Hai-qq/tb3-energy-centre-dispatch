#!/usr/bin/env bash
# Score an agent's deliverable in Harbor with a task's own verifier: copy the task, replace its
# solution with the deliverable, and run the oracle agent, which installs it as the agent left
# it. The verifier then runs exactly as in a trial (separate image, tool run as nobody).
#
#   scripts/replay_deliverable.sh <task-dir> <app-dir> <job-name>
#   e.g. scripts/replay_deliverable.sh tasks/energy-centre-dispatch \
#          results/v8-trials/ecd8-run3-claude/app replay-ecd8-run3-claude
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TASK="$1"; APP="$2"; NAME="$3"
COPY="$ROOT/staging/replay/$NAME"
rm -rf "$COPY"
mkdir -p "$(dirname "$COPY")"
rsync -a --exclude __pycache__ "$TASK/" "$COPY/"
rm -rf "$COPY/solution/app"
cp -R "$APP" "$COPY/solution/app"
cat > "$COPY/solution/solve.sh" <<'EOF'
#!/bin/bash
# Replay: install one trial's deliverable exactly as the agent left it.
set -euo pipefail
cp /solution/app/dispatch.py /app/dispatch.py
rm -rf /app/planner
cp -r /solution/app/planner /app/planner
EOF
chmod +x "$COPY/solution/solve.sh"
harbor run -p "$COPY" --agent oracle --env docker --yes -o "$ROOT/jobs" --job-name "$NAME"
