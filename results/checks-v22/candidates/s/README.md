# Candidate S build record

Built from the unchanged v19 task at commit `dde5461fe5f931aab86d14a308c90a690ccd739b` on `v22-prechecks`, using `rsync -a --exclude __pycache__`. The candidate task lives in `task/`; validation artifacts live in `build/`.

The package and executable gates are built and checked below. One requested pressure condition cannot be demonstrated within the allowed data edits: stopping both engines makes every half-hour of h2, h3 and h4 infeasible, rather than merely more expensive. No finite cost premium is claimed. The optional optimum with both engines running under reduced capacity was not observed. These limitations are recorded in `build/rule_pressure.json`.

## Changes and rule

`environment/data/plant.json` and all five `tests/days/*/plant.json` are byte-for-byte copies of the supplied S visible plant. All six original v19 plant files were byte-identical before copying. The supplied file changes only three logical items:

- Each engine's primary LT circuit ends at its own `LT PHE 1` or `LT PHE 2`.
- A secondary `lt_heat_rejection` circuit at 37/32 degrees C receives these PHE outlets and feeds both radiators.
- `lt_radiators` specifies `max_kw: 220` for each radiator.

For every half-hour, the LT heat entering a rejection circuit must not exceed the sum of its in-service radiator ratings. Engine LT heat is linearly interpolated from `part_load.lt_heat_kw`, flat beyond the curve endpoints, and zero when stopped. Any overlap with a radiator outage removes its full rating for that half-hour. A radiator outage does not directly stop an engine. Its primary LT outlet PHE remains a required component, so an overlapping PHE outage stops that engine for the whole half-hour.

Ownership is derived from the graph: engine intercooler source, primary circuit outlets, secondary circuit sources, secondary outlets, radiator ratings. The new reference and solution code hard-code no engine, PHE, radiator or circuit identifiers. The reference derives sources and available capacities in `tests/reference.py:Day.__init__`, recomputes LT heat/capacity in `true_flows`, and uses the existing engine segment variables in the full-day `least_cost` MILP. `tests/test_plans.py` only appends `test_lt_heat_rejection`, with 0.5 kW tolerance; every original test remains byte-for-byte unchanged. The solution derives circuit ownership in `planner/plant.py` and adds segment-specific linear capacity inequalities to `planner/optimize.py`.

All existing mutation anchors remain unchanged; no original mutation definition requires an override. The old `lt_radiator_outage_ignored` identifier is retained: its existing patch omits direct primary LT outlets, which are now PHEs. The new h1 PHE outage preserves pressure for that patch and `parts_by_name_prefix`.

Hidden changes (local time; all pre-existing outages retained):

- h1, **2026-08-08**: add `LT PHE 1`, **18:10–19:20**. GE1 must stop during 18:00–18:30, 18:30–19:00 and 19:00–19:30. Before this added outage the candidate solution runs GE1 at 1200 kWe in all three periods. None overlaps GE1's existing 11:20–17:00 outage. See `build/phe_outage_pressure.json` and `build/initial-plans/h1.solution.json`.
- h2, **2026-01-14**: `LT radiator 1` **21:10–23:00**, unchanged; reduced capacity applies to 21:00, 21:30, 22:00 and 22:30 starts.
- h3, **2026-04-20**: `LT radiator 2` **10:40–14:20**, unchanged; reduced capacity applies to starts from 10:30 through 14:00 inclusive.
- h4, **2026-07-29**: `LT radiator 1` **00:00–03:40**, unchanged; reduced capacity applies to starts from 00:00 through 03:30 inclusive.

Pressure on the new capacity rule is already present without changing radiator windows. Ignoring capacity produces 294.262 kW against 220 kW at h2 21:00, and up to 303.307 kW against 220 kW at h3 14:00. It violates the limit in four h2 periods and seven h3 periods. Corresponding candidate solution outputs are 201 kW. Capacity-ignored costs are lower by approximately GBP 137.534 on h2 and GBP 158.293 on h3, but those plans are infeasible under the new rule and are not valid savings. `build/rule_pressure.json` retains the solution heat, capacity and ignored heat for every half-hour of all five days.

The radiator-outage-stops-engines mutation has no feasible plan on h2, h3 or h4. `build/window_scan.json` checks all 48 half-hours of each of these days, using the actual period LP, and also records an independent optimistic lower bound: with both engines stopped there is no HT input to AC, so all cooling must be electric. Even using the best available COP without ratings/outages, full forecast PV and no auxiliary load, minimum full-day all-off apparent powers are 1318.314, 1258.080 and 1364.770 kVA, respectively, all above the 1220 kVA connection rating. Thus no adjustment confined to the same day's radiator outage window can produce a feasible all-off comparator with a finite premium. Changing demand, tariff, equipment or the selected day was not authorized and was not done. This is a limitation of the requested finite-cost pressure condition, not a failure of the solution to solve the candidate.

## Commands and gates

Run from the repository root with the existing venv:

```sh
PY=/private/tmp/claude-501/-Users-haiy-qq-Desktop----klavis/a70e7eab-ed43-4fbc-8c31-1d0858956a32/scratchpad/codex-v18-verify/venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export ECD_TASK="$PWD/results/checks-v22/candidates/s/task"
B="$PWD/results/checks-v22/candidates/s/build"
"$PY" "$B/run_checks.py" probe_pressure
"$PY" "$B/run_checks.py" scan_windows
"$PY" "$B/run_checks.py" verify_candidate
"$PY" "$B/run_checks.py" eval_solution
"$PY" "$B/candidate_mutants.py" --preflight > "$B/mutation_preflight.json"
"$PY" "$B/run_checks.py" mutants_1
"$PY" "$B/run_checks.py" mutants_2
"$PY" "$B/run_checks.py" fresh
"$PY" "$B/run_checks.py" eval_a16
"$PY" "$B/run_checks.py" eval_a19
"$PY" "$B/run_checks.py" final_audit
```

