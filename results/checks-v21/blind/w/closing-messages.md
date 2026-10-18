# Closing messages of the agent (each `result` event)

- turns 45, 33.4 min, error=False

The fixes are in place and verified; one modelling question is still open, and an independent review of the model is running. Status so far:

**What was wrong and is now fixed**
- **Gas too low:** engine fuel is on net CV but gas is billed gross. The code divided by 1.108 where it should multiply. It also counted the intercooler (LT) heat as recovered, but that heat goes to the LT radiators.
- **Heat dumped that can't be:** the engine heat circuit has no dump. All engine HT heat must now go to AC1 or through PHE1 to the LTHW circuit. This is now the main limit on how hard the engines can run.
- **Part-load tables:** they are now used through all three points. Recovered heat isn't linear in output, so the optimizer solves each part of the table separately.
- **Too many starts:** it used to pick the cheapest setup for each half-hour on its own, ignored start costs, and didn't count a start in the first half-hour. A day-long optimization now includes start costs from the engines running at midnight, and `cost_gbp` includes them.
- **Weather an hour out:** weather was matched by UTC date, so local midnight read the 00:00Z row instead of 23:00Z.
- **Weekend rates:** the weekend was decided from a UTC timestamp, so Saturdays and Mondays got the wrong rates.
- **Connection limit:** the kVA check now includes the reactive power the engines' generators supply.
- **Cooling towers:** the heat they must reject now includes the chillers' electrical input and the absorber's heat input, not just the cooling.
- **Outages:** they now apply to all plant (boilers, chillers, AC1, tower cells, PV, PHE1, LT radiators) and to any part of a half-hour.
- **Grid and PV:** the plan never imports and exports in the same half-hour (weekend night import at 5.0p is below the 5.9p export rate), and PV is capped at the 280 kW inverter rating.

**How it was checked**
- A separate checker rebuilds every balance, limit, gas and cost figure from the raw files. The plan passes.
- A separate full-day solver gets exactly the same optimum: **£6,303.56**, with 2 engine starts.
- On 21 made-up days (weekends, winter, various outages, hot humid weather, high PV) the tool matches that solver wherever a feasible plan exists.
- On days that can't be met, it still writes a plan, marked `grid_ok: false`.
- Output format is unchanged, results are identical across runs, and a run takes under 1 s.

**Open question: AC1 on cool days**
- **The rule now:** the tool switches AC1 off whenever the tower water would be below AC1's 22 °C minimum, as the old code did. With the towers' variable-speed fans, the plant could instead hold the water at 22 °C so AC1 can run.
- **Today's plan:** the choice makes no difference, because the water never drops below 22.4 °C.
- **Cooler days:** on a winter day, holding at 22 °C is about £630 cheaper. With the current rule, a cooler summer night has no feasible plan, because the engines need AC1 to take their heat.
- **Next step:** I've built and checked the alternative and will decide once the review comes back.

- turns 19, 14.0 min, error=False

The tool is fixed. `python3 /app/dispatch.py --data /app/data --output /output/plan.json` now gives a plan that meets every limit, in under a second and identically on every run. The data files are untouched and the plan's format is unchanged.

**Today's plan (Tuesday 21 July):** cost £6,303.56 and 64,944 kWh of gas as billed, with two engine starts. GE2 runs from midnight to 11:00, covering GE1's 07:00–11:00 outage. GE1 runs from 11:00 to midnight. Import peaks at 985 kVA against the 1,220 kVA limit. The old tool's £4,513 and 74,714 kWh came from a plan the plant couldn't run.

**What was wrong:**
- **Gas too low:** engine fuel is on net CV but gas is billed gross. The code divided by 1.108 instead of multiplying. It also counted the intercooler heat as recovered, but that goes to the LT radiators.
- **Heat dumping:** the engine heat circuit has no dump. All engine heat must now go to the absorption chiller or to the buildings' heating circuit. This is now what limits how hard the engines run.
- **Too many starts:** each half-hour was picked on its own, start costs were ignored, and a start in the first half-hour wasn't counted. The whole day is now optimised from the engines running at midnight, and `cost_gbp` includes start costs.
- **Part-load tables:** only their end points were used. All three points now are.
- **Weather an hour out:** it was matched by UTC date, so local midnight read the 00:00Z row instead of 23:00Z.
- **Weekend rates:** the weekday was taken from a UTC timestamp, so Saturdays and Mondays got the wrong rates.
- **Connection:** the import limit now counts the reactive power the generators supply.
- **Cooling towers:** the heat they must reject now includes the chillers' electrical input and the absorption chiller's heat input.
- **Outages:** they now apply to all plant, and to any part of a half-hour.
- **Grid and PV:** the plan never imports and exports in the same half-hour, which matters on weekend nights when import costs 5.0p and export pays 5.9p. PV is capped at the 280 kW inverter rating.

**How I checked it:** a separate checker rebuilt every balance, limit, gas and cost figure from the raw files, and the plan passes. A separate full-day optimiser reaches exactly the same optimum. That held across about 25 made-up days (weekends, winter, hot humid weather, outages of each type of plant). Of the review agent's flagged issues, the one I followed up was its £1.95 cost discrepancy, which came from its own model, not the tool. It was cut off before giving its views on the two judgement calls below.

**Decisions you should know about:**
- **Absorption chiller on cool days:** when the tower water would naturally be below the chiller's 22 °C minimum, the plan may hold the towers at 22 °C (they have variable-speed fans). The electric chillers then run at that temperature. Without this, an ordinary UK summer night has no workable plan. A second agent preferred this reading about 60:40. It makes no difference to today's plan, but on a winter day it saves about 10%.
- **PV can be cut back:** this only happens when there is no other way to stay within the export limit.
- **Running costs:** `cost_gbp` includes engine maintenance per MWh as well as start costs.
- **Days that can't be met:** if the connection limit can't be kept, the tool still writes a plan, marked `grid_ok: false`. If heat or cooling demand can't be met, it stops with an error naming the half-hour.
