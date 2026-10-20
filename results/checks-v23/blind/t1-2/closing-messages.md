# Closing messages of the agent (each `result` event)

- turns 60, 56.5 min, error=False

The tool now gives a least-cost plan the plant can actually run. For 21 July it costs **£6,235.28**, burns **69,688 kWh** of gas and makes **3 engine starts**; the plan is in `/output/plan.json`. All the fixes are in `planner/`. `dispatch.py`, the plan format and the data files are unchanged.

**Why the gas forecast was low:** engine fuel is quoted on net CV but billed on gross CV. The tool divided by the 1.108 ratio instead of multiplying, so engine gas came out at about 81% of what the meter reads. For GE1 at full load that is 1,295 kWh per half-hour instead of 1,590.

**Why it started and stopped the engines too often:** it picked each half-hour on its own and ignored the £38 and £27 start costs. It now plans the whole day at once with those costs. A start at 00:00 is counted against the engines running at midnight, and each half-hour's cost now includes its starts.

**Other faults I fixed:**
- **Engine heat:** the old plans threw away up to 456 kW of engine heat in 37 half-hours. The engines' hot-water circuit has no radiator, so that heat can only go to the absorption chiller or to the heating, which limits how hard the engines can run on summer nights.
- **Weather and PV:** the forecast was taken by UTC date, so in summer time it was an hour out.
- **Weekday vs weekend:** this was decided in UTC, so in summer time every Monday was priced at weekend rates and every Saturday at weekday rates.
- **Outages:** only engine outages were applied, so B2's all-day outage was ignored. Outages are now applied to any unit, for any half-hour they touch.
- **Engine curves:** fuel and heat ignored the middle part-load point.
- **Cooling towers:** their load was counted as the cooling only. It now includes chiller power and the absorption chiller's firing heat.
- **Grid limit:** the 1220 kVA check ignored the reactive power the generators supply. The `grid_ok` flag now uses the same check.
- **Intercooler heat:** it was used for the air handling units whatever their circuit temperature.
- **PV:** output is now capped at the 280 kW inverter rating.

**Checking:**
- A separate script recomputes every figure in the plan from the data and finds no problems.
- An independent whole-day solver matches the tool's cost to the penny on 21 July and on about 20 made-up days. These covered winter, spring and summer, weekends, both clock offsets, outages and days where the grid limit binds.
- An independent review found no material defects; I fixed the two small outage-time edge cases it raised.
- Each run takes under a second, and repeat runs give identical output.

**Two judgement calls.** Neither changes the 21 July plan, but both matter on cooler days:
1. **Absorption chiller on cool days:** it needs cooling water at 22 °C or warmer, and the towers would otherwise run down to 21 °C. I've assumed the variable-speed tower fans hold the water at 22 °C while it runs, which costs the electric chillers a little efficiency. The alternative, keeping it off, would leave ordinary summer nights with no workable plan: the engines couldn't shed their heat, and import alone exceeds the connection.
2. **Intercooler heat to the air handling units:** it can only preheat that circuit's return water up to 40 °C, and only cool the intercooler water down to that return temperature. A simpler rule (use it only when the circuit runs at 40 °C or below) would cost 0.03–0.9% more on mild days.

**Decision for you:** when the connection can't carry the load in some half-hour (say both engines out on a heavy day), the tool now keeps the overload as small as possible and marks those half-hours `grid_ok: false` instead of failing. I added this so engineers still get a plan to act on. If you'd rather it stop with an error, as it did before, it's a small change. Any other impossible day, such as too little cooling-tower capacity, still stops with an error naming the half-hour.
