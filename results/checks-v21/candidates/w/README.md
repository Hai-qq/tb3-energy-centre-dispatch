# Candidate W build record

Built from the unchanged v19 task at commit `08f5d78` on `v21-prechecks`, using `rsync -a --exclude __pycache__`. The candidate task lives in `task/`; all validation artifacts live in `build/`.

## Changes and rule

In `environment/data/supply.json` and all five `tests/days/*/supply.json`, `electricity.import_rates_p_per_kwh.weekend[0].rate` changed from **13.8 to 5.0 p/kWh** (00:00–07:00). Export remains 5.9 p/kWh; all weekday rates are unchanged.

Each steady half-hour has one net connection direction. `test_single_connection_direction` uses C1's exact tolerance: `min(import_kw, export_kw) <= 0.5 kW`. The reference MILP direction binary, signed-net grid cost recomputation, test, and solution direction enumeration were copied byte-for-byte from C1. This includes C1's `presolve=False` solver option.

No hidden day was changed beyond its tariff. On h1 (**2026-08-08**, Saturday), the `grid_direction_ignored` solution has simultaneous import/export in **14 half-hours, 00:00 through 06:30**. Minimum simultaneous import is 1133.576 kW and export is 188.597 kW. See `build/rule_pressure.json` and the retained plans.

The new mutation removes the solution's direction enumeration (`directions = (None,)`). It is caught on h1 by `test_single_connection_direction` and `test_reported_gas_and_cost`.

## Commands and gates

Run from the repository root with the existing venv:

```sh
PY=/private/tmp/claude-501/-Users-haiy-qq-Desktop----klavis/a70e7eab-ed43-4fbc-8c31-1d0858956a32/scratchpad/codex-v18-verify/venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export ECD_TASK="$PWD/results/checks-v21/candidates/w/task"
B="$PWD/results/checks-v21/candidates/w/build"
"$PY" "$B/verify_candidate.py" w
"$PY" tools/eval_energy.py "$ECD_TASK/solution/app"
"$PY" tools/energy_mutants.py
"$PY" "$B/candidate_mutants.py"
"$PY" tools/fresh_days.py --days 16 --seed 2026 --output "$B/fresh" "$ECD_TASK/solution/app"
"$PY" tools/eval_energy.py results/v16-trials/ecd16-run2-claude/app
"$PY" tools/eval_energy.py results/v19-trials/ecd19-run2-claude/app
```

`fresh` is the retained original output; use a new output pathname to repeat the random run. Exact argv, `ECD_TASK`, exit code and elapsed seconds for tool invocations are saved in `build/*.result.json`.

- **A: PASS.** `"$PY" "$B/verify_candidate.py" w` performs the byte and data checks, per-day cost comparison and rule-ignored-plan check. Full byte comparison permits only the specified environment JSON edits; instruction, task.toml, both Dockerfiles and tests/test.sh are unchanged. Other task edits are limited to the reference, tests, solution and the stated hidden statuses. See `build/gate_a.json`.
- **B: PASS.** Standard-answer `eval_energy.py` exit 0. All five `abs(least_cost - true_flows(solution))` gaps are below £0.001; maximum £0.000176562. Per-day costs: `build/costs.json`; plans: `build/plans/`. Fresh run exit 0, 0/16 days failed, seed 2026, 5 accepted weekend days. See `build/fresh.log`, `build/fresh/manifest.json`, and `build/fresh_coverage.json`.
- **C: PASS.** Shared `tools/energy_mutants.py` exit 0: **42/42 CAUGHT**. The candidate-local adapter exit 0: **1/1 CAUGHT**, giving **43/43 CAUGHT** including the new mutation. All 43 patch definitions pass preflight (each anchor appears exactly once); no fallback or skip is allowed. See `build/mutation_preflight.json`, `build/mutants_base.log`, and `build/mutants_new.log`.
- **E:** original A16 and A19 each evaluated once (the evaluator runs each day twice). See `build/eval_a16.log` and `build/eval_a19.log`.

`fresh_days.py` already reads the candidate plant and supply, so it required no adaptation. Every accepted random day has byte-identical candidate plant/supply files. The 16-day set includes five weekend dates; no tariff or random-day source generator was modified.

A16: exit 0, all tests pass. Its report reconstructs a signed net connection flow and recomputes billed cost. Its LP internally permits both directions, so passing this candidate does not prove that its optimization model enforces the new direction rule.

A19: exit 1, h1 fails `test_single_connection_direction` and `test_reported_gas_and_cost`; every other day passes. It reports the LP's simultaneous import/export and gross arbitration cost rather than a single metered net direction. These failures are due to the new rule under the changed tariff.

## Verification boundary

Harbor and Docker were not run, as instructed. No git commit/push, branch change, global dependency install, source-task/tool edits, network-configuration inspection, or deletion of user files was performed.
