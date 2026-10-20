# Hospital energy-centre dispatch repair

The complete application is in `app/`. It retains the original JSON structure, uses only Python's standard library, NumPy and SciPy, and reads the supplied data without changing them.

```bash
python3 app/dispatch.py --data app/data --output plan.json
```

The existing container entry point also works:

```bash
python3 /app/dispatch.py --data /app/data --output /output/plan.json
```

The output is written atomically after a complete feasible day has been found. An impossible day or invalid time alignment raises a clear error and does not produce a fictitious or partially written plan. Numerical values retain full floating-point precision so independently rounding plant outputs cannot violate binding physical balances.

## What was repaired

| Area | Implemented behaviour |
|---|---|
| Forecast alignment | Demand rows are sorted and validated as the 48 local half-hours of the stated date. Each weather/PV row is joined by its actual UTC instant, including UTC date boundaries and non-integer-hour offsets. |
| Tariff calendar | Weekday/weekend classification uses the local plan date, including local Mondays and Saturdays whose midnight is on the previous UTC date. |
| Gas billing | Net-CV engine fuel is multiplied by the gross-to-net ratio, 1.108, when billed on gross CV. Boiler fuel uses its stated efficiency basis. Both conversion directions are implemented. |
| Engine performance | Every adjacent pair of part-load points is used. A whole-day engine loading never substitutes one straight line across all points or a convex combination of non-adjacent operating points. |
| Heat grades and routes | Only jacket/exhaust HT feeds the absorber generator and the HT-to-LTHW exchanger. Intercooler LT goes to its own available radiator; it cannot heat the buildings or fire the absorber. |
| Complete heat balance | The listed HT circuit contains no dump. All recovered HT therefore reaches the absorber or the PHE. The PHE plus the boilers exactly supply building heat plus the 75 kW distribution loss. |
| PHE rating | The primary water-flow limit gives `20 × 4.18 × (90 − 70) = 1672 kW`, and a PHE outage removes that transfer path. |
| Cooling plant | Cooling outputs meet demand exactly. Electric-chiller COP depends on the **common condenser-water temperature**, not dry-bulb temperature. Absorbers require both a connected hot-water source and their cooling-water inlet minimum. |
| Cooling-water control | Variable-speed towers can maintain the required minimum on cold days and can operate at a higher common water temperature if needed. The feasible aggregate compressor-power range is represented exactly, with no temperature sampling. |
| Tower load | Electric chillers reject cooling plus compressor input. Absorbers reject cooling plus generator heat. LT radiator duty is outside the condenser-water circuit. Only available connected tower cells contribute capacity. |
| Electrical balance | Generator output, actual PV and grid exchange cover the specified site demand, engine auxiliaries, compressor input and absorber auxiliaries. Already-included tower fans and pumps are not charged a second time. |
| Reactive power | Each overexcited fixed-PF generator supplies `P × tan(acos(PF))` kvar. The grid limit uses the remaining **signed** site reactive power, including overcompensation into leading kvar. |
| Connection limits | Imported active power and net reactive power obey the actual apparent-power circle. Exported active power obeys the separate 250 kW export limit. Positive import/export price separation prevents simultaneous import and export. |
| All outages | Engine, boiler, chiller, absorber, tower-cell, PHE, PV and LT-radiator availability is respected. Any overlap with an outage prohibits operation throughout a half-hour whose output must be held constant. Intervals crossing midnight are supported. |
| PV | The inverter caps available AC production. An outage removes it. Available PV is used unless the connection requires curtailment; actual dispatched PV is reported. |
| Starts | The optimizer includes each off-to-on transition, beginning with `running_at_midnight`. Start costs enter both the optimization and the affected period's billed cost, and the reported count includes first-period starts. |
| Day optimization | Dynamic programming selects the least-cost path across all feasible engine commitments rather than choosing each period greedily. |
| Reporting | Fuel, maintenance, imports, exports and startup charges are recalculated from the selected physical outputs. Summaries are sums of the reported periods. |

The plant and supply files are unchanged. There is no hard-coded plan date, weather, load profile, engine schedule, expected objective or fixture-specific branch.

## Optimization model and why it is globally applicable

The two engines each have two adjacent part-load segments. For a given half-hour and engine on/off combination, the application enumerates the actual active segments, as well as the finite set of relevant absorption-chiller cooling-water inlet floors. This includes every permitted piece of the nonconvex engine curves and every absorber eligibility regime.

Within one such case, all energy balances, plant capacities, hydraulic limits and operating costs are linear. One convex constraint remains: the import connection's apparent-power circle. The implementation solves a sequence of small LPs with supporting lines of that circle. Every supporting line contains the entire circle, so every intermediate LP objective is a lower bound for that case. When the LP optimizer satisfies the actual circle to the checked tolerance, it is a feasible global minimum for that convex case. No engine output grid, fixed derating, inscribed polygon or local nonlinear optimizer is used.

With independently optimized running costs for each half-hour and on/off state, the only inter-period cost in the supplied data is engine starting. A four-state dynamic program adds the appropriate transition costs and traces the cheapest complete day from the supplied midnight state. No unprovided ramp rate, minimum uptime, minimum downtime, thermal store, HT dump, or terminal commitment is invented.

