# Fairness pre-check for v19's change (the LT radiators named without their engine)

Before building v19, two models that had seen nothing of the task's history read only
`instruction.md`, a `plant.json` with the LT radiators renamed (`LT radiator 1`, `LT radiator 2`)
and a `status.json` with four outages, and were asked, without a hint at the answer, what each
outage stops (`question.md`).

| reader | `LT radiator 1`, 18:00-20:00 | `LT radiator 2`, 02:10-02:20 |
|---|---|---|
| Codex, GPT-6.1 Sol, high (`codex-answer.md`) | GE1 cannot run: its intercooler's only listed heat sink is this radiator; GE2 available | GE2 cannot run; GE1 available |
| Claude Sonnet, a Claude Code subagent (`sonnet-answer.md`) | GE1 cannot run: its intercooler circuit `ge1_lt` ends only at that radiator; GE2 unaffected | GE2 cannot run; GE1 unaffected |

Both reach the reading the verifier demands. The points both leave open are settled elsewhere
in what the agent sees: a part-time outage takes out the whole half-hour because the shipped
tool's docstring says each output is "held for the whole half-hour", and an outage of a part
takes out its unit, as v17's and v18's trajectory reviews accepted.
