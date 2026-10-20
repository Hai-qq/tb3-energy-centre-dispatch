# Official trials (v17)

## ecd17-run1-claude / energy-centre-dispatch-v17__ZWTqkVF

- agent: `claude-code` with `anthropic/claude-opus-5-5`
- reward: **0**; exception: None; agent time: 132.9 min
- verifier: 4 failed, 11 passed, 40 errors in 0.62s
  - failed `test_same_plan_every_time[h1]`
  - failed `test_same_plan_every_time[h2]`
  - failed `test_same_plan_every_time[h3]`
  - failed `test_same_plan_every_time[h4]`

What the agent's tool does on each verifier day:

```
visible: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6303.56 vs least  6303.56 (+0.00)
h1: tool failed: ValueError: outage of unknown plant: EC1 condenser
h2: tool failed: ValueError: outage of unknown plant: GE1 LT radiator, GE1 intercooler
h3: tool failed: ValueError: outage of unknown plant: AC1 absorber and condenser, GE2 LT radiator
h4: tool failed: ValueError: outage of unknown plant: GE1 LT radiator, GE1 intercooler
```

Agent's closing message:

> Nothing more to do. The review agent reported earlier and I've already acted on its findings. It found no material bugs and agreed with each of my decisions. I closed the checks it had left open: the towers reaching capacity while held at 22 °C, a worst-case run time of under 1 s, and plans for days where the grid limit can't be met. I then regenerated `/output/plan.json` and it passed a strict check. No further checks are scheduled.

## ecd17-run2-claude / energy-centre-dispatch-v17__uN8xwS5

- agent: `claude-code` with `anthropic/claude-opus-5-5`
- reward: **0**; exception: None; agent time: 28.2 min
- verifier: 4 failed, 51 passed in 0.96s
  - failed `test_units_within_ratings_and_availability[h1]`
  - failed `test_units_within_ratings_and_availability[h2]`
  - failed `test_units_within_ratings_and_availability[h3]`
  - failed `test_units_within_ratings_and_availability[h4]`

What the agent's tool does on each verifier day:

```
visible: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6303.56 vs least  6303.56 (+0.00)
h1: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6403.31 vs least  6426.65 (-23.34)
h2: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  7904.02 vs least  8460.68 (-556.67)
h3: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  5182.63 vs least  5345.19 (-162.56)
h4: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  7270.94 vs least  7310.97 (-40.03)
```

Agent's closing message:

> The tool now produces a workable least-cost plan. For 21 July it costs **£6,303.56**, burns **64,944 kWh of gas** (gross CV, as billed), and makes **2 engine starts**. GE2 starts at midnight, covers the night and GE1's 07:00–11:00 outage, and then GE1 restarts at 11:00 and runs alone. The old plan reported £4,513 and 74,714 kWh. Its gas was about 18% short of what its own engine and boiler outputs would actually burn (91,600 kWh), and it relied on getting rid of engine heat the plant has no way to reject.
>
> **What was wrong:**
> 1. **Gas basis:** engine fuel is on net CV, billing is on gross. The tool divided by the 1.108 ratio instead of multiplying, which is the main reason gas forecasts were low on days the engines ran.
> 2. **Part-load tables:** fuel and heat were treated as straight lines from minimum to rated output instead of following the tables' points.
> 3. **Heat circuits:**
>    - Intercooler (LT) heat was counted as useful, but it only goes to the radiators.
>    - There is no dump on the engine HT circuit, yet the tool let surplus heat disappear. It planned GE1 at full output at night when only about 770 kW of it could be absorbed.
> 4. **Weather alignment:** forecast rows were picked by UTC date, which put the weather an hour out in summer time.
> 5. **Weekday:** the day of the week was worked out in UTC, so a summer Saturday was priced as a Friday and a Monday as a Sunday.
> 6. **Outages:** only engine outages were applied, so the all-day B2 outage was ignored. An outage now removes a unit for any half-hour it overlaps.
> 7. **Connection limit:** the 1,220 kVA check ignored the reactive power the generators supply.
> 8. **Cooling towers:** the heat they reject left out the chillers' compressor power and the absorption chiller's driving heat, and tower cell outages were ignored.
> 9. **Engine starts:** each half-hour was optimised on its own, ignoring start costs and the engines running at midnight. That is the over-cycling the engineers saw. Engine on/off is now chosen across the whole day, start costs are in the cost, and a start at 00:00 is counted.
> 10. **PV:** output wasn't capped at the 280 kW inverter rating.
>
> The output format is unchanged, and gas and cost are now calculated from the unit outputs. The changes are in `planner/data.py`, `plant.py`, `tariff.py` and `optimize.py`, plus one line in `dispatch.py`.
>
> **Checks:** I wrote a separate checker that recalculates every figure from the data files alone. I also built a whole-day optimisation model with a different method. On this day and 11 made-up feasible days (winter, weekend, cool nights, various outages, connection limit binding), the tool matched that model's optimum to within a penny and passed every check. A run takes about 0.5 s, and repeated runs give an identical plan.
>
> **Decisions for you to confirm:**
> - **Absorption chiller on cool days.** AC1 needs cooling water at 22 °C or warmer. The old tool switched it off whenever the towers would naturally give colder water. I assumed the variable-speed tower fans can hold the shared condenser water at 22 °C, with the electric chillers then working at 22 °C too. Under the old rule, any night with a wet bulb below about 18 °C has no plan within the connection limit. Without AC1 the engines' minimum heat has nowhere to go, and without the engines the site needs more than 1,220 kVA. It makes no difference on 21 July. If the plant can't actually hold the water warmer, this is a small change in `condenser_settings`.
> - **Days the connection can't supply.** Instead of crashing, the tool plans the smallest possible overload and sets `grid_ok: false` for those half-hours. It still stops with an error if the plant itself can't meet the heat or cooling.
> - **Safety margins.** The plan stays 0.001 kVA under the import limit and 0.005 kW under the towers' capacity, so the 3-decimal figures in the plan never show a breach. This costs under £0.001.
>
> I ran the command, so `/output/plan.json` holds the plan for 21 July. My test scripts are in `/tmp/work` and aren't part of the tool.

