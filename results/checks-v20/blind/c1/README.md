# Hospital energy-centre dispatch repair

The complete runnable repair is in `app/`. The original plant and supply data, and the visible day's status, demand and forecast, are preserved byte for byte. The command and JSON keys remain unchanged:

```bash
python3 app/dispatch.py --data app/data --output plan.json
```

The implementation uses only the Python standard library, NumPy and SciPy. It optimizes the entire local day, including starts relative to `running_at_midnight`, and reconstructs the bill from the dispatched outputs before writing the result. It has no dependency on a particular date, demand shape or outage schedule.

## Deliverables

| Path | Purpose |
|---|---|
| `app/dispatch.py` | Command-line entry point and atomic JSON output |
| `app/planner/data.py` | Complete local-day loading and timestamp-based weather alignment |
| `app/planner/plant.py` | Every engine performance segment, chiller COP tables and circuit connectivity |
| `app/planner/tariff.py` | Local weekday/weekend tariffs and calorific-value conversion |
| `app/planner/optimize.py` | Exact region enumeration, convex connection optimization, daily commitment and bill reconstruction |
| `checks/audit.py` | Independent physical and financial checker; imports no application modules |
| `checks/oracle.py` | Independent whole-day MILP optimality oracle; imports no application modules |
| `checks/run_checks.py` | Reproducible complete-day fixtures, feasibility witnesses, oracle comparisons and process-repeat checks |
| `checks/check_auditor.py` | Deliberately invalid plans that the independent auditor must reject |
| `experiments/check-results.json` | Machine-readable results of all 45 full-day cases |
| `experiments/check-run.log` | Console record of that complete run |
| `experiments/auditor-sensitivity/results.json` | Eleven successful rejection checks of the auditor itself |
| `experiments/data-integrity.json` | SHA256 evidence that the supplied data were not changed |
| `experiments/environment.json` | Actual Python/NumPy/SciPy runtime versions |
| `VALIDATION.md` | Validation methods, results and reproduction commands |
| `FREEZE.json` | Final hash manifest of the entire delivery, excluding the manifest itself |

The individual experiment directories contain their generated input data and resulting plans. `experiments/visible/` uses `app/data/` directly. Directories with an `oracle.json` also contain the independent solver certificate; feasible ones include its independently generated plan. The files in `experiments/auditor-sensitivity/` other than `results.json` are intentionally invalid test specimens.

## Physical model

### Engines, gas and auxiliaries

An engine is either off or running between its minimum and its usable rated output. The generator's kVA rating also bounds its active output at the specified fixed power factor. The optimizer retains every adjacent pair of points in each engine's part-load table. Fuel and HT heat are affine within the selected pair, and the same selected pair determines both quantities. Nonadjacent points cannot be averaged to obtain a fictitious operating point.

Off means zero generation, fuel, recovered heat, maintenance energy and engine auxiliary load. When running, the fixed auxiliary demand is charged in addition to the site's forecast active demand. Maintenance is charged on gross generated electrical kWh, using the supplied GBP/MWh rate.

Gas is converted to the billing basis before energy and cost are accumulated. For the supplied data:

\[
F_{\mathrm{gross}}=1.108F_{\mathrm{net}}.
\]

A boiler's supplied efficiency is already on gross CV, so its billed fuel rate is simply useful boiler output divided by that efficiency. There is no second CV conversion for those boilers.

For example, GE1 at the actual 900 kWe table point consumes 2275 kW on net CV. Its billed fuel rate is 2520.7 kW on gross CV, or 1260.35 kWh in a half-hour. This uses the supplied middle point; a line through only the first and last table points would give a different fuel input. The HT output at this point is 1110 kW. The separate 158 kW of LT heat does not become building heat or absorber generator heat.

### Exhaustive heat-circuit inventory

The supplied circuits determine where heat can go:

* Engine HT heat can enter the absorption generator or pass through PHE1 to LTHW.
* Engine LT heat goes to its listed LT radiator.
* Boilers supply LTHW. Their 80 °C circuit neither connects to nor meets the 85 °C minimum of the absorption generator.
* LTHW supplies the forecast building heat plus its 75 kW distribution loss.
* The condenser-water circuit receives the electric-chiller condenser duties and the absorption absorber/condenser duty.

No HT heat dump is listed. Consequently HT heat is balanced as an equality, with an explicit nonnegative PHE transfer internally:

\[
\sum H_{HT}=H_{PHE}+\sum A/COP_A,
\qquad
H_{PHE}+\sum B=H_{buildings}+75.
\]

This prevents both a fictitious LT heat credit and unreported disposal of unwanted HT heat. It also prevents boiler heat flowing backwards through the PHE into the absorber. The PHE has no additional rating in the data, so no invented transfer limit is imposed beyond the connected heat demand.

