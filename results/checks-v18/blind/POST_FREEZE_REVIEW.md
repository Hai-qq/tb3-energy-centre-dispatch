# Post-freeze semantic audit of the two strongest comparison implementations

## Isolation and scope

**This review was performed after the independent blind implementation was frozen. It is not part of E3 and cannot be used to characterize E3 as having incorporated benchmark feedback.** No frozen application file was changed. No comparison application was changed. The only file written for this assignment is this report.

The copied blind runtime files were rehashed during this review and all still matched the frozen manifest:

`89b4cbfad49a251e6a1d321cdae598264f6c6ff58beaf520015d0162a3e7d917`

The reviewed comparison apps are, relative to the repository root:

- `results/v16-trials/ecd16-run2-claude/app`
- `results/checks-v18/opponents/ecd17-run2-codex-parts/app`

I read their data, plant, tariff, and optimization implementations, Claude's entry point, and the current visible instruction. I reused only the fixed visible plant/supply and the original visible input template to construct new in-memory demand/status/weather profiles. I did not open a benchmark verifier, reference optimizer, or supplied hidden case. An initial filename inventory was used to locate the repository after the relative paths did not resolve from the shared scratch directory.

Candidate execution used `PYTHONDONTWRITEBYTECODE=1` and Python's `-B` option. All constructed profiles and outputs stayed in memory. The frozen code and its original report remain untouched.

## Main conclusion

I did **not** find an additional unambiguous, fixed-data semantic counterexample that falsifies **both** candidates independently of an unresolved physical interpretation.

The DP and adjacent-segment structures themselves are sound. The known common-header warming omission does falsify Claude's restricted temperature model under the interpretation that tower fan control can attain the necessary warmer setpoint. Codex's aggregate compressor-power interval is a mathematically valid way to cover that continuous temperature range.

There is a second substantive issue in Claude: it changes the absorber's tower heat balance when its usual balance makes a half-hour infeasible. This is an actual change of physical model, not a numerical solver detail. I reproduced it, and I also produced an ordinary feasible day on which the two candidates differ by **£20.323128223083** solely because they use different absorber-auxiliary heat conventions. Whether a particular result is wrong under the visible specification still depends on where that auxiliary heat is assumed to go.

I would not promote a dry-bulb/LT-radiator cutoff, a negative-PV test, or a signed-export kVA convention into an unqualified new verification requirement without resolving the corresponding specification ambiguity.

## 1. What the candidates do correctly

For the fixed visible plant, both candidates represent:

- Every adjacent engine part-load interval, preserving the intermediate point.
- The distinct off state, minimum load, rated output, fuel intercepts, and gross-CV billing.
- Generator reactive contribution at the given fixed overexcited power factor.
- The complete engine-HT split between the absorber and PHE1, with no invented HT dump.
- The one-way PHE transfer and the building-side boiler balance.
- Separate engine LT radiator rejection, without crediting LT heat to useful loads or towers.
- Electrical and chilled-water balances, plant auxiliaries, and tower capacity by available cells.
- Local-date tariffs and local/UTC matching.
- Engine starts from the midnight status and throughout the day.
- A full dynamic program over the engine on/off states.

Claude derives literal component names from the heat-circuit endpoints. The patched Codex implementation disables a parent when the outage name begins with the parent ID followed by a space, and separately checks LT radiators. Both handle the literal component names present in this plant, including the intercooler, condenser, absorber/generator, and radiator endpoints.

Nothing in the supplied data provides additional ramp rates, minimum up/down times, start fuel quantities, PHE capacity, boiler minimum load, fan power curves, or chiller part-load derating. Requiring such constraints would introduce new plant information rather than discover an omitted stated constraint.

The temporal reduction has a direct optimality argument. Let L_t(s) be the minimum feasible operating cost in half-hour t with commitment s, and let K(r,s) be the sum of the listed costs for engines that are off in r and on in s. Then

```text
D_t(s) = L_t(s) + min_r [ D_(t-1)(r) + K(r,s) ]
```

