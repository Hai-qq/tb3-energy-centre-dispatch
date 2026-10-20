# Closing messages of the agent (each `result` event)

- turns 49, 26.6 min, error=False

The fix is in place and verified. An independent review agent is still auditing it; I'll act on its findings when it reports.

- turns 2, 0.2 min, error=False

The audit agent is still running. I'll review its findings as soon as it reports, or check again at the next scheduled check-in.

- turns 3, 0.4 min, error=False

The audit agent is still running, with no notification yet. The next check-in is in about 30 minutes. If it still hasn't reported by then, I'll do a targeted second-pass audit myself.

- turns 8, 3.8 min, error=False

I've fixed the tool. `python3 /app/dispatch.py --data /app/data --output /output/plan.json` now writes the least-cost plan for 21 July in under a second, in the same format, and gives the same output on every run.

**The plan for 2026-07-21:** £6,303.56 for the day, 64,944 kWh of gas as billed, 2 engine starts, and within the connection limit all day. GE2 takes over from GE1 at midnight because it can run flat out overnight, while GE1 would be held back by how little heat there is to use. GE2 then covers GE1's 07:00–11:00 outage, and GE1 restarts at 11:00. The two starts are the minimum the outage allows. Boiler B2's all-day outage is now respected.

**What was wrong:**
- **Gas too low:** engine gas is quoted on net calorific value and billed on gross, and the tool divided by the conversion ratio (1.108) instead of multiplying. On this plan the old sums would have reported 52,909 kWh against the 64,944 kWh the meter will read, 18.5% low.
- **Too many starts:** it chose each half-hour on its own, never counted start costs, and ignored which engines were running at midnight. It now plans the whole day at once with start costs included, and each half-hour's cost includes any engine started in it.
- **Plans that couldn't be run:**
  - It counted intercooler heat as useful, but that heat goes to the LT radiators.
  - It let surplus engine heat disappear, but the engine heat circuit has no dump radiator. All of it must go to the absorption chiller or the buildings, which limits engine output at night.
  - It ignored the middle point of the engine part-load tables.
  - It undercounted the heat the cooling towers have to reject.
  - It ignored the reactive power the generators supply when checking the grid limit.
  - It applied outages to engines only.
- **Times and dates:** weather and PV were an hour out in summer time, and weekday/weekend import rates were decided from the UTC date.

**How I checked it:** a separate checker recomputes every balance, limit, gas and cost figure from the raw data, and it passes. An independently written whole-day optimisation gives the same answer for this day (£6,303.5603, identical engine schedule). It also matches on 30 other test days I built: weekends, winter, hot and cool weather, and outages of every kind of unit.

**Judgement calls you may want to confirm:**
- **Cool weather:** I kept the original rule that the absorption chiller can't run when the cooling-tower water would be below its 22 °C minimum. It doesn't affect 21 July, but on cool nights (wet bulb below 18 °C) with low heat demand it leaves the engines nowhere to put their heat. The site's night load is more than the connection can carry, so such a night could be infeasible. If the operators raise the tower setpoint to 22 °C when the chiller runs, the model should be changed to match.
- **Days that can't be met:**
  - If no running of the plant keeps the grid import within its limit, the tool still writes a plan that exceeds the limit by as little as possible, with those half-hours marked `grid_ok: false`.
  - If the heat or cooling can't be met at all, for example with a cooling-tower cell out at midday on a hot day, it stops with an error naming the half-hour.
- **Smaller choices:**
  - PV output is capped at the 280 kW inverter rating.
  - A half-hour counts as out of service if an outage covers any part of it.
  - An outage for a unit name the plant doesn't have produces a warning instead of being silently ignored.
- **Rounding:** day totals are summed from the rounded half-hour figures. `import_kwh` can differ by 0.0005 kWh because half of a three-decimal sum can't always be shown to three decimals.

The changes are in `dispatch.py` and the four `planner/` modules. The data files are unchanged. I also asked a separate review agent for a second opinion, but it never reported back, so I did that second check myself and found no further problems.
