# Candidate K build record

Built from the unchanged v19 task at commit `dde5461fe5f931aab86d14a308c90a690ccd739b` on `v22-prechecks`, using `rsync -a --exclude __pycache__`. The complete candidate task lives in `task/`; all validation artifacts and local adapters live in `build/`. This is the requested five-rule stacking experiment, prepared for a later blind surrogate trial.

## Changes and rules

The five source packages are:

| Source | Package | Rule-specific test |
|---|---|---|
| W | `results/checks-v21/candidates/w/` | `test_single_connection_direction` |
| P | `results/checks-v21/candidates/p/` | `test_lt_pump_outages` |
| C2 | `results/checks-v20/candidates/c2/task/` | `test_shared_gas_entry` |
| C4 | `results/checks-v20/candidates/c4/task/` | `test_phe_primary_water_flow` |
| S | `results/checks-v22/candidates/s/` | `test_lt_heat_rejection` |

Source READMEs and full `diff -ru` comparisons were read before merging. C2 and C4 have no candidate-level README; their task READMEs and the shared `results/checks-v20/README.md` describe those packages. The five full diffs are retained in `build/source-diffs/`.

Visible data, repeated identically in all five `tests/days/*/` inputs:

- `supply.json` combines W's weekend 00:00–07:00 import price of **5.0 p/kWh** with C2's **550 Sm³/h**, **39.6 MJ/Sm³** common gas entry supplying GE1, GE2, B1 and B2.
- `plant.json` starts with S's exact LT PHE/rejection-circuit topology and two **220 kW** radiator ratings. P's `pump` is appended as the final key of `ge1_lt` and `ge2_lt`; C4's `heat_exchangers` list is appended after `pv`, in the same position and with the same contents as C4 (**20 kg/s**, **4.18 kJ/kg/K**, engine HT primary circuit).
- Each JSON is written with `json.dumps(..., indent=2)` and a final newline. The environment has no other byte differences from v19. `instruction.md`, `task.toml`, both Dockerfiles and `tests/test.sh` are unchanged.

Merge handling:

- All source edits to `tests/reference.py` and `solution/app/` were combined relative to v19. C2 and C4 contain an identical reference-model extension; it is retained once, including its inherited inactive feeder support. No feeder data or additional rule was introduced.
- All five sources append tests at the same end-of-file location. Their additions were concatenated in W, P, C2, C4, S order; all original tests and each source's added test are preserved verbatim.
- P's pump dependency and S's LT graph tracing both operate through `engine_lt_sinks`. The list contains primary PHE outlets plus the pump; S traces intersections with secondary-circuit sources, while both remain required availability dependencies. Both meanings are retained.
- W's direction enumeration, signed-net cost recomputation, MILP direction binary and `presolve=False` are retained together with C2's gas constraints, C4's PHE constraints and S's LT capacity constraints.
- No incompatible replacement conflict occurred. Exact source-relative edit locations are recorded in `build/merge_record.json`; `build/implement.py` reproduces the merge, including the relocated PHE outage, on a fresh rsync copy.

Hidden statuses retain all original outages. P adds `LT pump 1` on h1 **18:10–19:20** and `LT pump 2` on h3 **17:10–17:20**. S's `LT PHE 1` outage is relocated within h1 to **20:10–21:20**, preserving its duration and avoiding every other GE1 dependency outage. Before adding it, K's standard answer runs GE1 at **1200 kWe** at 20:00, 20:30 and 21:00; afterwards GE1 is zero in all three periods. The before-plan and comparison are retained in `build/h1-before-phe.json` and `build/phe_outage_pressure.json`. Radiator outage windows on h2–h4 are unchanged.

Each rule retains independent hidden-day pressure in the combined task:

