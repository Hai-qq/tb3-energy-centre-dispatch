# Acceptance checklist

Each requirement of the assignment, the evidence for it and its status, for the delivered task
[`tasks/energy-centre-dispatch`](tasks/energy-centre-dispatch) (files hash `acdfe59ea74ff707`,
computed as under "Reproducing" in the [README](README.md)). The standard and `/cheat` trials
ran on v8 (`6826dc661e623be8`), which differs in its verifier's handling of crashing or hanging
runs and in its unpinned base image; see "Limitations" in the README.

The assignment's source of truth is the current Terminal-Bench CI. Everything below was checked
against `harbor-framework/terminal-bench` at `bf4c125` (main, 2026-10-07).

## Automated checks

| Requirement | Evidence | Status |
|---|---|---|
| All required static checks | CI's static-check step, run unchanged by `scripts/run_static_checks.sh`: [log](results/checks-v8.1/static-checks.log), [the comment CI would post](results/checks-v8.1/static-checks-comment.md) | met: 27 / 27 |
| Implementation rubric checks | `scripts/run_review.sh`: claude-code + Sonnet 5 with CI's rubric and prompt ([verdicts](results/checks-v8.1/review-verdicts.json)) | met: 35 / 35 criteria pass |
| Docker build | `docker build --no-cache` of both images ([log](results/checks-v8.1/docker-build.log)) | met: both images build |
| Oracle validation | reward 1.0, 55 / 55 tests ([output](results/checks-v8.1/oracle/test-stdout.txt)) | met |
| Nop validation | reward 0.0 ([output](results/checks-v8.1/nop/test-stdout.txt)) | met |

## Trials

| Requirement | Evidence | Status |
|---|---|---|
| codex + GPT-6.1 Sol (xhigh), three standard trials, all genuinely failing | rewards 0, 0, 0, no Harbor exception; each tool wrote no plan for three hidden days ([`results/official-v8.md`](results/official-v8.md), [`results/v8-trials/`](results/v8-trials/)) | met |
| claude-code + Opus 5.5 (max), three standard trials, all genuinely failing | rewards 0, 0, 0, no Harbor exception; plans that the plant or its connection cannot run ([`results/official-v8.md`](results/official-v8.md), [`results/v8-trials/`](results/v8-trials/)) | met |
| Infrastructure errors do not count as failures | two attempts stopped before the agent could work (the model at capacity; a dropped connection while installing Claude Code) were not counted and were run again; both are kept under other names (README, "Trial results") | met |
| `/cheat`, each configuration once, zero reward | codex 0 (OpenAI's API refused the first turn, twice), claude-code 0 ([`results/cheat-v8.md`](results/cheat-v8.md)) | met; no exploit was attempted |
| The verifier is not exploitable or bypassable | separate verifier image; tests, reference model and hidden days readable by root only; the tool run as `nobody` on private copies of each day; every figure recomputed; cost against a whole-day MILP; the reward written by `test.sh` (README, "Failure analysis", v5). CI's trajectory review checks every trial for reward hacking ([`results/analysis-v8/`](results/analysis-v8/)) | no exploit found; not tested by an independent red team |
| CI's agent and model configuration | the assignment names GPT-6.1 Sol and Opus 5.5, which were run with CI's other settings; CI's defaults (`gpt-6-astra`, `claude-fable-5-1`) were not run (README, "Configuration") | deviation, documented |

## Repository and documentation

| Requirement | Evidence | Status |
|---|---|---|
| A GitHub repository within seven days (by 2026-10-12) | [github.com/Hai-qq/tb3-energy-centre-dispatch](https://github.com/Hai-qq/tb3-energy-centre-dispatch), public, Apache 2.0 | met |
| Check results, trial results and a brief failure analysis | README: the table at the top, "Trial results", "Failure analysis" | met |
| Commands, configurations and results of every check and run | README: "Reproducing", "Configuration"; [`results/`](results/) | met |

## Contributing guide and review documentation

| Requirement | Evidence | Status |
|---|---|---|
| Task format, metadata, canary strings, separate verifier, pinned images and packages | the static checks above | met |
| README sections (difficulty, solution, verification, relevant experience) written completely by a human, one to three sentences each | [task README](tasks/energy-centre-dispatch/README.md) | open: to be rewritten by the author |
| Failure analysis of failed trajectories | CI's trajectory review of all nine v8 trials, with CI's prompt and criteria ([`results/analysis-v8/`](results/analysis-v8/)); CONTRIBUTING's `harbor analyze --job-prompt` command needs an option this Harbor version does not have, so CI's own staging was mirrored (`tools/stage_analysis.py`) | met: no reward hacking or specification failure in any trial; near miss flagged for three of the six standard trials, discussed there |
| Avoid creating tasks adversarially | one task, not filtered from many, but revised against the trials' failures from v4 to v8; disclosed (README, "How the task came about" and "Limitations") | partly; disclosed |
