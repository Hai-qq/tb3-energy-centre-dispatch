# Independent validation record

All tests use the plant and supply copied from the visible task package. Only the new fixtures' date, status, demand and weather are generated. Neither checker imports `planner`, so its equations, interpolation and billing do not silently reuse the application implementation.

## Main results

The final complete run is recorded in `experiments/check-results.json` and `experiments/check-run.log`.

| Measurement | Result |
|---|---:|
| Complete-day cases | 45 |
| Feasible days audited successfully | 39 |
| Deliberately infeasible days rejected | 6 |
| Independently constructed feasible-witness days | 12 |
| Feasible full-day MILP objective comparisons | 8 |
| Independent full-day infeasibility proofs | 2 |
| Diverse cases repeated in three fresh processes each | 6 |
| Primary CLI run-time range | 0.525–3.994 seconds |
| Largest heat-balance residual over feasible primary plans | 2.51e-12 kW |
| Largest electrical-balance residual after independent water-temperature inversion | 5.97e-13 kW |
| Largest period bill reconstruction difference | 5.69e-14 GBP |
| Largest period billed-gas reconstruction difference | 4.55e-13 kWh |
| Intentionally corrupted plans correctly rejected | 11 |

The CLI runs use a hard external 120-second process timeout. Timings include starting Python, loading the input, optimizing and writing JSON. The times above are for the 45 primary invocations; the byte-repeat invocations are also protected by that timeout.

## Visible-day plan

The final result is `experiments/visible/plan.json`.

| Quantity | Repaired plan |
|---|---:|
| Plan date | 2026-07-21 |
| Cost | GBP 5959.003279124662 |
| Billed gas | 58661.825839485 kWh |
| Grid import | 16783.762328461606 kWh |
| Grid export | 0 kWh |
| Engine starts | 2 |
| Grid limits satisfied | Yes |

GE2 starts at 00:00. GE1, although initially running, is stopped for the early part of the plan; it restarts at 11:00 after its outage. These starts cost GBP 27 and GBP 38 respectively and are included in the appropriate periods. The plan supplies all useful heat from engine HT heat, with surplus HT directed to the absorber within the actual circuit and tower limits. It does not credit LT radiator heat or assume an HT dump.

The independent whole-day MILP returned GBP 5959.003279124533, a difference of about GBP 1.29e-10, with a reported zero relative gap. Its plan also passed the independent physical checker. Both independently produced plans use the coldest permissible common condenser-water temperature on this date.

## Independent global-optimum comparisons

| Case | Absolute objective difference, GBP | Reported relative MIP gap | Added circle cuts |
|---|---:|---:|---:|
| `visible` | 1.29e-10 | 0 | 0 |
| `saturday_east_utc` | 0 | 0 | 0 |
| `tower_binding` | 0 | 1.73e-15 | 0 |
| `grid_positive_q` | 8.38e-10 | 0 | 14 |
| `grid_negative_q` | 0 | 0 | 28 |
| `warm_frontier` | 2.28e-13 | 3.23e-16 | 0 |
| `startup_continuity` | 0 | 0 | 0 |
| `witness_710` | 4.77e-10 | 0 | 5 |

The production solver enumerates continuous regions and uses a four-state dynamic program. The independent oracle instead creates one model over the whole day, selecting adjacent engine-table endpoints by explicit binary variables and modelling commitment transitions directly. It also uses binary import/export direction and, when needed, absorber water-temperature mode selection. The two implementations therefore do not share state selection, temporal optimization or engine performance parametrization code.

Each additional apparent-power cut contains the full true capacity circle. Once the final optimum satisfies the actual circle, the MILP's bound and gap provide a global certificate to the numerical precision shown. The visible oracle has 1200 variables, including 240 binary variables. The independently generated witness case requires nontrivial branching and connection refinement as well.

## Coverage of the generated days

**Dates and forecasts.** The fixtures cover Saturday local midnight falling on Friday in UTC, Monday local midnight falling on Sunday in UTC, a negative UTC offset, a +14:00 offset, winter temperatures, and shuffled demand and forecast rows. Adjacent UTC days carry deliberately different forecast values, so a positional or UTC-date join cannot pass by coincidence.

**Heat and engine performance.** Forced-boiler days confirm the more efficient boiler is loaded first and that boiler outages are honoured. Separate GE1 and GE2 cases force output at minimum, each intermediate table knot, interior points in both segments, and rated output. With boilers and absorption unavailable, the specified building heat fixes these engine powers exactly; both the powers and billed fuel are checked. Other cases remove the PHE or the LT radiators, or make both engines necessary throughout the day.

