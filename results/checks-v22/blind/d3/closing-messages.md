# Closing messages of the agent (each `result` event)

- turns 51, 30.9 min, error=False

The tool now produces a plan I've checked independently. For 21 July it costs **£5,346.57**, uses **91,008 kWh** of gas (the old tool said 74,714) and has **2 engine starts**, with the connection within limits all day. The output format is unchanged, and the plan is in `/output/plan.json`.

**What was wrong**
- **Gas too low:** engine fuel figures are on the net CV basis and gas is billed gross, but the conversion divided by 1.108 instead of multiplying, so engine gas was about 18% low. Fuel and heat also ignored the middle point of each engine's part-load table.
- **Heat circuits:** intercooler heat was counted as useful, but it goes to the LT radiators, whose capacity wasn't modelled either. The tool also assumed spare engine heat could be dumped, but only the exhaust can be bypassed. Jacket-water heat has to go to the absorption chiller (AC1) or the buildings' LTHW circuit, which limits when the engines can run.
- **Cooling towers:** they have to reject the chillers' compressor work and AC1's firing heat as well as the cooling. AC1 at full load rejects 2.4 times its cooling.
- **Connection limit:** the kVA limit and `grid_ok` ignored the reactive power the generators supply.
- **Time:** in summer time, weather and PV were read an hour late. The day of the week came from UTC, so in summer a Monday was priced at weekend rates and a Saturday at weekday rates.
- **Outages:** only engine outages were applied (B2 is out all day). Now every unit's outage counts, including one that covers only part of a half-hour.
- **Starts:** each half-hour was optimised on its own with no start costs. The day is now planned as a whole, starting from the engines running at midnight. Starts at 00:00 are counted, and each start's cost is in its half-hour's cost.

**How I checked it**
- A separate checker rebuilds every balance, limit, gas figure, cost and start count from the raw data, and finds no errors.
- A completely different whole-day optimisation finds the same optimum and schedule.
- On 46 made-up days (winter, weekends, Mondays, assorted outages) the two agree to within £0.01.
- The same data gives the same plan every time, and a run takes about 0.7 s.
- These scripts are in `/tmp/verify`.

**Behaviour to know about**
- If demand can't be met within the import capacity (for example both engines out), the plan goes over it by as little as possible and marks those half-hours `grid_ok: false`.
- If the plant itself can't meet demand, the tool stops with "no feasible loading at HH:MM", as before.

**Decision for you:** I kept the original rule that AC1 runs only when tower water, at the higher of wet bulb + 4 K or 21 °C, reaches AC1's 22 °C minimum. If your operators hold the towers at 22 °C whenever AC1 runs, the cost changes vary by season:
- **Summer days, including 21 July:** no difference.
- **Winter days:** about 0.1–0.4% cheaper.
- **Cool spring and autumn days:** 10–30% cheaper, because without AC1 the engines' jacket heat has nowhere to go beyond the LTHW load.

If they do hold the towers, the tool should change; it's a small change.
