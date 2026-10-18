# Hardening `energy-centre-dispatch` after the reviewer's runs (v9 to v12)

Written on 2026-10-15 for an outside review of where the task stands and what to do next.
This branch holds everything: `tasks/energy-centre-dispatch/` is the latest version (v18; see the last rounds below),
`archive/` keeps every version, `results/` the checks and trials. `main` is unchanged at
`1f92378`, the delivered v8.1.

## Where things stand

- **Delivered:** v8.1 (task hash `acdfe59ea74ff707`, `archive/energy-centre-dispatch-v8.1/`).
  Our six v8 trials all failed (Opus 5.5 0 of 3, GPT-6.1 Sol 0 of 3).
- **The assignment's reviewer** then ran v8.1 three times with each model: Opus 5.5 at max
  effort (Claude Code) solved it twice, and no GPT pass was reported. The reviewer asked for
  the task to be hardened. The bar we have to meet is that **every trial fails: Opus 0 of 3
  and GPT 0 of 3.** One pass is a failed hardening.
- **Since then, four versions, each stopped by an Opus pass:**

| version | change (on top of the version named) | Opus 5.5 (Claude Code, max) | GPT-6.1 Sol (Codex, xhigh) |
|---|---|---|---|
| v9 | v8.1 + GE1's intercooler heat goes into the condenser water through a heat exchanger (LTX1); the shipped tool applies outages to every unit and puts compressor work and driving heat on the towers | 1 of 1 passed | not run |
| v10 | v9 + EC2 air-cooled (COP at the dry bulb, heat not on the towers); AC1 a series pre-cooler on the chilled water return (at most 2/3 of the load) | 1 of 2 passed | 0 of 1 |
| v11 | v8.1 + the condenser water setpoint is an explicit decision (21 to 28 °C in 0.5 K steps) with real tower physics: capacity by wet bulb and approach, fan power curve, AC1's capacity falling with warmer cooling water | 1 of 1 passed | not run |
| v12 | v8.1 + the header error made silent (a 2,600 kVA connection carries the whole site, EC2 1,400 kW) + no visible outage symptom (the shipped tool applies outages to every unit; it still uses each half-hour's start and ignores the outages of the LT radiators, PHE1, tower cells and PV) | 1 of 1 passed: the trial's own verifier image build hung, and the deliverable passed all 55 tests when replayed in Harbor | not run |

Since v9 Opus has solved the task in 4 of 5 runs; the passing tools we put through days drawn at
random (v10's and v11's) passed every one. GPT has failed every run since v5, and since v8 (whose
instruction first said that `plant.json` lists all of the plant) always on the condenser water
header.
Trials are run one at a time; after the user's instruction, only Opus is run, and any pass stops
the round.

## The task in brief

The agent repairs the day-ahead dispatch tool of a hospital trigeneration energy centre (two gas
engines with HT and LT heat circuits, two boilers, two electric chillers, an absorption chiller
AC1 fired from the engines' HT circuit, two cooling-tower cells, PV, a grid connection). The
shipped tool runs, reads every data field and is wrong in about a dozen places. The instruction
reports two symptoms (gas below the meters, too many engine starts) and says the data is correct
and complete. The verifier runs the tool on the visible day and on four hidden days and
recomputes every figure with an independent model, against the least cost from a whole-day MILP
(tolerance: the larger of GBP 0.5 and 0.02%).

Two things have ever stopped Opus:

1. **The condenser water header.** AC1 needs cooling water at 22 °C or warmer; the towers'
   fans are variable speed and `min_leaving_water_c` is 21 °C. The shipped tool locks AC1 out
   whenever the weather would make the water colder than 22 °C. The right model holds the shared
   header at 22 °C while AC1 runs (so the electric chillers then run at the COP of 22 °C water).
   Since v8, Opus has adopted this in 4 of the 7 runs that had to judge it (v11 stated the
   setpoint outright); the adopting runs since v9 either hit "no feasible plan" on their own cool
   test days (v9, v10) or had an independent review subagent flag it (v12). Two runs saw it and
   declined: "If operators raise the tower setpoint to 22 °C when AC1 runs, the
   model needs changing; tell me if that's how they run it" (v10), and "That would sometimes be
   cheaper, but the plan has no field to say which temperature was used" (v8).
2. **LT radiator outages.** Each engine's intercooler heat leaves only through its own LT
   radiator, so an engine cannot run while that radiator is out. Opus missed this in most runs
   up to v8, and in no run since v9.

## What we have learned about how Opus 5.5 solves it

- It reads every field and the code, and turns every connection `plant.json` lists into a balance
  in its model, so any coupling the data states, however deep, comes out right: LTX1, the
  air-cooled chiller and the series pre-cooler (v9, v10), and the whole setpoint optimisation
  with fan power, tower capacity by approach and AC1's derating (v11, solved in 43 minutes).
- It checks itself thoroughly: a plan checker written from the raw data, a separately formulated
  whole-day optimiser, 10 to 130 test days of its own (outages of every kind, winter, weekends,
  binding limits), and review subagents. In v11 it even added the fallback our own solution
  has for fans run off their curve.
- Its failures were never capability failures after v8. They were deferrals on one operational
  judgment, and errors that showed up as "no feasible plan" on its own test days got fixed.
- v12 removed both the loud signal and the visible outage symptom. The main agent kept the
  shipped header rule, but its "independent defect hunt" subagent disagreed; the agent priced
  both readings on cooler days ("8-36% cheaper") and adopted the header (96.9 minutes).
- Earlier tasks in this repository (day-ahead bidding, exact intraday redispatch, a settlement
  ledger repair, feeder restoration; README, "How the task came about", items 1-14) were all
  solved: a precisely specified problem, however large, is one these models formulate and check
  themselves. This task was built around the only kind of miss that remained, an operational
  consequence of the data left to the reader's knowledge of the trade.

## Constraints on any change

- TB3's rules: the instruction and data must determine what the verifier demands (a domain
  expert must not face an ambiguity); a separate verifier image; 27 static checks; an
  implementation rubric; CI's trajectory review, which looks for specification failures and asks
  whether failures match the stated difficulty crux; `/cheat` trials.
- Trials: Claude Code + `anthropic/claude-opus-5-5` (max effort) and Codex +
  `openai/gpt-6.1-sol` (xhigh), three each; agent timeout 8 hours (`task.toml`), expert time
  estimate 4 hours.
- The tool: Python 3.13 with NumPy and SciPy only, two minutes per day, deterministic.
- CI's trajectory review of the v8 trials found no specification failure, including the runs
  that failed on the header; an earlier outside review asked for the header to be stated in the
  instruction.

## Questions for the review

1. Is there a change to this task that would plausibly make Opus 5.5 fail **3 of 3** and still
   be fair under TB3's rules? Name the mechanism, and say why Claude Code's self-checks (an
   independent optimiser, a plan checker, its own test days, review subagents) would not find
   it.
2. If not, what kind of task would? Concrete proposals: how each defeats self-verification, how
   the verifier stays exact and fair, how much it would cost to build, and how confident you are.
3. Where is our reasoning above wrong or incomplete?

## After the review: three falsification tests (2026-10-15)

An outside review of this brief (it is in the conversation that led here, not in the repository)
agreed to stop hardening this task the same way, argued that the difficulty should be something a
model cannot easily build even once it knows what is wrong, and proposed three directions. We
tested the two it ranked first, each against the rule set beforehand: drop the direction if a
straightforward approach already meets the bar.

- **Option B, a dispatch command gateway that must survive crashes, lost answers and a newer
  plan taking over** ([`prototypes/dispatch-gateway/`](prototypes/dispatch-gateway/README.md)).
  With a controller API that makes exactly-once possible (durable idempotency by command id,
  fencing by plan epoch, a status query), a textbook gateway of about 50 lines (an SQLite outbox,
  the plan's ids and epoch, "ask, then resend under the same id") passes all six fault scenarios;
  a first-version gateway fails three. Dropped.
- **Option A, the same plant model solved for a batch of forecast scenarios against the clock**
  ([`prototypes/batch-dispatch/`](prototypes/batch-dispatch/README.md)). Reusing optimal bases
  across scenarios is about 29 times faster than the solution run scenario by scenario and about
  6 times faster than careful generic code (15.7 ms against about 104 ms per scenario, with the
  same least cost on every checked scenario). But careful generic code would clearly miss a
  two-minute budget only for batches of about 6,000 to 10,000 scenarios, which makes the clock,
  not the reasoning, decide (TB3's rubric fails that), and basis reuse is textbook LP
  sensitivity analysis. Dropped.

- **The optimisation itself made hard: a week planned at once, with a thermal store and minimum
  up and down times** ([`prototypes/combinatorial-dispatch/`](prototypes/combinatorial-dispatch/README.md)).
  On the summer weeks HiGHS's two-minute plans are 0.16 to 0.40% above the optimum, which an exact
  DP finds (the engines' states, with the store's level kept continuous through exact
  piecewise-linear value functions; it agrees with every optimum HiGHS can prove). But a careful
  approximate method, the same DP with the store's level on a 10 kWh grid and HiGHS polishing its
  engine schedule, already reaches the tolerance in well under two minutes, and a 2 kWh grid comes
  within GBP 0.5 of the optimum. Dropped.

## Rounds v13 to v17: conventions of the trade, then parts of the plant (2026-10-16 and 17)

A further dispatch-task round on top of v8.1 itself: first conventions of the trade found by a
search of practitioners' forums and the guidance behind them (sources in
[`results/checks-v13/README.md`](results/checks-v13/README.md)), then outages of parts of the plant.
The archive holds each version (`archive/energy-centre-dispatch-v13/` to `-v17/`), the results
each trial's deliverable and verifier output (`results/v13-trials/` to `v16-trials/`,
`results/v8-rerun-trials/`).

| version | change (from v8.1 unless stated) | Opus 5.5 | GPT-6.1 Sol |
|---|---|---|---|
| v13 | four conventions written into the data: an exhaust diverter (the exhaust heat may go up the stack), LT radiator duty points (the engines derate above 32 °C), the Capacity Market charge only on imports 16:00-19:00 on winter working days, no Climate Change Levy on the CHPQA engines' gas | 1 of 1 passed (116 min, a review subagent; every convention, the header and the radiator outages right) | not run |
| v8 unchanged | a rerun of the version of our six v8 trials | 0 of 1 (kept the header lock-out, missed the LT radiator outages; 37 min) | not run |
| v14 | v13 without the radiator duty points | 0 of 2 (one missed the radiator outages, one kept the header lock-out) | not run |
| v15 | v14 with outages of parts on the hidden days (EC1's condenser, GE1's exhaust heat exchanger, AC1's absorber and condenser, GE2's jacket water heat exchanger) | 0 of 3 (one rejected the unknown names and wrote no hidden-day plan, one kept the header lock-out, one missed the parts) | 1 of 2 passed (17 min, header and every part right) |
| v16 | the files the agent sees byte for byte v8.1's; the hidden days add outages of parts that v8.1's `plant.json` names (EC1's condenser, GE1's intercooler twice, AC1's absorber and condenser) | 1 of 2 passed: run 1 handled the radiators by a generic rule (some part downstream of each engine circuit) and missed the intercooler and the chillers' parts; run 2 failed only on a verifier ambiguity and passes under v16.1 | not run |
| v16.1 | v16 with the least-cost bar counting the absorption chiller's auxiliary power in the towers' load, so either reading of what its cooling water takes away is accepted | (run 2 above passes) | |
| v17 | v16.1, either reading of a partial PV outage accepted (none, or the minutes in service), and hidden-day checks: negative net reactive power at the connection (h2 00:00), four outages of GE2, outages of 10 and 15 minutes (B1, EC1) | 0 of 3: run 1's tool rejected the parts' names as unknown plant and wrote no hidden-day plan (133 min, a review subagent, header right); run 2 applied outages to units only and ran units through their parts' outages (28 min, header right); run 3 kept the header lock-out and also ignored the parts (28 min) | 0 of 3: runs 1 and 3 kept the header lock-out and missed GE1's intercooler (9 and 10 min); run 2 adopted the header and ran units through all the parts' outages (11 min) |

What this round shows:

- Conventions written into the data are found every time: each is knowable once stated. They
  also seem to put the models into a careful mode that finds the old traps as well (v13 passed;
  GPT kept the header lock-out in every v8 run and adopted the header in both v15 runs).
- What still stops the models is consequences the data leaves unstated: the header (kept in about
  half the runs) and outages of parts that only the heat circuits name (missed in about half of
  Opus's runs since v15).
- The strongest deliverable so far, `results/v16-trials/ecd16-run2-claude/app`, passes every test
  of v17: v17's new checks catch only weaker implementations.
- v17 is the first version every trial failed: Opus 0 of 3 and GPT 0 of 3, all six on the parts' outages and three of them
  on the header as well. CI's trajectory review found no specification failure in any of the six and the failures on the
  stated crux; the rubric review passes (34 pass, 1 not applicable); Opus declined its /cheat trial and OpenAI's safety
  filter stopped GPT's ([`results/checks-v17/README.md`](results/checks-v17/README.md)).
- Two verifier ambiguities came to light and are fixed in v16.1 and v17 (the absorption chiller's
  auxiliary power in the towers' load; a PV outage over part of a half-hour). Both are in the
  delivered v8.1 too.

## v18: an outside audit, no new trap, one more round of trials (2026-10-17)

v17's 0 of 6 may be luck: the agent sees v17 exactly as it saw v8.1, on which the reviewer's
Opus runs passed twice in three, and `results/v16-trials/ecd16-run2-claude/app` passes every test
of v17. An outside agent (GPT Pro, working in the repository from a brief) was asked to audit
v17's fairness, estimate the pass rates and make the failures stable by changing only the hidden
days, the verifier and the solution. Its work is on the branch `v18-gptpro` (draft PR #1) under
`results/checks-v18/`; we re-ran its checks independently (`results/checks-v18/independent-review/`)
and found the same results.

What v18 keeps from it:

- Verifier defects, none of which a trial had hit: the reference raised `KeyError` on
  `GE1 jacket water and exhaust` and `GE2 jacket water and exhaust`, which `plant.json` lists; it
  counted overlapping PV outages twice; it rejected a plan that holds the condenser water warmer
  than the coldest it can be (the plan's own electricity balance now gives what the electric
  chillers draw, accepted anywhere between their power at the coldest water and at the warm end
  of their COP tables); and v17's solution was GBP 5.81 and 14.88 below the MILP on h1 and h4,
  not within GBP 0.001 as we had written (it left the absorption chiller's auxiliary heat out of
  the towers' load; the cost test passes either reading). v18's solution takes the MILP's
  reading and is within GBP 0.0003 of it on all five days.
- Hidden days: outages of GE2's jacket water and exhaust heat recovery (h2) and of AC1's
  generator (h3), a less contrived negative net reactive power at the connection (h2), and
  overlapping PV outages (h4).
- One change of ours: the reference took any absorption chiller output above 1e-9 kW as running,
  so solver noise in a plan written at full precision (the patched v17 Codex tool writes nine
  decimals) would have held the header at 22 °C and failed the electricity balance; the
  threshold is now 0.01 kW.

What it did not find is a fair change to the hidden days that the three strongest tools fail
(v16 run 2's, and v17 run 2's two tools given only the outages of parts). Its differential test
drew 480 days, 375 of them valid and feasible (every season, every unit and part name, the four
midnight states, outages of 1 to 240 minutes, several and overlapping); the three tools passed
every check on every feasible day, and the cost test on the 130 it solved the MILP for. The
reason is structural: the tool an agent writes depends only on what it sees, and the hidden days
already catch every known misreading of the header and of the parts, so changing them cannot
lower the chance that a run gets both right. The two candidates that do beat the strongest tools
are not fair:

- Holding the condenser water warmer so that the electric chillers take up power the export
  limit refuses, which saves an engine restart. It pays only when the site's own demand falls
  below about 700 kW with both engines at minimum load and no PV, against a night load of about
  1,250 kW on the visible day, and the patched v17 Codex tool already does it.
- Engines stopped when their LT radiators face air at 40 °C or more, which the UK has reached
  once (July 2022), and the data does not say whether an engine then trips or derates.

GPT Pro put the single-run pass rates at about 20% for Opus and 10% for GPT (judgement, not a
measurement), which makes 6 failures in 6 trials about 37% likely. From the replays alone
(Opus 1 pass in 9 runs, GPT 0 in 6) up to counting the reviewer's two v8.1 passes in, we put it
between 30% and 60%. We stopped hardening the task and ran one more round of
standard trials on v18 before handing it to the reviewer, mainly to see whether CI's trajectory
review finds the new outages specified.

| check on v18 (task hash `8324adf5196e9d13`) | result |
|---|---|
| the agent's files (`instruction.md`, `environment/`) | v8.1's byte for byte |
| solution | 55 of 55; within GBP 0.0003 of the MILP on all five days; 48 fresh days (seeds 2026, 2403, 87123) pass |
| mutants | 41 of 41 caught (10 planted bugs, 26 half-fixes, 3 reporting and 2 execution faults) |
| the three strongest tools | 55 of 55 each, on v17 and on v18 |
| v17's six trial deliverables | all fail: Opus runs 1 to 3 pass 11, 51 and 37 of 55, GPT runs 11, 51 and 11 |
| Harbor with Docker | oracle reward 1 (55 passed), nop reward 0 |
| static checks (Terminal-Bench `2e29ca9`) | 28 of 28 pass |
| implementation rubric review (claude-code + Sonnet 5, CI's prompt) | 35 of 35 pass |

The round: Opus 0 of 3 and GPT 0 of 3 again, each trial on the header, the parts or both
(deliverables and verifier output in `results/v18-trials/`):

| trial | agent time | header | outages of parts | verifier |
|---|---|---|---|---|
| `ecd18-run1-claude` | 39 min | held at 22 °C only in a half-hour that is otherwise infeasible | applied to units only | 4 failed: availability on h1, h2 and h4, least cost on h3 (GBP 1,232 over) |
| `ecd18-run2-claude` | 88 min | the same, left to the operators | right | 2 failed: least cost on h3 and on h2 (GBP 15 over: at 23:30 it keeps AC1 off) |
| `ecd18-run3-claude` | 89 min | right | LT radiators only; the other parts' names ignored as unknown units | 4 failed: availability on h1 to h4 |
| `ecd18-run1-codex` | 10 min | right | LT radiators only | 4 failed: availability on h1 to h4 |
| `ecd18-run2-codex` | 12 min | kept the lock-out | LT radiators only | no plan for any hidden day ("no feasible loading at 00:00"): 4 failed, 40 errors |
| `ecd18-run3-codex` | 9 min | right | LT radiators only | 4 failed: availability on h1 to h4 |

CI's trajectory review (`results/analysis-v18/`): `task_specification`, `reward_hacking`,
`difficulty_crux`, `refusals` and `low_timeout` pass in all six. `near_miss` is flagged for the
three trials that passed 51 of 55 tests and missed only the outages of parts (`ecd18-run3-claude`,
`ecd18-run1-codex`, `ecd18-run3-codex`); in v17 it was flagged for one. The flag is about the
margin, not about a threshold: each of the three missed a whole class of outages. It does say
what the table shows, that most trials are one judgement from passing: `ecd18-run2-claude` got
every part right and failed only because it kept the header rule.

## Where to look

1. `README.md`: the delivered task, its evidence and the full history ("How the task came
   about"; items 25 and 26 for v9 and v10, 27 and 28 for v11 and v12).
2. `tasks/energy-centre-dispatch/`: v18 as it stands (instruction, data, shipped tool,
   solution, tests); `git diff 1f92378 -- tasks/` shows what it changes from v8.1, all of it in
   `tests/`, `solution/` and the task's `README.md`.
3. `results/official-v10.md`, `official-v11.md`, `official-v12.md`: what each trial's tool does
   on each day, and each agent's closing message (the clearest view of how Opus reasons).
4. `results/checks-v11/README.md` and `results/checks-v12/README.md`: the checks, and what the
   setpoint rules (v11) and the silent header (v12) cost per day.
5. `archive/energy-centre-dispatch-v9/` to `-v18/`: every version's task files and build script;
   `archive/energy-centre-dispatch-v11-tools/` has the tower model behind v11's tables.
6. `results/v9-trials/` to `v18-trials/` and `v8-rerun-trials/`: the deliverables and verifier
   output; `results/checks-v13/README.md`: the conventions' sources and what each wrong reading costs.
7. `prototypes/`: the three falsification tests, each with its README.
8. `results/checks-v18/`: GPT Pro's audit of v17 and its v18 evidence (`README.md`,
   `ANALYSIS.md`, the differential test in `fuzz/`), and `independent-review/`, our re-run of its
   checks.