| Rule | Rule-omitting mutation | Hidden days | Dedicated test that catches it |
|---|---|---|---|
| W | `grid_direction_ignored` | h1 | `test_single_connection_direction` |
| P | `lt_pump_outage_ignored` | h1, h3 | `test_lt_pump_outages` |
| C2 | `shared_gas_limit_ignored` | h2 | `test_shared_gas_entry` |
| C4 | `phe_flow_limit_ignored` | h2 | `test_phe_primary_water_flow` |
| S | `lt_capacity_ignored` | h2, h3 | `test_lt_heat_rejection` |

W also fails reported cost on h1; P also fails availability on h1 and h3. `build/rule_pressure.json` records all nine new mutations, their failing tests/days and execution errors. The over-stopping mutation can be caught by an infeasible plan; no finite cost premium is claimed or required by K's task brief.

## Commands and gates

Run from the repository root with the supplied existing venv:

```sh
PY=/private/tmp/claude-501/-Users-haiy-qq-Desktop----klavis/a70e7eab-ed43-4fbc-8c31-1d0858956a32/scratchpad/codex-v18-verify/venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export ECD_TASK="$PWD/results/checks-v22/candidates/k/task"
B="$PWD/results/checks-v22/candidates/k/build"
"$PY" "$B/run_checks.py" pressure
"$PY" "$B/run_checks.py" verify_candidate
"$PY" "$B/run_checks.py" eval_solution
"$PY" "$B/candidate_mutants.py" --preflight > "$B/mutation_preflight.json"
"$PY" "$B/run_checks.py" mutants_1
"$PY" "$B/run_checks.py" mutants_2
"$PY" "$B/run_checks.py" fresh
"$PY" "$B/run_checks.py" eval_a16
"$PY" "$B/run_checks.py" eval_a19
"$PY" "$B/run_checks.py" rules_solution
"$PY" "$B/run_checks.py" rules_a16
"$PY" "$B/run_checks.py" rules_a19
"$PY" "$B/run_checks.py" final_audit
```

The mutation groups may run concurrently; each has its own `TMPDIR`. Their disjoint union is checked against all 51 definitions. `candidate_mutants.py` without names runs the complete suite and exits nonzero if any mutation survives. Every patch is preflighted sequentially against its current file, requiring exactly one anchor occurrence. **No original or new patch needed rewriting; there are no skips or fallbacks.** The original `lt_radiator_outage_ignored` identifier still omits the LT dependency list, which now contains PHEs and pumps; its identifier is retained, as in the source S package.

`run_checks.py` records exact argv, `ECD_TASK`, exit status, elapsed seconds and full logs in `build/*.result.json` and `build/*.log`. Historical-app evaluations are expected to exit 1. Fresh and rule-evaluation output directories require a new pathname on repeat runs; do not overwrite retained evidence. For example, rerun fresh directly with `--output NEW_OUTPUT`, or `eval_rules.py APP --output NEW_OUTPUT`.

- **A: PASS.** `verify_candidate.py` checks exact JSON composition/order/formatting, every changed pathname, all hidden statuses and preservation of each source's added tests. Only `environment/data/plant.json` and `environment/data/supply.json` differ in the environment. See `build/gate_a.json`.
- **B: PASS.** `tools/eval_energy.py task/solution/app` exits 0, all 16 test groups pass on all five days. Each independent `least_cost()` versus `true_flows(solution)` gap is below GBP 0.001; maximum absolute gap **GBP 0.000189064**. The retained fixed-day solution times are below **1.2 seconds** and MILP times below **0.9 seconds**, each well below 120 seconds. See `build/eval_solution.log`, `build/costs.json` and `build/plans/`.
- **B fresh: PASS.** Seed 2026, **16/16 accepted days pass**, **39 draws**, 23 rejected for the generator's existing input/reference-feasibility criteria, and **3 weekends**. All accepted plant/supply files are byte-identical to K. Accepted days include pump, LT PHE and radiator outages. See `build/fresh/manifest.json`, `build/fresh.log` and `build/fresh_coverage.json`.
- **C: PASS.** Both wrapper groups exit 0: **51/51 CAUGHT** (42 existing plus W 1, P 1, C2 2, C4 2, S 3), no skipped patches. All 58 patch anchors match exactly once. See `build/mutation_preflight.json`, `build/mutants_1.log`, `build/mutants_2.log`, `build/mutants_all.json` and `build/final_audit.json`.
- **E: EXECUTED.** Original A16 and A19 each ran `tools/eval_energy.py` once, with its normal two executions per day. Both exit 1. See `build/eval_a16.log` and `build/eval_a19.log`; exact failures are described below.
- **Rule evaluator: PASS on the standard answer.** Both original K and the copy without old component outages pass every rule and every other test. Standard-answer, A16 and A19 examples are retained under `build/rules_solution/`, `build/rules_a16/` and `build/rules_a19/`, each with `result.json`, `summary.txt` and its control task copy.

