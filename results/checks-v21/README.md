# v21 prechecks: a weekend night price inversion (W) and LT circuit pumps (P)

Branch `v21-prechecks`, from `v20-gptpro` at `08f5d78`. The official task in `tasks/energy-centre-dispatch/` is still v19 and was not changed. Both candidates were rejected by the blind precheck: a fresh Opus implementer, given only the new visible files, handled each new rule without being told.

## The candidates

| | W: weekend night price inversion | P: a pump on each LT circuit |
|---|---|---|
| Visible change | `supply.json` `import_rates_p_per_kwh.weekend[0]` (00:00–07:00) 13.8 → 5.0 p/kWh; export stays 5.9 | `plant.json` `heat_circuits.ge1_lt.pump = "LT pump 1"`, `ge2_lt.pump = "LT pump 2"` |
| Rule the verifier adds | one connection, one direction: `min(import_kw, export_kw) <= 0.5` each half-hour (C1's test, MILP and solution, ported) | a pump outage stops its circuit and so the engine whose intercooler feeds it; ownership from the circuit, not the name |
| Hidden days | unchanged; on h1 (Saturday 2026-08-08) the unconstrained solution imports and exports at once in all 14 half-hours 00:00–06:30 | h1: `LT pump 1` 18:10–19:20 (the solution otherwise runs GE1 at 1200 kWe 18:00–19:30); h3: `LT pump 2` 17:10–17:20 (GE2 stopped for 17:00–17:30) |
| New mutant | `grid_direction_ignored` | `lt_pump_outage_ignored` |

Codex built both packages to a brief from Claude; its records are in `candidates/<c>/README.md` and `candidates/<c>/build/`.

## Checks

Claude reran these:

| Check | W | P |
|---|---|---|
| `environment/` against v19 | only `weekend[0].rate`; `instruction.md` identical | only the two `pump` keys; `instruction.md` identical |
| Solution, `tools/eval_energy.py` with `ECD_TASK` | all tests pass | all tests pass |
| Solution in Harbor (oracle, jobs `ecd21w-oracle`, `ecd21p-oracle`) | reward 1.0 | reward 1.0 |
| Mutants, all 42 shared plus the new one (`build/mutants_claude_rerun.log`) | 43 of 43 caught; `grid_direction_ignored` on h1 | 43 of 43 caught; `lt_pump_outage_ignored` and `parts_by_name_prefix` on h1, h3 |
| A16 (`results/v16-trials/ecd16-run2-claude/app`) | all tests pass: it nets import and export when it writes the plan | fails `lt_pump_outages` and `units_within_ratings_and_availability` on h1, h3: it takes only the circuit's `to` |
| A19 (`results/v19-trials/ecd19-run2-claude/app`) | fails `single_connection_direction` and `reported_gas_and_cost` on h1 | exits on h1, h3: "outage of LT pump 1, which is not in plant.json" |

Only Codex ran the MILP cost gap check (largest gap £0.00018 for W, £0.00027 for P) and `fresh_days.py --days 16 --seed 2026` (16 of 16 pass for each). Claude did not rerun them.

## Fairness precheck

Two isolated readers per candidate, Codex (gpt-6.1-sol) and Claude Sonnet, each given only `instruction.md` and the visible files, with open questions and no hint. The questions and the raw answers are in `fairness/<c>/`.

- W: both readers settle on one net direction per half-hour. Both also name the other reading: import and export metered separately, so cycling is allowed. Sonnet notes that the instruction's "as they will be metered and billed" favours the net reading without saying it outright.
- P: both readers conclude that GE1 must be off while `LT pump 1` is out and that GE2 can run, and that a 10-minute outage takes the whole half-hour. The alternatives they consider (ignore the outage, derate, use the other circuit) have no support in the data.

## Blind precheck

One trial per candidate with Claude Code and Opus 5.5 at max effort, with the official trial settings (`scripts/run_trials.sh claude run 1`, task staged from `candidates/<c>/task`). The deliverable, the verifier output, the agent's closing messages and two evaluations are in `blind/<c>/`. The second evaluation, `eval-no-part-outages.log`, runs on a copy of the candidate with every part outage (a name with a space, such as `GE1 intercooler` or `LT radiator 1`) removed from h1–h4. The `LT pump` outages stay in P's copy. This separates the new rule from the old parts trap.

| | W (`ecd21w-blind-claude`, 69 min) | P (`ecd21p-blind-claude`, 124 min) |
|---|---|---|
| Reward | 0 | 0 |
| Fails | `units_within_ratings_and_availability` on h1–h4 only | `connection_limits` on h1–h4; `least_cost` on h1, h3, h4; `units_within_ratings_and_availability` on h1, h2; h3 exits ("no feasible loading at 13:30") |
| Without part outages | all tests pass | still fails `connection_limits` and `least_cost` on h1–h4; h3 still exits |
| New rule | handled: `planner/optimize.py` solves each half-hour twice, once only importing and once only exporting, when the import rate is below the export rate | handled: `planner/plant.py` adds each LT circuit's `pump` to its engine's needs. GE1 is unavailable 18:00–19:30 on h1 and GE2 at 17:00 on h3; `lt_pump_outages[h1]` passes, and h3's test errors only because the tool exits |
| Header (AC1 on cool days) | holds the condenser water at 22 °C when AC1 runs | keeps the original lock-out and leaves the choice to the operators. On h1's nights both engines and AC1 then stay off and the import is 1300–1490 kW against 1220 kVA (`grid_ok: false`) |
| Part outages | applied to whole units and the LT radiators only | applied to whole units, radiators and pumps; other part names produce a warning and are ignored |

## Decision

Both candidates fail the blind precheck: the fresh implementer found each new rule unprompted, as the v20 blind stand-ins did for C1, C2 and C4. W also leaves A16 passing. Neither goes into the task; the official task stays v19.

Both blind trials failed only on the two traps that already work, the header and the part outages. Over v16–v19 plus these two trials, Opus has the header right in 7 of 12 trials and the part outages in 3 of 12.
