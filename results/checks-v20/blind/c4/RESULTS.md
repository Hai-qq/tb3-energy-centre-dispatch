# Validation results

## Final state

All **33 scenarios passed**: 29 feasible operating days and four deliberately impossible days. The suite invoked the actual command-line tool **66 times**. Both runs of every feasible day produced byte-identical JSON. Every feasible plan passed the separate physical/accounting checker and the independent full-day MILP lower-bound certificate.

| Measurement | Result |
|---|---:|
| Longest measured application invocation | 3.188411 s |
| Required maximum single-day runtime | 120 s |
| Largest positive plan-to-independent-lower-bound gap | £5.89225237491e-08 |
| Certificate monetary tolerance | £0.0002 |
| Largest electric balance residual | 7.95808e-13 kW |
| Largest heat balance residual | 2.95586e-12 kW |
| Largest cooling balance residual | 4.54747e-13 kW |
| Largest recomputed period-cost difference | £2.84217e-14 |
| Largest recomputed period-gas difference | 4.54747e-13 kWh |
| Largest numerical kVA-circle excess | 5.68775e-09 kVA |

The tiny positive circle residual is numerical roundoff within the solver's checked 0.0000002 kVA tolerance. Application runtime includes process startup and imports of NumPy/SciPy. Oracle runtime is separate from application runtime.

Environment: Python **3.13.16**, NumPy **2.3.4**, SciPy **1.17.0**.

## Supplied day's plan

The unchanged supplied day is **2026-07-21**. Its repaired optimum is:

| Field | Value |
|---|---:|
| Cost | £6303.560319427 |
| Billed gross-CV gas | 64944.185839485 kWh |
| Electricity imported | 13775.407766202 kWh |
| Electricity exported | 0.000000000 kWh |
| Engine starts, including midnight transitions | 2 |
| Connection valid in every half-hour | True |

GE2 runs from **00:00 to 11:00**; GE1 runs from **11:00 to 24:00**. GE1 is initially running before the day boundary, so changing to GE2 at 00:00 incurs GE2's £27 start. GE1's later return incurs its £38 start. The two starts and both charges are included in the period costs and daily totals. The specified GE1 outage from 07:00 to 11:00 and all-day B2 outage are respected.

The independently formulated full-day model returns the same optimum for this day. The standalone sample, verification and certificate are `experiments/visible_plan.json`, `experiments/visible_verification.json` and `experiments/visible_optimality.json`.

## Boundary coverage

Across the 29 feasible plans, the independent checker observed:

- 395 engine outputs strictly inside actual curve segments.
- 208 half-hours requiring the absorber's inlet minimum above the cold-day tower minimum.
- 48 half-hours with further common-water modulation required by the heat/export interaction.
- 34 binding circular connection limits, including leading reactive power.
- 137 binding PHE hydraulic limits.
- 114 binding tower rejection limits.
- 49 half-hours with some available PV curtailed.

The short-demand-dip scenario correctly keeps the initially running engine online and records **zero new starts**. The longer dip shuts the engine down and records **one subsequent start**. Both outcomes are certified against the complete-day mixed-integer formulation.

## Scenario results

| Scenario | Result | Slowest CLI run, s | Independent bound gap, GBP | Starts |
|---|---|---:|---:|---:|
| `visible` | Pass | 1.508 | 0 | 2 |
| `monday_local_previous_utc_sunday` | Pass | 1.320 | 0 | 2 |
| `saturday_local_previous_utc_friday` | Pass | 1.467 | 0 | 2 |
| `offset_plus_14_shuffled` | Pass | 1.396 | 0 | 2 |
| `offset_minus_7_shuffled` | Pass | 1.385 | 0 | 2 |
| `offset_plus_5_30` | Pass | 1.413 | 0 | 2 |
| `cold_absorption` | Pass | 2.171 | 9.09e-13 | 1 |
| `cold_absorber_outage` | Pass | 1.347 | 0 | 1 |
| `every_plant_outage_category` | Pass | 1.500 | 9.09e-13 | 2 |
| `partial_and_midnight_outages` | Pass | 1.377 | 0 | 2 |
| `very_hot_flat_table_ends` | Pass | 1.606 | 9.09e-13 | 2 |
| `tower_capacity_boundary` | Pass | 1.491 | 1.82e-12 | 1 |
| `phe_flow_boundary` | Pass | 2.100 | 3.64e-12 | 2 |
| `high_heat_and_boiler_merit` | Pass | 1.839 | 1.82e-12 | 2 |
| `reactive_demand_above_connection_rating` | Pass | 1.427 | 1.82e-12 | 2 |
| `leading_reactive_circle_boundary` | Pass | 2.486 | 5.89e-08 | 2 |
| `no_ht_dump_low_heat` | Pass | 1.606 | 1.82e-12 | 1 |
| `no_towers_no_cooling` | Pass | 1.935 | 9.09e-13 | 1 |
| `pv_export_curtailment` | Pass | 0.943 | 1.14e-13 | 0 |
| `pv_ac_rating` | Pass | 1.549 | 9.09e-13 | 1 |
| `heat_led_cooling_water_modulation` | Pass | 1.103 | 0 | 1 |
| `short_dip_keep_running` | Pass | 1.004 | 1.82e-12 | 0 |
| `long_dip_restart` | Pass | 0.918 | 0 | 1 |
| `random_feasible_0` | Pass | 3.188 | 9.09e-13 | 8 |
| `random_feasible_1` | Pass | 1.859 | 9.09e-13 | 6 |
| `random_feasible_2` | Pass | 2.017 | 9.09e-13 | 4 |
| `random_feasible_3` | Pass | 2.359 | 4.55e-12 | 6 |
| `random_feasible_4` | Pass | 1.825 | 9.09e-13 | 6 |
| `random_feasible_5` | Pass | 2.966 | 9.09e-13 | 7 |
| `infeasible_reactive` | Correctly rejected | 0.583 | — | — |
| `infeasible_towers` | Correctly rejected | 1.236 | — | — |
| `infeasible_missing_ht_sink` | Correctly rejected | 0.592 | — | — |
| `infeasible_electricity` | Correctly rejected | 0.935 | — | — |

## Integrity and revision evidence

`experiments/data_integrity.json` verifies that every supplied application data file is byte-for-byte unchanged from the permitted visible task package. No other repository files, history, candidate solutions, tests, research or external feedback were accessed.

`experiments/revisions/` retains the first visible-day output and its independent checks, a clearly labelled summary of the first 32-case suite, the engineering counterexample that motivated the final common-water-control revision, and the complete original-visible-to-repaired source diff. The earlier aggregate suite JSON was replaced by the test runner, so its retained summary is explicitly identified as a summary transcribed from its actual tool output rather than an original archived aggregate. No unexpected application test failure was observed; the four impossible-day rejections are intentional tested outcomes.

The final complete deliverable is covered by `FREEZE.json`. No application or checker code is edited, and no further self-tests are run, after freezing.