The local `build/fresh_days.py` changes only the repository ROOT, graph-derived primary LT PHE/pump outage sampling names, and known-name recognition for circuit pumps. Existing radiator sampling remains unchanged. The draw algorithm, seed, feasibility rejection and tests are unchanged; `build/fresh_days.patch` records the full adaptation. No shared tool was edited and no accepted draw was replaced to tune results. Accepted pump outages are on f3, f10, f12 and f16; LT PHE outages are on f1, f10, f12 and f16; radiator outages are on f2, f10, f11, f13, f15 and f16. Full unique draw names and windows are in the coverage JSON. LT pump 1 is not sampled in an accepted random day; it remains covered by fixed h1.

## Per-rule evaluation tool

```sh
"$PY" "$B/eval_rules.py" /absolute/path/to/app --output /new/output/folder
```

The tool runs the entire canonical test suite on K, then on a full task copy whose h1–h4 statuses omit only outages with a space in the name that do not match `LT pump N`, `LT PHE N` or `LT radiator N`. Unit outages, PHE1, cooling-tower, PV and all new LT outages remain. The visible day remains unchanged. Each invocation of pytest imports that variant's reference and independently recomputes its own cost benchmark. JSON includes every test's per-day pass flags, five dedicated rule summaries, failed tests, run errors, and the exact removed outages. JSON and a readable summary are both saved and printed. Exit 0 means both variants pass all tests; exit 1 means at least one variant fails.

A16: all five days fail all 16 test groups because the parser raises `ValueError: the engines' recovered heat must feed one heat circuit`; it does not produce plans under S's topology. Removing old component outages does not resolve this topology incompatibility.

A19: visible passes all tests. h1–h4 fail all 16 test groups with no plan: h1 rejects `LT pump 1`, h2/h4 reject `LT radiator 1`, and h3 rejects `LT radiator 2` as absent from plant.json. The same failures occur without old component outages, because the new LT outages remain. These are parser/outage-name compatibility failures, not measured physical violations or evidence that any specific optimization rule was omitted.

The 16 test groups are `test_plan_covers_the_day`, `test_same_plan_every_time`, `test_units_within_ratings_and_availability`, `test_electricity_balance`, `test_heat_balance`, `test_cooling_balance`, `test_cooling_towers`, `test_connection_limits`, `test_reported_gas_and_cost`, `test_reported_import_export_and_grid_flags`, `test_least_cost`, `test_single_connection_direction`, `test_lt_pump_outages`, `test_shared_gas_entry`, `test_phe_primary_water_flow` and `test_lt_heat_rejection`.

## Verification boundary

Harbor, Docker and blind surrogate trials were not run. No commit/push, branch change, global dependency installation, network-setting inspection or deletion of user files was performed. Writes are confined to the new K directory. Formal v19, shared tools, historical applications and existing candidate packages were not edited. Final audit passes: `git status --porcelain` lists only `?? results/checks-v22/`; tracked diff is empty, the branch remains `v22-prechecks`, and K contains no `__pycache__`. Exact scope checks and task SHA-256 hashes are retained in `build/final_audit.json` and `build/task_sha256.json`.
