# Official trials (v19)

## ecd19-run1-claude / energy-centre-dispatch-v19__Cvhgm2b

- agent: `claude-code` with `anthropic/claude-opus-5-5`
- reward: **0**; exception: None; agent time: 26.7 min
- verifier: 8 failed, 37 passed, 10 errors in 0.89s
  - failed `test_units_within_ratings_and_availability[h1]`
  - failed `test_connection_limits[h1]`
  - failed `test_least_cost[h1]`
  - failed `test_units_within_ratings_and_availability[h2]`
  - failed `test_connection_limits[h2]`
  - failed `test_connection_limits[h4]`
  - failed `test_least_cost[h4]`
  - failed `test_same_plan_every_time[h3]`

What the agent's tool does on each verifier day:

```
visible: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6303.56 vs least  6303.56 (+0.00)
h1: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess  378.7 | cost  7143.75 vs least  6426.65 (+717.10)
h2: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess   12.7 | cost  8074.61 vs least  8879.73 (-805.12)
h3: tool failed: RuntimeError: no feasible loading at 13:30
h4: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess  534.8 | cost  7756.50 vs least  7310.97 (+445.52)
```

Agent's closing message:

> I've fixed the tool and the plan is in `/output/plan.json`. For 21 July it costs **£6,303.56**, burns **64,944 kWh** of gas as billed, starts engines **2 times**, and stays within the grid connection's limits in every half-hour. The data files are unchanged, the output format is the same, and a run takes about 0.6 s and gives byte-identical output each time.
>
> ## What was wrong
> **Why the gas forecast was too low**
> - **Wrong gas conversion.** Engine fuel is given on a net-CV basis, but gas is billed on gross CV. Billed gas is net × 1.108; the code divided by 1.108, so engine gas came out about 18% too low.
> - **Middle part-load point ignored.** The engines' fuel and heat curves used only their minimum and rated points; they now follow all three.
>
> **Why the plans weren't workable**
> - **Intercooler heat counted as useful.** It goes to the LT radiators and can't be recovered; only jacket-water and exhaust heat can.
> - **Engine heat could be dumped.** The engine hot-water circuit has no dump radiator, so all of its heat must go to the absorption chiller or through PHE1 to the buildings. The old plan ran GE1 at full output all night and threw the heat away. This limit now decides how hard the engines can run.
> - **Cooling towers under-loaded.** They must reject the chillers' electricity or heat input as well as the cooling they produce.
> - **Engines' reactive power ignored in the 1220 kVA import limit.** The engines run at a fixed power factor of 0.95 and supply reactive power to the site.
> - **Weather an hour out.** Weather rows were picked by UTC date, putting them an hour off the local half-hours in summer.
> - **Weekend rates on the wrong day.** The weekday was taken from UTC, so in summer Saturdays were priced as weekdays and Mondays as weekends.
> - **Outages only applied to engines.** They now apply to every unit (B2 was out all day), including half-hours an outage only partly covers.
>
> **Why it started and stopped engines too often**
> - **Start costs ignored.** It picked the cheapest option for each half-hour on its own. It now plans the whole day at once, charging each start (£38 for GE1, £27 for GE2) in the half-hour the engine starts.
> - **Midnight state ignored.** Engines already running at midnight are now taken into account, and starts in the first half-hour are counted.
>
> The resulting plan follows the heat demand. GE2 runs at full output overnight and during GE1's outage, and GE1 takes over from 11:00. Every half-hour's cost now includes running costs and any start costs.
>
> ## How I checked it
> - **Independent checker:** recomputes every figure in a plan from the raw data files (energy balances, heat circuits, towers, kVA, outages, gas, cost, start count and totals). The plan passes all checks, and I worked two half-hours out by hand as well.
> - **Separate whole-day optimiser:** it matched the tool's cost to within £0.002 on every feasible test day. That covered weekends and winter dates, different midnight states, outages of each kind of unit, and higher gas prices that push the import up to the kVA limit.
>
> ## Decisions for you
> - **Cool nights can have no workable plan.** The absorption chiller needs cooling water at 22 °C or warmer, and the towers deliver max(wet bulb + 4, 21) °C, so it can't run when the wet bulb is below 18 °C. On a summer night like that, the import limit needs an engine running but nothing can take its heat. I kept the existing 22 °C rule; letting the towers hold the water at 22 °C would be a plant-operation decision. On days that really can't be met, the tool keeps the grid overrun as small as possible and sets `grid_ok` to false. If the cooling or heat demand itself can't be met, it stops with an error.
> - **PV:** the forecast is capped at the 280 kW inverter rating. This has no effect on this day, because the forecast peaks at 267 kW.
>
> All the changes are in `planner/` (mostly `optimize.py` and `plant.py`), plus one line in `dispatch.py`.

## ecd19-run2-claude / energy-centre-dispatch-v19__V6R3e25

- agent: `claude-code` with `anthropic/claude-opus-5-5`
- reward: **1**; exception: None; agent time: 105.4 min
- verifier: 55 passed in 0.94s

What the agent's tool does on each verifier day:

```
visible: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6303.56 vs least  6303.56 (+0.00)
h1: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6420.84 vs least  6426.65 (-5.80)
h2: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  8879.74 vs least  8879.73 (+0.01)
h3: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  5375.54 vs least  5375.54 (-0.00)
h4: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  7296.10 vs least  7310.97 (-14.87)
```

Agent's closing message:

> There was nothing left to do: the independent review had already finished, and I'd compared it with the fixes in my last update. I've stopped the scheduled check-ins.
>
> The review agreed with every fix and every judgement call; its reference plan for 21 July came to about £6,304, against the tool's £6,303.56. It raised two small points, which I applied:
> - **Connection limit in both directions.** The kVA limit now applies when the site exports as well as imports. It can't bind with this plant (well under 1220 kVA either way), and today's plan is byte-identical.
> - **Overload warning.** When the connection can't carry the site, the tool now prints a warning naming the half-hours, as well as setting `grid_ok: false` on them.
>
> After both changes the plan still passes the independent checker, and still matches the separate whole-day optimisation on all the test days.

