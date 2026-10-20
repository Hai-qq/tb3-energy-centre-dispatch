# Candidate P build record

Built from the unchanged v19 task at commit `08f5d78` on `v21-prechecks`, using `rsync -a --exclude __pycache__`. The candidate task lives in `task/`; all validation artifacts live in `build/`.

## Changes and rule

In `environment/data/plant.json` and all five `tests/days/*/plant.json`, `heat_circuits.ge1_lt` gained final key `"pump": "LT pump 1"` and `ge2_lt` gained final key `"pump": "LT pump 2"`. The keys were absent before. JSON is written with `json.dumps(..., indent=2)` and a final newline.

A pump outage stops circulation and therefore its circuit's source engine for every overlapping half-hour. Ownership is derived by finding `<engine id> intercooler` in the circuit's `from`; its `pump` is included alongside its LT outlets in availability dependencies. No pump name or engine id is hard-coded in the reference or solution. Pump names are recognized as maintenance targets by the reference. `test_lt_pump_outages` also checks the corresponding engine explicitly.

Hidden changes (local time; all pre-existing outages retained):

- h1, **2026-08-08**: `LT pump 1`, **18:10–19:20**. GE1 must stop for 18:00–18:30, 18:30–19:00, and 19:00–19:30. Without the pump dependency it runs at 1200 kWe in all three periods; with the dependency it is zero.
- h3, **2026-04-20**: `LT pump 2`, **17:10–17:20** (10 minutes). GE2 must stop for the entire 17:00–17:30 period. Without the dependency it runs at 600 kWe; with the dependency it is zero.

The retained no-outage baseline plans and pump-ignored plans establish that the outages change the dispatch. See `build/baseline-h*.json`, `build/plans/`, and `build/rule_pressure.json`.

The new mutation omits the pump from the derived LT dependencies. It is caught on h1 and h3 by `test_lt_pump_outages` and `test_units_within_ratings_and_availability`. The existing `parts_by_name_prefix` mutation is also caught on both h1 and h3 by the pump test (and by availability).

## Commands and gates

Run from the repository root with the existing venv:

```sh
PY=/private/tmp/claude-501/-Users-haiy-qq-Desktop----klavis/a70e7eab-ed43-4fbc-8c31-1d0858956a32/scratchpad/codex-v18-verify/venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export ECD_TASK="$PWD/results/checks-v21/candidates/p/task"
B="$PWD/results/checks-v21/candidates/p/build"
"$PY" "$B/verify_candidate.py" p
"$PY" tools/eval_energy.py "$ECD_TASK/solution/app"
"$PY" tools/energy_mutants.py
"$PY" "$B/candidate_mutants.py"
"$PY" "$B/fresh_days.py" --days 16 --seed 2026 --output "$B/fresh" "$ECD_TASK/solution/app"
"$PY" tools/eval_energy.py results/v16-trials/ecd16-run2-claude/app
"$PY" tools/eval_energy.py results/v19-trials/ecd19-run2-claude/app
```

`fresh` is the retained original output; use a new output pathname to repeat the random run. Exact argv, `ECD_TASK`, exit code and elapsed seconds for tool invocations are saved in `build/*.result.json`.

- **A: PASS.** `"$PY" "$B/verify_candidate.py" p` performs the byte and data checks, per-day cost comparison and rule-ignored-plan check. Full byte comparison permits only the specified environment JSON edits; instruction, task.toml, both Dockerfiles and tests/test.sh are unchanged. Other task edits are limited to the reference, tests, solution and the stated hidden statuses. See `build/gate_a.json`.
- **B: PASS.** Standard-answer `eval_energy.py` exit 0. All five `abs(least_cost - true_flows(solution))` gaps are below £0.001; maximum £0.000266612. Per-day costs: `build/costs.json`; plans: `build/plans/`. Fresh run exit 0, 0/16 days failed, seed 2026, 5 accepted weekend days. See `build/fresh.log`, `build/fresh/manifest.json`, and `build/fresh_coverage.json`.
- **C: PASS.** Shared `tools/energy_mutants.py` exit 0: **42/42 CAUGHT**. The candidate-local adapter exit 0: **1/1 CAUGHT**, giving **43/43 CAUGHT** including the new mutation. All 43 patch definitions pass preflight (each anchor appears exactly once); no fallback or skip is allowed. See `build/mutation_preflight.json`, `build/mutants_base.log`, and `build/mutants_new.log`.
- **E:** original A16 and A19 each evaluated once (the evaluator runs each day twice). See `build/eval_a16.log` and `build/eval_a19.log`.

The shared `fresh_days.py` reads candidate plant/supply but its outage sampling list and known-name check omit pump fields. `build/fresh_days.py` is a local copy with only three adjustments: repository ROOT for its new location, append circuit pump names to UNITS, and recognize circuit pump names during input validation. Draw logic, seed, rejection policy and tests are unchanged. The shared tool and `build_energy_days.py` were not modified; a patch is retained as `build/fresh_days.patch`.

The 16 accepted days contain three LT pump 2 outages: f1-draw-0002 (15:40–18:30), f13-draw-0025 (14:50–18:00), and f16-draw-0033 (13:50–16:40). LT pump 1 appeared in drawn days rejected as infeasible by the reference MILP, and is covered by fixed h1. These rejected draws and reasons are retained in the manifest; no accepted day was replaced or resampled to tune results.

A16: exit 1. On h1 and h3, `test_lt_pump_outages` and `test_units_within_ratings_and_availability` fail. Its structural parts list omits circuit `pump`, so it ignores those outages; all other days pass. These are new-rule failures.

A19: exit 1. On h1 and h3 both runs exit with `ValueError: outage of LT pump 1/2, which is not in plant.json`, because its known-name/owner lookup omits pump fields and uses engine-name prefixes for other component ownership. No plan is available on those days, so all 12 test groups fail there:

`test_connection_limits`, `test_cooling_balance`, `test_cooling_towers`, `test_electricity_balance`, `test_heat_balance`, `test_least_cost`, `test_lt_pump_outages`, `test_plan_covers_the_day`, `test_reported_gas_and_cost`, `test_reported_import_export_and_grid_flags`, `test_same_plan_every_time`, `test_units_within_ratings_and_availability`. Other days pass. This is a new-data/new-rule compatibility failure, rather than evidence from an invalid dispatch plan.

## Verification boundary

Harbor and Docker were not run, as instructed. No git commit/push, branch change, global dependency install, source-task/tool edits, network-configuration inspection, or deletion of user files was performed.
