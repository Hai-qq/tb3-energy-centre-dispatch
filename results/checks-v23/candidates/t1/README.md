# Candidate T1 build record

Built from the unchanged v19 task at `5ae65f8cfb79209ce8a1c2959bc348d430fed23e` on `v23-prechecks`, using `rsync -a --exclude __pycache__`. The complete Harbor task is in `task/`; executable checks and retained evidence are in `build/`. Harbor, Docker and blind surrogate trials have not been run.

## Changes and rule

The supplied visible files come from the task owner's `scratchpad/v23-t1/visible/`. The candidate instruction and the five allowed environment files are byte-for-byte copies: `data/plant.json`, `data/demand.csv`, and `planner/{data,plant,optimize}.py`. Every other environment file, both Dockerfiles, `task.toml`, and `tests/test.sh` are unchanged. Before copying, all six v19 plant files (environment plus five verifier days) were byte-identical. All five verifier plants now match the supplied plant. `build/gate_a.json` records the allowlist, hashes, package inventory and exact instruction-sentence check.

The new `ahu_heat_kw` column is heat at the AHU heating coils, separate from building heat. Engine HT heat still feeds the absorption chiller and, through PHE1, LTHW; LTHW feeds the remaining AHU requirement through PHE2. Intercooler LT heat can feed the AHU circuit through its connected LT PHE. The supplied broken tool models this last transfer by energy balance alone, ignoring temperature; all its other existing bugs remain in place.

For each local half-hour, dry-bulb weather is aligned to its UTC timestamp exactly as wet bulb is. AHU flow and return temperatures are interpolated from the plant tables, flat outside their endpoints:

\[
T_f=\operatorname{interp}(T_{db};[(-3,55),(18,34)]),\qquad
T_r=\operatorname{interp}(T_{db};[(-3,45),(18,29)]).
\]

The source LT temperature is the intercooler circuit's `flow_c` (40 °C). LT heat uses every `lt_heat_kw` part-load point, linearly interpolated and flat beyond the endpoints, with zero heat when stopped. Recovery is limited by AHU demand and the sum of LT heat from running, available engines whose connected LT PHE is available. Two temperature limits represent the visible files' unresolved exchanger approach and hydraulic arrangement:

\[
R_{len,temp}=D_{AHU}\operatorname{clip}\!\left(\frac{T_{LT}-T_r}{T_f-T_r},0,1\right),\qquad
R_{strict,temp}=D_{AHU}\mathbf1[T_f\le T_{LT}-5].
\]

The former allows series preheating with zero approach; the latter assumes parallel heating with a 5 K approach. Actual `R_len` and `R_strict` also take the available LT-heat minimum. With `H = engine HT − AC heat input + boiler output`, grading requires

\[
D_{heat}+L+D_{AHU}-R_{len}\le H\le D_{heat}+L+D_{AHU}.
\]

Thus surplus HT heat cannot be dumped. The independent full-day MILP and standard answer use a recovery variable `R`, bounded by the **strict** temperature cap and by piecewise LT production, with `H + R = D_heat + L + D_AHU`. This conservative cost bound lets either interpretation pass. The copied task README's Verification explanation adds this convention to the existing wording.

The visible day's aligned dry bulb is 19.9–28.8 °C, so both temperature limits equal the AHU demand in every period. Its strict standard-answer cost is **£6,235.284** as reported, or £6,235.284129325 recomputed from rounded outputs. Replacing only the strict recovery rule with the shipped tool's energy-only recovery rule produces the **identical complete visible plan** and reported cost. This parity isolates recovery modelling; it does not claim that the otherwise broken environment tool is correct. See `build/visible_parity.json`.

Implementation: `task/tests/reference.py:Day.__init__` independently derives the AHU schedule and LT connections; `true_flows` records all 48 `T_f`, `T_r`, `lt_heat`, available LT heat, `R_len` and `R_strict` values; `least_cost` adds `R` and LT coefficients to the existing full-day segment MILP. `task/tests/test_plans.py:test_heat_balance` replaces only its former building-only equality with the two heat bounds; every other assertion and all 11 test groups are retained, with no new grading tests. In `task/solution/app/planner/plant.py`, LT ownership follows intercooler sources → circuit outlets → outlets also present in the AHU circuit's `from`; no new engine, PHE, radiator or circuit identifiers are hard-coded. `optimize.py` adds strict recovery to the existing per-segment LP; the whole-day start-cost dynamic programme is retained. An LT PHE outage removes recovery while leaving the radiator path available.

`build/model_checks.py` separately checks the 2 °C, 10 °C, 17 °C and 24 °C boundaries, flat extrapolation, LT part-load interpolation, stopped-engine heat and PHE-only recovery loss. It is a build check, not an added hidden verifier test.

## Hidden demand and radiator windows

