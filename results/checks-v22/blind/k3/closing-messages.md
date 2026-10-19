# Closing messages of the agent (each `result` event)

- turns 45, 28.4 min, error=False

I've fixed the tool. The command now writes a plan for 21 July that meets every plant and connection limit. Cost is **£6,303.56**, gas is **64,944 kWh** and there are **2 engine starts**. A whole-day optimisation written separately from the tool reaches the same cost to the penny, with the same engine schedule. The data files are untouched, the plan's format is unchanged and a copy is at `/output/plan.json`.

**The new plan.** GE1 stops at midnight and GE2 runs at 800 kW until 11:00. GE1 restarts at 11:00 and runs for the rest of the day. Only one engine can run at a time: the engines' hot-water circuit can only pass heat to the buildings (250–500 kW today) or the absorption chiller, so all of it must be used. Overnight, GE2 makes more electricity than GE1 for the heat that can be absorbed. Both engines can never be off together, because the site's load is more than the 1220 kVA connection can import.

**What was wrong:**
- **Gas too low:** engine gas was converted from net to gross by dividing by 1.108 instead of multiplying, about 19% low. The tool also counted the intercooler heat as useful; that heat can only go to the radiators.
- **Too many starts:** each half-hour was chosen on its own, ignoring start costs and which engines were running at midnight. Starts weren't included in the cost, and a start in the first half-hour wasn't counted.
- **Weather an hour out:** weather rows were picked by UTC date, so PV and wet-bulb were an hour off from the local half-hours.
- **Weekend tariff:** the day of the week came from the UTC time, which made Saturdays weekdays and Mondays weekends in summer.
- **Plans that couldn't be run:**
  - The plan dumped hot-water heat, which has nowhere to go.
  - Engine tables were treated as straight lines from minimum to rated output, ignoring the middle point.
  - It ignored the 1672 kW limit of the heat exchanger to the buildings' heating circuit and the radiator capacity.
  - Cooling towers were sized on the cooling load alone, without the chillers' compressor power and the absorption chiller's driving heat.
  - It left out the generators' reactive power at the connection.
  - It could import and export at once on weekend nights, when import is cheaper than export pays.
  - It ignored the gas entry limit (6050 kW) and every outage except engines. B2 is out today.

**Checks:**
- I wrote a checker that recomputes every figure from the data files.
- I made about 20 test days: weekends, winter, spring, and outages of each type of equipment.
- On every day that can be met, the plan passes the checker and matches the separate optimisation.
- Each run takes under a second and gives an identical file on repeated runs.

**Decisions to confirm.** None of these affects today's plan:
- **Tower heat:** heat rejected by the absorption chiller counts cooling plus its driving heat, not its auxiliary electricity. This only matters when the towers are at their limit (about £4 in one test case).
- **Cold tower water:** the absorption chiller is treated as unavailable when tower water is below 22 °C. The tool doesn't assume the towers can be run warmer to allow it.
- **PV curtailment:** PV can be curtailed, though with this site's load it never is.

**Days with no workable plan.** If a half-hour can't stay within the connection limit in any engine combination, the tool writes the plan that exceeds it least and marks those half-hours `grid_ok: false`. It also prints a warning. Any other impossibility, such as towers unable to reject the cooling load during an outage, stops with an error naming the half-hour.

One other change: the summary totals are now sums of the half-hour figures as written, so they add up exactly.
