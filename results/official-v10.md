# Official trials (v10)

## ecd10-run1-claude / energy-centre-dispatch__KVPQAHm

- agent: `claude-code` with `anthropic/claude-opus-5-5`
- reward: **0**; exception: None; agent time: 32.7 min
- verifier: 5 failed, 40 passed, 10 errors in 1.09s
  - failed `test_connection_limits[h1]`
  - failed `test_least_cost[h1]`
  - failed `test_connection_limits[h4]`
  - failed `test_least_cost[h4]`
  - failed `test_same_plan_every_time[h3]`

What the agent's tool does on each verifier day:

```
visible: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6445.04 vs least  6445.04 (-0.00)
h1: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess  378.7 | cost  7007.60 vs least  6423.18 (+584.42)
h2: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  7569.29 vs least  7569.29 (-0.00)
h3: tool failed: RuntimeError: no feasible loading at 13:30
h4: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess  534.8 | cost  7654.56 vs least  7264.74 (+389.82)
```

Agent's closing message:

> The tool now produces a workable plan. For 21 July it costs **£6,445.04**, burns **60,768 kWh** of gas (gross CV, as billed), imports 15,666 kWh and uses **3 engine starts**. It stays within the connection limits in every half-hour. It runs in about 0.6 s and gives byte-identical output on every run. The output format is unchanged, and the data files are untouched.
>
> The old plan's £4,513 was never achievable. It dumped engine heat that has nowhere to go, ran the absorption chiller (AC1) beyond what the chilled water allows, and under-stated the engines' gas by about 23%.
>
> **What was wrong**
> - **Gas:** the engines' fuel figures (net CV) were *divided* by 1.108 instead of multiplied to get the gross CV the gas is billed on. That's the "forecast well below the meters" complaint.
> - **Starts:** engines were chosen half-hour by half-hour, with no start costs and no regard for which engines were running at midnight. Starts were also missing from the cost. Which engines run is now chosen over the whole day, and each start is charged to the half-hour it happens in.
> - **Weather:** rows were picked by UTC date, so in summer time every half-hour used weather from an hour later.
> - **Weekday:** the tariff worked out the day from the UTC time of local midnight. On a summer Monday it would charge weekend rates, and on a Saturday weekday rates.
> - **Engine curves:** fuel and heat were treated as straight lines from minimum to rated output, ignoring the middle point of each table.
> - **Heat circuits**, following the connections in `plant.json`:
>   - Only the jacket-water and exhaust (HT) heat is useful. GE1's intercooler heat goes to the cooling towers, and GE2's goes to its radiator.
>   - The HT circuit has no dump radiator, so all of its heat must go to AC1 or to the heating circuit.
>   - EC2 is air-cooled: its efficiency depends on the outdoor temperature, and its heat doesn't go to the towers.
>   - AC1 can't cool the chilled water below 8 °C, so it can carry at most ⅔ of the cooling load.
> - **Connection:** the kVA limit ignored the reactive power the engines supply (fixed 0.95 power factor). The plan now holds the real apparent-power limit and the 250 kW export limit.
> - **Smaller fixes:** outages of tower cells, PV, PHE1 and LTX1 are now taken into account. An outage covering any part of a half-hour now takes the unit out for that whole half-hour. PV is capped at the 280 kW inverter rating.
>
> **Why the plan looks the way it does:** because the HT heat has nowhere else to go, it limits when the engines can run.
> - **Overnight:** GE1's heat even at minimum load can't be absorbed, so GE2 runs instead.
> - **Never together:** two engines make more heat for less power than GE1 alone at full output.
> - **Evening peak:** expect about 600 kW of import from 16:00 to 19:00.
>
> **How I checked it**
> - **Plan audit:** a separate auditor recomputes every figure from the data files (balances, limits, gas, cost, starts) and finds no problems.
> - **Optimality:** a separately written whole-day optimisation finds the same cost and the same engine schedule.
> - **Other days:** I generated about 57 test days covering summer Mondays and weekends, winter days, outages of each unit, outages starting mid-half-hour, high PV and exporting days. Wherever a plan within the limits exists, the tool matched or beat the separate optimisation. Where it beat it, I confirmed the tool's plan meets all the same constraints; the solver had stopped short.
>
> **Decisions for you**
> 1. **AC1 on cool days:** AC1 needs cooling water at 22 °C or more, but the towers hold 21 °C when the wet bulb is under 18 °C. So on those days AC1 is off, as in the original code. On a cool summer night the engines then have nowhere to put their heat, and the site can't stay within the 1220 kVA connection. If operators raise the tower setpoint to 22 °C when AC1 runs, the model needs changing; tell me if that's how they run it.
> 2. **Days with no workable plan:** if the import capacity can't be met, the tool exceeds it by as little as possible and marks those half-hours `grid_ok: false`. It doesn't crash. If heat or cooling demand can't be met at all, it stops with an error naming the half-hour.
> 3. **PV curtailment:** the tool may turn PV down, but only to stay within the 250 kW export limit. This hasn't happened on any test day.
>
> The checking scripts are in `/tmp/check` and aren't part of the tool.

## ecd10-run1-codex / energy-centre-dispatch__G7eMeB2