For h1–h4 and every fresh draw, the deterministic demand formula, in kW, is

\[
D_{AHU}(t)=\operatorname{round}_{0.001}\{q_{reheat}(t)+\max[0,25(14-T_{db}(t))]\}.
\]

Here `q_reheat(t)` is exactly the supplied visible day's `ahu_heat_kw` at the same **local** half-hour (the operating-theatre reheat profile). There is no random term, retuning or change to electricity, reactive, building-heat or cooling demand. `build/ahu_days.py` implements the same formula for fresh days. The visible day is copied unchanged, rather than regenerated.

The inherited radiator-outage ⇒ engine-off rule is retained only where the entire AHU's lenient cap is smaller than that engine's LT heat at minimum output. This proves that even granting all available AHU recovery capacity to that engine cannot dispose of its LT heat. `Day.__init__` asserts this condition for **every** overlapping outage half-hour. Fixed-day certificates are in `build/rule_pressure.json`; fresh draws violating it are rejected before feasibility screening.

| Hidden day / date | Radiator | Original local window | Candidate local window | Maximum lenient AHU cap / minimum engine LT heat |
|---|---|---|---|---|
| h2 / 2026-01-14 | LT radiator 1 | 21:10–23:00 | unchanged | 0 / 118 kW |
| h3 / 2026-04-20 | LT radiator 2 | 10:40–14:20 | **03:40–04:50** | 81.653041 / 83 kW |
| h4 / 2026-07-29 | LT radiator 1 | 00:00–03:40 | unchanged | 65.8 / 118 kW |

The h3 change also **shortens** maintenance from 220 to 70 minutes. Under the chosen AHU formula, only starts 03:30, 04:00 and 04:30 meet the condition; there is no same-day safe window of the original duration. The new window touches exactly those three periods. The original afternoon maximum was 167.7 kW, which does not force GE2 off. This timing limitation is explicit in `build/hidden_adjustments.json`, `build/window_probe_initial.json` and `build/window_probe.json`. No other status entry changes. h1 and visible have no radiator outages. All 15 fixed-day overlapping radiator periods are certified.

## Commands and gates

Run from the repository root with the existing venv; no global dependency installation is required:

```sh
PY=/private/tmp/claude-501/-Users-haiy-qq-Desktop----klavis/a70e7eab-ed43-4fbc-8c31-1d0858956a32/scratchpad/codex-v18-verify/venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export ECD_TASK="$PWD/results/checks-v23/candidates/t1/task"
B="$PWD/results/checks-v23/candidates/t1/build"
"$PY" "$B/run_checks.py" verify_candidate
"$PY" "$B/run_checks.py" eval_solution
"$PY" "$B/run_checks.py" costs_pressure
"$PY" "$B/run_checks.py" model_checks
"$PY" "$B/candidate_mutants.py" --preflight > "$B/mutation_preflight.json"
"$PY" "$B/run_checks.py" mutants_1
"$PY" "$B/run_checks.py" mutants_2
"$PY" "$B/run_checks.py" traits
"$PY" "$B/run_checks.py" fresh
"$PY" "$B/run_checks.py" eval_a16
"$PY" "$B/run_checks.py" eval_a19
"$PY" "$B/run_checks.py" final_audit
```

`run_checks.py` retains exact argv, working directory, the required environment subset, exit status, duration and complete stdout/stderr. Each mutation group uses its own `TMPDIR` under the requested external scratch directory; they may run concurrently. The two original historical apps were each evaluated **once**, using the normal evaluator's two runs per day; do not rerun those commands merely to reproduce this report. Fresh output refuses an existing output directory: use a new `--output` path for another independent run. The shared tools remain unchanged; candidate-only adapters are in `build/`. `implement.py` is a build recipe for a **fresh** copy of v19, not an in-place updater.

- **A: PASS.** Exactly the five allowed environment files differ and match supplied bytes; the instruction differs only in the named demand sentence; original plant equality and complete task inventory are checked. The audit excludes pre-existing source `__pycache__` exactly as the copy does. No candidate cache is present.
- **B: PASS.** `ECD_TASK=<candidate task> python tools/eval_energy.py <candidate task>/solution/app` exits 0 with all five days passing all tests. The largest absolute solution true-flow versus MILP cost gap is **£0.000076113**. In the retained cost run, each solution day takes below 0.71 seconds and each reference MILP below 0.34 seconds, well within two minutes. Full plans and unrounded cost comparisons are in `build/plans/` and `build/costs.json`.
- **B fresh: PASS.** `build/fresh_days.py --days 16 --seed 2026` accepts 16 of 45 draws: four winter, four spring/autumn and eight summer days; all 16 pass every test. Demand includes `ahu_heat_kw`; radiator forcing is asserted before accepting each draw. Accepted days exercise both LT PHE names and both radiator names. See `build/fresh.log`, `build/fresh/manifest.json`, `build/fresh_coverage.json` and the fresh certificates in `build/rule_pressure.json`.
- **Traits: PASS.** `build/eval_traits.py <app>` runs every test, including a freshly recomputed MILP cost bound, on `T1`, `no_part_outages`, `no_t1` and `header_only`. Hidden status ablations remove every outage whose name contains a space; T1 ablations zero AHU demand exactly where the lenient temperature fraction is less than 1. The visible day stays unchanged. The standard answer passes all four versions; JSON and a readable summary are in `build/traits_solution.json` and `build/traits.log`.
- **E: EXECUTED.** A16 and A19 each exit 1 under one unchanged-app evaluation. Their distinct execution/topology versus physical/test failures are detailed below; neither was adapted or rerun.

