# Independent blind dispatch repair

## Scope and freeze

This implementation was developed from the visible instruction and the copied application only. No benchmark tests, reference implementation, earlier deliverables, parent benchmark results, task-specific online solution, or files from another task directory were read. The parent supplied only the implementation assignment, the location of the exact Python runtime, and resource-sharing settings. No benchmark feedback was received before this freeze.

All edits and generated files are inside `/workspace/scratch/3a594630faca/ecd-blind/`. The five application data files were not modified. The application changes are in `planner/data.py`, `planner/plant.py`, `planner/tariff.py`, and `planner/optimize.py`. The original command-line entry point, JSON keys, period order, summary schema, and three-decimal presentation are retained.

**Frozen runtime-code digest:** `89b4cbfad49a251e6a1d321cdae598264f6c6ff58beaf520015d0162a3e7d917`

The precise hash definition, individual source hashes, input-data hashes, instruction hash, validation-script hash, and runtime versions are recorded in `FROZEN_SHA256.json`. This digest covers the six runtime Python files, including the unchanged entry point and package initializer.

## Task source files read

The complete original task-source access list is:

- `instruction.md`
- `app/dispatch.py`
- `app/planner/__init__.py`
- `app/planner/data.py`
- `app/planner/plant.py`
- `app/planner/tariff.py`
- `app/planner/optimize.py`
- `app/data/plant.json`
- `app/data/supply.json`
- `app/data/status.json`
- `app/data/demand.csv`
- `app/data/weather.csv`
- `app/Dockerfile`

The copied app was inventoried with `rg --files`. Afterwards I read and ran my own modified sources, generated plans, validation script, and result files. General Python, NumPy, and SciPy runtime imports were used; no task-specific external documentation or network search was used.

## Physical model and interpretation

### Time and tariffs

Demand is sorted by its offset-bearing local timestamps and checked to contain exactly the 48 half-hours of the stated local plan date. Each weather row is joined to the corresponding demand row by its UTC instant. Selecting weather by the text of its UTC calendar date is incorrect for a local day with a nonzero offset.

The import tariff's weekday/weekend selection uses the local date's weekday. Half-hour bands use local clock time. Engine starts at the first half-hour are measured from `running_at_midnight`, including a charge when an initially stopped engine starts at 00:00.

Engine fuel is tabulated on net calorific value. Billed gross-CV fuel is therefore net-CV fuel multiplied by 1.108. Boiler efficiencies are already on gross CV, so boiler fuel is not converted again. All operating quantities are powers, converted to half-hour energies by multiplying by 0.5. Engine maintenance uses gross generator electrical output; engine auxiliary electricity remains a separate load.

### Engines and heat circuits

Each engine may be off, or operate continuously between its minimum and rated output. Fuel and HT recovery are evaluated on the actual adjacent pair of table points. In particular, the intermediate part-load point is preserved. Flat-end interpolation is also retained in the public performance functions, with the separate off state producing zero fuel and heat.

HT and LT recovery remain distinct. The engine HT circuit has only the absorber generator and PHE1 as its stated outlets. The LT circuits feed separate engine LT radiators. Thus:

- LT recovery is not credited against building heat.
- LT recovery does not drive absorption cooling.
- LT radiator heat does not consume cooling-tower capacity.
- There is no invented HT dump radiator, thermal store, or additional heat connection.
- Boiler heat cannot flow backwards from the 80°C building circuit to the absorber's 90°C engine-HT supply.

If (H_{e}) is total engine HT recovery, (A) is absorption cooling, (h) is the PHE transfer, and (B_1,B_2) are boiler heat outputs, the balances are:

```text
H_e = A / COP_abs + h,     h >= 0
h + B1 + B2 = building heat + 75 kW
```

The first equality prohibits unlisted HT disposal. The nonnegative exchanger flow prohibits boiler firing of the absorber. An outage of PHE1 removes that heat route. An outage of an engine's only LT radiator makes that engine unavailable.

No ramp limits, minimum run durations, or minimum stopped durations were added, because none are given. Cycling is discouraged through the actual start costs and whole-day optimization.

### Cooling and auxiliaries

The minimum common condenser-water temperature is the larger of wet bulb plus the tower approach and the tower minimum leaving-water temperature. Variable-speed fans permit a warmer setpoint when an absorber needs its 22°C minimum inlet temperature. Both electric chillers then use that common warmer condenser temperature.

