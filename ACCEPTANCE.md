# Acceptance checklist

Each requirement of the assignment, the evidence for it and its status, for the task proposed for delivery: v19, in [`tasks/energy-centre-dispatch`](tasks/energy-centre-dispatch). Its files hash is `9a92bbace1766bde`, computed as under "Reproducing" in the [README](README.md).
- **The trials** ran on v19 as trialled, `archive/energy-centre-dispatch-v19/` (`05f58dca0b55b63f`). The task differs from it only in a `difficulty_explanation` field in `task.toml`'s metadata, which no agent sees and the verifier does not use.
- **The assignment's reviewer** ran v8.1 (`acdfe59ea74ff707`, on `main`), the version delivered first, and Opus passed two of their three runs. v9 to v19 are the hardening that followed (README, "Status"; [`HARDENING.md`](HARDENING.md)).

The assignment's source of truth is the current Terminal-Bench CI. Everything below was checked against `harbor-framework/terminal-bench` at `cac7593` (main, 2026-10-20).

## Automated checks

| Requirement | Evidence | Status |
|---|---|---|
| All required static checks | CI's static-check step, run unchanged by `scripts/run_static_checks.sh`: [log](results/checks-v19/static-checks-cac7593.log), [the comment CI would post](results/checks-v19/static-checks-cac7593-comment.md) | met: 28 / 28 |
| Implementation rubric checks | `scripts/run_review.sh`: claude-code + Sonnet 5 with CI's 36-criterion rubric and prompt ([verdicts](results/checks-v19/review-verdicts.json)); our own reading of each criterion ([`rubric-self-review.md`](results/checks-v19/rubric-self-review.md)) | met: 35 pass, 1 not applicable (`artifact_efficiency`), 0 fail, 0 warn |
| Docker build | `docker build --no-cache` of both images ([log](results/checks-v19/docker-build.log)) | met: both images build |
| Oracle validation | reward 1.0, 55 / 55 tests ([output](results/checks-v19/oracle/test-stdout.txt)) | met |
| Nop validation | reward 0.0 ([output](results/checks-v19/nop/test-stdout.txt)) | met |

## Trials

The v19 trials ran in batches of three Opus and three GPT trials, one batch after another, until a batch failed all six. The rule was set before the first batch, and every trial is reported (README, "Trial results", v19; [`results/v19-batches/README.md`](results/v19-batches/README.md)).

| Requirement | Evidence | Status |
|---|---|---|
| codex + GPT-6.1 Sol (xhigh), three standard trials, all genuinely failing | Batch 2: rewards 0, 0, 0, no Harbor exception; each tool wrote no plan for any hidden day. Batch 1's three GPT trials failed as well, so GPT failed all 6 of its v19 trials ([`results/official-v19-batches.md`](results/official-v19-batches.md), [`results/v19-batches/`](results/v19-batches/)) | met |
| claude-code + Opus 5.5 (max), three standard trials, all genuinely failing | Batch 2: rewards 0, 0, 0, no Harbor exception. Two tools ran units through outages of their parts on every hidden day, and one wrote no plan for any hidden day (same sources). The earlier v19 trials include two Opus passes, one in the first round (1 of 2) and one in batch 1 (1 of 3). Counting every v19 trial, Opus passed 2 of 8 | met in batch 2; the earlier passes disclosed |
| Infrastructure errors do not count as failures | One attempt, `ecd19-b1-run2-claude`, stopped before the agent could work: a dropped connection while installing Claude Code. It was not counted, and its slot was run again. It is kept under its own name (README, "Trial results", v19) | met |
| `/cheat`, each configuration once, zero reward | On the task as delivered (`9a92bbace1766bde`), both 0. claude-code: Opus listed the container, found no tests or reference outputs, and ran the shipped tool. After a safety classifier stopped one of its turns, it ended the run without changing anything. codex: OpenAI's filter refused the cheat prompt (`AgentSafetyRefusalError`, after 17 seconds) ([`results/cheat-v19.md`](results/cheat-v19.md), [`results/v19-cheat/`](results/v19-cheat/)). v17 and v8 gave the same outcomes | met; no exploit was attempted |
| The verifier is not exploitable or bypassable | Separate verifier image; tests, reference model and hidden days readable by root only; the tool run as `nobody` on private copies of each day; every figure recomputed; cost against a whole-day MILP; the reward written by `test.sh` (README, "Failure analysis", v5). CI's trajectory review found no reward hacking in any of the 14 v19 trials ([`results/analysis-v19/`](results/analysis-v19/)) | no exploit found; not tested by an independent red team |
| CI's agent and model configuration | The assignment names GPT-6.1 Sol and Opus 5.5, which were run with CI's other settings. CI's defaults (`gpt-6-astra`, `claude-fable-5-1`) were not run (README, "Configuration") | deviation, documented |

## Repository and documentation

| Requirement | Evidence | Status |
|---|---|---|
| A GitHub repository within seven days (by 2026-10-12) | [github.com/Hai-qq/tb3-energy-centre-dispatch](https://github.com/Hai-qq/tb3-energy-centre-dispatch), public, Apache 2.0 | met |
| Check results, trial results and a brief failure analysis | README: the table at the top, "Fairness of v19", "Trial results" and "Failure analysis" (v19 first) | met |
| Commands, configurations and results of every check and run | README: "Reproducing", "Configuration"; [`results/`](results/) | met |

## Contributing guide and review documentation

| Requirement | Evidence | Status |
|---|---|---|
| Task format, metadata, canary strings, separate verifier, pinned images and packages | the static checks above | met |
| README sections (difficulty, solution, verification, relevant experience) written completely by a human, one to three sentences each | [task README](tasks/energy-centre-dispatch/README.md); `task.toml`'s `difficulty_explanation` repeats its "Difficulty explanation" word for word | met: written by the author, one to three sentences each |
| Failure analysis of failed trajectories | CI's trajectory review of all 14 v19 trials, with CI's prompt and criteria ([`results/analysis-v19/`](results/analysis-v19/)). CONTRIBUTING's `harbor analyze --job-prompt` command needs an option this Harbor version does not have, so CI's own staging was mirrored (`tools/stage_analysis.py`) | met: no reward hacking or specification failure in any trial, and the difficulty crux confirmed for all 14. Near miss is flagged for the five that failed only on outages of parts (README, "Fairness of v19") |
| Avoid creating tasks adversarially | One task, not filtered from many. But it was revised against its trials from v4 to v19, and v19 was run in batches until one failed all six. Both are disclosed (README, "How the task came about", "Fairness of v19" and "Trial results"; [`HARDENING.md`](HARDENING.md)) | partly; disclosed |