A listed radiator or its LT circuit being unavailable prevents its connected engine from running. A PHE outage removes the HT-to-LTHW path; the remaining connected equipment can still operate if it can meet all balances. The boiler, chiller, absorber, tower-cell and PV outages all affect the corresponding bounds.

### Cooling and tower duty

Electric-chiller COP is interpolated against condenser-entering **water** temperature, using all supplied COP knots and flat values outside the table. Dry-bulb temperature is not substituted for condenser-water temperature.

The minimum attainable tower leaving temperature is

\[
T_{base}=\max(T_{wetbulb}+4,21).
\]

The supplied variable-speed fans allow the water to be maintained warmer. In particular, an operating absorber requires at least 22 °C cooling water; cool weather therefore does not, by itself, prohibit absorption operation. The common water temperature must satisfy every running absorber's inlet requirement.

The model also covers a warmer feasible operating point when a minimum engine output and the export ceiling make the most efficient electric-chiller operating point infeasible. This is bounded by the actual supplied COP curves, rather than an unrestricted electrical dump. It can matter on general same-structure inputs with low active demand and useful CHP heat.

There is an exact linear way to include the common controllable temperature. For fixed electric-chiller outputs \(C_j\), define

\[
W(T)=\sum_j C_j/COP_j(T).
\]

Every supplied COP curve is positive, continuous and nonincreasing with temperature. Therefore \(W(T)\) is continuous and nondecreasing. If \(T_0\) is the lowest temperature allowed by the active absorber mode, and \(T_1\) is at least the final knot of every COP table, its attainable values are exactly

\[
\sum_j C_j/COP_j(T_0)\le W\le\sum_j C_j/COP_j(T_1).
\]

These are linear inequalities in the chiller outputs and total compressor power. Every point in this interval has a **single common** attainable condenser-water temperature by continuity. The optimizer does not assign independent water temperatures to the two chillers, and does not interpolate reciprocals of COP in place of the actual COP tables. Above the last knots, the given flat tables produce no new electrical operating points.

Distinct absorber inlet thresholds are enumerated as operating modes. The present plant has only one such threshold. The colder mode prohibits an absorber whose inlet minimum it cannot satisfy; the warmer mode permits it. An absorber may be at zero in a warmer mode without compromising coverage or feasibility.

Cooling demand is met exactly. Tower rejection includes electric compressor work and absorption generator heat:

\[
Q_{tower}=C_{total}+W+\sum A/COP_A.
\]

The capacity is the interpolated rejection rating **per available cell**, multiplied by the number of available cells. LT radiators are outside this circuit. Engine and absorber auxiliary electricity is included in the site's active balance as specified; no additional condenser heat duty is assigned to auxiliary loads for which the plant data do not specify a thermal return. Tower fans and the separately forecast pumps are already in the supplied site demand, so they are not charged a second time.

### Recovering controls without changing the JSON schema

The retained plan schema does not contain a water-temperature or PHE-transfer field. Both are nevertheless constrained and reproducible from the reported operation.

The PHE transfer is HT output minus absorption generator heat. Total compressor input is obtained from the electrical balance:

\[
W=\sum P+PV+I-X-E_{site}-E_{engine\ aux}-E_{absorber\ aux}.
\]

With the reported chiller outputs, solving \(W(T)=W\) over the allowed temperature interval gives a common feasible water temperature. The independent checker performs this inversion and reports its range. When no electric chiller runs, or when the coldest point already attains the required compressor power, use the minimum permissible water temperature. In the visible-day optimum, this is always the coldest permissible operating point.

At an export ceiling, warming water solely to consume otherwise-curtailable PV can be an equal-cost degeneracy. The implementation removes that degeneracy by reducing PV and compressor consumption together, as far as the coldest permissible operating point permits. Grid exchange, fuel and cost are unchanged.

### Active and reactive electricity

The active balance is

\[
\sum P+PV+I-X=E_{site}+E_{engine\ aux}+W+E_{absorber\ aux}.
\]

Each overexcited generator supplies

\[
Q_g=P\tan(\arccos(0.95)).
\]

Thus the connection's reactive exchange is the forecast site reactive demand **minus** generator reactive output. Both positive and negative residual reactive power matter to the apparent-power limit. Reactive demand is neither treated as unchanged by CHP operation nor clipped to a convenient sign.

The stated import and export limits are applied as

\[
\sqrt{I^2+Q_{net}^2}\le1220\ \mathrm{kVA},
\qquad
0\le X\le250\ \mathrm{kW}.
\]

These use the supplied import-kVA and export-kW contract quantities. No additional, unstated export-kVA contract limit is introduced.

Import and export are mutually exclusive within a period. This is important because the supplied night import rate is below the export rate: independent positive import and export variables would otherwise earn fictitious arbitrage revenue. Both net-exchange directions are explicitly enumerated, including their common zero-exchange boundary.

