# Closing messages of the agent (each `result` event)

- turns 56, 31.6 min, error=False

I've fixed the tool, and `python3 /app/dispatch.py --data /app/data --output /output/plan.json` now produces a workable plan in about 0.5 s. The output format is the same and runs are repeatable byte for byte; the data files are untouched.

**The plan for 21 July:**
- **Cost:** £5,346.57. The old tool said £4,513.47, but its plan couldn't be run.
- **Gas:** 91,008 kWh billed on gross CV. The old forecast of 74,714 kWh was 18% low.
- **Engine starts:** 2. GE2 starts at 07:00 to cover the GE1 outage, and GE1 restarts at 11:00 when it ends. GE1 runs all night because the import alone can't carry the night load.
- **Grid limit:** met in every half-hour.

**What was wrong:**
1. **Gas billing:** engine fuel was divided by the gross/net ratio (1.108) instead of multiplied. This, plus counting intercooler heat as useful, is why gas read low on engine days.
2. **Part-load curves:** a straight line from minimum to rated output, ignoring the middle point.
3. **Intercooler heat** was counted as useful heat, but its circuit only goes to the LT radiators. Those radiators now have their capacity limit.
4. **Jacket-water heat** could be dumped. Only the exhaust has a bypass, so this heat must now go to AC1 or the heating circuit.
5. **Cooling towers** were only loaded with the chilled-water duty. The load now also includes the chillers' compressor power and AC1's heat input.
6. **Grid limit:** the engines' reactive power (fixed power factor, overexcited) was ignored, both in the limit and in `grid_ok`.
7. **Outages:** only engines were handled (B2 out all day was ignored), and only the start of each half-hour was checked.
8. **Weather and PV** were an hour out: rows were picked by UTC date rather than matched to local time.
9. **Weekend tariff** was worked out from the UTC day, which gives the wrong day in summer time.
10. **Engine scheduling:** each half-hour was optimised on its own, starts were never charged, and the engines running at midnight were ignored. That caused the extra starts and stops. The new optimizer plans the whole day at once with start costs.

**How I checked it:**
- An independent checker of every balance, limit and reported figure finds nothing wrong with the new plan, and 153 problems in the old one.
- A separate whole-day optimizer matches the cost to £0.0002, with the same engine schedule.
- Across 53 other workable test days, with outages, weekends, winter days and random cases, every result matches within £0.0005.

**Decisions for you:**
- **Jacket-water rule.** It's the one with real consequences, and comes from `plant.json` showing no dump radiator. It can make a day impossible to meet: a summer night with wet-bulb below 18 °C (so AC1 can't run) and low heating demand means neither engine can run, and the grid can't carry the load. It makes no difference on 21 July. If your plant does have a way to reject engine heat, tell me and I'll relax it.
- **Days that can't be met within the grid limit:** the tool still writes a plan, exceeding the limit as little as possible, with `grid_ok: false` and a warning. If the demand can't be met at all (e.g. cooling beyond the chillers in service), it stops with an error naming the half-hour.
- **AC1 and the towers:** I kept the existing assumption that the towers deliver the higher of wet-bulb + 4 °C and 21 °C, so AC1 (needs 22 °C) is off below 18 °C wet-bulb. I didn't model raising the tower setpoint to run it.
- **Smaller assumptions:** PV is capped at the inverter's 280 kW, and a unit out for part of a half-hour is out for all of it. Neither affects this day.

The test scripts are in `/tmp/work` and aren't part of the tool.
