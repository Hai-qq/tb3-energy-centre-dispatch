# v23 prechecks: a larger plant with hidden consequences, and T1 (intercooler heat into a weather-compensated AHU circuit)

Branch `v23-prechecks`, from `5ae65f8`. The official task in `tasks/energy-centre-dispatch/` is still v19 and was not changed. This round tried the "major revision" route: let the plant grow, as long as every new part hides an unstated consequence rather than a stated rule. The candidate search found one candidate, T1, that passed every qualitative screen. Three blind Opus trials all got T1 right, so it does not go into the task.

## The search

Two reports, both in `research/`:
- `literature-review.md` surveys benchmark design, LLM blind spots, energy-system sources and small-sample statistics. Claude spot-checked its decision-relevant claims against the upstream TB3 files and the cited PR. Its main points:
  - 90% confidence that 3+3 all fail needs an Opus pass rate of at most 3.45% per trial, with GPT at about 0;
  - v19's two traps behave as independent;
  - no fair third trap exists in v19's current fields.
- `hidden-trap-candidates.md` lists about 30 candidate mechanisms, each checked against the rules learned in v20–v22:
  - stated rules get modelled;
  - parts written as equipment give the part outages away;
  - priority rules vanish when the optimiser is rewritten;
  - a candidate must also be fair, silent on the visible day, independent of the header and the part outages, and real.

  Only T1 passed every screen. The report estimated that it would lift the 3+3 all-fail probability to about 0.8, not 0.9.

## T1

**What changes** (Claude drafted the visible files; Codex built the package to a brief, record in `candidates/t1/README.md`):
- `plant.json`:
  - each engine's LT circuit gets a second outlet, `LT PHE 1` or `LT PHE 2`;
  - LTHW gets an outlet `PHE2`;
  - a new circuit `ahu_heating` takes heat from both LT PHEs and from PHE2 and delivers it to `AHU heating coils`;
  - its flow and return temperatures are tables by dry bulb, 55/45 °C at −3 °C and 34/29 °C at 18 °C, flat beyond.
- `demand.csv` gets `ahu_heat_kw`; the instruction's demand sentence names it. Nothing else in the instruction changes.
- The shipped tool reads the new column and credits the running engines' intercooler heat to the AHU circuit by energy balance alone, with no look at temperatures. That is the trap, and its comment states only the topology. It no longer counts intercooler heat towards LTHW, the old planted error in its place.

**The unstated consequence.** Heat only flows from warmer to cooler water. The intercooler circuits run at 40/35 °C, so:
- in cold weather the AHU circuit returns above 40 °C, and no intercooler heat can enter it;
- in summer, at 34/29 °C, all of it can.

The visible day (dry bulb 19.9–28.8 °C) is all summer, and its plan is the same whether temperatures are checked or not.

**Fairness.** Two isolated readers, Codex and Sonnet (`fairness/t1/`), gave the same three answers:
- in January at 2 °C, none of the intercooler heat can reach the AHUs, which get engine heat only through PHE1, LTHW and PHE2;
- in July at 24 °C, all of the AHU heat can come from the intercoolers;
- a January outage of `LT radiator 1` stops GE1.

Both pointed to what the files leave open in between: the LT PHEs' approach, and whether they work in series with PHE2 or in parallel. The verifier therefore:
- accepts any recovery up to the generous reading (series, zero approach) in the heat balance;
- sets the least-cost bar with the strict reading (full recovery only when the AHU flow is at or below 35 °C).

Plans built on either reading pass.

**Checks.**

| Check | Result |
|---|---|
| Changed files | the drafted visible files byte for byte; besides them, the task README's verification sentence |
| Solution, `tools/eval_energy.py` (rerun by Claude) | all tests pass |
| Solution in Harbor (job `ecd23t1-oracle`) | reward 1.0 |
| Mutants, rerun by Claude (`candidates/t1/build/mutants_claude_rerun.log`) | 44 of 45 caught, including the following; the one missed, `t1_dry_bulb_utc` (dry bulb an hour out), is the exception the brief allowed |
| → `t1_energy_bus` | caught on h2 and h3 by the heat balance |
| → `t1_never_recover` | caught on the visible day, h1 and h4 by least cost |
| → header lock-out | caught on h1 |
| → part outages and radiator outages | caught on h2 and h4 |
| MILP gap, `fresh_days.py --days 16 --seed 2026` (Codex only) | under £0.0001; 16 of 16 across winter, spring and autumn, and summer |

AHU demand on the hidden days is the visible day's reheat shape plus `max(0, 25 × (14 − dry bulb))` kW. h3's `LT radiator 2` outage moved from 10:40–14:20 to 03:40–04:50, because only at night does the generous reading leave GE2 unable to send its minimum intercooler heat to the AHUs. The verifier asserts, for every radiator outage, that the engine must stop under every reading.

## Blind trials

Claude Code with Opus 5.5 at max effort, the official settings, one at a time. `candidates/t1/build/eval_traits.py` reruns every test on four versions of the hidden days:
- as built;
- without the part outages;
- without T1's pressure, the AHU demand set to zero wherever the generous share is below 1;
- with neither.

Each `blind/t1-<n>/` holds the deliverable, the verifier output, the evaluation and the agent's closing messages.

| Trial | Minutes | Reward | T1 | Header | Part outages |
|---|---|---|---|---|---|
| t1-1 (`ecd23t1-blind1-claude`) | 37 | 0 | right: a general rule that a heat exchanger cools its hot side no further than the cold side's return and heats its cold side no further than the hot side's flow; all tests pass without the part outages | right | wrong: exits on `EC1 condenser` and the like as "not part of the plant" |
| t1-2 (`ecd23t1-blind2-claude`) | 58 | 0 | right: listed "intercooler heat used for the AHUs whatever their circuit temperature" among the bugs it fixed, and limits it to preheating the return to 40 °C | right | wrong |
| t1-3 (`ecd23t1-blind3-claude`) | 83 | 0 | right: treats the intercooler circuits as preheating the AHU return, and noted that its reviewers split between the two readings | right, after its two review agents argued against the lock-out | wrong |

All three agents read the temperature tables, asked what they were for, and modelled them.

## Decision

T1 does not go into the task; the official task stays v19.
- **T1** fails the blind precheck, three of three. The temperature tables are new visible fields, and visible fields get modelled: once they are there, the second law follows. The trap the search ranked best behaved like every stated rule since v13.
- **The major-revision route** ends here, because the search found no other candidate that passed the screens.

Tally for the v19 structure: over v16–v19 and the nine blind trials W, P, S1, K1–K3 and T1-1–T1-3, Opus got the part outages right in 3 of 19 trials, the header in 13 of 19, and both in 2 of 19. The D trials are left out, since D names the parts differently. In the blind trials the part outages were missed every time (0 of 9), while the header was right in 7 of 9.
