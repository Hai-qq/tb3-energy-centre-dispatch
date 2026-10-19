# Closing messages of the agent (each `result` event)

- turns 53, 27.5 min, error=False

The fix is implemented and verified. I'm waiting on an independent review of the physical model before finalising; I'll compare its findings with the implementation when it reports back.

- turns 2, 0.2 min, error=False

The independent review is still running, so I have nothing to compare yet. I'll compare its findings with the model in `/app/planner` when it reports; there's a fallback check in 20 minutes.

- turns 6, 1.2 min, error=False

The review agent hasn't sent its final report yet, but its scratch reference model already agrees with the fixed tool. It gives £5346.572, 91007.56 kWh of gas and 2 engine starts for the plan date; the tool gives £5346.569 (the sum of its rounded half-hours), 91007.558 kWh and 2 starts. It also made the same choice on every judgement call I'd flagged. I'll check its written report for anything further when it arrives; there's a fallback check in 20 minutes.

- turns 5, 0.6 min, error=False

The reviewer had stopped without sending a report, so I've resumed it and asked for a final written report. Its reference model already matches the fixed tool on every modelling choice and on the plan-date numbers. I'll compare any further points it raises when the report arrives; there's a fallback check in 15 minutes.

- turns 7, 2.1 min, error=False

I've fixed the tool. For 21 July it now plans £5,346.57 and 91,008 kWh of gas (gross CV), with 2 engine starts and the grid within limits. The old tool reported £4,513.47 and 74,714 kWh; that gas figure was 18% low for its own engine outputs, and its plan couldn't meet the heat demand in 10 of the 48 half-hours. The command in the task runs in about 0.6 s, gives an identical plan every run, and has written `/output/plan.json`. The output format and the data files are unchanged.

**What was wrong**
- **Gas was under-forecast:** engine fuel is quoted on net CV but billed on gross CV, and the code divided by 1.108 instead of multiplying. That made engine gas about 23% low, which is what the engineers saw against the meters.
- **Heat went places it can't go:** the intercooler heat was counted as useful, but it only goes to the LT radiators. All engine heat was also allowed to be dumped. In fact the jacket-water heat must be taken by the absorption chiller or the LTHW, and only the exhaust can be diverted to the stack. The LT radiators' 440 kW limit wasn't modelled at all.
- **Engine curves ignored the middle part-load point.** They now pass through all the points.
- **Cooling towers were under-loaded:** they were charged with the cooling only. They also have to reject the compressors' work and the absorber's driving heat, which nearly fills them at 15:30.
- **Import limit:** it ignored the reactive power the generators supply (power factor 0.95, overexcited), and so did `grid_ok`.
- **Weather was an hour late:** it was picked by UTC calendar date. It's now matched to each local half-hour by its UTC time.
- **Wrong day of the week in summer:** the tariff day came from the UTC date, so summer Mondays were priced as Sundays and Saturdays as Fridays.
- **Outages applied only to engines,** so B2 was available on a day it's out. Outages now cover all plant, including tower cells, radiators, PV and heat exchangers, whenever they overlap a half-hour.
- **Too many starts:** each half-hour was optimised on its own, start costs were never used or billed, and the engines running at midnight were ignored. The engines' on/off pattern is now chosen over the whole day with start costs.

**How I checked it**
- A separate checker rebuilds every balance, limit, gas figure, cost and summary total from the plan.
- A whole-day optimisation model written independently of the tool gives the same plan and cost for 21 July. It agrees to within £0.04 on about 50 synthetic days (winter and summer, weekends, varied outages and engine states). Almost all of that gap is a 0.01 kW margin I keep at limits so rounding never shows a breach.
- A separate reviewer, working from the description alone, reached the same model and the same totals.

**Judgement calls you may want to confirm**
- **The absorption chiller needs condenser water of at least 22 °C, taken as the larger of wet-bulb + 4 °C and the towers' 21 °C minimum.** This is the original rule, and it is the most consequential call. The 21 July nights sit just above the threshold (wet-bulb 18.4–18.8 °C). On a cooler night the absorber can't run, so the jacket heat has nowhere to go, no engine can run, and the import exceeds the connection.
- **PV can't be turned down;** it's only capped at the inverter's 280 kW. `plant.json` gives no control for it, and this makes no difference at this site's demand.
- **Tower load leaves out the absorber's pump power** (at most about 18 kW; it doesn't bind here). **The kVA limit applies to import only;** the export limit is in kW.

**Days that can't be planned within limits**
- If no plan stays within the import capacity, the tool exceeds it by as little as possible and reports `grid_ok: false`.
- Any other shortfall stops the tool with a message naming the half-hour and the plant out of service. An example is a tower cell out on a hot afternoon.

The changes are in `planner/data.py`, `plant.py`, `tariff.py` and `optimize.py`, plus one line in `dispatch.py`.

- turns 2, 0.3 min, error=False

There's nothing more to check: the independent review is finished and matches the fixed tool, and no further checks are scheduled.

The review and the tool agree on every defect and modelling choice. Both give the same plan for 21 July: £5,346.57, 91,007.6 kWh of gas at gross CV, and 2 engine starts (GE2 at 07:00 and GE1 at 11:00). The one difference is that the reviewer would let the tool turn PV down, while the tool keeps PV at the forecast. That can't change a plan at this site's demand, so I left the tool as it is.