Initialize only the actual midnight state at zero cost and all other initial states at infinity. There is no stated coupling through load level, stored heat, ramps, or elapsed run time, so a more expensive loading with the same commitment cannot improve a later period. Once each L_t(s) correctly covers the continuous period model, the recurrence is an exact whole-day algorithm. Both candidates implement this structure. Their differences concern the feasible period model or its physical conventions, not a failure to optimize starts across the day.

## 2. Common-header warming: the known failure and why Codex's representation works

Claude considers only the coldest attainable condenser water and the absorption-chiller minimum inlet thresholds. See its `planner/optimize.py`, line 128. Its implicit dominance argument is incomplete: a less efficient electric chiller can provide a useful controllable electrical load when engine generation is constrained by reactive demand, heat routing, and the export cap.

The parent supplied an already-found case requiring a common-header setpoint near 24.26°C. I did not rerun that supplied case or inspect its files. Its relevance is supported by the control-space reasoning above.

Codex uses a total electric-chiller electrical-input variable. For fixed cooling outputs \(C_1,C_2\), define

\[
W(T)=\frac{C_1}{\operatorname{COP}_1(T)}
     +\frac{C_2}{\operatorname{COP}_2(T)}.
\]

For the fixed tables, \(W(T)\) is continuous and nondecreasing. Its image over a connected allowed temperature interval is therefore the entire interval between the endpoint values. Codex's two linear inequalities on total compressor input exactly describe that image; it is not mixing incompatible independently chosen chiller temperatures. See Codex `planner/optimize.py`, lines 104–105 and 153–171.

The cooling balances, tariff, grid constraint, and tower balance need only that total compressor input. A common temperature producing it exists by continuity and can be recovered from the reported plant and grid quantities if needed. Above 34°C both fixed COP tables are flat, so further warming does not add any new compressor-input values in this mathematical model.

This establishes the correctness of the aggregate formulation **conditional on the allowed temperature-control interval**. Variable-speed fans establish a control mechanism, but the input does not state minimum fan speed, natural-draft performance, water bypass control, or an explicit upper attainable setpoint. I would distinguish that equipment/control ambiguity from the valid mathematical reduction.

This insight arrived after the blind freeze. In particular, it does not retroactively repair or qualify the blind implementation's original temperature-dominance argument.

## 3. Absorber auxiliary heat: a reproduced model difference and a Claude fallback

### Source evidence

Claude initially sets `absorber_aux_to_towers = True` (optimization line 141), and its tower coefficient is

\[
1+\frac{1}{0.71}+0.022
\]

per kW of absorption cooling (line 259). If every usual loading is infeasible, however, it changes that flag to false and resolves the half-hour (lines 345–350).

Codex consistently uses

\[
1+\frac{1}{0.71}
\]

for the absorber's tower coefficient, while accounting for its 0.022 kW/kW auxiliary electricity in the site electrical balance. See its optimization lines 126–128 and 173–178.

These are different physical models. Claude additionally switches between them based on whether the first model found a feasible solution.

### An ordinary feasible whole-day profile

I constructed a 48-period weekday using the visible local timestamps and unchanged plant/supply. Every period has:

| Input | Value |
|---|---:|
| Site electricity | 1,000 kW |
| Site reactive demand | 200 kvar |
| Building heat | 250 kW |
| Cooling | 778.5 kW |
| Dry bulb | 26°C |
| Wet bulb | 22°C |
| PV forecast | 0 kW |

GE2 is already running at midnight. GE1 and CT2 are out for the day. All other units are available. One available tower cell has a 1,425 kW rejection rating. The common condenser-water temperature is 26°C, so EC1's COP is 5.6. Both plans import electricity throughout, so this profile does not depend on export control or discretionary header warming.

The measured results were:

| Quantity | Claude | Patched Codex |
|---|---:|---:|
| Day cost | £4,169.909054651655 | £4,149.585926428572 |
| Billed gas | 52,540.3224208916 kWh | 52,918.08 kWh |
| Starts | 0 | 0 |
| GE2 output, every period | 793.2353880309795 kW | 800 kW |
| EC1 cooling | 373.1317246988028 kW | 370.25 kW |
| AC1 cooling | 405.3682753011972 kW | 408.25 kW |
| Grid import | 306.3133791504331 kW | 299.0975714285714 kW |
| Tower duty excluding absorber auxiliary heat | 1,416.0718979433736 kW | 1,419.616071428571 kW |
| Tower duty including absorber auxiliary heat | 1,424.99 kW | 1,428.5975714285712 kW |

Both report `grid_ok = true`, correctly for the electrical connection.

If absorber auxiliaries ultimately load the condenser-water circuit, Codex's plan exceeds the tower rating by **3.5975714285712 kW**. A feasible lower-engine-loading plan exists, as Claude demonstrates.

If the specified auxiliary electricity is outside the absorber/condenser thermal balance, Codex's reported schedule is a feasible schedule **£20.323128223083 cheaper** than Claude's. Consequently, Claude is not least-cost under that convention.

The 0.01 kW tower reserve in Claude is not the explanation for this difference: the disputed auxiliary duty is approximately 9 kW. The difference is physical-model semantics.

### A fallback profile that changes the heat accounting

I also constructed a single period with:

- Electricity 1,000 kW; reactive demand 200 kvar.
- Building heat 100 kW; cooling 589.5 kW.
- Dry bulb 26°C; wet bulb 22°C; PV zero.
- GE2 initially running.
- GE1, CT2, EC1, and EC2 unavailable.

Both candidates report:

| Quantity | Result |
|---|---:|
| GE2 | 800 kW |
| B1 heat | 105.28169014084517 kW |
| AC1 cooling | 589.5 kW |
| Grid import | 236.969 kW |
| Tower duty excluding auxiliary heat | 1,419.781690140845 kW |
| Tower duty including auxiliary heat | 1,432.750690140845 kW |
| Available tower rating | 1,425 kW |

Claude first finds its full auxiliary-heat model infeasible, then removes auxiliary heat from the tower equation and returns this plan. Its diagnostic is only: `cooling towers at their full rating`.

Under the full auxiliary-heat convention, this particular profile is physically infeasible with both electric chillers out. Thus the example demonstrates improper physical relaxation and reporting, rather than a missing feasible minimum-cost schedule under that convention.

The fallback is inconsistent even if one tries to assign an unspecified but fixed fraction \(\lambda\) of the auxiliary electricity to the tower circuit:

- The fallback output requires \(\lambda \leq 0.4023679434925548\) to fit the 1,425 kW tower.
- At every such fraction, the full-GE2 schedule in the ordinary 48-period profile is also feasible and is £20.323128223083 cheaper than Claude's result.
- At larger fractions, the fallback output itself exceeds the rating.

This proves that Claude's behavior is not the exact answer to either of the usual fixed conventions, or indeed to any fixed fraction convention across those two profiles. It does not establish which heat-routing convention the benchmark is entitled to require.

### Why I do not call the physical convention unambiguous

The input supplies an auxiliary electrical-load coefficient, but does not explicitly locate its heat release. Pumps acting on the absorber's process fluids normally provide a strong argument for including their work in the heat rejected by the device. Conversely, the phrase “auxiliary” can include equipment outside the stated thermal COP boundary, and the task does not explicitly state that all its heat enters condenser water.

“All heat-circuit connections are listed” constrains the modeled hydraulic topology, but does not by itself specify every casing, motor, or ambient heat loss. The engine fuel/recovery figures and boiler efficiency already show that not every input-energy watt is represented as an explicit useful-water circuit flow.

The software's conditional switch is unsupported either way. A hard hidden test selecting one convention should nevertheless identify the specification basis for that choice.

## 4. Apparent import versus signed net exchange

The candidates also differ in their contractual interpretation:

| Candidate | Apparent-power constraint |
|---|---|
| Claude | \(\sqrt{I^2+Q_{\rm grid}^2}\leq S\), where \(I\) is positive import |
| Codex | \(\sqrt{(I-X)^2+Q_{\rm grid}^2}\leq S\) |

Claude's source locations are optimization lines 286 and 434. Codex uses signed exchange in its circle solver and reporting; see optimization lines 74 and 220.

These coincide during import. They differ during export with large residual reactive exchange. For example, exporting 250 kW while the residual reactive exchange is 1,200 kvar yields approximately 1,225.765 kVA of physical net apparent exchange, while the positive-import expression evaluates to 1,200 kVA.

This is a mathematical illustration, not a newly executed plant-day counterexample.

A physical conductor or transformer rating naturally concerns signed net active exchange. However, the supplied field is specifically named `import_capacity_kva`, and the separate export limit is specified in kW. It may represent an agreed import capacity rather than the bidirectional thermal rating of the connection. The input does not explicitly resolve that distinction. I would not silently treat either convention as a new unambiguous benchmark requirement.

## 5. LT radiators and hot ambient air

Neither candidate uses dry bulb to restrict engine LT rejection. That is not enough to establish a supported cutoff from this data alone.

For a dry sensible air cooler required to return water at 35°C, ambient dry bulb at or above that return temperature prevents the stated return condition without some other colder sink. At ambient at or above the 40°C flow temperature, an ordinary dry sensible cooler cannot reject positive heat from water constrained to that temperature.

Those implications are valid **after** specifying:

1. The radiator's heat-rejection medium and mechanism.
2. That 40/35°C are fixed operating requirements or limits rather than nominal/design temperatures.
3. Whether the circuit may operate warmer or use any evaporative assistance.
4. The capacity/approach behavior needed to establish useful constraints below the limiting temperature.

The input says “LT radiator” and lists flow/return temperatures, but does not explicitly supply those additional facts. “Radiator” is strong engineering context, yet it is not a complete rejection-performance specification. Without a dry-air/type statement and a temperature limit, a new hard failure at 35°C or 40°C would depend on assumptions that the existing optimizer was not given.

I therefore do not recommend presenting the hot-radiator hypothesis as an unambiguous data-only falsification of these implementations. It is an excellent question for a clarified plant model.

## 6. Other avenues considered and not promoted to hard defects

**Negative PV.** Claude preserves a negative PV forecast as inverter consumption; Codex clips it to zero. A signed AC-terminal forecast can represent standby consumption, but the visible data provide nonnegative production, and the treatment of inverter consumption versus site demand and the ability to switch the inverter off are not specified. This is a real behavioral difference, but not a clean new fixed-specification requirement.

**Additional component names.** Claude recognizes literal circuit endpoints; Codex accepts parent-prefixed component names. Names such as “GE1 generator”, “CT1 fan”, or an entire circuit key might be sensible maintenance descriptions, but the outage identifier namespace is not explicitly defined beyond the visible names. The literal plant components relevant to the intended component-outage repair are already covered.

**Temperature-dependent engine or boiler derating.** No such curves or limits are given. An ambient-temperature derating schedule would be new data.

**Hydraulic limits and mass flow.** Flow/return temperatures alone do not establish mass-flow bounds, exchanger UA, pump curves, or pipe capacities. The unbounded PHE transfer in the LP is already bounded by available engine heat and building demand; there is no additional quantified stated capacity to impose.

**Minimum run durations, start fuel, and terminal state.** No values or post-day constraints are given. DP is exact for the stated coupling through start costs. Additional operational dynamics would be new requirements.

**Intra-half-hour forecast variability.** The input resolution and output contract are half-hour quantities held for each period. Robust instantaneous dispatch against unknown intra-period variation cannot be inferred from half-hour averages.

**Numerical reserves, finite penalty, and iteration limits.** These can create separate numerical or infeasibility-handling concerns, especially in Claude's softened import formulation, but they were outside this assignment's requested semantic focus. I did not use them to manufacture an “exactness” counterexample.

