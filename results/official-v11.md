# Official trials (v11)

## ecd11-run1-claude / energy-centre-dispatch__wkc79y5

- agent: `claude-code` with `anthropic/claude-opus-5-5`
- reward: **1**; exception: None; agent time: 43.1 min
- verifier: 55 passed in 41.30s

What the agent's tool does on each verifier day:

```
visible: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6366.31 vs least  6366.31 (+0.00)
h1: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6269.32 vs least  6269.32 (+0.00)
h2: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  7570.07 vs least  7570.07 (-0.00)
h3: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  5195.99 vs least  5195.99 (-0.00)
h4: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  7306.96 vs least  7306.96 (-0.00)
```

Agent's closing message:

> I've fixed the tool, and the plan for 21 July (in `/output/plan.json`) is now workable. It costs £6,366.31, bills 64,944 kWh of gas and has 2 engine starts, with every half-hour within the connection limits. It runs in about 3 seconds and gives a byte-identical plan on every run. The old tool's £4,524 figure isn't a fair comparison, because its plan broke several plant limits and under-counted gas.
>
> To check the results, I wrote two separate checks that don't use the tool's code:
> - **Plan checker:** recomputes every period from the raw data files (energy and heat balances, limits, outages, gas, cost, starts). The new plan passes; the old one fails dozens of checks.
> - **Whole-day optimiser:** solves the same day by a different method. On the real day and 17 test days I built (winter days on GMT, weekends, outages of each kind of plant, the import limit binding, PV curtailment), the tool matched its best cost every time. The largest gap was £0.0015, from the 1 VA safety margin I keep under the import limit.
>
> **What was wrong**
> - **Gas too low:** the engines' gas figures were divided by the 1.108 ratio between gross and net calorific value instead of multiplied by it. That understated engine gas by about 19%, which is what the engineers saw on days the engines run.
> - **Too many starts:** each half-hour was planned on its own, with no start costs and ignoring which engines run at midnight. The tool now plans the whole day at once and adds each start's cost to the half-hour it happens in.
> - **Engine curves:** fuel and heat ignored the middle part-load point, and the intercooler heat was counted as recovered, though it only goes to the LT radiators.
> - **Heat dumped that has nowhere to go:** the engines' HT circuit has no dump radiator, but the plan threw away surplus heat. All of it now has to go to the absorption chiller or, through PHE1, to the buildings. This is why both engines can't run together on a summer day.
> - **Cooling side:**
>   - The absorption chiller's capacity is now read at the actual condenser-water temperature, instead of always taking its best figure.
>   - The towers now carry the compressor work and the absorber's firing heat as well as the cooling.
>   - The fans' power now follows that heat load.
> - **Connection:** the import kVA limit now includes the engines' reactive power.
> - **Data:**
>   - Outages only covered the engines, so B2 was planned to run all day despite being out of service; they now cover all plant.
>   - The weather was an hour out of step under BST.
>   - Weekday or weekend rates came from the UTC date, so a summer Monday was billed at weekend rates.
>
> **Decisions you may want to review**
> - **Tower setpoint:** the old code fixed it at 4 K above the wet bulb, a figure that isn't in the data. The plan now picks the cheapest setpoint in 0.5 °C steps between 21 and 28 °C for each half-hour.
> - **PV curtailment:** the plan may curtail the PV when the 250 kW export limit would otherwise be broken. That only happens when the engines must run for heat; on normal days all the PV is used.
> - **Days that can't be met within the connection:** instead of crashing, the tool now produces a plan that goes over the limit by as little as possible and marks those half-hours `grid_ok: false`. An example is AC1 out on a summer day, when the engines have nowhere to put their heat. A day the plant itself can't meet still stops with an error.
> - **Outages past midnight:** one written with an end time earlier than its start (say 22:00 to 02:00) is treated as running to the end of the plan date.
>
> The changes are in `dispatch.py` and the four modules in `planner/`; the data files and the plan format are unchanged.

