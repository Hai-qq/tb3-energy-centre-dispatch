# Closing messages of the agent (each `result` event)

- turns 38, 23.4 min, error=False

The rewritten tool runs, its plans pass all my checks, and it matches the full-day MILP on 14 test days. An independent review of the modelling assumptions is still running in the background. I'll act on its findings when it reports.

- turns 3, 0.2 min, error=False

The independent review is still running and I'll act on its findings when it reports. The fixed tool is otherwise complete: it passes all my checks and matches the full-day MILP on 14 test days.

- turns 2, 0.2 min, error=False

The independent review is still running, and I'll act on its findings once it reports. The tool fix is otherwise done and passes all my checks.

- turns 2, 0.2 min, error=False

The independent review is still running, and I'll act on its findings once it reports. The fixed tool already passes all my checks.

- turns 4, 0.2 min, error=False

I've asked the review agent to wrap up and send its findings. I'll act on them as soon as they arrive.

- turns 4, 1.7 min, error=False

I've fixed the tool. For 21 July it now plans a day costing £6,303.56, with 64,944 kWh of gas as billed, 13,775 kWh imported and 2 engine starts. The plan is written to `/output/plan.json` in the same format as before; `dispatch.py` and the data files are unchanged.

**What was wrong**
- **Gas read low:** engine fuel is quoted on net calorific value and billed on gross. The tool divided by 1.108 instead of multiplying, so engine gas came out about 19% low. It also counted intercooler heat as useful, which hid gas the boilers really burn. That heat can only go to the LT radiators.
- **Unworkable plans:** the tool let engine jacket and exhaust heat disappear, but `plant.json` gives it nowhere to go except the absorption chiller and the heat exchanger into the heating circuit. That exchanger can carry at most 1,672 kW. On this day the two engines together make more of that heat than can be used, so they never run at the same time.
- **Too many starts:** each half-hour was planned on its own and start costs were ignored. The plan is now optimised over the whole day, counting starts from the engines running at midnight.
- **Time errors:** the weather and PV forecast was matched one hour out in summer time. In summer time the day of the week also came out wrong, so a Saturday would be priced as a weekday and a Monday as a weekend.
- **Missing limits:**
  - outages were only applied to the engines, and only by the start time of each half-hour;
  - the grid limit ignored the reactive power the engines supply;
  - there was no limit on gas entry, cooling tower duty, LT radiators or the PV inverter.

  On weekend nights, importing (5.0p) is cheaper than exporting pays (5.9p), so the plan now prevents importing and exporting at once.

**Verification**
- I wrote a separate checker that rebuilds every balance, limit, gas and cost figure.
- It also solves the whole day as one optimisation problem to compare against the tool.
- On today's data and 19 made-up days, the tool matched that solve to within £0.0005. The days covered winter, weekends, exports, cool weather, binding limits and outages of different units.
- A second, independent review rebuilt the model from scratch and agreed.
- Each run takes under a second and gives identical output every time.

**Things to know**
- **Absorption chiller on cool days:** it needs cooling water at 22 °C or warmer. When the towers would make colder water, I assumed their variable-speed fans hold 22 °C for all three chillers, which makes the electric chillers slightly less efficient. The old tool simply barred the absorption chiller then. This doesn't affect today, but on cool days it changes the plan, and with the old rule some cool days had no possible plan at all.
- **Impossible days still stop with an error rather than writing a plan.** An example is the absorption chiller out at a summer peak.
- **Outages:** an outage with equal start and end times is now treated as zero-length rather than all day. An unknown unit name in `status.json` produces a warning instead of being silently ignored.

- turns 2, 0.1 min, error=False

Nothing further to do: the independent review had already finished, and I acted on its findings in my last update.

- **Its conclusion:** it found nothing missing from the model. Its own from-scratch solve gave the same cost and the same half-hour dispatch on today's data and on its five made-up days.
- **What I changed:** an outage whose end time equals its start time now counts as zero-length rather than the whole day. An unknown unit name in `status.json`, or an unknown engine running at midnight, now prints a warning instead of being ignored or crashing the run.
- **Rechecked after the changes:** every test day still matches the whole-day optimisation, and today's plan is byte-identical: £6,303.56 and 2 engine starts, written to `/output/plan.json`.

I've stopped the background check-ins.
