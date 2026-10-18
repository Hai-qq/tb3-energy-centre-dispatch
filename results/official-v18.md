# Official trials (v18)

## ecd18-run1-claude / energy-centre-dispatch-v18__iKEwnVA

- agent: `claude-code` with `anthropic/claude-opus-5-5`
- reward: **0**; exception: None; agent time: 39.1 min
- verifier: 4 failed, 51 passed in 0.99s
  - failed `test_units_within_ratings_and_availability[h1]`
  - failed `test_units_within_ratings_and_availability[h2]`
  - failed `test_least_cost[h3]`
  - failed `test_units_within_ratings_and_availability[h4]`

What the agent's tool does on each verifier day:

```
visible: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6303.56 vs least  6303.56 (+0.00)
h1: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6403.30 vs least  6426.65 (-23.35)
h2: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  8079.08 vs least  8879.73 (-800.65)
h3: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6607.15 vs least  5375.54 (+1231.61)
h4: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  7270.93 vs least  7310.97 (-40.04)
```

Agent's closing message:

> I've fixed the tool. The command now writes a plan that passes every check I wrote, in the same output format. It takes about 0.6 s and produces byte-identical output on every run. The data files are unchanged.
>
> ## What was wrong
>
> **Gas reading low on engine days**
> - Engine fuel is given on a net-CV basis but gas is billed on gross CV. The tool divided by 1.108 when it should multiply, so engine gas came out about 18% low (1.108² ≈ 1.23).
> - It counted the engines' intercooler heat as useful. `plant.json` sends that heat to the LT radiators, so it is never recovered.
> - It drew a straight line from minimum to rated output instead of using all three part-load points.
>
> **Too many starts and stops**
> - Each half-hour was optimised on its own, with no start costs and ignoring which engines were running at midnight.
> - The new optimizer plans the whole day and charges each start in the half-hour it happens.
>
> **Plans that couldn't be run**
> - **Engine heat:** the engines' main (HT) heat circuit has no dump. All of it must go to AC1 or through PHE1 to the buildings, but the tool let engines make heat with nowhere to go. In summer this now caps engine output; running both engines after 11:00 isn't possible.
> - **Cooling towers:** they must take the cooling plus the chillers' electrical input and AC1's heat input, not just the cooling.
> - **Import limit:** the 1,220 kVA limit ignored the reactive power the engines supply to the site.
> - **Outages:** only engine outages were applied, so B2's all-day outage was ignored. Outages now cover every unit, and an outage covering any part of a half-hour blocks the whole half-hour.
> - **Time zones:** the weather was matched by UTC date, an hour out from local time. The weekend tariff was chosen from the UTC date, which is wrong on Saturdays and Mondays in summer.
> - **Reported figures:** each half-hour's cost now includes its starts, and `grid_ok` uses the import and reactive power the plan actually has.
>
> ## Today's plan
> GE2 starts at midnight and runs through GE1's outage. GE1 restarts at 11:00 and runs to the end of the day. That is 2 starts, a total cost of £6,303.56 and 64,944 kWh of gas (gross). This is £12 cheaper than the obvious alternative of keeping GE1 on overnight.
>
> ## How I checked it
> - A separate checker, which doesn't use the tool's code, recomputes every balance, limit, gas and cost figure from the raw files. Today's plan and all valid test days pass.
> - I built about 120 test days (weekends, winter on GMT, odd-time outages of any unit, days where the import limit binds) and solved them independently as a single optimisation (a MILP). The tool was never beaten. The solver I used for that check (HiGHS, in SciPy) sometimes returned "optimal" answers that were worse than the tool's, and those plans of the tool's still passed the checker.
>
> ## One decision for you
> AC1 needs cooling water at 22 °C or warmer, but the towers make water as cold as 21 °C. On nights with a wet-bulb below 18 °C, AC1 then can't run, so the engines have nowhere to put their heat and the site goes over its import limit. In those half-hours only, the tool holds the towers at 22 °C so AC1 can run. Today it never happens (the lowest night wet-bulb is 18.4 °C). Making this an everyday optimisation choice would cut costs on cool days. I left it as a last resort because the plan has no field showing the condenser-water temperature.
>
> If a day still can't be planned within the import limit, the plan is written with `grid_ok: false` and a warning. If demand can't be met at all, for example a cooling-tower cell out on a hot afternoon, the tool stops with an error naming the half-hour.

