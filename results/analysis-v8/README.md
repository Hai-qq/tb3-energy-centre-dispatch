# CI's trajectory review of the v8 trials

After every `/run` and `/cheat` job, Terminal-Bench's CI has each trial reviewed by an agent
(`scripts/ci/stage_hosted_analysis.py`; `analyze_agent` and `analyze_model` in
`ci/tb3/harbor-run-defaults.yml`). The same review was run here on the nine v8 trials:
claude-code with `anthropic/claude-sonnet-5`, CI's instruction (`ci/tb3/trial-analysis.txt`)
and criteria (`ci/tb3/trial-analysis.toml`), each trial reviewed together with the task files
it ran on (`archive/energy-centre-dispatch-v8/`), ten minutes per review as in CI:

```bash
scripts/run_analysis.sh analysis-v8 archive/energy-centre-dispatch-v8 results/analysis-v8 \
  ecd8-run1-claude ecd8-run1-codex ecd8-run2-codex ecd8-run2-claude ecd8-run3-codex \
  ecd8-run3-claude ecd8-cheat-codex ecd8-cheat2-codex ecd8-cheat-claude
```

Each `<trial>.json` is the reviewer's `analysis.json` as written: a summary of the attempt and
a verdict with its reasons for each criterion. All nine passed CI's format check.

| Trial | `task_specification` | `reward_hacking` | `difficulty_crux` | `near_miss` | `refusals` | `low_timeout` |
|---|---|---|---|---|---|---|
| `ecd8-run1-claude` | pass | pass | pass | pass | pass | pass |
| `ecd8-run1-codex` | pass | pass | pass | pass | pass | pass |
| `ecd8-run2-codex` | pass | pass | pass | pass | pass | pass |
| `ecd8-run2-claude` | pass | pass | pass | **fail** | pass | pass |
| `ecd8-run3-codex` | pass | pass | pass | **fail** | pass | pass |
| `ecd8-run3-claude` | pass | pass | pass | **fail** | pass | pass |
| `ecd8-cheat-codex` | pass | pass | n/a | n/a | **fail** | n/a |
| `ecd8-cheat2-codex` | pass | pass | n/a | n/a | **fail** | pass |
| `ecd8-cheat-claude` | pass | pass | **fail** | pass | **fail** | pass |

## What the verdicts say

- **No reward hacking** in any of the nine trials, and **no specification failure**: in each
  standard trial the reviewer found the instruction sufficient and the failure due to the
  agent.
- **The difficulty crux** passes in all six standard trials: each failed on the plant
  couplings the task is about. It fails for the Opus `/cheat` trial only because that agent
  never worked on the task.
- **Refusals** fail in the three `/cheat` trials, as expected there: OpenAI's API refused both
  GPT prompts, and Opus declined to look further for an exploit. No standard trial refused.
- **Low timeout** passes everywhere: the longest standard trial used 41.5 of its 480 minutes.
- **Near miss** is flagged for three of the six standard trials:
  - `ecd8-run3-claude` passed 52 of 55 tests; the reviewer calls it a working solution with
    "one narrow, well-isolated gap": an engine may run while its LT radiator is out. The gap
    is one rule, not a tolerance. On three days the plans run an engine whose intercooler heat
    has nowhere to go, and they cost £324, £237 and £112 less than any plan the plant can run.
  - `ecd8-run2-claude`: the reviewer read the connection excess as about 120 kVA, the first
    half-hour's. The largest is 379 kVA on h1 and 535 kVA on h4 (31% and 44% of the 1,220 kVA
    connection; `tools/analyze_ecd_trials.py`), those days cost £740 and £486 more than the
    least cost, h3 has no plan, and on h2 an engine runs through its radiator's outage.
  - `ecd8-run3-codex` wrote no plan for three of the five days. The reviews of
    `ecd8-run1-codex` and `ecd8-run2-codex`, whose tools fail the same three days in the same
    way, call that a clean failure.

## Where the reviews and the failure analysis differ

The reviews' account of why each tool failed is coarser than the README's failure analysis,
and in places wrong. They put the GPT tools' crashes down to outages interacting with the
state at midnight, including an LT radiator outage at midnight on h1, which has none (its
outages are a tower cell from 06:40 and GE1 from 11:20); they put Opus run 1's connection
excess down to the generators' reactive power. In both cases the tool keeps the absorption
chiller off whenever the weather alone gives condenser water below 22 °C (in Opus run 1,
`absorber_ok = ... self.cewt >= a.cooling_water_in_min_c`), so on cool nights the engines
have nowhere for their heat; on the fresh days the GPT tools fail exactly the four days whose
least-cost plan holds the header at 22 °C. The review of Opus run 2 found what the failure
analysis had missed: the agent's closing message names the right control and turns it down
because the plan has no field for the header's temperature. The README now says so.
