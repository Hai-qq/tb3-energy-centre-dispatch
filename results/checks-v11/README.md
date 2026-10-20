# Checks on v11 (the condenser water setpoint as a decision)

Run on 2026-10-14 on the task files in `archive/energy-centre-dispatch-v11/` (hash
`ea19cd9096c6134e`), against Terminal-Bench `1d49c52` and Harbor `0.23.1.dev202609170426`.

| file | what | command |
|---|---|---|
| `static-checks.log`, `static-checks-comment.md` | CI's static-check step (27 checks, all pass) | `scripts/run_static_checks.sh <terminal-bench-checkout>` |
| `oracle/`, `nop/` | the verifier's output: oracle reward 1 (55 passed), nop reward 0 | `harbor run -p <task> --agent oracle` (or `nop`) `--env docker` |
| `mutants.txt` | 42 planted bugs, half-fixes, reporting and execution faults, each applied alone to the solution: all caught | `python archive/energy-centre-dispatch-v11-tools/energy_mutants.py` |
| `fresh-days.txt` | eight days drawn at random: the solution passes all eight, the shipped tool fails all eight | `python tools/fresh_days.py <app> ...` |
| `cross-check.txt` | the verifier's whole-day MILP against a decomposition (every half-hour, engine combination and setpoint, the fans exactly on their curve, then a DP over the day): equal to 0.0001 GBP on all five days. The decomposition is written separately but imports the reference's `Day` and its plant functions, so it checks the optimisation's formulation, not the reading of the data | `python archive/energy-centre-dispatch-v11-tools/crosscheck_decomposition.py archive/energy-centre-dispatch-v11` |

The Harbor runs used a frozen copy of the task (`staging/`).

How much more than the least cost a plan costs when the setpoint follows a rule instead of
being chosen each half-hour (GBP per day; the verifier's tolerance is the larger of 0.5 and
0.02% of the least cost, 1.0 to 1.5 here; measured with a scratch script that applies each
mutant of `energy_mutants.py` and prices its plans with the reference model):

| rule | visible | h1 | h2 | h3 | h4 |
|---|---|---|---|---|---|
| fixed approach 4 K, held at 22 °C while AC1 runs (v8.1's correct model) | +24.89 | +105.78 | 0 | 0 | +31.80 |
| fixed approach 5 K, held at 22 °C while AC1 runs (the best single rule) | +3.31 | +9.75 | 0 | 0 | +10.98 |
| water no warmer than 22 °C or the wet bulb + 4 K (fans flat out) | +44.92 | +231.44 | 0 | 0 | +54.08 |

The tables in `plant.json` come from a physical model of a counterflow tower cell
(`archive/energy-centre-dispatch-v11-tools/tower_tables.py`).