The electric-chiller COP curves decrease with temperature. Consequently, the only undominated setpoints are the physical minimum and the absorber eligibility thresholds above it. There is no need to discretize a continuous temperature range: any higher temperature between such thresholds worsens electric COP without enabling additional plant or increasing the stated tower capacity.

Cooling demand is met exactly. Tower heat rejection includes electric-chiller cooling plus electrical input, and absorber cooling plus generator heat and its auxiliary electrical input. Per-cell tower capacity is interpolated from wet bulb, with unavailable cells removed.

The treatment of absorber auxiliary electricity as heat ultimately rejected by its absorber/condenser is an explicit energy-balance assumption. The data do not state a separate heat-rejection route for that auxiliary input. This choice adds `auxiliary_kwe_per_kw * absorption_kw` to the absorber tower duty.

Tower fans and the pumps already included in site active demand are not counted again. Engine and absorber auxiliary loads explicitly listed in the plant data are added separately.

### Electricity, PV, and reactive power

Electrical balance includes gross engine generation, usable PV, import, export, site demand, both electric chillers, and the explicitly listed auxiliaries.

The overexcited fixed-power-factor generators supply:

```text
generator kvar = generator kW * tan(acos(0.95))
grid kvar = forecast site kvar - sum(generator kvar)
```

The import limit is imposed on the actual residual reactive power:

```text
hypot(import kW, grid kvar) <= 1220 kVA
export kW <= 250 kW
```

Leading as well as lagging residual reactive exchange is handled. Generator apparent ratings are checked against their output and fixed power factor. The grid check uses the same relation as the optimization. The separately named apparent-import and active-export contractual limits are preserved; no extra apparent-export rating is invented.

Import and export are separate nonnegative variables. They cannot both be positive in a least-cost solution: reducing both equally preserves the electrical balance, relaxes the import constraint, and strictly lowers cost because every given import rate exceeds the export rate.

PV is limited by both the forecast and the 280 kW inverter rating, and is zero during an inverter/PV outage. The inverter is assumed to permit curtailment to enforce the export limit. With the given positive tariffs, available PV is otherwise used fully. Curtailment capability is an explicit operational assumption rather than a separately specified control field.

Every unit must be available throughout its half-hour because its output is held for the whole period. An outage that begins within a half-hour therefore removes that unit from that half-hour. Outages spanning midnight are supported.

## Optimization method and globality

For each half-hour, the solver considers every engine commitment. Within a commitment, it enumerates the actual adjacent part-load segments for each operating engine and all undominated condenser regimes. For two engines with two segments each, there are nine segment/off combinations in total, and at most two condenser regimes for the supplied plant.

For a fixed combination, all quantities and costs are affine except the apparent-import constraint, which is a convex disk in active import and residual reactive exchange. The subproblem is solved with supporting-plane linear programs:

1. Solve a linear relaxation using SciPy's HiGHS dual simplex.
2. If its optimum violates the exact apparent-import disk, add the disk's supporting tangent at that direction.
3. Repeat until the solution satisfies the disk within (10^{-7}) kVA.

Every tangent contains the entire physical disk. Hence every intermediate LP objective is a global lower bound, and a disk-feasible LP optimum certifies the continuous subproblem's global optimum to the stated numerical tolerances. This is adaptive convergence to the nonlinear boundary, not a fixed polygon, a discretization of engine loads, an endpoint blend, or a local nonlinear optimization heuristic. LP primal and dual tolerances are (10^{-9}).

The cheapest loading for each commitment then enters a dynamic program over the whole day. Its state is the engine on/off tuple; transition cost is exactly the cost of engines changing from off to on. This captures all stated inter-period coupling. Enumerating every segment/regime and then using the state recurrence gives the global whole-day optimum of this model, up to floating-point solver tolerance.

State, segment, and temperature enumeration orders are fixed. HiGHS is run with one thread and a fixed seed. Tiny numerical cost ties use a deterministic order, with fewer starts preferred for tied state paths. No stochastic optimization is used.

An infeasible day raises an explicit error. Failed or nonconverged optimization is not silently relabeled as physical infeasibility or accepted as a workable plan.

## Validation and results

### Commands and environment

The exact task environment was used:

- Python 3.13.16
- NumPy 2.3.4
- SciPy 1.17.0

The application itself uses only the Python standard library, NumPy, and SciPy. The independent validation script also needs no additional package.

The primary commands were:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /workspace/scratch/3a594630faca/ecd-venv/bin/python \
  /workspace/scratch/3a594630faca/ecd-blind/app/dispatch.py \
  --data /workspace/scratch/3a594630faca/ecd-blind/app/data \
  --output /workspace/scratch/3a594630faca/ecd-blind/plan.json

OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /workspace/scratch/3a594630faca/ecd-venv/bin/python \
  /workspace/scratch/3a594630faca/ecd-blind/self_checks.py
```

### Visible day

The least-cost plan found for the visible input has:

| Quantity | Unrounded result |
|---|---:|
| Total cost | £6,303.560319426553 |
| Billed gas | 64,944.185839485 kWh |
| Imported electricity | 13,775.408 kWh at displayed precision |
| Exported electricity | 0 kWh |
| Engine starts | 2 |
| Grid checks | All pass |

GE2 starts at midnight and operates through the GE1 outage. GE1 starts at 11:00 and supplies the remainder of the day. Its late-evening part-load outputs follow the intermediate table breakpoint and the available HT heat sinks.

The latest full-day optimization took **1.297 seconds**, made **390 LP calls**, and required at most **three conic refinements** in any subproblem. A previous timed run took 2.36 seconds under concurrent CPU sharing. These are well below two minutes.

Two independent CLI processes wrote byte-identical plans. Their SHA-256 was:

`e38c867d8aac236235635c2b1bd170e7b000714a46f69601bad43d234829c9a5`

### Independent checks

All **nine validation groups passed**, including **96 constructed feasible operating cases**. The complete results are in `SELF_CHECK_RESULTS.json`; the tests and their generated inputs are reproducible from `self_checks.py`.

The validator reconstructs electrical balance, HT allocation, building heat, chilled water, tower duty, rated limits, outages, gross-CV gas, generator reactive output, import/export limits, maintenance, starts, and costs directly from raw input dictionaries. It does not use the repaired plant-model functions to calculate expected balances or bills.

Key checks include:

- Weather matching across the UTC/local-date boundary; shuffled demand and weather rows; Saturday local midnight falling on Friday in UTC; Monday local midnight falling on Sunday in UTC.
- Exact table points and interpolation on both sides of the intermediate engine breakpoint; correct gross/net fuel conversion.
- A binding nonlinear reactive-capacity case with a separately calculated quadratic root. The analytic GE1 output is **799.5024149930226 kW**; the optimizer gives **799.5024149976533 kW**.
- Exhaustive enumeration of every commitment sequence over a three-period example. Keeping GE1 on through the middle half-hour costs **£4.740930679643007** more locally, but avoids its **£38** restart. The dynamic-program result agrees with the exhaustive optimum of **£323.8029799538462**. Changing the initial status to stopped adds exactly one first-period start and £38.
- Cold-weather operation both with and without absorption: the absorber causes a 22°C common loop and COP 6.5 for EC1, while the no-absorption case retains the colder 21°C loop and COP 6.725.
- Boiler, electric-chiller, cooling-tower-cell, PV, PHE1, and LT-radiator availability; outages beginning inside a half-hour and crossing midnight.
- Rejection of a case that would require an unlisted HT heat dump; rejection of boiler-driven absorption cooling; correct feasibility of engine LT rejection while both cooling towers are out.
- Inverter clipping, PV outage, curtailment, and the active export limit.
- Ninety-six seeded feasible plant points with varied engine segments, cooling splits, tower availability, temperatures, and leading/lagging reactive exchange. Each optimized output is independently feasible and no more expensive than its known feasible operating point.

For those 96 cases, the worst single-period optimization took **0.336 seconds**, the largest solve used **63 LP calls**, and the largest subproblem needed **16 conic refinements**. The complete validation script, including repeated full-day CLI runs, finished in **14.586 seconds**.

On the visible day, maximum unrounded electrical, heat, and cooling residuals were all below (3 × 10^{-13}) kW. Independent gas and cost calculations agreed exactly at floating-point precision. After the unchanged three-decimal JSON rounding, the largest measured balance/billing discrepancy was **0.0005668** in its corresponding reported unit; no serialized visible-day grid violation was observed.

## Deliverables

- `app/`: complete repaired runnable application, with its original unchanged data files.
- `plan.json`: final visible-day output in the original format.
- `self_checks.py`: independently written validation and generated-case checks.
- `SELF_CHECK_RESULTS.json`: successful validation output and timings.
- `FROZEN_SHA256.json`: frozen runtime-code and input hash manifest.
- `BLIND_REPORT.md`: this report.

The report and result files describe only the visible specification and self-generated validation. They make no claim about unseen benchmark outcomes.
