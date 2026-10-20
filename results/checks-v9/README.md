# Checks on the delivered task (v9)

Run on 2026-10-14 on the task files with hash `a68b1baa343fb396` (README, "Reproducing"), with
Harbor `0.23.1.dev202609170426`.

| file | what | command |
|---|---|---|
| `oracle/`, `nop/` | the verifier's output (`test-stdout.txt`, `ctrf.json`, `reward.txt`) | `harbor run -p tasks/energy-centre-dispatch --agent oracle` (or `nop`) `--env docker` |
| `mutants.txt` | each planted bug, likely half-fix, reporting and execution fault applied alone to the solution | `python tools/energy_mutants.py` |
| `docker-build.log` | both images built from scratch | `docker build --no-cache` on `environment/` and `tests/` |

The Harbor runs used a frozen copy of the task (`staging/`, copied from `tasks/`). The oracle and
nop runs were made on the files before the Saturday's tower-cell outage was moved (hash
`f5be70c9741ddeb6`; see "How the task came about", v9, in the README); the verifier's tests and
both images are the same, and `tools/eval_energy.py` gives the same results on both.
