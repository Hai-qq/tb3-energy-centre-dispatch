# Checks on the delivered task

Run on 2026-10-08 on the task files with hash `acdfe59ea74ff707` (README, "Reproducing"),
against Terminal-Bench `bf4c125` (main, 2026-10-07) and Harbor `0.23.1.dev202609170426`.

| file | what | command |
|---|---|---|
| `static-checks.log`, `static-checks-comment.md` | CI's static-check step (27 checks) and the comment it would post | `scripts/run_static_checks.sh <terminal-bench-checkout>` |
| `docker-build.log` | both images built from scratch | `docker build --no-cache` on `environment/` and `tests/` |
| `oracle/`, `nop/` | the verifier's output (`test-stdout.txt`, `ctrf.json`, `reward.txt`) | `harbor run -p tasks/energy-centre-dispatch --agent oracle` (or `nop`) `--env docker` |
| `review-verdicts.json` | the implementation rubric review's verdicts, run again on 2026-10-09 after the task README's explanation sections were rewritten | `TASK_NAME=energy-centre-dispatch scripts/run_review.sh <job-name>` |
| `mutants.txt` | each planted bug, likely half-fix, reporting and execution fault applied alone to the solution | `python tools/energy_mutants.py` |

The Harbor runs used a frozen copy of the task (`staging/`, made with `rsync` from `tasks/`).
