# v22 prechecks: a shared LT heat-rejection circuit (S), five new rules at once (K), and part outages with different consequences (D)

Branch `v22-prechecks`, from `dde5461`. The official task in `tasks/energy-centre-dispatch/` is still v19 and was not changed. None of the three candidates goes into the task:
- In S and K, seven blind Opus trials in all implemented every new rule they were given, 16 of 16 rule implementations. They failed only on the two traps v19 already has, the condenser water header and the part outages.
- D was meant to make the part outages harder. All three of its blind trials got every part outage right, the old ones included, and failed only on the header. D's visible part structure taught the implementers what v19's part names hide.

## The candidates

**S, a shared LT heat-rejection circuit.** This is the mechanism from `results/checks-v20/research/ADDITIONAL_DESIGN_AUDIT.md`, in the form that section 4 there calls more defensible.
- Each engine keeps its own LT circuit, which now ends at its own plate heat exchanger (`LT PHE 1`, `LT PHE 2`). Both exchangers feed one new circuit, `lt_heat_rejection` (37/32 °C). Its two radiators are listed in a new `lt_radiators` table at `max_kw: 220` each.
- GE1's full-load LT heat is 201 kW and GE2's is 139 kW. With both radiators in service (440 kW) the limit never binds, and the visible day's plan and cost are identical to v19's. With one radiator out, the two engines share 220 kW.
- The v19 hidden-day radiator outages (h2, h3, h4) now cut the capacity instead of stopping an engine, and h1 gains an `LT PHE 1` outage at 18:10–19:20.
- Codex built the package; its record is in `candidates/s/README.md`.

**K, five rules stacked.** K is v19 plus W and P (`results/checks-v21/`), C2 and C4 (`results/checks-v20/`) and S, merged without other changes:
- W: weekend night import at 5.0 p/kWh, below the 5.9 p/kWh export rate; one direction per half-hour.
- P: a pump on each LT circuit; a pump outage stops its engine.
- C2: a 550 Sm³/h gas entry shared by GE1, GE2, B1 and B2.
- C4: PHE1 limited to 20 kg/s on its primary side.
- S: the shared LT heat-rejection capacity.

The test was whether a blind implementer facing five new rules at once misses some of them. S's `LT PHE 1` outage moved to h1 20:10–21:20 so that it does not coincide with P's `LT pump 1` outage at 18:10–19:20. Every rule's own mutant is still caught on at least one hidden day (`candidates/k/build/rule_pressure.json`). Codex built the package and `candidates/k/build/eval_rules.py`, which reports each rule's own test on K and on a copy with the old part outages removed.

**D, part outages with different consequences.** In the hidden days of v19, every part outage stops its unit. The two Opus trials that passed both mapped a part to its unit by its name's prefix and stopped the unit. D is S plus v15's exhaust diverter (`archive/energy-centre-dispatch-v15/`):
- each engine's HT heat is split in `part_load` into `jacket_water_heat_kw` and `exhaust_heat_kw`, with the same totals;
- each engine has `exhaust_heat_exchanger: {"bypass": "modulating diverter to the stack"}`;
- the HT circuit's sources are `GE? jacket water heat exchanger` and `GE? exhaust heat exchanger`.

The shipped tool changes only in the two lines that read these fields. Part outages now have three consequences, and none of the shortcuts gets all three right:

| Consequence | Hidden-day outages | Wrong under |
|---|---|---|
| The unit stops | `GE1 intercooler` (h2, h4), `GE2 jacket water heat exchanger` (h2 18:20–18:40), `EC1 condenser` (h1), the AC1 parts (h3), `LT PHE 1` (h1) | units only; unknown names ignored or rejected |
| The engine runs on, its exhaust heat going up the stack | `GE1 exhaust heat exchanger`, h2 12:00–14:50: stopping GE1 leaves h2 with no feasible plan; ignoring the outage claims 450 kW of heat that cannot be recovered | a unit's prefix stops the unit |
| Both engines share the remaining radiator | `LT radiator 1` (h2, h4), `LT radiator 2` (h3) | a circuit's outlet stops its engine; any one outlet will do |

The diverter can also send exhaust heat up the stack when nothing is out, which makes the visible day's least cost £956.99 lower than v19's (stack duty in 38 of 48 half-hours). Codex built the package and `candidates/d/build/eval_traits.py`, which reruns every test on four versions of the hidden days: as built, without the stopping part outages, without the exhaust and radiator outages, and with whole units only.

## Checks

| Check | S | K | D |
|---|---|---|---|
| `environment/` against v19 | only `plant.json`; `instruction.md` identical | only `plant.json` and `supply.json`; `instruction.md` identical | only `plant.json` and `planner/plant.py`; `instruction.md` identical |
| Solution, `tools/eval_energy.py` with `ECD_TASK` (rerun by Claude) | all tests pass | all tests pass | all tests pass |
| Solution in Harbor (jobs `ecd22s-oracle`, `ecd22k-oracle`, `ecd22d-oracle`) | reward 1.0 | reward 1.0 | reward 1.0 |
| Mutants, rerun by Claude (`build/mutants_claude_rerun.log`) | 45 of 45 caught | 51 of 51 caught | 48 of 48 caught, the header's lock-out on h1 among them |
| MILP cost gap, `fresh_days.py --days 16 --seed 2026` (Codex only) | £0.00027; 16 of 16, with radiator and LT PHE outages | £0.00019; 16 of 16, with pump, LT PHE and radiator outages and 3 weekends | £0.00023; 16 of 16, with exhaust, jacket water, LT PHE and radiator outages |
| A16 and A19 unchanged | both exit on the new topology or names | both exit on h1–h4; A19 passes the visible day, where none of the five rules binds | both exit on the new HT fields |

