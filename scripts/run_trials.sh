#!/usr/bin/env bash
# Run trials of the task with the TB3 CI agent settings and subscription authentication.
#
#   scripts/run_trials.sh <claude|codex> <run|cheat> <attempts> <job-name> [extra harbor args...]
#
# Mirrors ci/tb3/harbor-run-defaults.yml for agent kwargs/env; the models are the ones the
# assignment names (Opus 5.5 at max effort, GPT-6.1 Sol at xhigh). "cheat" appends the TB3
# red-team prompt (ci/tb3/hack-trial-prompt.md) and always runs one attempt, like /cheat.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AGENT="$1"; KIND="$2"; N="$3"; NAME="$4"; shift 4
TASK="$ROOT/tasks/${TASK_NAME:-energy-centre-dispatch}"
JOBS="$ROOT/jobs"

# Use only the subscription credentials below; drop API settings inherited from the shell
# so they neither redirect the agent nor get copied into the trial container.
unset ANTHROPIC_BASE_URL ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_MODEL \
  ANTHROPIC_SMALL_FAST_MODEL ANTHROPIC_DEFAULT_OPUS_MODEL ANTHROPIC_DEFAULT_SONNET_MODEL \
  ANTHROPIC_DEFAULT_HAIKU_MODEL CLAUDE_CODE_USE_BEDROCK CLAUDE_CODE_USE_VERTEX \
  OPENAI_API_KEY OPENAI_BASE_URL

EXTRA=()
if [ "$KIND" = "cheat" ]; then
  EXTRA+=(--extra-instruction-path "$ROOT/ci/tb3/hack-trial-prompt.md")
  N=1
elif [ "$KIND" != "run" ]; then
  echo "kind must be run or cheat" >&2; exit 2
fi

case "$AGENT" in
  claude)
    export CLAUDE_FORCE_OAUTH=1
    export CLAUDE_CODE_MAX_OUTPUT_TOKENS=128000
    CLAUDE_CODE_OAUTH_TOKEN="$(tr -d '\n' < "$HOME/.claude-oauth-token")"
    export CLAUDE_CODE_OAUTH_TOKEN
    exec harbor run -p "$TASK" --agent claude-code --model anthropic/claude-opus-5-5 \
      --ak reasoning_effort=max --env docker --yes -k "$N" -o "$JOBS" --job-name "$NAME" \
      ${EXTRA[@]+"${EXTRA[@]}"} "$@"
    ;;
  codex)
    export CODEX_FORCE_AUTH_JSON=1
    exec harbor run -p "$TASK" --agent codex --model openai/gpt-6.1-sol \
      --ak reasoning_effort=xhigh --env docker --yes -k "$N" -o "$JOBS" --job-name "$NAME" \
      ${EXTRA[@]+"${EXTRA[@]}"} "$@"
    ;;
  *) echo "agent must be claude or codex" >&2; exit 2 ;;
esac
