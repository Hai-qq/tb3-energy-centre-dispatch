# Energy-centre dispatch repair — isolated C2 delivery

## Run the repaired tool

The complete runnable application is in `app/`. It has the same command-line entry point and the same plan schema:

```bash
python3 app/dispatch.py --data app/data --output plan.json
```

When installed at the original location, the requested command remains:

```bash
python3 /app/dispatch.py --data /app/data --output /output/plan.json
```

Runtime dependencies are Python 3.13, NumPy and SciPy only. Validation used Python **3.13.16**, NumPy **2.3.4** and SciPy **1.17.0**. The original Dockerfile is retained unchanged; its container image was not rebuilt during this isolated work.

No supplied data file was changed. The five files in `app/data/` were compared byte for byte with the visible task package after all experiments. Generated cases have their own folders under `experiments/cases/`; their plant and supply files are unchanged copies.

## Result for the visible operating day

The final plan for 2026-07-21 is in `experiments/plans/visible.json`.

| Quantity | Result |
|---|---:|
| Total cost | £6,303.560319427 |
| Billed gas | 64,944.185839485 kWh |
| Imported electricity | 13,775.407766202 kWh |
| Exported electricity | 0 kWh |
| Engine starts | 2 |
| Every grid check | true |
| Largest grid apparent power | 985.400041507 kVA |
| Largest gas-entry rate | 289.087272727 standard m³/h |
| Smallest available tower headroom | 231.034982632 kW |

GE1 is initially running according to the supplied status. The optimal plan stops it at midnight, starts GE2, and later starts GE1 at 11:00 after its outage. The first period includes GE2's £27 start charge, and 11:00 includes GE1's £38 start charge. These are the two reported starts.

The independent whole-day MILP oracle proved a lower bound of **£6,303.560319426553**, agreeing with the published feasible plan within **£0.000000001**. The bound is produced by a separate formulation, not by reusing the production planner's period costs.

## What was repaired

### Time and forecast alignment

Demand timestamps are parsed as offset-aware local timestamps, sorted chronologically and checked to be exactly the 48 half-hours of the status date. Their local UTC offset must remain constant, as required by the task.

Each demand timestamp is then converted to its UTC instant and matched by key to the weather forecast. Forecast row order and the UTC calendar date of a row do not determine its position in the plan. Missing required forecasts and duplicate forecast instants are rejected.

The electricity tariff uses the **local weekday** and the local start time. A local Monday beginning on a UTC Sunday therefore receives the weekday tariff. No UTC-epoch weekday calculation remains.

### Metered gas, costs and the gas entry

A net-CV engine fuel figure is multiplied by the supplied gross/net ratio, **1.108**, to obtain gross-CV billed energy. The opposite conversion divides by that ratio. Boiler efficiencies already expressed on gross CV are not converted a second time.

The gas entry is a real instantaneous resource constraint shared by the units listed in its `supplies` field:

```text
gross gas input limit
  = 550 standard m³/h × 39.6 MJ/standard m³ ÷ 3.6 MJ/kWh
  = 6,050 kW on gross CV
```

Consequently, its maximum half-hour consumption is 3,025 gross-CV kWh. Standard volume and calorific value already refer to the same stated standard conditions; ambient weather does not require an additional temperature or pressure correction.

Every candidate loading constrains the sum of the engines' and boilers' **gross-CV** fuel rates at the entry, independently of the tariff's billing basis. A gas-entry outage gives that entry zero available capacity.

Each published period cost is recomputed from the selected unit outputs:

```text
0.5 × (
    billed gas input kW × gas price
  + engine gross electrical kW × maintenance price
  + imported kW × local import price
  - exported kW × export price
)
+ actual OFF-to-ON engine start charges
```

The start charge is a charge per event, so it is not multiplied by half an hour. Gas energy and maintenance are evaluated from the actual published engine loading and the actual adjacent table interval.

### Engine performance and electrical limits

Every intermediate part-load point is used. An operating engine must select exactly one **adjacent** part-load segment, with its output between that segment's endpoints. Fuel and HT recovery use the same electrical loading on that segment. The optimizer cannot average nonadjacent points, average the off state with an operating point, or run an engine below minimum output.

Fixed, overexcited generator power factor supplies reactive power:

```text
Q_generator = P_generator × tan(acos(power_factor))
Q_grid = forecast whole-site kvar − sum(Q_generator)
P_grid = import − export
```

The net exchange obeys the physical apparent-power circle and the independent real-power export limit:

```text
P_grid² + Q_grid² ≤ import_capacity_kva²
P_grid ≥ −export_limit_kw
```

This correctly handles both reactive support and reactive overcompensation. Clamping a negative square-root argument to zero is not used to turn an infeasible reactive demand into an apparently valid import limit. Generator kVA ratings are also checked against their fixed power factor.

