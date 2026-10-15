# Checks on the delivered task (v10)

Run on 2026-10-14 on the task files with hash `aa00a9fa0c67426f` (README, "Reproducing"), against
Terminal-Bench `1d49c52` (main, 2026-10-12; its static checks are those of `bf4c125`) and
Harbor `0.23.1.dev202609170426`.

| file | what | command |
|---|---|---|
| `static-checks.log`, `static-checks-comment.md` | CI's static-check step (27 checks) and the comment it would post | `scripts/run_static_checks.sh <terminal-bench-checkout>` |
| `oracle/`, `nop/` | the verifier's output (`test-stdout.txt`, `ctrf.json`, `reward.txt`) | `harbor run -p tasks/energy-centre-dispatch --agent oracle` (or `nop`) `--env docker` |
| `mutants.txt` | each planted bug, likely half-fix, reporting and execution fault applied alone to the solution | `python tools/energy_mutants.py` |

The Harbor runs used a frozen copy of the task (`staging/`, copied from `tasks/`). Both images
were built by Harbor for these runs; a build from scratch (`docker build --no-cache`) could not be
completed on 2026-10-14 because the Debian package mirror kept dropping the connection, and the
Dockerfiles are those that built from scratch for v8.1 (`results/checks-v8.1/docker-build.log`).
