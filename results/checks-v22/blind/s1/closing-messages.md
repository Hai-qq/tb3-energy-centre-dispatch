# Closing messages of the agent (each `result` event)

- turns 50, 34.9 min, error=False

The tool now produces a correct plan, and `/output/plan.json` has been written. For 21 July it costs £6,303.56 with 2 engine starts: GE2 starts at midnight and covers the night and GE1's 07:00–11:00 outage, and GE1 restarts at 11:00. Each run takes about 0.6 s and gives byte-identical output. The data files and the plan format are unchanged.

**What was wrong**
- **Gas too low (the meter complaint):** two causes.
  - Engine fuel, given on net calorific value, was divided by 1.108 instead of multiplied to get the billed gross figure.
  - Intercooler heat was counted as useful heat, so the plan assumed boilers were burning less gas than they would. Per the circuit layout, that heat can only go to the LT radiators (440 kW).

  On its own plan, the old tool reported 74.7 MWh of gas where the meters would read 91.6 MWh.
- **Too many starts:** each half-hour was optimised on its own, start costs were never charged, and the engines running at midnight were ignored. The whole day is now planned at once, with start costs, from the midnight state.
- **Unworkable plans:**
  - The HT circuit was allowed to dump heat, but it has no dump. The old plan ran GE1 at full output all night and threw away about 300 kW of heat.
  - Fuel and heat were interpolated only between the minimum and rated points, skipping the middle part-load point.
  - Weather and PV were taken by UTC date, so they were an hour out in summer time.
  - Weekend rates were judged from the UTC timestamp of local midnight, so in summer time a Saturday was treated as a weekday and a Monday as a weekend day.
  - Outages were applied to engines only, so B2 was used while out of service.
  - The cooling towers were checked against the cooling load alone, leaving out the compressor work and AC1's firing heat. They were also always credited with both cells.
  - The connection limit and `grid_ok` ignored the reactive power the generators supply.

The heat circuits are now built from `heat_circuits` in `plant.json`, so an outage of any listed plant is handled, including PHE1 and the LT heat exchangers.

**How I checked it**
- I wrote a plan checker and a full-day mixed-integer program, both separate from the tool's code. The checker recomputes every balance, limit, gas, cost and start figure from the raw data. The mixed-integer program re-solves the whole day from scratch.
- The checker finds no problems in the new plan and 225 in the old one.
- On 21 July the tool's plan cost matches the independent solve exactly.
- I also ran 12 designed days and 200 random ones: weekends, winter days on GMT, varied outages and loads. The tool matched the independent solve to within £0.001 on every feasible day, and the two agreed on which days had no feasible plan.

**Decision for you:** AC1 needs its cooling water at 22 °C or warmer, but the towers make water as cold as 21 °C. I let the towers hold the water at 22 °C whenever AC1 runs; the fans are variable speed and 21 °C is only a minimum. The electric chillers then work against 22 °C water, which is slightly less efficient.
- **Why:** under the strict reading (no AC1 whenever the towers make water below 22 °C), an ordinary summer night becomes impossible to plan. An engine has to run at night to keep imports within the 1,220 kVA connection, and only AC1 can take its surplus heat. Winter days would also cost 16–23% more.
- **If you disagree:** it's a short change where `_Period` sets `condenser_c` in `planner/optimize.py`.

**Two smaller behaviours**
- PV may be held back, but only the export limit ever calls for it.
- On a day where no plan can meet the demand within the plant and connection limits, the tool stops with an error naming the first half-hour that can't be met, rather than writing a plan.