Engine auxiliaries are charged whenever that engine is on. Absorber auxiliaries are proportional to absorption cooling. The demand file already includes tower fans and pumps, so these are not added again.

PV is available up to the smaller of the forecast AC output and the inverter rating, subject to its outage status. It may be curtailed when needed to respect the connection limits. Reported PV is actual dispatched output. The electricity formulation represents net import/export and does not allow profitable artificial simultaneous transactions.

### Complete heat routing

The supplied connection list is treated as complete:

- Engine **HT** can supply the absorption generator and PHE1.
- PHE1 and the boilers supply LTHW.
- Engine **LT** goes to each engine's own LT radiator; it supplies neither the buildings nor the absorption generator.
- There is no HT dumping connection.

Therefore the model enforces the closed heat balance, rather than merely requiring heat production to exceed demand:

```text
sum(engine HT)
+ sum(boiler heat)
− sum(absorption cooling / absorption COP)
= building heat + LTHW loss
```

It separately requires nonnegative PHE transfer:

```text
sum(absorption cooling / absorption COP) ≤ sum(engine HT)
```

Together these conditions prevent both fictitious HT dumping and boiler heat being routed backward to an absorber. When PHE1 is unavailable, HT must go entirely to absorption, while boilers can still serve LTHW. An engine cannot run without its connected LT circuit/radiator. Unit outages, tower-cell outages, PV outages, heat-circuit outages and gas-entry outages are all respected.

Any overlap between an outage and a held half-hour loading makes that unit unavailable for that loading. Clock intervals wrapping midnight use the union `[from,24:00)` and `[00:00,to)`.

### Chillers, common cooling water and cooling towers

The minimum possible condenser inlet temperature is the larger of wet bulb plus tower approach and the stated tower minimum. Electric-chiller COP is interpolated **at condenser inlet water temperature**, not dry bulb. All table evaluations are linear between points and flat outside their ends.

An operating absorber must receive sufficiently hot HT water and sufficiently warm condenser water. Variable-speed tower fans permit holding the common loop warmer when necessary. The optimizer includes the relevant absorber minimum-temperature modes rather than declaring absorption impossible merely because the weather permits colder water.

It also handles the less usual case in which warmer condenser water is useful while the export limit binds. All chillers still share **one physical water temperature**. This is represented exactly with a total electric-chiller power variable. For any fixed chiller cooling outputs and any chosen absorber-temperature mode, total compressor power is a continuous, nondecreasing function of the common water temperature. Its possible values are precisely the interval between:

1. the sum of cooling divided by each COP at the minimum permitted temperature; and
2. the same sum at the flat high-temperature ends of the COP tables.

Both interval endpoints are linear in chiller output. Thus this representation is exact for the supplied monotone tables; it does not mix independent chiller water temperatures. The actual common temperature is recovered by monotone bisection and checked.

The tower duty is the complete refrigeration energy balance:

```text
tower rejection =
    total cooling
  + electric-chiller compressor electricity
  + absorption generator heat
  + absorption machine auxiliary electricity
```

Absorption-machine auxiliary electrical work is included in its rejected heat because no separate thermal outlet is specified. Engine LT radiator heat is not charged to the tower circuit.

Tower capacity is interpolated at the matched wet bulb and multiplied only by available cells.

The original JSON schema has no water-temperature or heat-flow field. Those quantities are uniquely reconstructible where they affect compressor power. A review helper is provided to make the selected operating conditions explicit:

```bash
python3 checks/explain_plan.py \
  --data app/data \
  --plan experiments/plans/visible.json \
  --output operating-details.json
```

This validates the plan first, then reports each half-hour's common condenser temperature, compressor power, HT/PHE/absorption flows, LT radiator recovery, tower duty, net reactive exchange and gas-entry volume. Examples for the visible day and an export-constrained warmer-water case are included in `experiments/`.

## Optimization and numerical guarantees

For the supplied two engines, each engine has an off mode and two adjacent operating segments. At most nine engine segment combinations must be examined per half-hour, with at most two condenser-water eligibility modes.

Within each such combination, the problem is linear except for the two-dimensional grid circle. The production solver starts with supporting half-planes that enclose that circle, solves the resulting LP using HiGHS dual simplex, and adds an exact separating tangent whenever the LP's solution lies outside the circle. Each LP objective is a lower bound on that continuous regime's optimum. Refinement stops only when the actual grid norm satisfies the circle within **1e-7 kVA**.

After choosing the best loading for each engine on/off state in each half-hour, a dynamic program solves the entire day:

```text
D[t, current] =
  period_cost[t, current]
  + min over previous (
      D[t−1, previous]
      + start_cost(previous → current)
    )
```

