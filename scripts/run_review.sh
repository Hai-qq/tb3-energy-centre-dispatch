#!/usr/bin/env bash
# Run the TB3 implementation-rubric review locally (reviewer: claude-code + Sonnet 5, as in
# ci/tb3/harbor-run-defaults.yml) and print the verdict summary. Exits non-zero unless every
# criterion of the rubric has a verdict and none is "fail".
#   [TASK_NAME=<task>] scripts/run_review.sh <job-name>
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NAME="$1"
STAGE="$ROOT/jobs/review-stage/$NAME"
python3 "$ROOT/tools/stage_review.py" "$STAGE"

unset ANTHROPIC_BASE_URL ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_MODEL \
  ANTHROPIC_SMALL_FAST_MODEL ANTHROPIC_DEFAULT_OPUS_MODEL ANTHROPIC_DEFAULT_SONNET_MODEL \
  ANTHROPIC_DEFAULT_HAIKU_MODEL CLAUDE_CODE_USE_BEDROCK CLAUDE_CODE_USE_VERTEX \
  OPENAI_API_KEY OPENAI_BASE_URL
export CLAUDE_FORCE_OAUTH=1
CLAUDE_CODE_OAUTH_TOKEN="$(tr -d '\n' < "$HOME/.claude-oauth-token")"
export CLAUDE_CODE_OAUTH_TOKEN

harbor run --path "$STAGE" --agent claude-code --model anthropic/claude-sonnet-5 \
  --env docker --yes -o "$ROOT/jobs" --job-name "$NAME" --agent-setup-timeout-multiplier 5

python3 - "$ROOT/jobs/$NAME" "$ROOT/ci/tb3/task-implementation.toml" <<'PY'
import glob, json, sys, tomllib
paths = glob.glob(f"{sys.argv[1]}/*/artifacts/app/verdicts.json")
if not paths:
    sys.exit("no verdicts.json: the review did not finish")
criteria = [c["name"] for c in tomllib.load(open(sys.argv[2], "rb"))["criteria"]]
checks = json.load(open(paths[0]))["checks"]
counts = {}
for name, v in checks.items():
    counts[v["outcome"]] = counts.get(v["outcome"], 0) + 1
print("verdicts:", counts, "of", len(checks), "for", len(criteria), "criteria")
bad = [n for n in criteria if checks.get(n, {}).get("outcome") not in ("pass", "not_applicable")]
for name in bad:
    v = checks.get(name)
    print(f"FAIL {name}: {v['explanation']}" if v else f"MISSING {name}")
sys.exit(1 if bad else 0)
PY