## 7. Reproduction of the newly executed profiles

The read-only execution pattern was:

```bash
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /workspace/scratch/3a594630faca/ecd-venv/bin/python -B -
```

Each candidate's planner package was imported under a separate in-memory package name with `importlib.util.spec_from_file_location`. Its data loader read the unchanged visible template. The generated quantities were then assigned to the `DayData` arrays in memory, and its status dictionary was replaced with the outages and midnight state listed above. I called its `plan_day` directly and reconstructed tower duties from the resulting cooling outputs and the visible COP values.

For the 48-period profile, all seven numeric arrays were constant and the original local timestamps and date were retained. For the fallback profile, the arrays, `starts`, and Claude's additional `start_times` were truncated to the first period. No case files or output plans were written.

## Assessment for the parent review

- The conditional warming failure is a sound critique of the restricted temperature enumeration; Codex's continuous aggregate formulation addresses that mathematical issue.
- Claude's auxiliary-heat fallback is an independently reproduced change in physical model and should not be described as an exact fixed-model optimizer without qualification.
- The ordinary 48-period auxiliary-duty profile cleanly exposes a non-numerical £20.323 difference while avoiding exports, temperature-range questions, unrealistic ambient limits, and extra plant data.
- Choosing which candidate's tower calculation to grade as correct requires an explicit or defensible auxiliary-heat boundary.
- I found no further unambiguous fixed-data semantic gap that defeats the patched Codex model under its stated control and heat-boundary assumptions.
- The frozen E3 implementation remains byte-for-byte unchanged; these observations belong only to this post-freeze review.


## 8. Final search context and why this review adds no fair E case

The parent reported, after the blind freeze and after the substantive review above, that its main and supplementary fuzz searches had covered **more than 343 valid feasible cases**, with **0/3 adversaries failing**, and that the final v18 matrix was **E1=false, E2=false, F=true**. Those are parent-supplied results, not independent measurements made by this review; I did not open their verifier or case files.

That empirical coverage is not a mathematical completeness proof. It is consistent with the structural audit: for the fixed visible plant, the strong candidates already have adjacent-segment enumeration, a continuous connection constraint, correct component availability, and exact startup DP. Codex also represents the aggregate continuous compressor-input interval. A proposed new counterexample must therefore identify a genuine omitted feasible control or a constraint supported by the existing data, not merely exhibit a difficult dispatch combination.

The remaining candidate witnesses found in this review fall into three categories:

- The already known restricted-header-temperature issue in Claude, conditional on the permitted warmer setpoint.
- Different auxiliary-heat, signed-exchange, or attainable-header-range conventions that the visible input does not resolve sufficiently to select a new unqualified failure condition.
- Additional radiator, hydraulic, derating, startup, or other operating limits that are not supplied and would become new task requirements.

I therefore add **no new fair E witness** to the parent's validated comparison set. In particular, this review does not justify adding new plant requirements to force a stronger model to fail. Claude's conditional auxiliary fallback remains a documented internal model inconsistency; the ordinary feasible profile gives a useful way to measure the auxiliary-boundary choice if that choice is settled independently.

### Late feedback on the frozen blind experiment

The same parent message reported that the actual frozen blind implementation **passed the visible v17/v18 case and failed h1–h4 on availability handling**. This feedback arrived only after the runtime-code freeze and after the independent blind source/report/manifest had been delivered. Those hidden-case outcomes were not known during blind implementation or self-validation.

I have not changed the frozen app, its original BLIND_REPORT.md, its original validation results, or its freeze manifest in response. This post-freeze review must not be treated as a repair to, or additional knowledge available during, E3. E3 remains the immutable implementation identified by the original runtime digest.


Final verification after completing this report: all six frozen runtime Python files and all five input-data files match FROZEN_SHA256.json. The recomputed runtime aggregate is `89b4cbfad49a251e6a1d321cdae598264f6c6ff58beaf520015d0162a3e7d917`. Only POST_FREEZE_REVIEW.md was written by this post-freeze assignment.
