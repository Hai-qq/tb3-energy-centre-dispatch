# v10 trials: deliverables and verifier output

Three standard trials ran on v10 before the round was stopped, in this order:

| Trial | Agent and model | Reward | Tests | Agent time |
|---|---|---|---|---|
| `ecd10-run1-claude` | claude-code 2.1.299, `anthropic/claude-opus-5-5` at max effort | 0 | 5 failed, 40 passed, 10 errors | 32.7 min |
| `ecd10-run1-codex` | codex 0.162.1, `openai/gpt-6.1-sol` at xhigh | 0 | 3 failed, 22 passed, 30 errors | 29.4 min |
| `ecd10-run2-claude` | claude-code 2.1.299, `anthropic/claude-opus-5-5` at max effort | 1 | 55 passed | 56.1 min |

`ecd10-run2-claude` started seven minutes before `ecd10-run1-codex` ended, when the order was
changed to Opus first (README, "Trial results", v10). What each tool does on the verifier's days
and each agent's closing message are in `results/official-v10.md`.

Exported by `tools/export_trials.py` as for v8 (`results/v8-trials/README.md`):

- `<job>/app/`: the agent's `/app/dispatch.py` and `/app/planner`
- `<job>/verifier/`: `test-stdout.txt`, `ctrf.json`, `reward.txt`
- `<job>/trial.json`: agent, model, settings, timing, tokens and reward
- `MANIFEST.sha256`: SHA-256 of every file here (`shasum -a 256 -c MANIFEST.sha256`)

All three ran on the task files with hash `aa00a9fa0c67426f`, as `trial.json` records, which
are now in `archive/energy-centre-dispatch-v10/`.