## ecd17-run3-claude / energy-centre-dispatch-v17__YQ9Rmi3

- agent: `claude-code` with `anthropic/claude-opus-5-5`
- reward: **0**; exception: None; agent time: 27.5 min
- verifier: 7 failed, 38 passed, 10 errors in 0.72s
  - failed `test_units_within_ratings_and_availability[h1]`
  - failed `test_connection_limits[h1]`
  - failed `test_least_cost[h1]`
  - failed `test_units_within_ratings_and_availability[h2]`
  - failed `test_connection_limits[h4]`
  - failed `test_least_cost[h4]`
  - failed `test_same_plan_every_time[h3]`

What the agent's tool does on each verifier day:

```
visible: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6303.56 vs least  6303.56 (+0.00)
h1: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess  378.7 | cost  7143.74 vs least  6426.65 (+717.10)
h2: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  7579.70 vs least  8460.68 (-880.99)
h3: tool failed: RuntimeError: no loading of the plant meets the demand at 13:30
h4: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess  534.8 | cost  7756.49 vs least  7310.97 (+445.52)
```

Agent's closing message:

> I've fixed the dispatch tool. `python3 /app/dispatch.py --data /app/data --output /output/plan.json` now produces a least-cost plan that stays within the plant and connection limits. It runs in about 0.6 s, gives the same output every run, and keeps the original format. The data files are unchanged.
>
> **Plan for 2026-07-21:** £6,303.56, 64,944 kWh of gas, 2 engine starts, every half-hour within the connection limits.
> - GE2 runs 00:00–11:00 at 800 kWe. That is cheaper overnight than keeping GE1 on, and GE1 is out 07:00–11:00 anyway.
> - GE1 starts at 11:00 and runs to midnight. Late in the evening it is turned down because there is nowhere to put its heat.
> - AC1 takes the engines' surplus heat, and the boilers aren't needed.
>
> **Why the gas forecast was low**
> - Engine fuel is on a net CV basis and gas is billed on gross CV. The tool divided by 1.108 instead of multiplying, so engine gas came out about 19% low.
> - It counted the intercooler heat as useful, but that heat goes to the LT radiators. The boilers' real top-up gas was therefore missing.
> - Fuel and heat were a straight line from minimum to rated output, ignoring the middle part-load point.
>
> **Why it started and stopped the engines so often**
> - It chose each half-hour on its own and ignored the £38/£27 start costs. It now plans the whole day at once, including start costs.
> - It didn't count starts against the engines running at midnight, and per-period costs left out the start costs.
>
> **Why the plans weren't workable**
> - **Engine heat:** the HT circuit has nowhere to dump heat, only AC1 and PHE1 to the buildings. The old tool assumed surplus heat could be thrown away, so it ran both engines flat out all afternoon. This constraint changes the plan most: at peak, GE1 alone at 1,200 kWe beats running both engines.
> - **Cooling towers:** they also have to reject the chillers' compressor work and AC1's driving heat, not just the cooling.
> - **Connection limit:** this now allows for the reactive power the generators supply (they run at a fixed 0.95 power factor).
> - **Outages:** they now apply to all plant (B2 was ignored) and to any half-hour they overlap.
> - **Weather and PV:** they were an hour out against local time.
> - **Weekday or weekend rates:** these were taken from the UTC date, which is the previous day at local midnight in summer.
>
> **How I checked it:** I wrote a separate checker that reads only the raw data and re-checks every balance and limit, and recomputes gas, cost and starts. I also solved each day as one whole-day optimisation in a different way. On the real day and 11 made-up days that could be met, both gave the same engine choices and the same cost to within £0.003. The made-up days cover winter, spring, weekends, part-hour outages, PHE1/cooling-tower/PV outages and a binding connection limit. Two more made-up days had no plan that could stay within the connection limit. On those the tool exceeds it as little as it can and sets `grid_ok` to false instead of crashing.
>
> **Assumptions to confirm:**
> - **AC1 on cool days:** I treat AC1 as unavailable whenever the tower water is below its 22 °C minimum (wet bulb under 18 °C). I don't assume the towers can be held warmer to let it run. On a cool night with low heat demand, no engine could then shed its heat, and the plan would breach the connection limit (`grid_ok` false). If the towers' setpoint can be raised in practice, this should be modelled.
> - **Small adjustments:** I keep imports 0.001 kVA under the limit so the rounded figures stay inside it. PV is capped at the 280 kW inverter rating.

