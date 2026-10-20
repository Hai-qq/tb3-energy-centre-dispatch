# Closing messages of the agent (each `result` event)

- turns 49, 35.4 min, error=False

The tool now produces correct, least-cost plans. For the 21 July data it gives £6,235.28, 69,688 kWh of gas and 3 engine starts, in about 0.6 s. The output format is unchanged and the data files are untouched. The broken tool had reported £4,528; the difference is mostly understated gas and engine heat it dumped where the plant has nowhere to send it.

**The engineers' two complaints**
- **Gas too low:** engine fuel is quoted on net calorific value and gas is billed on gross, and the conversion was the wrong way round (÷1.108 instead of ×1.108). Engine gas came out about 19% low.
- **Too many starts:** each half-hour was optimised on its own, with no start costs and no knowledge of which engines were running at midnight. It now plans the whole day at once and counts every start, including in that half-hour's cost.

**Other faults fixed**
- **Time handling:** weather and PV were read an hour out during British Summer Time. Weekday/weekend was taken from the UTC date, so Mondays and Saturdays in BST could get the wrong tariff.
- **Outages:** only engines were taken out of service, so B2 was planned during its outage. Every unit now respects its outages, as do the tower cells, PV and the heat exchangers.
- **Engine performance:** fuel and heat were straight lines from minimum to rated output, ignoring the 900 kW and 600 kW points in the tables.
- **Heat circuits:** engine jacket heat was allowed to vanish, but that circuit has no dump radiator, so it must go to AC1 or the heating water. That often limits how hard the engines can run. Tower heat now includes the chillers' input energy as well as the cooling.
- **Grid limit:** the 1,220 kVA check now allows for the reactive power the engines' generators supply.
- **PV:** PV is now capped at the inverter's 280 kW.

**Three judgement calls you should confirm** (they only matter away from hot summer days):
- **AC1 and the towers:** AC1 needs condenser water at 22 °C or warmer. I let the towers' variable-speed fans hold the shared water at 22 °C while AC1 runs, with the electric chillers then working at 22 °C too. The old code instead banned AC1 whenever the towers would naturally run colder. That makes spring/autumn days 25–30% dearer and leaves many summer nights with no feasible plan, so I'm fairly confident, but it is an interpretation.
- **Engine intercooler heat:** this heat (the engines' 40 °C circuits) is only counted for the AHU heating as far as the AHU water temperatures allow, using the ideal heat-exchanger limit. Simpler threshold rules would raise mild-day costs by about 0.4%; ignoring temperature altogether, as before, understates them by 1–4%.
- **Impossible days:** if no plan can stay within the connection limits, the tool now gives the plan with the least excess and sets `grid_ok` to false for those half-hours. If demand can't be met at all, it stops with an error naming the half-hour. That happened in my tests only with PHE2 (the link from the heating water to the AHUs) out overnight in cold weather.

**How I checked it**
- An independent checker recalculated every balance, limit, gas and cost figure from the plan file.
- A separate whole-day optimisation matched the tool's optimum to within half a penny on the real data and about 70 synthetic days. Those covered all seasons, winter and summer time, weekends, and random outages of every unit.
- Output is identical on every run.

The test scripts are in `/tmp/work` and aren't part of the tool.
