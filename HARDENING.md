# Hardening `energy-centre-dispatch` after the reviewer's runs (v9 to v12)

Written on 2026-10-15 for an outside review of where the task stands and what to do next.
This branch holds everything: `tasks/energy-centre-dispatch/` is the latest version (v12),
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

## After the review: two falsification tests (2026-10-15)

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

A third test is under way: whether the optimisation itself can be made hard to solve exactly in
two minutes (several days, a thermal store, minimum up and down times) in a way that a careful
use of SciPy's MILP solver does not already handle.

## Where to look

1. `README.md`: the delivered task, its evidence and the full history ("How the task came
   about"; items 25 and 26 for v9 and v10, 27 and 28 for v11 and v12).
2. `tasks/energy-centre-dispatch/`: v12 as it stands (instruction, data, shipped tool,
   solution, tests). `git diff 1f92378 -- tasks/` shows exactly what v12 changes from v8.1.
3. `results/official-v10.md`, `official-v11.md`, `official-v12.md`: what each trial's tool does
   on each day, and each agent's closing message (the clearest view of how Opus reasons).
4. `results/checks-v11/README.md` and `results/checks-v12/README.md`: the checks, and what the
   setpoint rules (v11) and the silent header (v12) cost per day.
5. `archive/energy-centre-dispatch-v9/` to `-v12/`: every version's task files and build script;
   `archive/energy-centre-dispatch-v11-tools/` has the tower model behind v11's tables.
6. `results/v9-trials/` to `v12-trials/`: the deliverables and verifier output.
7. `prototypes/`: the falsification tests of options A and B, each with its README.