Claude changed one line of S's `tests/reference.py` after the build: LT heat now counts only for an engine above 0.5 kWe, as everywhere else in `true_flows`. Before the change, a plan with an engine at a few watts would have been charged its minimum LT heat. K and D were built from S after the change.

## Fairness prechecks

Two isolated readers per candidate, Codex (gpt-6.1-sol) and Claude Sonnet, each given only `instruction.md` and the visible files. The questions and raw answers are in `fairness/s/` and `fairness/d/`. K was not put to readers: its rules are W's, P's, C2's, C4's and S's, which readers had already checked one by one.

- S: both readers say the same things:
  - with `LT radiator 1` out, either engine can run alone over its whole range, and both can run together only while their LT heat stays within 220 kW;
  - with `LT PHE 2` out for ten minutes, GE2 is off for the whole half-hour and GE1 is unaffected;
  - with no LT outages the capacity never binds.

  Both noted that the radiators have no derating with air temperature and the exchangers no capacity. Neither offered another reading.
- D: both readers say the same things:
  - GE1 can run through an outage of its exhaust heat exchanger, with 270–450 kW less heat recovered;
  - GE2 must stop while its jacket water heat exchanger is out;
  - a radiator outage leaves both engines 220 kW to share.

  Sonnet noted that no file defines an outage of a part, so it inferred one from the circuits, and that the diverter's range is unstated; it took the full range, as the verifier does.

## Difficulty prechecks

A16 and A19 got only the changes needed to read each candidate's data (`difficulty/<c>/*.patch`).
- S: A16 needed one rule, that an exchanger whose own circuit only reaches radiators is a dump outlet. A19 needed the `lt_radiators` names added to the outage names it knows. Both then fail only `test_lt_heat_rejection`, on h2 and h3: neither has any idea of a shared capacity.
- D: on top of S's changes, both read the split heat fields and the new port names. Each then fails three things:
  - h2, because stopping GE1 for its exhaust exchanger leaves no feasible loading at 14:00;
  - `test_least_cost` on the visible day, h1, h2 and h4, because neither uses the diverter;
  - `test_lt_heat_rejection` on h2 and h3.

  The four-version runs are in `difficulty/d/eval-traits-*.log`.

## Blind trials

Claude Code with Opus 5.5 at max effort and the official trial settings (`scripts/run_trials.sh claude run 1`), one trial at a time. Each `blind/<trial>/` holds the deliverable, the verifier output, the agent's closing messages and the evaluations.

| Trial | Minutes | Reward | New rules | Header | Part outages |
|---|---|---|---|---|---|
| S1 (`ecd22s-blind1-claude`) | 36 | 0 | S implemented: a heat network with each radiator a capacity-limited node; all tests pass once the old part outages are removed | right | wrong: exits on `EC1 condenser`, `GE1 intercooler` and the like as unknown plant |
| K1 (`ecd22k-blind1-claude`) | 122 | 0 | all five pass on every day; all tests pass without the old part outages | right, after its own review agent found the lock-out | wrong |
| K2 (`ecd22k-blind2-claude`) | 124 | 0 | all five pass on every day; all tests pass without the old part outages | right | wrong: unknown names give a warning and are ignored |
| K3 (`ecd22k-blind3-claude`) | 29 | 0 | all five implemented in the code (direction modes, pumps, gas entry, PHE flow, radiator capacities). Each rule's test passes wherever the tool writes a plan; on h3 it exits | wrong: keeps the lock-out, so h1, h2 and h4 break the connection limit and h3 has no feasible plan | wrong |
| D1 (`ecd22d-blind1-claude`) | 98 | 0 | diverter, exhaust outage (GE1 at 1200 kWe through h2 12:00–14:50) and radiator capacity right | wrong: kept the lock-out and called it its most consequential call | **right**: the four versions fail the same tests, all from the header |
| D2 (`ecd22d-blind2-claude`) | 32 | 0 | the same as D1 | wrong: "I didn't model raising the tower setpoint" | **right** |
| D3 (`ecd22d-blind3-claude`) | 32 | 0 | the same as D1 | wrong: kept the lock-out and left the choice to the operators | **right** |

S was rejected after its first trial, as the v20 audit proposed: the blind tool limited the combined LT heat itself.

## Decision

None of the three goes into the task; the official task stays v19.
- **S** fails the blind precheck. The fresh implementer models the radiators as capacity-limited sinks of a heat network and gets the rule right, even though the strongest earlier tools have no such idea.
- **K** shows that stacking rules does not help: three blind implementers got all five rules right. The new fields are read as constraints, whether there is one of them or five.
- **D** makes the part outages easier, not harder. Every D trial applied outages to the heat exchangers, the radiators and the old part names alike. In the other blind trials of v21 and v22 (W, P, S1, K1, K2, K3) none of them did, and over v16–v19 only 3 of 10 did. D's parts look like equipment, such as `GE1 exhaust heat exchanger` with its own bypass field, and so they invite the question of what an outage of each does. v19's parts read as heat streams (`GE1 jacket water and exhaust`, `GE1 intercooler`), which is what keeps their outages out of view. All three D trials failed on the header instead. Three trials cannot show whether D makes the header harder, while it plainly gives away the part outages, the trap that stops the most runs.

Tally for the v19 structure: over v16–v19 and the six blind trials of W, P, S1, K1, K2 and K3, Opus got the part outages right in 3 of 16 trials, the header in 10 of 16, and both in 2 of 16. The D trials are not in the tally, since D changes how the parts are named.