Its initial state is the supplied `running_at_midnight` set. There are four engine states and sixteen possible transitions per period. This is the exact temporal optimization for the data provided: no ramp rate, minimum up/down time, shutdown charge or terminal running-state requirement is specified, so none is invented.

Within each dynamic-program state, numerically equal paths prefer fewer starts. Engine regimes, variables and availability identifiers have fixed ordering. HiGHS uses one thread and a fixed random seed. A per-day cache only reuses identical numerical operating inputs, tariff rates and outage availability.

Actual interpolated heat, electricity, cooling, gas-entry loading, grid loading and invoices are checked before output. A solver failure is not silently treated as a valid plan. Genuine infeasibility raises a clear error. A complete successful plan is written atomically.

The schema and units are unchanged. Numeric values retain nine decimal places instead of three so that serialization does not create material balance or binding-capacity violations.

## Independent validation

Run the full generated-case suite:

```bash
python3 checks/run_checks.py
```

Run the independent whole-day optimality oracle:

```bash
python3 checks/reference_milp.py
```

Audit any produced plan directly:

```bash
python3 checks/check_plan.py --data app/data --plan experiments/plans/visible.json
```

The physical/billing checker imports **no production planner code**. It independently parses and matches the files, implements interpolation using bisection, reconstructs common water temperature, rebuilds all balances, calculates generator vars, derives the gas standard-volume rate, checks outages and ratings, recounts starts and recomputes invoices.

The whole-day reference oracle uses one mixed-integer model with binary adjacent-segment selection and explicit startup variables. This is structurally different from production's continuous subproblem enumeration plus dynamic programming. Its outer polygon gives a certified lower bound for the true circular grid constraint. When that bound agrees with a separately audited physical plan, it certifies the plan's least cost to numerical precision.

### Completed checks

**29 complete daily scenarios passed:** 25 feasible plans and four deliberately infeasible cases rejected correctly.

They cover the visible day; shuffled rows; positive, negative, half-hour and zero UTC offsets; local Monday and weekend boundaries; engine, boiler, electric-chiller, absorber, tower, PV, PHE, radiator and heat-circuit availability; midnight states; startup bridging; cold absorption; warmer-water operation under an export limit; PV curtailment; table end clamping; high and negative reactive demand; binding grid, gas and tower constraints; and three independently generated feasible-witness days.

The four infeasible cases separately exercise an insufficient gas-entry capacity, an unavailable gas entry, no available tower cells and uncorrectable reactive demand.

A binding-circle case also has an independent analytic solution. With only GE2 available and optimally at 800 kWe, its net kvar fixes exact permissible import; the remaining electrical balance fixes the minimum absorption load and boiler heat. Every period of the produced plan agrees with this calculation within 2e-5 kW.

Five fresh-process replays, using a different Python hash seed, produced **byte-identical JSON**, including a binding grid case, warmer-water control and two randomized days.

| Validation measure | Final result |
|---|---:|
| Maximum observed single-day runtime | 2.703465 s |
| Largest electricity-balance residual | 1.08e-9 kW |
| Largest heat-balance residual | 9.83e-10 kW |
| Largest cooling-balance residual | 4.55e-13 kW |
| Largest metered-gas residual | 9.98e-10 kWh |
| Largest period invoice residual | 5.59e-10 GBP |
| Whole-day independent MILP comparisons | 7 |
| Maximum absolute plan / certified-bound cost gap | 4.47e-10 GBP |

The seven globally checked cases are the visible day, binding gas entry, binding tower, electric-chiller outage, both initial-state versions of the startup-bridging case, and warmer-water operation under an export constraint. Their independent MILP relative gaps were all zero.

Machine-readable results are in:

- `experiments/checks-report.json`
- `experiments/optimality-report.json`
- `experiments/visible-audit.json`
- `experiments/visible-operating-details.json`
- `experiments/warmer-water-operating-details.json`

## Delivery and freeze

- `app/`: complete runnable tool and unchanged supplied data.
- `checks/`: independent audit, case generator, test runner, optimality oracle and operating-detail explainer.
- `experiments/`: generated inputs, feasible witnesses, plans, deterministic replays and recorded results.
- `FREEZE.json`: SHA256 and byte size of every delivered regular file, excluding the manifest itself; separate aggregate hashes identify the application and checking-code trees.

All implementation and experiments were performed solely from the isolated visible instruction and application files, without external task solutions, repository history or evaluation feedback. The freeze manifest is written only after the delivery is complete. No application or checking code is modified or rerun after that freeze.

## Development evidence and freeze

`DEVELOPMENT_LOG.md` records the self-directed revisions, intermediate result observations, tool failures, and the limitations of retained intermediate evidence. `FREEZE.json` hashes all final delivered regular files except itself. The manifest SHA256 is reported separately at delivery. No implementation or checker changes and no further self-tests follow that freeze.
