# Official trials (v16)

## ecd16-run1-claude / energy-centre-dispatch-v16__mshsST2

- agent: `claude-code` with `anthropic/claude-opus-5-5`
- reward: **0**; exception: None; agent time: 98.5 min
- verifier: 5 failed, 50 passed in 0.97s
  - failed `test_units_within_ratings_and_availability[h1]`
  - failed `test_units_within_ratings_and_availability[h2]`
  - failed `test_units_within_ratings_and_availability[h3]`
  - failed `test_units_within_ratings_and_availability[h4]`
  - failed `test_electricity_balance[h4]`

What the agent's tool does on each verifier day:

```
visible: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6303.56 vs least  6303.56 (+0.00)
h1: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6403.30 vs least  6420.84 (-17.53)
h2: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  7569.29 vs least  8125.96 (-556.67)
h3: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  5182.63 vs least  5345.19 (-162.56)
h4: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  7232.28 vs least  7293.32 (-61.04)
```

Agent's closing message:

> Nothing new to fold in: the reviewer's findings were checked and built in last turn, and the scenario suite and checker were re-run then. I've just re-run the exact task command once more and the plan is unchanged: £6,303.56 for 21 July with 2 engine starts, passing the independent checker. Since there's nothing left to wait for, I haven't set another wake-up.
>
> The one open decision is still yours: the absorption chiller now runs with the towers holding its cooling water at 22 °C on cool days. It makes no difference to tonight's plan, but if you'd rather keep the old rule of switching the chiller off below an 18 °C wet bulb, cooler days will cost more and some nights will exceed the 1,220 kVA connection.

## ecd16-run2-claude / energy-centre-dispatch-v16__qJ7Q3d5

- agent: `claude-code` with `anthropic/claude-opus-5-5`
- reward: **0**; exception: None; agent time: 91.1 min
- verifier: 2 failed, 53 passed in 0.89s
  - failed `test_least_cost[h1]`
  - failed `test_least_cost[h4]`

What the agent's tool does on each verifier day:

```
visible: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6303.56 vs least  6303.56 (+0.00)
h1: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6426.66 vs least  6420.84 (+5.82)
h2: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  8125.96 vs least  8125.96 (-0.00)
h3: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  5345.19 vs least  5345.19 (+0.00)
h4: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  7308.21 vs least  7293.32 (+14.89)
```

Agent's closing message:

> The background audit is finished and its findings are in the tool, so no more check-ins are scheduled.
>
> Two of its points changed the tool:
>
> - **AC1 on cool days:** AC1 now runs on cool days, with the towers holding the condenser water at its 22 °C minimum.
> - **AC1's pump power** is counted in the tower heat. If that makes a half-hour impossible, the tool drops it for that half-hour and prints a warning.
>
> I also added two small fixes it suggested. An outage given for part of a unit, such as an engine's radiator, now takes that unit out. A misspelt or unknown unit name now prints a warning instead of being ignored.
>
> None of this changed the plan for the supplied day: £6303.56, 64,944 kWh of gas and 2 engine starts, written to `/output/plan.json`. It passes my independent checker with no problems. Two separate whole-day optimisations agree with its cost, and so do the audit's own variant days.