The two mutation groups may run concurrently; each has its own `TMPDIR`. `candidate_mutants.py` without arguments runs all 45 mutations and exits nonzero if any survives. Every patch anchor is mandatory and preflighted to occur exactly once; no skip or fallback exists. `run_checks.py` retains exact argv, `ECD_TASK`, exit code, elapsed seconds and full logs. Fresh output uses `exist_ok=False`; use a new output pathname for a repeat run rather than overwriting retained evidence. `implement.py` records source edits and is intended for a fresh copy of v19, not for rerunning against an already edited task.

- **A: PASS.** `verify_candidate.py` proves that the only environment byte difference is `data/plant.json`. Instruction, task.toml, both Dockerfiles and test.sh are unchanged. The exact changed-file allowlist, supplied plant hash, original plant equality and additive-only test change are checked. See `build/gate_a.json`.
- **B: PASS.** Standard-answer `tools/eval_energy.py` exits 0. All five independent MILP/solution true-flow cost gaps are below GBP 0.001; maximum absolute gap GBP 0.000266612. Solution and reference MILP per-day times are each below one second in the retained comparison, comfortably below 120 seconds. Visible-day complete plan JSON, all 48 periods and reported cost GBP 6303.560 match v19 exactly; maximum LT heat is 201 kW with at least 239 kW spare capacity. See `build/costs.json`, `build/visible_parity.json`, and `build/plans/`.
- **B fresh: PASS.** 0/16 accepted days fail, seed 2026, 33 draws, 5 weekends. All random-day plant files are byte-identical to candidate plant.json. See `build/fresh.log`, `build/fresh/manifest.json`, and `build/fresh_coverage.json`.
- **C: PASS.** Both mutation wrapper groups exit 0: **45/45 CAUGHT** (42 existing plus 3 new), zero skips. Preflight checks all 52 patch anchors exactly once. `lt_capacity_ignored` and `lt_capacity_ignores_outages` fail `test_lt_heat_rejection` on h2 and h3. `lt_radiator_outage_stops_engines` has no feasible plan on h2, h3 and h4. The retained original `lt_radiator_outage_ignored` and `parts_by_name_prefix` mutations fail availability on h1 because they omit the primary LT PHE dependency. See `build/mutation_preflight.json`, `build/mutants_1.log`, `build/mutants_2.log`, and `build/final_audit.json`.
- **E: EXECUTED; compatibility failures.** Original A16 and A19 were each evaluated exactly once, with the evaluator's normal two runs per day. See `build/eval_a16.log`, `build/eval_a19.log` and their result JSON files. No adaptation or rerun of either historical app was performed.

The local `build/fresh_days.py` differs from shared `tools/fresh_days.py` in only its repository ROOT for the new location and the addition of graph-derived primary LT outlets to the outage sampling list. Existing radiator sampling and endpoint-name validation already cover the new graph. The drawing algorithm, seed, feasibility rejection policy and tests are unchanged. The patch is retained in `build/fresh_days.patch`; shared tools were not modified.

Accepted fresh days contain radiator outages on f2-draw-0003 (`LT radiator 1`, 22:00–24:00), f5-draw-0015 (`LT radiator 2`, 18:30–24:00), and f9-draw-0021 (`LT radiator 1`, 08:00–09:50; `LT radiator 2`, 12:20–14:50). LT PHE 2 outages occur on f1-draw-0002 (15:40–18:30), f13-draw-0025 (14:50–18:00), and f16-draw-0033 (13:50–16:40). LT PHE 1 appeared in infeasible rejected draws and is covered by fixed h1; no accepted day was replaced to tune coverage or results. Rejected specs and reasons are retained in the manifest.

A16: exit 1 on all five days. Its dump classification recognizes radiator/dump names only. The new primary PHE outlets therefore cause intercooler heat to be classified as recovered heat, leading to `ValueError: the engines' recovered heat must feed one heat circuit` before any plan is written. This is a new-topology compatibility failure, not evidence of the anticipated radiator-outage over-stopping in a produced plan.

A19: exit 1 on h2, h3 and h4; visible and h1 pass. It collects known outage names from its modeled primary outlets and omits the secondary radiators, causing `ValueError: outage of LT radiator 1/2, which is not in plant.json`. No plan is written on those days. This is a new-topology/outage-name compatibility failure, not a measured capacity excess in a produced plan.

For each failed day above, all 12 test groups fail due to the missing plan: `test_connection_limits`, `test_cooling_balance`, `test_cooling_towers`, `test_electricity_balance`, `test_heat_balance`, `test_least_cost`, `test_lt_heat_rejection`, `test_plan_covers_the_day`, `test_reported_gas_and_cost`, `test_reported_import_export_and_grid_flags`, `test_same_plan_every_time`, and `test_units_within_ratings_and_availability`.

## Verification boundary

Harbor, Docker and blind surrogate trials were not run. The source v19 task, shared tools, historical apps and pre-existing results were not modified. No git commit/push, branch change, global dependency install, network-configuration inspection, or deletion of user files was performed. All writes are within the new candidate directory. No claim of a finite all-off premium, an observed two-engine derated optimum, or historical-app physical failure beyond the parser errors is made.

Final scope audit: `git status --porcelain` lists only `?? results/checks-v22/`; tracked-file diff is empty, the branch is unchanged, and the candidate contains no `__pycache__`. The three executable acceptance checks pass. Overall handoff remains **partial** solely because the requested finite all-off cost-premium pressure cannot be achieved using the permitted radiator-window edits. The frozen candidate was not redesigned to conceal that limitation.
