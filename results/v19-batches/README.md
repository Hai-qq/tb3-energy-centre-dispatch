# v19 in batches of 3+3

The official task, v19 in `tasks/energy-centre-dispatch/` and unchanged, was run in batches of three Opus and three GPT trials, one batch after another, until one batch failed all six. The stopping rule was set before the first trial. Every attempt is recorded here, including the batch in which Opus passed.

| Batch | Opus (agent minutes) | GPT (agent minutes) | Result |
|---|---|---|---|
| 1 | fail (33.9), fail (32.6)\*, **pass** (80.6) | fail (13.5), fail (9.6), fail (15.0) | Opus passes 1 of 3 |
| 2 | fail (104.3), fail (30.9), fail (20.2) | fail (11.5), fail (12.5), fail (12.3) | all six fail; the run stopped |

\* The first attempt at this slot, `ecd19-b1-run2-claude`, failed to install Claude Code in the container (`NetworkConnectionError`). The agent never started, so the attempt is not counted. See the end of `../official-v19-batches.md`.

## Setup

- **Agents.** `scripts/run_trials.sh`, one attempt per job, with `--agent-setup-timeout-multiplier 5`:
  - Claude Code with `anthropic/claude-opus-5-5` at `reasoning_effort=max`;
  - Codex with `openai/gpt-6.1-sol` at `xhigh`.
- **Task files.** The trials ran on `staging/energy-centre-dispatch-v19`, which is byte-identical to `tasks/energy-centre-dispatch`. Harbor's task checksum, `b4223eae…`, is the same in every trial here and in the original v19 trials in `../v19-trials/`.
- **Order.** Opus trials ran one at a time. A batch's GPT trials ran alongside its Opus trials.
- **Pre-flight.** Before the first batch, the oracle scored 1 (job `ecd19-batches-oracle`).

## Stopping rule

The rule is in `run/ecd19-batches-driver2.py`; its progress log is `run/ecd19-batches.status`.
- A batch ends when all six of its trials have counted. The run stops at the first batch with no pass, or after four batches.
- An attempt counts when it has a reward and ended without an exception or with an agent timeout. A reward of 1 always counts.
- An attempt stopped by an infrastructure error before it had a reward is not counted, and its slot is run again. Any other outcome stops the driver for review.

The first driver, `run/ecd19-batches-driver.py`, stopped for review at the failed Claude Code install. It was replaced by the second, which differs in three ways:
- it treats network errors as infrastructure;
- it pauses before running a slot again, for 30 minutes after a rate limit;
- it resumes from the jobs already run instead of running them again.

## What failed

Per-trial detail is in `../official-v19-batches.md`: each tool's failing tests, what it does on every verifier day, and the agent's closing message.
- Five tools fail only `test_units_within_ratings_and_availability`, on all four hidden days: their plans keep units running through outages. These are batch 1's Opus 2, GPT 1 and GPT 2, and batch 2's Opus 1 and 2.
- Five tools write no plan for any hidden day, exiting with "no feasible loading". These are batch 1's GPT 3, and batch 2's Opus 3 and GPT 1–3.
- Batch 1's Opus 1 writes no plan for h3. Its plans for h1, h2 and h4 exceed the connection limit; those for h1 and h4 also cost more than the least cost, and those for h1 and h2 keep units running through outages.

## Files

- `MANIFEST.sha256` covers the exported trial files, written by `tools/export_trials.py`.
- Each `<job>/` holds:
  - `app/`, the agent's deliverable;
  - `verifier/`, the verifier's own output;
  - `trial.json`, Harbor's result without local paths.
- `run/` holds the drivers and their progress log. These are not in the manifest.