PV output is between zero and the lesser of the AC forecast and the 280 kW inverter rating, or zero during its outage. Curtailment is available to respect the connection's export limit.

## Whole-day least-cost algorithm

For two engines there are four commitment states. For a fixed state, the optimizer enumerates all combinations of adjacent engine performance segments, admissible condenser-water modes and import/export directions. The supplied plant has nine combinations of off/first-segment/second-segment operation across the two engines. The continuous plant dispatch is otherwise linear except for the import apparent-power circle.

That circle is solved by supporting hyperplanes. A supporting half-plane contains every point of the true circle; therefore the LP objective is a valid lower bound for the convex subproblem. If the LP solution lies outside the circle, another supporting cut at its radial direction is added. Once the optimum of the resulting LP satisfies the true circle, it is both feasible and optimal for the continuous subproblem, to the numerical feasibility tolerance. This is adaptive refinement, not a fixed inscribed or circumscribed polygon used as the final plant limit.

The accepted circle residual is at most `1e-7` kVA. Linear-program primal and dual feasibility tolerances are `1e-9`. An independent reconstruction checks the selected operation with a `3e-6` engineering-unit tolerance before writing it. Tiny residual tolerances do not substitute for lost-demand or overload slack variables; there are no such variables in the model.

The cheapest operating cost for each commitment and period is then passed to a shortest-path/dynamic-programming calculation:

\[
V_t(s)=C_t(s)+\min_r\left[V_{t-1}(r)+\sum_{e:\,r_e=0,s_e=1}K_e\right].
\]

The initial state is exactly `running_at_midnight`. A start at 00:00 is charged if and only if that engine was not already running. Later starts are charged in the half-hour in which the engine first runs. Stops have no charge because none is supplied. There is no imposed terminal commitment, minimum run time, ramp rate or thermal storage constraint absent from the plant data.

Start costs are the only specified coupling between periods. Consequently minimizing each period's continuous dispatch within each state, then minimizing the state path over the full day, is globally valid. No pointwise greedy commitment or heuristic suppression of starts is used. Fixed enumeration order and deterministic tie handling make repeated input produce repeated output.

## Data alignment and reporting

Demand must describe all 48 local half-hours of the stated plan date, with an explicit UTC offset and no clock change. Demand rows are sorted and checked for missing or repeated times. Weather rows are matched by their absolute UTC start instant. A UTC date filter or the order of forecast rows cannot accidentally shift a local summer day or a day with another UTC offset.

Weekday/weekend selection uses the **local** calendar day. The rate bands are selected using the local half-hour start. The fixed supplied tariff boundaries align with those starts.

Every output is held for its complete half-hour. An outage overlapping any part of that interval makes the affected unit unavailable for the interval. Outages are half-open; touching an endpoint does not cause an extra shutdown. Wrapping clock intervals, such as 23:15–00:45, cover the appropriate portions of both ends of the local day.

The final bill is reconstructed from actual plant outputs, not copied from an optimizer objective:

\[
\mathrm{cost}_t=0.5\left[F_{billed}r_g+\sum P_em_e+Ir_i-Xr_x\right]+\mathrm{starts}_t.
\]

The period gas quantity is \(0.5F_{billed}\). Day energy and cost totals are accurate sums of those same period quantities. The JSON keeps full float precision rather than independently rounding constrained loads to three decimal places. It retains the original top-level, period and summary keys.

A physically infeasible input produces an explicit nonzero exit and no newly written plan. Output is written atomically after every period has passed reconstruction. The optimization has a 110-second internal budget, leaving room inside the specified two-minute command limit for loading and output. The complete generated-day validation runs took approximately 0.53–3.99 seconds per primary CLI invocation on the supplied runtime.

## Validation outcome

The complete run contains 45 full days: 39 feasible days and six deliberately infeasible days. All behaved as required. Twelve of the feasible cases start from independently generated feasible physical dispatches, derive demand from those dispatches, and require the optimizer to find an independently audited plan at no greater cost.

Eight feasible days were also solved as one independent whole-day MILP with explicit segment, commitment and grid-direction selection. The largest objective difference was `8.38e-10` GBP; the largest reported relative MIP gap was approximately `1.73e-15`. Two infeasible days were independently proved infeasible by that model. The positive- and negative-reactive boundary comparisons required additional circle cuts, so they exercised the nonlinear capacity limit rather than only unconstrained LP cases.

Six diverse days were run in three fresh Python processes with different hash seeds; their JSON files were identical byte for byte. The independent auditor also rejected all 11 deliberate corruptions covering gas, start charges, heat disposal, outage operation, simultaneous meters, connection and tower overloads, inverter limits, summary counts, incorrect engine interpolation and premature rounding.

See `VALIDATION.md` and the machine-readable experiment reports for the full evidence and reproduction commands.
