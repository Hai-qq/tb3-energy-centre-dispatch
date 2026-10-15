# v9 trial: deliverable and verifier output

One standard trial ran on v9 before the round was stopped: `ecd9-run1-claude` (claude-code
2.1.299, `anthropic/claude-opus-5-5` at max effort), reward 1, 55 of 55 tests, 33.0 agent
minutes. Exported by `tools/export_trials.py` as for v8 (`results/v8-trials/README.md`):

- `ecd9-run1-claude/app/`: the agent's `/app/dispatch.py` and `/app/planner`
- `ecd9-run1-claude/verifier/`: `test-stdout.txt`, `ctrf.json`, `reward.txt`
- `ecd9-run1-claude/trial.json`: agent, model, settings, timing, tokens and reward
- `MANIFEST.sha256`: SHA-256 of every file here

The trial started on a frozen copy of v9 in which the Saturday's tower-cell outage still ran from
06:40; it was moved to 08:10 while the agent was working. The agent's files (instruction,
environment, data) are the same in both, and `tools/eval_energy.py` passes the deliverable on
both sets of days. `trial.json` gives the hash of the final v9 files
(`archive/energy-centre-dispatch-v9/`, `a68b1baa343fb396`).
