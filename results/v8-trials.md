# Trials of v8 (the current task)

## ecd8-run1-codex / energy-centre-dispatch__FV4r5PC

- agent: `codex` with `openai/gpt-6.1-sol`
- reward: **0**; exception: None; agent time: 17.2 min
- verifier: 3 failed, 22 passed, 30 errors in 0.66s
  - failed `test_same_plan_every_time[h1]`
  - failed `test_same_plan_every_time[h3]`
  - failed `test_same_plan_every_time[h4]`

What the agent's tool does on each verifier day:

```
visible: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6303.56 vs least  6303.56 (-0.00)
h1: tool failed: RuntimeError: no feasible loading at 00:00
h2: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  7569.29 vs least  7569.29 (-0.00)
h3: tool failed: RuntimeError: no feasible loading at 13:30
h4: tool failed: RuntimeError: no feasible loading at 00:00
```

Agent's closing message:

> Fixed the tool and generated [plan.json](/output/plan.json).
>
> It now accounts for billed gas, all performance points, heat circuits, tower loads, reactive power, outages and whole-day start costs.
>
> The plan costs **£6,303.56**, uses **64,944.186 kWh of gas**, and includes **2 engine starts**. All 21 tests pass; repeated runs produce identical output in about 0.6 seconds. Data files were unchanged.

## ecd8-run1-claude / energy-centre-dispatch__4Lq33pH

- agent: `claude-code` with `anthropic/claude-opus-5-5`
- reward: **0**; exception: None; agent time: 26.4 min
- verifier: 5 failed, 40 passed, 10 errors in 0.80s
  - failed `test_connection_limits[h1]`
  - failed `test_least_cost[h1]`
  - failed `test_connection_limits[h4]`
  - failed `test_least_cost[h4]`
  - failed `test_same_plan_every_time[h3]`

What the agent's tool does on each verifier day:

```
visible: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6303.56 vs least  6303.56 (+0.00)
h1: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess  378.7 | cost  7143.75 vs least  6403.30 (+740.45)
h2: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  7569.29 vs least  7569.29 (-0.00)
h3: tool failed: RuntimeError: the plant available at 13:30 cannot meet the demand for heat and cooling within its limits
h4: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess  534.8 | cost  7753.73 vs least  7268.16 (+485.57)
```

Agent's closing message:

> The tool now produces a workable plan for 21 July: **£6,303.56** for the day, **64,944 kWh of gas** (gross CV, as billed) and **2 engine starts**. It runs in about 0.5 s, gives the same file every time, and keeps the original plan format. A separate whole-day optimisation, written independently of the tool, reaches exactly the same cost and schedule.
>
> **What was wrong:**
>
> *Gas forecast below the meters on engine days*
> - Converting engine fuel from net to gross CV divided by 1.108 instead of multiplying, so engine gas came out about 23% low.
> - The engines' intercooler heat was counted as usable


## ecd8-run1-codex-overloaded (stopped by the API, not counted)

- agent: `codex` with `openai/gpt-6.1-sol`
- reward: 0; exception: ApiOverloadedError; agent time: 0.5 min
- OpenAI's API answered "Selected model is at capacity. Please try a different model." after the
  agent's first listing command, and the turn failed. The verifier scored the shipped tool. The
  GPT trial above was run after the Opus one, with the same settings.