### Exact treatment of a controllable common condenser temperature

For fixed electric-chiller cooling outputs `Q_j`, aggregate compressor input is

`W(T) = sum(Q_j / COP_j(T))`.

The supplied COP curves are positive, continuous and non-increasing. Consequently `W(T)` is continuous and non-decreasing. Let `T_min` be the maximum of the wet-bulb-plus-approach temperature, the tower leaving-water floor, and the inlet minima of the operating absorbers. Let `T_max` be the larger of `T_min` and the final temperature of all COP tables. The curves are flat beyond their final points.

Every compressor input between `W(T_min)` and `W(T_max)` is attained at **one common water temperature**, by continuity. The endpoints are linear functions of the cooling outputs. The optimizer therefore introduces one aggregate compressor-input variable between those linear bounds. Electricity and tower heat rejection depend on that aggregate input, so this is an exact elimination of the temperature variable rather than a relaxation or an interpolation of reciprocal COP.

Ordinarily the positive electricity prices select the lowest sufficient water temperature. The more general formulation matters when heat and outages force an engine to run and a higher condenser temperature is needed to keep export within its limit. The dedicated `heat_led_cooling_water_modulation` experiment constructs such a feasible day. A model that always fixes tower leaving water to its minimum incorrectly declares that day impossible.

### Keeping the existing output format

The original schema has no condenser-temperature field. Its existing values nevertheless determine actual aggregate compressor input:

`W = sum(engine kW) + PV + import − export − site active demand − engine auxiliaries − absorber auxiliaries`.

Given those cooling outputs and `W`, the common temperature is recovered monotonically from the COP tables. `Plant.condenser_temperature(...)` implements and checks that recovery; the independent verifier implements its own recovery without importing application code. Thus higher-water-temperature operation does not require adding fields or reporting inconsistent chiller electricity. When electric chillers are off, the lowest inlet setting compatible with the operating plant suffices.

### Metering equations

For each half-hour:

- Engine gross-CV gas is its interpolated net-CV fuel multiplied by 1.108, then by 0.5 hours.
- Boiler gas is delivered heat divided by efficiency, converted only when the stated efficiency and billing bases differ, then multiplied by 0.5 hours.
- Maintenance is gross generated kW times the stated GBP/MWh(e) rate divided by 1000, then multiplied by 0.5 hours.
- Import and export energy are the reported active powers multiplied by 0.5 hours. Import rates use the local half-hour and local day type.
- Each engine changing from off to on adds its stated fixed starting cost in that half-hour.

The daily totals are direct sums. `grid_ok` checks the actual selected operation, including engine reactive production and the export limit.

## Independent validation

The `checks/` directory is part of the deliverable and imports no application modules:

- `verify_plan.py` reads the raw input files and the JSON output, independently interpolates performance tables, checks every output and outage, reconstructs common condenser temperature, validates electrical/thermal/cooling balances and connection limits, and recomputes gas, charges, starts and summaries.
- `optimality_oracle.py` uses a **single full-day mixed-integer model**, unlike the application's period-by-period enumeration and dynamic program. It models engine segments with disaggregated binary choices and interpolation fractions, models starts across all periods, and obtains a lower bound using supporting apparent-power cuts. Comparing a physically verified plan with this independent lower bound certifies optimality to a stated monetary tolerance.
- `run_experiments.py` deterministically constructs feasible physical witnesses and representative modified daily inputs, checks the witnesses, invokes the actual CLI twice per scenario, checks byte-for-byte output identity, validates every output, and compares the plan cost with the independent lower bound and the feasible witness.

Run the full suite:

```bash
python3 checks/run_experiments.py
```

Run a single output through the independent checker:

```bash
python3 checks/verify_plan.py --data app/data --plan experiments/visible_plan.json
```

Certify a plan against the separate full-day optimizer:

```bash
python3 checks/optimality_oracle.py --data app/data --plan experiments/visible_plan.json
```

`experiments/scenarios.json` lists the generated scenarios and their purpose. `experiments/experiment_results.json` holds full timings, hashes, physical residuals and optimality certificates. Each scenario directory retains its complete daily inputs, output plans, repeat plan, validation result and, where generated from physical dispatch, an independently checked feasible witness.

The suite covers local weekdays/weekends, UTC offsets of +14, −7 and +05:30, shuffled inputs, cold and hot curve endpoints, common-water control, every outage category, partial-period and midnight-wrapping outages, independent boiler efficiencies, the PHE hydraulic boundary, total condenser rejection, high and leading reactive demand, the actual circular connection boundary, PV limits/curtailment, low heat with no HT dump, six random feasible days, and startup economics across short and long demand dips. Four deliberately impossible cases check that the CLI fails instead of producing an invalid plan.

Detailed final timings, residuals and per-scenario results are in `RESULTS.md`.

## Delivery and freeze

`FREEZE.json` records SHA-256 for every delivered file other than the manifest itself. Python bytecode caches are removed before freezing. The application and validation code are not changed after that manifest is written.
