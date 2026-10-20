# v11 trial: deliverable and verifier output

One standard trial ran on v11 before the round was stopped: `ecd11-run1-claude` (claude-code
2.1.299, `anthropic/claude-opus-5-5` at max effort), reward 1, 55 of 55 tests, 43.1 agent
minutes. Exported by `tools/export_trials.py` as for v8 (`results/v8-trials/README.md`):

- `ecd11-run1-claude/app/`: the agent's `/app/dispatch.py` and `/app/planner`
- `ecd11-run1-claude/verifier/`: `test-stdout.txt`, `ctrf.json`, `reward.txt`
- `ecd11-run1-claude/trial.json`: agent, model, settings, timing, tokens and reward
- `MANIFEST.sha256`: SHA-256 of every file here

The trial ran on the task files in `archive/energy-centre-dispatch-v11/` (hash
`ea19cd9096c6134e`). Its tool also passes the eight days `tools/fresh_days.py` draws with its
default seed. What it does on each day and the agent's closing message:
`results/official-v11.md`.
