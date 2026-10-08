#!/usr/bin/env bash
# Run Terminal-Bench's static checks on a task the way its CI does.
#
# Usage: scripts/run_static_checks.sh <tb3-checkout> [task-name] [out-dir]
#
# Takes the "Run all static checks" step from <tb3-checkout>/.github/workflows/static-checks.yml
# and runs it unchanged in a throwaway linux/amd64 container with no network: the checkout's
# scripts/checks as the trusted base, a copy of tasks/<task-name> as the pull request, and
# dockerfile-pin installed as CI installs it (same release, checked against the same SHA-256).
# Writes the log and the comment CI would post to <out-dir> (default jobs/static-checks) and
# exits non-zero if any check fails.
set -euo pipefail

TB3=$(cd "$1" && pwd)
TASK=${2:-energy-centre-dispatch}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT=${3:-$ROOT/jobs/static-checks}
IMAGE=python:3.13-slim-bookworm@sha256:a1165e272e578941b84abc79e4ab38a0305cd12803a5c4247979ac7655f4d641
PIN_URL=https://github.com/azu/dockerfile-pin/releases/download/v1.5.0/dockerfile-pin_linux_amd64.tar.gz
PIN_SHA256=88845bfbe4918596f00eb77ebeec8a0826026c9b24bcc83053cae48402e95ea6

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/base" "$WORK/pr/tasks" "$WORK/tool" "$OUT"
cp -R "$TB3/scripts" "$WORK/base/scripts"
cp -R "$ROOT/tasks/$TASK" "$WORK/pr/tasks/$TASK"
find "$WORK/pr" -name __pycache__ -type d -prune -exec rm -rf {} +
python3 - "$TB3/.github/workflows/static-checks.yml" "$WORK/run.sh" <<'EOF'
import sys, yaml
steps = yaml.safe_load(open(sys.argv[1]))["jobs"]["static-checks"]["steps"]
open(sys.argv[2], "w").write(next(s for s in steps if s.get("name") == "Run all static checks")["run"])
EOF
curl --fail --silent --show-error --location "$PIN_URL" --output "$WORK/tool/dockerfile-pin.tar.gz"
echo "$PIN_SHA256  $WORK/tool/dockerfile-pin.tar.gz" | shasum -a 256 -c -

COMMIT=$(git -C "$TB3" rev-parse HEAD)
{
  echo "Terminal-Bench checkout: $COMMIT"
  echo "Task: tasks/$TASK"
  echo "Checks: $(grep -c '|check-' "$WORK/run.sh") in the CI step"
  echo
} > "$OUT/static-checks.log"

set +e
docker run --rm --platform linux/amd64 --network none -v "$WORK:/work" -w /work/pr \
  -e GITHUB_WORKSPACE=/work -e GITHUB_OUTPUT=/work/github-output -e BASE_DIR=/work/base \
  -e TASK_DIRS="tasks/$TASK" -e FIX_DIRS="tasks/$TASK" \
  -e REPO_URL=https://github.com/harbor-framework/terminal-bench -e PR_NUMBER= \
  -e HEAD_REPO_URL=local -e HEAD_SHA=local -e RUN_URL=local \
  "$IMAGE" bash -c '
    echo "'"$PIN_SHA256"'  /work/tool/dockerfile-pin.tar.gz" | sha256sum --check &&
    tar --extract --gzip --file /work/tool/dockerfile-pin.tar.gz --directory /usr/local/bin dockerfile-pin &&
    bash --noprofile --norc -eo pipefail /work/run.sh' >> "$OUT/static-checks.log" 2>&1
status=$?
set -e
cp "$WORK/github-output" "$OUT/github-output" 2>/dev/null || true
[ -f "$WORK/github-output" ] && grep '^comment_b64=' "$WORK/github-output" | cut -d= -f2- | base64 --decode > "$OUT/static-checks-comment.md"
grep -E '^(✅|❌)' "$OUT/static-checks.log" || true
echo "passed: $(grep -c '^✅' "$OUT/static-checks.log"), failed: $(grep -c '^❌' "$OUT/static-checks.log")"
grep -q '^all_passed=true$' "$OUT/github-output" 2>/dev/null && [ $status -eq 0 ]
