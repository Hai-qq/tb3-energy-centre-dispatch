# Closing messages of the agent (each `result` event)

- turns 51, 28.5 min, error=False

I've fixed the main bugs, and an independent whole-day solver confirms the plan is the true least-cost one. Two background reviews are still running: one hunts bugs in the original code without seeing my list, the other critiques my fixes. I'll act on what they find.

For now, on the given day (21 July) the plan costs £6,235.28, burns 69,688 kWh of gas (gross CV) and has 3 engine starts. It passes my own checker, which works everything out again from the raw files.

**Fixes so far:**
- **Gas too low on engine days:** engine fuel is quoted on net CV and billed on gross, but the code divided by 1.108 instead of multiplying. At GE1 full load it reported 1,295 kWh per half-hour against 1,590 metered.
- **Unworkable plans:**
  - The engines' hot-water circuit has no radiator, so all its heat must go to the absorption chiller or the LTHW circuit. The old code let it dump heat, e.g. GE1 at 1,200 kW overnight dumping about 250–330 kW.
  - The cooling-tower check counted only the chilled water; it now includes the chillers' compressor power and the absorption chiller's generator heat.
  - The import limit ignored the reactive power the generators supply.
  - Outages were applied only to engines, so B2's all-day outage was ignored. They now apply to every unit, for any half-hour they overlap.
  - PV is now capped at the 280 kW inverter rating.
- **Too many starts and stops:** each half-hour was chosen on its own, with no start costs and ignoring which engines were running at midnight. The engines' on/off pattern is now optimised over the whole day, counting start costs and starting from the midnight state. Each start's cost goes into its half-hour.
- **Other:** weather and PV rows were matched by UTC date, an hour out in summer time. Weekend rates were worked out from the UTC date, so a summer-time Monday was priced as Sunday. Engine fuel and heat now follow all three part-load points, not a straight line between minimum and rated output. Each engine segment is solved separately because the heat curve bends the wrong way for a single linear model.

**Checks:**
- Runs in about 0.6 s and gives byte-identical output across runs.
- On 8 made-up days (winter, spring/autumn, a hot Saturday, summer-time Monday/Sunday, partial and multi-unit outages) the costs match the whole-day solver to within £0.0005.

**Decision for you:** the data doesn't say exactly how much heat the 40/35 °C intercooler circuits can pass to the air handling units' circuit when that runs hotter in cool weather. I treat them as preheating the return water, using both supply and return temperatures. It makes no difference on 21 July (outside 19.9–28.8 °C, so the AHU circuit runs at 34/29 °C). On cool days, the stricter reading (no recovery unless the AHU flow is at or below 40 °C) would cost 0.1–0.4% more.

**Two behaviours that may surprise you:**
- If no plant set-up in a half-hour can stay within the 1,220 kVA connection, the plan now goes over the limit as little as possible and marks that half-hour `grid_ok: false`, rather than crashing.
- The absorption chiller is treated as unavailable whenever the tower water is below its 22 °C minimum, as the original code had it. On a cool night with little heat demand, that can make a day impossible to plan within the connection.

The plan is written to `/output/plan.json`. My test scripts are in `/tmp/work`, outside `/app`, and the data files are untouched.

- turns 3, 0.3 min, error=False

Both reviews are still running and neither has reported back yet, so there are no findings to act on. The plan in `/output/plan.json` is unchanged. I'll pick their findings up as soon as either one finishes, or check again in about 20 minutes.

- turns 21, 11.9 min, error=False

I've acted on both reviews; one modelling rule changed as a result. On the given day the plan is unchanged: £6,235.28, 69,688 kWh of gas (gross CV), 3 engine starts. It's written to `/output/plan.json`, and repeat runs give an identical plan in under a second.

**What the reviews found:**
- **Bug hunt (it didn't see my list):** it found the same 12 bugs I had fixed and nothing new. Its own corrected optimiser arrived at exactly the same plan.
- **Critique of my fixes:** no code or accounting errors. Its own checker and whole-day optimiser confirm the plan is consistent and least-cost.

**Changed as a result:**
- **AC1 in cool weather:** I had kept the original rule that stops AC1 whenever the tower water would be below its 22 °C minimum. Both reviewers argued against it, and I agree. The fans are variable speed and 21 °C is only the towers' minimum leaving temperature, so they can hold 22 °C while AC1 runs. The electric chillers then run slightly less efficiently, and each half-hour the planner now picks the cheaper of the two settings.
  - This doesn't affect 21 July, where the tower water is above 22 °C all day.
  - On my cool test days it cuts cost by about £900–1,030 a day.
  - A cool night that used to exceed the 1,220 kVA connection is now feasible.
- **Day totals:** the summary is now the exact sum of the rounded half-hour figures. Previously the cost total could differ by £0.001.
- **Small robustness changes:**
  - An empty (`null`) outage list or running-at-midnight list in `status.json` is now accepted.
  - The error raised when a day genuinely can't be met now says what that means.

**Checks:** all 9 test days that can be planned pass my independent checker and match the whole-day optimiser. Of the two that can't, the extreme hot day is planned with `grid_ok: false` where the connection can't hold. The day with a tower cell out at peak cooling stops with a clear error.

**Still uncertain, kept as is:** how much heat the 40 °C intercooler circuits can pass to the air handling units' circuit in cool weather. I treat them as preheating its return water. The reviewers split on this. The stricter reading (no recovery unless that circuit runs at or below 40 °C flow and 35 °C return) costs about 0.2–0.4% more on cool days and gives the same engine starts.