- agent: `codex` with `openai/gpt-6.1-sol`
- reward: **0**; exception: None; agent time: 29.4 min
- verifier: 3 failed, 22 passed, 30 errors in 0.85s
  - failed `test_same_plan_every_time[h1]`
  - failed `test_same_plan_every_time[h3]`
  - failed `test_same_plan_every_time[h4]`

What the agent's tool does on each verifier day:

```
visible: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6445.04 vs least  6445.04 (-0.00)
h1: tool failed: RuntimeError: no feasible loading at 00:00
h2: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  7569.29 vs least  7569.29 (-0.00)
h3: tool failed: RuntimeError: no feasible loading at 13:30
h4: tool failed: RuntimeError: no feasible loading at 00:00
```

Agent's closing message:

> Fixed the tool and generated [plan.json](/output/plan.json). Corrected gas billing, weather alignment, plant performance, heat balances, cooling limits, reactive power and day-wide engine scheduling with start costs.
>
> The supplied day costs **£6,445.044**, uses **60,767.903 kWh of billed gas**, and requires **3 engine starts**.
>
> All 24 regression tests and 30 varied-day checks pass. Repeated runs produce identical JSON; runtime is about **0.64 seconds** on Python 3.13. Data files and the output schema are unchanged.

## ecd10-run2-claude / energy-centre-dispatch__UeNkcCh

- agent: `claude-code` with `anthropic/claude-opus-5-5`
- reward: **1**; exception: None; agent time: 56.1 min
- verifier: 55 passed in 1.31s

What the agent's tool does on each verifier day:

```
visible: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6445.04 vs least  6445.04 (+0.00)
h1: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6423.19 vs least  6423.18 (+0.01)
h2: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  7569.29 vs least  7569.29 (-0.00)
h3: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  5327.51 vs least  5327.51 (+0.00)
h4: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  7264.74 vs least  7264.74 (+0.00)
```

Agent's closing message:

> I've fixed the tool, and `python3 /app/dispatch.py --data /app/data --output /output/plan.json` now produces a workable plan (written to `/output/plan.json`). For 21 July it costs **£6,445.04**, burns **60,768 kWh** of gas and has **3 engine starts**, all within the connection limits. It runs in about half a second and gives the same plan every time. The data files are untouched.
>
> The old plan's £4,513 was unworkable: it ran GE1 flat out all night with nowhere for the engine's heat to go.
>
> **Why the gas forecast was too low**
> - The engines' fuel figures are on the net basis and gas is billed on the gross basis. The tool divided by the 1.108 conversion factor instead of multiplying, so engine gas was about 18% low.
> - Engine fuel and heat were drawn as straight lines from minimum to rated output, ignoring the middle part-load point.
> - The intercooler heat was counted as useful. In fact GE1's goes to the cooling towers and GE2's to its radiator.
> - The engines' main heat circuit only feeds the absorption chiller (AC1) and the heat exchanger to the heating circuit; it has no dump. The tool let engines waste heat. GE1 at minimum load makes 835 kW of heat, more than those two can absorb on a summer night, so it now stops at midnight and GE2 runs overnight, following the heat load.
>
> **Why the engines started and stopped too often**
> - Each half-hour was optimised on its own with no start costs. The engine schedule is now chosen over the whole day with each start costed, starting from the engines running at midnight. Start costs now appear in the cost of the half-hour the engine starts.
>
> **Other errors fixed**
> - Weather was matched by UTC date, so in summer time it was an hour out.
> - Weekends were judged from the UTC date, so Mondays were priced as weekend and Saturdays as weekday.
> - AC1 sits first on the chilled-water return and can only cool it from 12 °C to 8 °C, so it can carry at most two-thirds of the cooling load.
> - EC2 is air-cooled: its efficiency depends on outdoor air temperature and it doesn't load the towers.
> - The import limit ignored the reactive power the generators supply.
> - Outages of tower cells and PV were ignored, as were outages that don't start on the half-hour. PV wasn't capped at its 280 kW inverter rating.
>
> **How I checked it**
> - An independent checker, written without using the tool's code, confirms every period's balances, limits, gas, costs and day totals.
> - A separately formulated whole-day optimisation finds the same schedule and cost. On 130 test days (weekends, a winter day, outages, cool weather) every day it could solve matched to within £0.006.
> - An independent reviewer found no errors and reproduced the figures by hand. I made its robustness suggestions, for odd outage times and solver failures.
>
> **Decisions for you to confirm**
> - **Cool days:** when the towers' water would be colder than AC1's 22 °C minimum, the tool slows the tower fans to hold 22 °C rather than locking AC1 out. EC1 loses a little efficiency as a result. Under the old lock-out rule, my synthetic cool spring days had no workable plan.
> - **Days that can't be met:** if no way of running the plant keeps a half-hour within the import capacity, the tool exceeds it by as little as possible and marks that half-hour `grid_ok: false`, rather than producing no plan.
> - **Outage times and names:** an outage whose end time is earlier than its start runs past midnight into the next day. An outage naming a unit that isn't in `plant.json` is ignored with a warning.
> - **Minor details:**
>   - PV may be cut back, but only if the 250 kW export limit is reached.
>   - The summary's `import_kwh` and `export_kwh` carry four decimals rather than three, so they equal the half-hourly figures exactly.

