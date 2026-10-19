# Candidate D build record

Built on `v22-prechecks` from the accepted candidate S using `rsync -a --exclude __pycache__`. The runnable Harbor package is in `task/`; local verification scripts and retained evidence are in `build/`. The formal v19 task and candidate S were not edited. No Harbor or Docker run was performed.

## Changes and rule

The supplied D `data/plant.json` was copied byte for byte into `environment/data/plant.json` and all five verifier days. The supplied D `planner/plant.py` was copied byte for byte into `environment/planner/plant.py`. These are the only environment differences from formal v19. `instruction.md`, `task.toml`, both Dockerfiles and `tests/test.sh` are unchanged. The environment tool retains its other original defects.

Each engine's former HT curve is split into jacket-water and exhaust heat, whose sum equals the former value at every part-load point. The plant names the separate HT source endpoints and an exhaust heat exchanger with a modulating diverter to the stack. Curves interpolate linearly and remain flat outside their endpoints. All jacket heat must enter the engine HT circuit. Any amount from zero to all exhaust heat may instead go directly to the stack. An exhaust-exchanger outage forces all that engine's exhaust to the stack without stopping the engine; a jacket-water-exchanger outage stops it. Any outage overlap removes availability for the entire half-hour.

S's LT topology and rule remain: each engine needs its own primary LT PHE; the two PHEs feed a common rejection circuit with two 220 kW radiators. A primary PHE outage stops its engine. Radiator outages reduce the shared remaining capacity without directly stopping either engine. All other physics, tariffs, availability and reporting rules remain those of v19.

Implementation:

- `tests/reference.py`: independent jacket/exhaust interpolation, separate `exhaust_ok` availability, HT recovery interval in `true_flows`, and a stack variable constrained by available exhaust heat in the full-day `least_cost` MILP. No v15 levy, capacity-market charge or radiator-rating rule was imported.
- `tests/test_plans.py`: retain every S test and fixture. Only `test_heat_balance` changes its body to the v15 jacket/exhaust interval check. The unchanged output schema determines aggregate recovered heat from demand, boilers and absorption heat; no new plan field is required. Shared-header interval feasibility is equivalent to allocating a feasible recovery amount to each engine.
- `solution/app/planner/plant.py`: source ownership comes from the plant endpoints and `exhaust_heat_exchanger.bypass`, with no hard-coded engine, circuit, PHE or radiator identifiers. Extend each engine segment with exhaust intercept and slope.
- `solution/app/planner/optimize.py`: mandatory jacket and primary-LT dependencies, available-exhaust segment selection, and one aggregate modulating stack variable in each period LP. The existing start-aware day dynamic programme remains.

`build/implement.py` records the edits for a fresh copy of S; it is not an idempotent updater. Five mutation definitions needed equivalent D anchors: `heat_can_be_dumped`, `lt_heat_counted`, `intercooler_outage_ignored`, `ht_source_outage_ignored`, and `parts_by_name_prefix`. Their full replacements are explicit in `build/candidate_mutants.py` and `build/candidate_mutants.patch`. Every patch must match exactly once; no skip/fallback path exists. All other S definitions retain their original anchors and meanings.

Hidden changes (local time; all unlisted inputs and outages unchanged):

- h1, 2026-08-08: retain S's `LT PHE 1` outage **18:10–19:20**.
- h2, 2026-01-14: rename `GE2 jacket water and exhaust` to `GE2 jacket water heat exchanger`, retaining **18:20–18:40**. Add `GE1 exhaust heat exchanger` **12:00–14:50**, covering six starts from 12:00 through 14:30. Retain `LT radiator 1` **21:10–23:00**.
- h3, 2026-04-20: retain `LT radiator 2` **10:40–14:20**.
- h4, 2026-07-29: retain `LT radiator 1` **00:00–03:40**.

The first reference-model probe used v15's h2 **09:20–14:50** window. Both exhaust pressure conditions held, but this overlapped the existing GE1 intercooler outage **09:20–11:50**. The start was therefore moved to 12:00, with no other data adjustment. The final window overlaps no other GE1 maintenance. Stopping GE1 for the exhaust outage makes the full-day MILP infeasible. Ignoring the outage yields an infeasible heat-recovery claim of **450 kW above the physical upper bound in each of the six periods**, with cost **GBP 65.836732 below** the valid optimum. See `build/exhaust_pressure.json`; the candidate-local solution mutations independently exercise the same two errors in the normal evaluator.

## Visible day

The standard answer costs **GBP 5346.572** (independently recomputed GBP 5346.571630). The original v19 and S standard answers were each run on their own unchanged visible input: both report **GBP 6303.560**, so D is **GBP 956.988 cheaper** than either. This is a material visible-day change produced by the specified bypass rule.