## Mutation pressure and historical apps

The wrapper imports the existing **42** mutations from `tools/energy_mutants.py`, adds `t1_energy_bus`, `t1_never_recover`, and `t1_dry_bulb_utc`, and requires every patch anchor exactly once before execution. Only `heat_can_be_dumped` and `no_lthw_loss` need equivalent anchor overrides for the new AHU balance. The existing `lt_heat_counted` anchor is unchanged: its patch adds LT heat to the HT curve and therefore incorrectly counts intercooler heat in **LTHW**, in addition to the separate AHU recovery path. No mutation is skipped or silently replaced. `build/mutation_preflight.json` lists every checked anchor; exact failing tests/days are retained in `build/mutation_results_all.json` and the two group logs. The permitted dry-bulb-only UTC exception is reported explicitly if it survives.

**C: PASS with the permitted dry-bulb UTC exception.** Both mutation wrapper groups exit 0; **44/45 CAUGHT**, including all 42 original mutations, with **zero skipped patches**. All 51 sequential patch anchors are mandatory and preflighted exactly once. Both required T1 mutations are caught on hidden days:

| Mutation | Hidden failures |
|---|---|
| `t1_energy_bus` | `test_heat_balance`: h2, h3 |
| `t1_never_recover` | `test_least_cost`: h1, h4 |
| `t1_dry_bulb_utc` | **MISSED**: no hidden failure |

The engine-HT no-dump rule still fails `test_heat_balance` on h1, h3 and h4 when removed; ignoring PHE1 fails it on h4. The common cooling-water-header mutation still fails electricity balance on h1, h3 and h4. Radiator, intercooler and name-prefix shortcuts fail availability on h2/h4; HT-source maintenance fails on h2; electric-condenser maintenance fails on h1; absorption-generator and absorber/condenser shortcuts fail on h3. These are the original pressure mechanisms, not patch failures. The hanging mutation reaches the evaluator timeout on every invocation; the error-after-write mutation exits 77, so neither receives a plan merely because it wrote a JSON file.

A16 exits 1 before writing a plan on all five days: its recovery-topology parser treats an LT PHE outlet as a heat user, then rejects the resulting multiple recovered-heat circuits with `ValueError: the engines' recovered heat must feed one heat circuit`. All 11 test groups consequently fail on all five days because plans are missing. This is a topology compatibility failure, rather than a measured imbalance or a missing-column parser error.

A19 writes plans on all five days and exits 0 per planner invocation, but evaluation exits 1. Its demand loader ignores `ahu_heat_kw`; its engine eligibility rule accepts **any** available LT outlet, so the new LT PHE allows an engine to run despite its radiator outage without checking whether the AHU can take its heat. `test_heat_balance` fails on visible, h1, h2, h3 and h4; `test_least_cost` fails on visible, h1 and h4; `test_units_within_ratings_and_availability` fails on h2 and h4. Thus it is **not** a format/execution failure. The stated causes are supported by the original loader and `_half` implementation; no historical app was patched or rerun for diagnosis. Full original logs and parsed JSON are in `build/eval_a16.*` and `build/eval_a19.*`.

## Verification boundary

The source v19 task, shared tools, historical apps, existing results and fairness records were not edited. No Harbor or Docker run, git commit/push, branch/history change, global configuration/dependency change, network-settings inspection, or deletion of user files was performed. Generated rejected fresh draws and completed disposable mutation copies are removed by the local validation tools. Existing source caches are left untouched; the candidate has none. The result is a locally validated candidate package for Claude's subsequent Harbor and blind-surrogate runs, with the h3 maintenance-duration limitation explicitly retained. `build/final_audit.json` verifies all gate records, all 45 mutation entries, 15 fixed-day and 30 fresh-day radiator-period certificates, source syntax and unchanged branch/HEAD. `build/task_sha256.json` freezes every delivered task file. The final porcelain status lists only `?? results/checks-v23/`, with no tracked diff, candidate cache or empty directory.
