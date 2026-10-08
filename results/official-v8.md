# Official trials (v8)

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

## ecd8-run2-codex / energy-centre-dispatch__3Wxx3fH

- agent: `codex` with `openai/gpt-6.1-sol`
- reward: **0**; exception: None; agent time: 13.3 min
- verifier: 3 failed, 22 passed, 30 errors in 0.72s
  - failed `test_same_plan_every_time[h1]`
  - failed `test_same_plan_every_time[h3]`
  - failed `test_same_plan_every_time[h4]`

What the agent's tool does on each verifier day:

```
visible: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6303.56 vs least  6303.56 (+0.00)
h1: tool failed: RuntimeError: no feasible loading at 00:00
h2: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  7569.29 vs least  7569.29 (-0.00)
h3: tool failed: RuntimeError: no feasible loading at 13:30
h4: tool failed: RuntimeError: no feasible loading at 00:00
```

Agent's closing message:

> Fixed the planner and generated [plan.json](/output/plan.json). It now optimizes engine starts across the day and correctly models gas billing, heat routing, cooling rejection, outages, tariffs and grid limits.
>
> The supplied day costs **£6,303.56**, uses **64,944.186 kWh of billed gas**, and requires **two engine starts**.
>
> All 12 tests passed, including independent checks of physics and billing. Repeated runs produce identical output in under a second on Python 3.13. Data files are unchanged.

## ecd8-run2-claude / energy-centre-dispatch__DRxEYtm

- agent: `claude-code` with `anthropic/claude-opus-5-5`
- reward: **0**; exception: None; agent time: 29.9 min
- verifier: 6 failed, 39 passed, 10 errors in 0.79s
  - failed `test_connection_limits[h1]`
  - failed `test_least_cost[h1]`
  - failed `test_units_within_ratings_and_availability[h2]`
  - failed `test_connection_limits[h4]`
  - failed `test_least_cost[h4]`
  - failed `test_same_plan_every_time[h3]`

What the agent's tool does on each verifier day:

```
visible: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6303.56 vs least  6303.56 (+0.00)
h1: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess  378.7 | cost  7143.75 vs least  6403.30 (+740.45)
h2: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  7244.97 vs least  7569.29 (-324.32)
h3: tool failed: RuntimeError: no loading of the plant meets the demand at 13:30
h4: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess  534.8 | cost  7753.73 vs least  7268.16 (+485.57)
```

Agent's closing message:

> The tool now produces a workable least-cost plan, and `/output/plan.json` has been written. For the plan date (Tuesday 21 July) it costs **£6,303.56** and burns **64,944 kWh of gas** on the billed gross-CV basis, with **2 engine starts**. Every half-hour stays within the plant and connection limits. The data files are untouched, the output format is unchanged, it runs in about 0.6 s, and repeated runs give byte-identical output.
>
> **Why the gas was low.** The engines' fuel figures are on net CV, but gas is billed on gross CV. The tool divided by 1.108 when it should have multiplied, so engine g

## ecd8-run3-codex / energy-centre-dispatch__aKvGUDN

- agent: `codex` with `openai/gpt-6.1-sol`
- reward: **0**; exception: None; agent time: 16.0 min
- verifier: 3 failed, 22 passed, 30 errors in 0.69s
  - failed `test_same_plan_every_time[h1]`
  - failed `test_same_plan_every_time[h3]`
  - failed `test_same_plan_every_time[h4]`

What the agent's tool does on each verifier day:

```
visible: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6303.56 vs least  6303.56 (+0.00)
h1: tool failed: RuntimeError: no feasible loading at 00:00
h2: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  7569.29 vs least  7569.29 (-0.00)
h3: tool failed: RuntimeError: no feasible loading at 13:30
h4: tool failed: RuntimeError: no feasible loading at 00:00
```

Agent's closing message:

> Fixed the dispatch tool’s daily scheduling, startup costs, gas billing, forecast alignment, heat routing, outages, cooling and connection limits.
>
> Generated [plan.json](/output/plan.json): **£6,303.56**, **64,944.186 kWh billed gas**, **2 engine starts**.
>
> All 13 regression tests pass, including independent balance and billing checks. Repeated runs produce identical JSON; the requested command finished in **0.67 seconds** on Python 3.13. Data files remain unchanged.

## ecd8-run3-claude / energy-centre-dispatch__EcvSum4

- agent: `claude-code` with `anthropic/claude-opus-5-5`
- reward: **0**; exception: None; agent time: 41.5 min
- verifier: 3 failed, 52 passed in 0.98s
  - failed `test_units_within_ratings_and_availability[h2]`
  - failed `test_units_within_ratings_and_availability[h3]`
  - failed `test_units_within_ratings_and_availability[h4]`

What the agent's tool does on each verifier day:

```
visible: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6303.56 vs least  6303.56 (+0.00)
h1: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  6403.31 vs least  6403.30 (+0.01)
h2: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  7244.97 vs least  7569.29 (-324.32)
h3: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  4945.17 vs least  5182.63 (-237.46)
h4: heat surplus max     0.0 kW in  0 periods | tower excess    0.0 | kVA excess    0.0 | cost  7156.64 vs least  7268.16 (-111.53)
```

Agent's closing message:

> I've fixed the tool. `python3 /app/dispatch.py --data /app/data --output /output/plan.json` now produces a workable least-cost plan in about half a second, gives the same output every run, and keeps the original format. The data files are unchanged.
>
> **The plan for 21 July:** £6,303.56, 64,944 kWh of gas (gross CV, as billed), 13,775 kWh imported and 2 engine starts. GE1 stops at midnight, GE2 runs until 11:00, covering GE1's 07:00–11:00 outage, and GE1 then restarts and runs to the end of the day. The old tool showed £4,513 because it under-read gas and relied on things the plant can't do: it


## Attempts not counted

Each was stopped by a provider or by the environment before the agent could work, kept under
another name, and run again with the same settings.

- `ecd8-run1-codex-overloaded` (codex, `openai/gpt-6.1-sol`): OpenAI's API answered "Selected
  model is at capacity. Please try a different model." after the agent's first listing command
  (`ApiOverloadedError`, 0.5 min). The verifier scored the shipped tool (reward 0). GPT run 1
  was run again after Opus run 1.
- `ecd8-run3-claude-NetworkConnectionError1` (claude-code, `anthropic/claude-opus-5-5`):
  installing Claude Code in the container failed (`curl: (35) ... SSL_ERROR_SYSCALL` to
  downloads.claude.ai, `NetworkConnectionError`); the agent never started and the verifier did
  not run. Opus run 3 was run again after the GPT `/cheat` trial that had already started.