The D visible plan bypasses exhaust in **38 of 48 half-hours**, using **7649.036972 kWh** of exhaust bypass over the day, with maximum half-hour stack duty **582.284037 kW**. `build/visible_comparison.json` records all 48 starts, each engine's generated exhaust heat and aggregate stack duty; complete plans are in `build/plans/`. The unchanged plan schema determines total stack duty but does not identify its allocation between simultaneously running engines. No unique per-engine allocation is claimed.

## Commands and gates

Run from the repository root with the supplied existing venv:

```sh
PY=/private/tmp/claude-501/-Users-haiy-qq-Desktop----klavis/a70e7eab-ed43-4fbc-8c31-1d0858956a32/scratchpad/codex-v18-verify/venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export ECD_TASK="$PWD/results/checks-v22/candidates/d/task"
B="$PWD/results/checks-v22/candidates/d/build"
"$PY" "$B/run_checks.py" verify_candidate
"$PY" "$B/run_checks.py" eval_solution
"$PY" "$B/candidate_mutants.py" --preflight > "$B/mutation_preflight.json"
"$PY" "$B/run_checks.py" mutants_1
"$PY" "$B/run_checks.py" mutants_2
"$PY" "$B/run_checks.py" fresh
"$PY" "$B/run_traits.py" solution
"$PY" "$B/run_traits.py" a16
"$PY" "$B/run_traits.py" a19
"$PY" "$B/run_checks.py" final_audit
```

`run_checks.py` records exact argv, `ECD_TASK`, exit status, duration and full logs. The mutation groups may run concurrently, using distinct `TMPDIR` folders under the assigned external D scratch directory. The wrapper with no arguments evaluates all 48 mutations and exits nonzero if any required mutation lacks a hidden-day failure; `diverter_ignored` is the sole permitted exception. Fresh output requires a new pathname on a repeat run; do not overwrite retained randomized-day evidence. The `run_traits.py` example runs intentionally return 1 for an app that fails any version.

- **A: PASS.** Byte-level environment allowlist is exactly `data/plant.json` and `planner/plant.py`, both identical to the supplied files; instruction and protected packaging files are unchanged. Full task change allowlist and AST comparison retain all original tests, changing only the heat-balance body. See `build/gate_a.json`.
- **B: PASS.** `ECD_TASK=<D task> python tools/eval_energy.py <D task>/solution/app` exits 0, all 12 test groups on all five days. Independent full-day MILP and solution true-flow cost agree within GBP 0.001 on every day; maximum absolute gap **GBP 0.000232513**. Retained per-day solution and reference runs each take less than one second, below 120 seconds. See `build/eval_solution.log`, `build/costs.json`, and `build/verify_candidate.log`.
- **B fresh: PASS.** Seed 2026, **16 accepted days from 31 draws**, zero failed days or execution errors. Every random-day plant is byte-identical to D; tests/reference hashes and input hashes are retained in `build/fresh/manifest.json`. Accepted days cover exhaust-exchanger, jacket-water-exchanger, primary LT PHE, and radiator outages. See `build/fresh.log` and `build/fresh_coverage.json`.
- **C: PASS.** Both wrapper groups exit 0: **48/48 CAUGHT on at least one hidden day**, comprising all 45 S mutations and the three D mutations. All **55 patch anchors** match exactly once; zero skips. `diverter_ignored` is caught on h1, h3 and h4, so the optional exception is not needed. No non-hanging mutation times out. See `build/mutation_preflight.json`, both `build/mutants_*.log` files, their complete `build/mutation_results_mutants_*.json` records, and `build/rule_pressure.json`.
- **E: EXECUTED; compatibility failures.** A16 and A19 each have exactly one original D evaluation within their four-version example run (the normal evaluator runs each day twice). Neither app was adapted or modified. See the D sections of `build/traits_a16.json` and `build/traits_a19.json`.

The candidate-local `build/fresh_days.py` adaptation changes only its repository-root location and outage sampling names: split the old combined HT component into jacket and exhaust exchangers and include S's graph-derived primary LT outlets. The existing random draw algorithm, seed, input validation, feasibility rejection policy and evaluator are unchanged. `build/fresh_days.patch` records the complete difference from the shared tool. Rejected draws are retained as specifications and reasons in the manifest; no accepted day was replaced to tune results.

Accepted coverage includes GE2 jacket **13:10–14:10** and exhaust **15:40–18:30** on `f1-draw-0002`; GE1 exhaust **08:20–13:30** and LT PHE 1 **13:20–15:10** on `f15-draw-0025`; LT PHE 2 **12:20–15:00** on `f3-draw-0005`; radiators on `f2-draw-0003`, `f7-draw-0011`, and `f16-draw-0031`. All accepted specs are retained.

## Rule pressure

Every required mutation is caught on a hidden day. The retained JSON names every failed test/day and execution error, with no missing-anchor skip. Representative category coverage:

| Consequence / retained rule | Mutation | Hidden days caught | Evidence |
| --- | --- | --- | --- |
| Stop for intercooler maintenance | `intercooler_outage_ignored` | h2, h4 | Availability |
| Stop for jacket-water exchanger maintenance | `ht_source_outage_ignored` | h2 | Availability |
| Stop for primary LT PHE maintenance | `lt_radiator_outage_ignored` | h1 | Availability |
| Prefix shortcut loses LT dependency / over-stops exhaust | `parts_by_name_prefix` | h1, h2 | h1 availability; h2 infeasible |
| Keep running with less recovered exhaust heat | `exhaust_outage_stops_engine` | h2 | No feasible plan |
| Exhaust unavailable during exchanger maintenance | `exhaust_outage_ignored` | h2 | Heat balance |
| Share remaining radiator capacity | `lt_capacity_ignored`, `lt_capacity_ignores_outages` | h2, h3 | LT heat rejection |
| Radiator maintenance must not directly stop engines | `lt_radiator_outage_stops_engines` | h2, h3, h4 | No feasible plan |
| Free modulating exhaust bypass | `diverter_ignored` | h1, h3, h4 | Least cost |
| Common condenser header / absorber temperature floor | `header_not_shared`, `absorber_cooling_water_ignored` | h1, h3, h4 | Electricity balance |
| PHE1 outage | `phe1_outage_ignored` | h4 | Heat balance |
| Electric-chiller condenser outage | `condenser_outage_ignored` | h1 | Availability |
| Absorber generator outage | `ac_generator_outage_ignored` | h3 | Availability |
| Absorber/condenser dependencies | `absorption_chiller_parts_ignored` | h3 | Availability |
| Tower-cell outage | `tower_cell_outage_ignored` | h1 | Cooling towers |
| PV outage | `pv_outage_ignored` | h4 | Electricity balance |

The original `lt_radiator_outage_ignored` name is retained from S; its patch omits the primary LT outlets, which are PHEs in this topology. The new radiator-capacity mutations separately exercise secondary radiator availability. No hidden input was changed to strengthen `diverter_ignored`.

## Trait evaluator and historical apps

`build/eval_traits.py <app> [--output <json>]` runs every test once per version (including the evaluator's normal two planner executions per day), prints JSON and a readable summary, and exits 0 only if all versions pass. Each version gets an isolated copy of D's tests; only h1–h4 statuses change and the reference bound is recalculated by pytest. Versions:

- `D`: unchanged candidate inputs.
- `no_stop_parts`: remove engine intercooler/jacket, electric condenser, absorption generator/absorber-condenser and primary LT PHE outages; keep exhaust and radiator outages.
- `no_new_parts`: remove exhaust-exchanger and radiator outages; retain stopping components.
- `units_only`: remove every outage whose name contains a space.

The standard answer passes **all four versions**, with no failed tests or execution errors; see `build/traits_solution.json` and its readable log. A16 and A19 fail **all five days in all four versions**, with the same parser/schema failure independent of outage ablation:

- **A16:** `ValueError: GE1 jacket water and exhaust must feed exactly one heat circuit`. Its fixed old heat-stream mapping expects the combined HT source endpoint, which D has split.
- **A19:** `KeyError: 'ht_heat_kw'`. It reads the former combined heat field before producing any plan.

On each affected day every test group fails because no accepted plan exists: `test_plan_covers_the_day`, `test_units_within_ratings_and_availability`, `test_electricity_balance`, `test_heat_balance`, `test_cooling_balance`, `test_cooling_towers`, `test_connection_limits`, `test_reported_gas_and_cost`, `test_reported_import_export_and_grid_flags`, `test_least_cost`, `test_lt_heat_rejection`, and `test_same_plan_every_time`. `traits_a16.json` and `traits_a19.json` enumerate every test/day and first/rerun execution error. These are compatibility failures, not measured physical-rule violations in produced historical plans; the ablations cannot diagnose their maintenance semantics because parsing fails first.

## Verification boundary

Harbor, Docker and blind surrogate trials were not run. No formal task, shared tool, archive, script, staging file, historical app or pre-existing candidate/result was changed. No commit, push, branch change, global install, network-facility inspection or user-file deletion was performed. The only repository writes belong to the new `results/checks-v22/candidates/d/` tree. Final scope audit passes: `git status --porcelain` contains only `?? results/checks-v22/`, the tracked diff is empty and the branch remains `v22-prechecks`. The candidate has no `__pycache__` or empty temporary directories. All executable acceptance gates and the four-version standard-answer check pass; see `build/final_audit.json`. `build/task_sha256.json` records all 51 runnable-package file hashes. The outstanding execution boundary is the explicitly excluded Harbor/Docker/blind-surrogate run; historical-app failure analysis is limited by their parser errors.