## ecd17-run1-codex / energy-centre-dispatch-v17__A4qVNiw

- agent: `codex` with `openai/gpt-6.1-sol`
- reward: **0**; exception: None; agent time: 8.7 min
- verifier: 4 failed, 21 passed, 30 errors in 0.66s
  - failed `test_units_within_ratings_and_availability[h2]`
  - failed `test_same_plan_every_time[h1]`
  - failed `test_same_plan_every_time[h3]`
  - failed `test_same_plan_every_time[h4]`

What the agent's tool does on each verifier day:

```
visible: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6303.56 vs least  6303.56 (+0.00)
h1: tool failed: RuntimeError: no feasible loading at 00:00
h2: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  7904.02 vs least  8460.68 (-556.67)
h3: tool failed: RuntimeError: no feasible loading at 13:30
h4: tool failed: RuntimeError: no feasible loading at 00:00
```

Agent's closing message:

> Fixed the tool and generated [plan.json](/output/plan.json).
>
> Corrected gas billing, plant heat balances, cooling-tower loads, reactive-power limits, outages, forecast timing and day-wide startup optimization. Input data is unchanged.
>
> All 14 regression tests pass, including independent balance and billing checks. Repeated runs produce identical output in about 0.6 seconds.
>
> The day’s plan costs **£6,303.56**, uses **64,944.19 kWh of billed gas**, and requires **2 engine starts**.

## ecd17-run2-codex / energy-centre-dispatch-v17__K6NXJSg

- agent: `codex` with `openai/gpt-6.1-sol`
- reward: **0**; exception: None; agent time: 11.0 min
- verifier: 4 failed, 51 passed in 0.95s
  - failed `test_units_within_ratings_and_availability[h1]`
  - failed `test_units_within_ratings_and_availability[h2]`
  - failed `test_units_within_ratings_and_availability[h3]`
  - failed `test_units_within_ratings_and_availability[h4]`

What the agent's tool does on each verifier day:

```
visible: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6303.56 vs least  6303.56 (-0.00)
h1: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6403.30 vs least  6426.65 (-23.35)
h2: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  7904.02 vs least  8460.68 (-556.67)
h3: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  5182.63 vs least  5345.19 (-162.56)
h4: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  7270.93 vs least  7310.97 (-40.04)
```

Agent's closing message:

> Fixed the tool and generated [plan.json](/output/plan.json). Data files are unchanged.
>
> The plan meets demand and plant and connection limits, with corrected gas billing, heat balances and engine start-cost optimization.
>
> - Total cost: **£6,303.56**
> - Gas: **64,944.186 kWh**
> - Engine starts: **2**
>
> All 16 tests pass. Repeated runs produce identical output; runtime was **0.52 seconds**.

## ecd17-run3-codex / energy-centre-dispatch-v17__NrJUaae

- agent: `codex` with `openai/gpt-6.1-sol`
- reward: **0**; exception: None; agent time: 10.1 min
- verifier: 4 failed, 21 passed, 30 errors in 0.64s
  - failed `test_units_within_ratings_and_availability[h2]`
  - failed `test_same_plan_every_time[h1]`
  - failed `test_same_plan_every_time[h3]`
  - failed `test_same_plan_every_time[h4]`

What the agent's tool does on each verifier day:

```
visible: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6303.56 vs least  6303.56 (+0.00)
h1: tool failed: RuntimeError: no feasible loading at 00:00
h2: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  7579.70 vs least  8460.68 (-880.99)
h3: tool failed: RuntimeError: no feasible loading at 13:30
h4: tool failed: RuntimeError: no feasible loading at 00:00
```

Agent's closing message:

> Fixed the tool and generated [plan.json](/output/plan.json).
>
> Corrected gas billing, engine performance curves, heat routing, tower and grid limits, outages, forecast timing, and whole-day startup optimization.
>
> The plan reports £6,303.560 cost, 64,944.186 kWh gas and 2 engine starts.
>
> All 13 tests pass, including independent balance and billing checks. Repeated runs produce identical output; runtime is about 1 second. Input data was preserved.