## ecd18-run2-claude / energy-centre-dispatch-v18__LJCdRwd

- agent: `claude-code` with `anthropic/claude-opus-5-5`
- reward: **0**; exception: None; agent time: 88.4 min
- verifier: 2 failed, 53 passed in 0.97s
  - failed `test_least_cost[h2]`
  - failed `test_least_cost[h3]`

What the agent's tool does on each verifier day:

```
visible: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6303.56 vs least  6303.56 (+0.00)
h1: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6426.65 vs least  6426.65 (+0.00)
h2: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  8895.13 vs least  8879.73 (+15.40)
h3: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6607.15 vs least  5375.54 (+1231.61)
h4: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  7310.97 vs least  7310.97 (-0.00)
```

Agent's closing message:

> The tool is fixed. `python3 /app/dispatch.py --data /app/data --output /output/plan.json` now produces a plan for 21 July costing **£6,303.56**, burning **64,944 kWh** of gas (as billed), with **2 engine starts** and every half-hour within the grid limits. It runs in about 0.5 s and gives byte-identical output each time. The data files are untouched and the plan's format is unchanged.
>
> For comparison, the old tool reported £4,513 and 74,714 kWh. Its own plan, costed correctly, actually burns about 91,600 kWh, and the plant couldn't run it because it threw away engine heat.
>
> **What was wrong**
> 1. **Gas billing (the low gas forecast):** engine fuel is quoted on net CV and the gas is billed on gross CV. The tool divided by the 1.108 gross/net ratio instead of multiplying, so engine gas came out about 23% low.
> 2. **Engine heat had nowhere to go:** `plant.json` lists every heat-circuit connection, and the engines' hot-water circuit feeds only AC1 and the heat exchanger into the heating circuit. There is no dump radiator. The tool let engine heat be wasted, so its plans ran the engines harder than the plant can absorb. This was the main reason plans weren't workable.
> 3. **Extra starts and stops:** it chose each half-hour on its own, ignoring start costs and which engines were running at midnight. It now plans the whole day at once and includes starts in each half-hour's cost.
> 4. **Weather an hour out:** the forecast is in UTC but rows were picked by UTC date, so in summer time the weather and PV were shifted an hour.
> 5. **Wrong tariff day:** the weekday/weekend check used the UTC day, so in summer time a Saturday was priced as a weekday and a Monday as a weekend. It had no effect on this Tuesday.
> 6. **Engine performance:**
>    - Fuel and heat were a straight line from minimum to rated output; they now follow all the part-load points.
>    - Recovered heat included the intercooler heat, which goes to the engines' own radiators.
> 7. **Grid limit:** the 1220 kVA import limit ignored the reactive power the engines' generators supply.
> 8. **Towers:** their load counted only the cooling, not the chillers' compressor power or AC1's heat input.
> 9. **Outages:** only engine outages were applied, so B2's all-day outage was ignored.
> 10. **PV:** output is now capped at the inverter rating (no effect on this day's forecast).
>
> **Today's plan:** GE2 runs from 00:00 to 10:30 and GE1 from 11:00 to midnight. GE1 is stopped at midnight because it's out from 07:00 to 11:00 anyway, and at night GE2 can produce more power within what AC1 and the heating can absorb. The two engines can't run together today because their combined heat can't be taken.
>
> **How I checked it**
> - A separate checker recomputes every balance, limit, gas and cost figure from the raw files.
> - A whole-day optimisation solved a different way gives the same cost (within £0.002). It matched on the given day and on about 60 other days I generated: winter, weekends, outages, and days where the grid, tower or export limit binds.
> - An independent review, with its own optimisation, reached the same £6,303.56 and found no remaining errors.
>
> **Decisions for you**
> - **AC1's cooling-water limit:**
>   - I kept the original rule: AC1 runs only when the tower water is at least 22°C, which needs a wet bulb of 18°C or more. On this day it always is.
>   - If you read the variable-speed tower fans as able to hold the water at 22°C whenever AC1 is wanted, spring and autumn plans would be 5–30% cheaper. Holding the water at 22°C is only an option if your plant can actually do it.
>   - The tool holds the water at 22°C only when a half-hour is otherwise impossible, and prints a warning when it does.
> - **Days that can't be met:**
>   - If the demand can't be met within the import capacity, the tool still writes a plan, keeps the overload as small as possible and sets `grid_ok: false` for those half-hours.
>   - If heat or cooling can't be met at all, it stops with an error naming the half-hour.
> - **Smaller calls with no effect on this day:** AC1's pump power counts towards the tower load, and an outage whose end is before its start blocks both ends of the day. Both are conservative.
>
> The changes are in the four files under `planner/`. In `dispatch.py` the only change stops it writing `-0.0`.

## ecd18-run3-claude / energy-centre-dispatch-v18__KryEDRh

- agent: `claude-code` with `anthropic/claude-opus-5-5`
- reward: **0**; exception: None; agent time: 88.9 min
- verifier: 4 failed, 51 passed in 0.91s
  - failed `test_units_within_ratings_and_availability[h1]`
  - failed `test_units_within_ratings_and_availability[h2]`
  - failed `test_units_within_ratings_and_availability[h3]`
  - failed `test_units_within_ratings_and_availability[h4]`

What the agent's tool does on each verifier day:

```
visible: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6303.56 vs least  6303.56 (+0.00)
h1: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6403.31 vs least  6426.65 (-23.34)
h2: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  8063.68 vs least  8879.73 (-816.05)
h3: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  5182.63 vs least  5375.54 (-192.91)
h4: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  7270.94 vs least  7310.97 (-40.03)
```

Agent's closing message:

> Both reviews are back. Neither found anything that changes the plan. I fixed the robustness issues they raised, and re-checked everything. The plan for the day hasn't changed: £6,303.56, 2 engine starts, within the connection limit in every half-hour.
>
> **Independent bug hunt on the original code.** This reviewer worked only from the original tool and the data, without seeing my version. They found the same defects and got the same optimum: £6,303.56, 64,944 kWh of gas, GE2 alone 00:00–10:30 and GE1 alone 11:00–23:30. They also reached the same view on the three judgement calls:
> - engine heat can't be dumped;
> - the towers hold the condenser water at 22 °C while the absorption chiller runs;
> - maintenance and start costs belong in the reported cost.
>
> **Review of my implementation.** Their own checker and optimiser agreed with every plan to within £0.004, and agreed on which days have no feasible plan. Runtime stays at 1 s or less. The findings were about robustness, and I fixed these:
> - **Possible solver errors:** each solution is now checked against the constraints, and any doubtful answer is solved again without the solver's presolve step. (The reviewer saw that step give a wrong answer on their own, larger model; it never happened in the tool.)
> - **Time formats:** outage times with seconds no longer crash; times given with a UTC offset are converted to local time; zero-length outages are ignored. Tariff bands that run past midnight (e.g. 23:00–07:00) now work.
> - **Impossible days:** a day the plant can't serve, such as a tower cell out during a heavy cooling load, now stops with a plain message listing every affected half-hour, instead of a crash naming only the first.
>
> **Left as designed:**
> - PV can be cut back if exports hit their limit; this never happened in any test.
> - An outage written as "22:00" to "02:00" blocks the unit at both ends of the plan date, since it could mean either night and this never plans a unit that's out.
> - Clock-change days are refused, as the task excludes them.
>
> **Re-verification.** The plan from the required command is unchanged byte for byte and identical on every run. All feasible scenarios and random days still match the independent optimiser, and the data files are untouched. My checking scripts are in `/tmp/work`, outside the deliverable.

## ecd18-run1-codex / energy-centre-dispatch-v18__ns8Uob3

- agent: `codex` with `openai/gpt-6.1-sol`
- reward: **0**; exception: None; agent time: 10.2 min
- verifier: 4 failed, 51 passed in 0.93s
  - failed `test_units_within_ratings_and_availability[h1]`
  - failed `test_units_within_ratings_and_availability[h2]`
  - failed `test_units_within_ratings_and_availability[h3]`
  - failed `test_units_within_ratings_and_availability[h4]`

What the agent's tool does on each verifier day:

```
visible: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6303.56 vs least  6303.56 (-0.00)
h1: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6403.30 vs least  6426.65 (-23.35)
h2: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  8063.68 vs least  8879.73 (-816.05)
h3: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  5182.63 vs least  5375.54 (-192.91)
h4: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  7270.93 vs least  7310.97 (-40.04)
```

Agent's closing message:

> Fixed the dispatch tool and generated [plan.json](/output/plan.json), preserving its structure and leaving all input data unchanged.
>
> The fixes cover gas billing, performance curves, heat circuits, cooling towers, reactive power, outages, forecast alignment and daily start-cost optimization.
>
> For the supplied day: **£6,303.56**, **64,944.186 kWh gas**, **2 engine starts**. All 13 regression tests pass; an independent model confirms the minimum cost. Runtime was **0.57 seconds**, with identical output on repeated runs.

## ecd18-run2-codex / energy-centre-dispatch-v18__ZU8gkYy

- agent: `codex` with `openai/gpt-6.1-sol`
- reward: **0**; exception: None; agent time: 12.3 min
- verifier: 4 failed, 11 passed, 40 errors in 0.62s
  - failed `test_same_plan_every_time[h1]`
  - failed `test_same_plan_every_time[h2]`
  - failed `test_same_plan_every_time[h3]`
  - failed `test_same_plan_every_time[h4]`

What the agent's tool does on each verifier day:

```
visible: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6303.56 vs least  6303.56 (-0.00)
h1: tool failed: RuntimeError: no feasible loading at 00:00
h2: tool failed: RuntimeError: no feasible loading at 00:00
h3: tool failed: RuntimeError: no feasible loading at 13:30
h4: tool failed: RuntimeError: no feasible loading at 00:00
```

Agent's closing message:

> Fixed the tool and generated [plan.json](/output/plan.json), correcting gas billing, plant constraints, forecast timing and engine scheduling.
>
> The plan costs **£6,303.56**, uses **64,944.19 kWh** of billed gas and includes **2 engine starts**.
>
> All 14 tests pass. A separate full-day optimizer confirms the minimum cost. Repeated runs are identical and finish in under a second. Data files are unchanged.

## ecd18-run3-codex / energy-centre-dispatch-v18__kQcd7rp

- agent: `codex` with `openai/gpt-6.1-sol`
- reward: **0**; exception: None; agent time: 8.8 min
- verifier: 4 failed, 51 passed in 0.99s
  - failed `test_units_within_ratings_and_availability[h1]`
  - failed `test_units_within_ratings_and_availability[h2]`
  - failed `test_units_within_ratings_and_availability[h3]`
  - failed `test_units_within_ratings_and_availability[h4]`

What the agent's tool does on each verifier day:

```
visible: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6303.56 vs least  6303.56 (+0.00)
h1: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6409.70 vs least  6426.65 (-16.95)
h2: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  8063.68 vs least  8879.73 (-816.05)
h3: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  5182.63 vs least  5375.54 (-192.91)
h4: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  7285.81 vs least  7310.97 (-25.16)
```

Agent's closing message:

> Fixed the tool and generated [plan.json](/output/plan.json), preserving its JSON schema.
>
> Corrected gas billing, plant performance, operating constraints, outages, time alignment and whole-day startup scheduling.
>
> The supplied day totals **£6,303.56**, **64,944.19 kWh billed gas** and **2 engine starts**.
>
> All 14 tests pass. Runtime is under one second, output is repeatable, and an independent optimization confirms the minimum cost.

