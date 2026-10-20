# Closing messages of the agent (each `result` event)

- turns 40, 28.0 min, error=False

Status: the fixed tool is in place and `/output/plan.json` has been produced (£6,303.56, 64,944 kWh gas, 2 engine starts, grid within limits). An independent MILP confirms it's the true optimum, and an independent checker finds no limit violations. A fresh-eyes audit of the modelling is still running; I'll fold in anything it finds before wrapping up.

- turns 4, 0.5 min, error=False

The audit is still running. Meanwhile I tested one more case: an engine that is running at midnight but on outage from 00:00. The tool turns it off with no start cost, and the MILP gives the same plan. I'll act on the audit's findings when it reports.

- turns 2, 0.2 min, error=False

The audit agent is still running. The fixed tool and `/output/plan.json` are already in place and verified. I'll fold in anything the audit finds once it reports.

- turns 4, 0.4 min, error=False

The audit agent had stopped without its report reaching me. I've resumed it to write up its findings, and I'll review them against the fix when they arrive. The fixed tool and the verified `/output/plan.json` are unchanged in the meantime.

- turns 11, 7.6 min, error=False

I've fixed the tool, and `/output/plan.json` now holds a workable least-cost plan for 21 July:

| | |
|---|---|
| Cost | £6,303.56 |
| Gas (gross, as billed) | 64,944 kWh |
| Import | 13,775 kWh |
| Export | none |
| Engine starts | 2 |
| Grid limit | met in every half-hour |

GE2 runs overnight and covers GE1's 07:00–11:00 outage. GE1 then takes over for the rest of the day. The plan format is unchanged, the data files are untouched, it runs in about half a second, and it gives byte-identical output on repeat runs.

**What was wrong:**
- **Gas too low:** engine fuel is quoted on net calorific value but billed on gross. The tool divided by 1.108 instead of multiplying, so engine gas came out 18.5% low for any given loading. The new total is still below the old tool's 74,714 kWh because the old plan ran engines whose heat had nowhere to go.
- **Too many starts:** it picked each half-hour on its own, with no start costs and no regard for which engines were running at midnight. It now plans the whole day, charging each start in the half-hour it happens.
- **Unworkable plans:**
  - The engines' high-temperature heat has no dump. It must all go to the absorption chiller or the heat exchanger (PHE1), which is limited to 1672 kW. The intercooler heat goes to the radiators and can't be recovered.
  - The cooling towers must reject the compressor work and the absorber's heat input as well as the cooling load.
  - The grid limit has to count the reactive power the generators supply.
  - Outages of plant other than the engines were ignored (B2 is out all day).
  - Missing limits: the gas entry (6050 kW) and the LT radiators.
  - The tool could import and export at the same time on weekend nights, when import is cheaper than export.
- **Time handling:** weather and PV were an hour out of step in summer time, and weekends were found from UTC, so a Saturday was priced as a Friday.

**How it's checked:** I wrote an independent checker that rebuilds every figure from the raw data, and an independent whole-day optimisation. They agree with the tool to within a penny on the given day and on 11 generated days. Those include winter, a weekend, outages, cooler weather, and a day where the grid limit binds.

**Decisions for you:**
- **Absorption chiller on cool days.** It needs cooling water at 22 °C or more, but when the wet bulb is below 18 °C the towers can make water as cold as 21 °C. I first kept the original rule of switching the chiller off then. An independent review showed that on an ordinary summer day (wet bulb 3 K lower than this one) no engine could run and the grid would be overloaded all day. So the plan now chooses each half-hour between the coldest tower water and holding it at 22 °C for the absorption chiller, with the electric chillers then working at 22 °C. That makes such days workable and saves £500–1000 a day in cool weather; it makes no difference to 21 July. It rests on the towers' variable-speed fans being able to hold that temperature, so please confirm the site does run them that way.
- **When demand can't be met within the connection,** for example the absorption chiller out on a summer afternoon so neither engine can run, the plan exceeds the import limit as little as possible and shows `grid_ok: false`. A day the plant itself can't serve (too much heat or cooling) stops with an error naming the half-hour, rather than writing a misleading plan.
- **Safety margin:** limits are kept 0.005 kW inside their values so the plan still meets them after rounding to three decimals. That costs well under a penny a day.

- turns 2, 0.5 min, error=False

The audit agent reported, and I've already acted on everything it found, so there's nothing further to do. I've stopped the check-ins.

- **Main finding, fixed:** the tool switched the absorption chiller off whenever the towers could make water colder than its 22 °C minimum. On an ordinary summer day that left no engine able to run and overloaded the grid all day. Each half-hour now chooses between the coldest tower water and holding it at 22 °C so the absorption chiller can run. Cooler days are now workable; at a wet bulb 3 K lower than 21 July the plan costs £6,264.43, matching the audit's own figure. Cool-weather days come out £500–1000 cheaper, and 21 July's plan is unchanged.
- **Smaller points:**
  - The generator's control setting is now read from `plant.json` instead of being assumed.
  - A day the plant can't serve now stops with an error naming the half-hour. It doesn't write a misleading plan.
  - I left the handling of outages given as clock times past midnight as it is, because the conservative reading is safer.

The rest of the audit confirmed the fixes I'd already made. My independent checker and whole-day optimisation still agree with the tool on every test day. `/output/plan.json` is final: £6,303.56, 64,944 kWh of gas billed, 2 engine starts, and the grid within limits all day.
