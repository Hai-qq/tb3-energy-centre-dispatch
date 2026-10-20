# Development and retained evidence

This document records the isolated implementation and its self-directed checks before the final freeze. No repository material outside the supplied `visible/instruction.md` and `visible/app/` was read. No external evaluation results, hints, or task clarification were received. No child agents were used. All generated material was written within this delivery directory.

## Revision history

The stages below are contemporaneous observations from this working session. Intermediate source versions and full intermediate report files were not separately archived. This record preserves the observed results and reasons for revision; it does not represent those missing intermediate files as archived evidence. The final source, generated inputs, plans, audit reports, and independent comparison results are retained.

### 1. Complete initial physical model and independent audit

Replaced the original dispatch calculation with exact adjacent engine-table segments, closed high-temperature heat routing, low-temperature radiator availability, gross-CV gas accounting, a shared gas-entry constraint, net apparent-power grid limits, individual cooling equipment and tower constraints, and full-day startup optimization. Added input validation, UTC-to-local weather joining, tariff selection, and independent output auditing.

The first complete self-generated suite passed 26 scenarios, including expected infeasibility results, with 3 byte-identical repeat runs. Its slowest measured single-day dispatch took 2.1747870899998816 seconds. The visible day cost was GBP 6303.560319427. The random witness with seed 891 cost GBP 6088.762304441 and had 5 starts.

An independent whole-day mixed-integer formulation initially checked the visible, gas-binding, startup-bridge, and midnight-start examples. Their independently certified costs agreed with the dispatch output.

### 2. General common condenser-water temperature control

Manual review of variable-speed cooling-tower operation found that always choosing the lowest feasible common water temperature can be suboptimal under an export limit. A slightly warmer common condenser-water temperature can consume excess electrical generation while retaining useful engine heat, avoiding a shutdown or extra startup. This condition is not limited to the supplied date.

The implementation was revised to optimize total electric-chiller compressor power over the exact interval reachable by a single shared condenser-water temperature. The physical common temperature is reconstructed by monotone inversion for auditing. The earlier artificial tiny positive absorption-cooling bound was removed. New tests cover binding tower rejection, an unavailable electric chiller, and an export-limited warmer-water case.

The expanded suite passed 29 scenarios and 3 byte-identical repeat runs; maximum measured runtime was 2.481093600999884 seconds. The visible-day result was unchanged. On the same random-witness input with seed 891, cost improved from GBP 6088.762304441 to GBP 6067.249791517, an improvement of GBP 21.512512924, and starts fell from 5 to 4. This comparison is evidence of a material general-model revision, not an external evaluation result.

### 3. Low-temperature circuit outages and final delivery checks

Further manual review found that an outage naming a low-temperature circuit, as distinct from its radiator, must also disable the associated engine. Added that connection to engine availability and exercised it by adding a `ge1_lt` outage from 16:00 to 17:00 to the partial-and-overnight-outage case. Also made output publication atomic: an infeasible or invalid calculation cannot leave a partial output plan.

The modified outage scenario costs GBP 3427.554207333 with 5 starts. Its earlier version, without the additional low-temperature-circuit outage, cost GBP 3306.115502681 with 3 starts. These are different input cases and are not a before/after cost comparison on unchanged data.

The final suite passed all 29 scenarios: 25 feasible plans passed the independent physical and invoice auditor, and 4 deliberately infeasible days produced a clear failure and no output file. Five selected days were rerun under a different `PYTHONHASHSEED`; their JSON output was byte-identical. The slowest measured final single-day dispatch took 2.7034645730000193 seconds in the supplied Python 3.13.16 / NumPy 2.3.4 / SciPy 1.17.0 environment.

The final independent whole-day MILP comparison certified seven cases to zero MIP gap: visible, gas binding, tower binding, electric-chiller outage, startup bridge, midnight start, and warmer-water export. Its largest absolute cost difference from an independently audited output was GBP 4.4656189857050776e-10. A separate analytical grid-circle case verifies a binding 1220 kVA connection limit. These are independent checks on the listed cases, not a claim that every generated case was solved by a second whole-day optimization model.

## Failures, corrections, and limitations of the retained record

- No unexpected application failure or failed physical-audit assertion occurred in the completed self-generated suite runs. The four infeasible inputs are deliberate negative tests; their input data and observed diagnostic results remain in `experiments/cases/` and `experiments/checks-report.json`.
- Before the first suite run, manual review removed an invalid auditor assertion that every period must have a nonnegative invoice. Export receipts can make a period's net cost negative. This was a pre-run review correction, not an observed failed test execution.
- An initial source-writing `apply_patch` attempt failed with `invalid patch: multiple operations target .../app/planner/data.py` because the patch attempted to delete and add the same path. That tool failure made no file changes. The source files were then written within the authorized output tree.
- A later documentation-only `apply_patch` attempt failed to find an expected README line containing accidentally escaped backticks. It made no changes. The two intended wording corrections were subsequently applied: the original Dockerfile was retained but its image was not rebuilt, and the fewer-starts tie preference was described precisely as applying within each dynamic-program state.
- No external solver other than installed SciPy/HiGHS was installed or used. No Docker build was performed. Runtime measurements are observations on this environment, not hardware-independent timing guarantees.

## Retained final artifacts

- `app/`: runnable implementation and the unchanged supplied data files.
- `checks/check_plan.py`: independently written schema, physics, availability, meter, startup, and invoice auditor; it imports no application planner code.
- `checks/generate_cases.py` and `checks/run_checks.py`: reproducible scenario generation and the full independent suite.
- `checks/reference_milp.py`: separate full-day mixed-integer comparison model.
- `checks/explain_plan.py`: validated operating-detail reconstruction, including the common condenser-water temperature.
- `experiments/checks-report.json`: final scenario results, infeasibility diagnostics, timing, physical residuals, and determinism checks.
- `experiments/optimality-report.json`: seven independent optimization comparisons.
- `experiments/visible-audit.json`, `experiments/visible-plan.json`, and operating-detail JSON files: retained standalone results.
- `experiments/cases/` and `experiments/plans/`: generated inputs, final plans, and repeat-run plans.
- `README.md`: model, assumptions grounded in the visible data, CLI usage, verification, and limitations.

The `FREEZE.json` manifest is created only after this record and all delivered files are final. It hashes every delivered regular file except itself. Its separate SHA256 is reported in the final response. After publication of that manifest, the application and check code will not be modified and no further self-tests will be run.
