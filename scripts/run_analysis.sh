#!/usr/bin/env bash
# Run Terminal-Bench's trajectory review on local trials (reviewer: claude-code + Sonnet 5, as
# analyze_agent and analyze_model in ci/tb3/harbor-run-defaults.yml) and copy each trial's
# analysis.json to <out-dir>/<trial-job>.json. Exits non-zero unless every trial got a valid one.
#   scripts/run_analysis.sh <job-name> <task-dir> <out-dir> <trial-job> [<trial-job> ...]
#   e.g. scripts/run_analysis.sh analysis-v8 archive/energy-centre-dispatch-v8 \
#          results/analysis-v8 ecd8-run1-codex ecd8-run1-claude
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NAME="$1"; TASK="$2"; OUT="$3"; shift 3
STAGE="$ROOT/jobs/analysis-stage/$NAME"
python3 "$ROOT/tools/stage_analysis.py" "$STAGE" "$TASK" "$@"

unset ANTHROPIC_BASE_URL ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_MODEL \
  ANTHROPIC_SMALL_FAST_MODEL ANTHROPIC_DEFAULT_OPUS_MODEL ANTHROPIC_DEFAULT_SONNET_MODEL \
  ANTHROPIC_DEFAULT_HAIKU_MODEL CLAUDE_CODE_USE_BEDROCK CLAUDE_CODE_USE_VERTEX \
  OPENAI_API_KEY OPENAI_BASE_URL
export CLAUDE_FORCE_OAUTH=1
CLAUDE_CODE_OAUTH_TOKEN="$(tr -d '\n' < "$HOME/.claude-oauth-token")"
export CLAUDE_CODE_OAUTH_TOKEN

harbor run --path "$STAGE" --agent claude-code --model anthropic/claude-sonnet-5 \
  --n-concurrent 3 --env docker --yes -o "$ROOT/jobs" --job-name "$NAME" \
  --agent-setup-timeout-multiplier 5

python3 - "$ROOT/jobs/$NAME" "$OUT" "$#" <<'PY'
import json, sys
from pathlib import Path
job, out, expected = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
valid = 0
for result in sorted(job.glob("*/result.json")):
    r = json.loads(result.read_text())
    source = r["task_name"].rsplit("__", 1)[0]
    reward = ((r.get("verifier_result") or {}).get("rewards") or {}).get("reward")
    artifact = result.parent / "artifacts" / "analysis.json"
    if reward == 1 and artifact.is_file():
        (out / f"{source}.json").write_text(artifact.read_text())
        checks = json.loads(artifact.read_text())["checks"]
        print(source, {k: v["outcome"] for k, v in checks.items()})
        valid += 1
    else:
        print(source, "no valid analysis:", reward, (r.get("exception_info") or {}).get("exception_type"))
print(f"{valid} valid of {expected} trials")
sys.exit(0 if valid == expected else 1)
PY