**Cooling.** Cases remove either or both electric chillers, disable absorption, and restrict cooling to absorption in weather whose minimum tower leaving temperature is below the absorber's inlet requirement. A hot single-cell day binds the actual cooling-tower rejection capacity, including compressor work and generator heat. Temperature tables are exercised below and above their wet-bulb ranges and above their final COP knots.

**Warm-water control.** The `warm_frontier` case has GE2, AC1 and EC2 unavailable, GE1 initially running, 760 kW building heat, 100 kW cooling and 300 kW active site demand. GE1's 600 kWe minimum gives exactly the 835 kW HT requirement. To respect the 250 kW export ceiling, EC1 needs 18 kW input, which is attainable at approximately 26.19753 °C common water temperature. This tests actual variable-speed tower control and the exact compressor-power interval, rather than assuming that colder water is mandatory under every operating constraint. The independent MILP confirms its least cost.

**Connection and billing.** Positive- and negative-reactive cases bind the curved apparent-power limit. A reactive-heavy exporting case requires generator compensation. Exact corner cases cover zero real import at 1220 kvar and nonzero import exactly on the circle. A case 0.001 kW beyond an otherwise fixed import limit is rejected. Zero-cooling days with both tower cells unavailable remain feasible. Separate low-tariff cases establish that the tool never buys and sells simultaneously. PV fixtures require inverter clipping, curtailment at the export ceiling and outage handling.

**Starts and availability.** The positive-reactive day is run once with GE2 initially off and once initially on; the same necessary running pattern differs by exactly one start and GBP 27. In `startup_continuity`, alternating short operating-cost preferences do not induce repeated starts: the initially running engine stays running and the daily start total is zero. Quarter-hour outage endpoints are applied to every intersecting whole half-hour, and a wrapping 23:15–00:45 outage covers both ends of the day.

**Infeasibility.** The six rejected cases lack an HT sink, exceed available cooling output, lose all tower capacity, exceed available boiler heat, exceed achievable reactive compensation, or sit just above a fixed connection boundary. The independent MILP also proves the HT-sink and reactive-capacity cases infeasible.

**Generated witnesses.** Seeds 710–721 construct a feasible dispatch before constructing demand. The witnesses vary engine commitments and loads, boilers, both electric chillers, absorption, fan temperature, signed residual reactive power, grid direction, PV and outages. They satisfy every limit by construction and then pass the independent auditor. The production tool beats each witness's cost; the improvements range from approximately GBP 1583 to GBP 2273. One witness day also receives a complete independent MILP optimum comparison.

## Determinism

The `visible`, `saturday_east_utc`, `grid_positive_q`, `warm_frontier`, `startup_continuity` and `witness_710` days each ran in three new Python processes with `PYTHONHASHSEED` set to 11, 37 and 211. Complete output bytes, not merely summary numbers, were identical. Their hashes are retained in the main result file.

## Checker sensitivity

`checks/check_auditor.py` deliberately changes valid plans in eleven ways. The auditor rejects understated gas, a missing start charge, unrouted HT surplus, simultaneous meter flows, engine operation during an outage, apparent-power overload, PV above its inverter limit, tower overload, an incorrect start total, endpoint-chord fuel at a middle engine knot and independent three-decimal rounding of tightly constrained outputs. Each rejection must include the relevant diagnostic, preventing a different incidental failure from making the test pass.

## Reproduction

From the delivery directory, using the Python interpreter that has NumPy and SciPy installed:

```bash
python3 app/dispatch.py --data app/data --output experiments/reproduced-plan.json
python3 checks/audit.py --data app/data --plan experiments/reproduced-plan.json
python3 checks/run_checks.py
python3 checks/check_auditor.py
```

For a separate global certificate on any fixture:

```bash
python3 checks/oracle.py \
  --data experiments/grid_positive_q/data \
  --report experiments/grid_positive_q/reproduced-oracle.json \
  --plan experiments/grid_positive_q/reproduced-oracle-plan.json
```

The executable runtime used for the recorded tests was `/workspace/scratch/e1216eed3f00/ecd-venv/bin/python`, with Python 3.13.16, NumPy 2.3.4 and SciPy 1.17.0. The exact runtime record and supplied-data integrity hashes are saved with the experiments. `FREEZE.json` identifies the final delivered bytes; reproducing tests later naturally creates or rewrites experiment outputs and should be done in a copied working directory if the frozen delivery must be retained unchanged.
