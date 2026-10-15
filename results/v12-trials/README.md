# v12 trial: deliverable, replay and verifier output

One standard trial ran on v12 before the round was stopped: `ecd12-run1-claude` (claude-code
2.1.300, `anthropic/claude-opus-5-5` at max effort), 96.9 agent minutes. Harbor recorded
`VerifierTimeoutError`: building the separate verifier image hung for 30 minutes, so the tests
never ran. That is a failure of this Docker Desktop host, not of the agent; the hung build was
still running afterwards and was stopped by hand. The deliverable was then scored in Harbor with
the task's own verifier (`scripts/replay_deliverable.sh`): reward 1, 55 of 55 tests.

- `ecd12-run1-claude/app/`: the agent's `/app/dispatch.py` and `/app/planner`
- `ecd12-run1-claude/replay-v12/`: the replay's `test-stdout.txt`, `ctrf.json`, `reward.txt`
- `ecd12-run1-claude/trial.json`: agent, model, settings, timing, tokens, the exception and no reward
- `MANIFEST.sha256`: SHA-256 of every file here

The trial ran on the task files in `archive/energy-centre-dispatch-v12/` (hash
`7c9fb0eb20e576e8`). What the tool does on each day and the agent's messages:
`results/official-v12.md`.
