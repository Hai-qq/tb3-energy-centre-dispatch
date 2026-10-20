# Checks on v12 (v8.1 with the header error made silent)

Run on 2026-10-15 on the task files in `archive/energy-centre-dispatch-v12/` (hash
`7c9fb0eb20e576e8`), against Terminal-Bench `1d49c52` and Harbor `0.23.1.dev202609170426`.

| file | what | command |
|---|---|---|
| `static-checks.log`, `static-checks-comment.md` | CI's static-check step (27 checks, all pass) | `scripts/run_static_checks.sh <terminal-bench-checkout>` |
| `oracle/`, `nop/` | the verifier's output: oracle reward 1 (55 passed), nop reward 0 | `harbor run -p <task> --agent oracle` (or `nop`) `--env docker` |
| `mutants.txt` | 29 planted bugs, half-fixes, reporting and execution faults, each applied alone to the solution: all caught | `python tools/energy_mutants.py` |
| `fresh-days-without-header.txt` | the solution with only the shipped header rule put back (`absorber_needs_cold_weather`), on 16 days drawn at random: it writes a plan for every day and fails only the least cost, on 9 | `python tools/fresh_days.py --days 16 --seed 31 <app>` |

The Harbor runs used a frozen copy of the task (`staging/`). v12 drops four mutants of v8.1's
list (`kva_ignores_engines`, `kva_as_kw`, `kva_engines_absorb_kvar`,
`grid_flag_without_generators`): the connection now carries the whole site, so it never binds
and they pass.

How much more than the least cost the plans of the mutants this version is about cost (GBP per
day; a negative figure is a plan that breaks a limit, which other tests fail; measured with a
scratch script that prices each mutant's plans with the reference model):

| mutant | visible | h1 | h2 | h3 | h4 |
|---|---|---|---|---|---|
| `absorber_needs_cold_weather` (the shipped header rule) | 0 | +740.44 | 0 | +1654.28 | +485.56 |
| `lt_radiator_outage_ignored` | 0 | 0 | -324.32 | -237.46 | -111.54 |
| `phe1_outage_ignored` | 0 | 0 | 0 | 0 | -178.59 |

The header mutant fails nothing but `test_least_cost`: a tool that keeps the shipped rule writes
a workable plan for every day, here and on all 16 random days, and nothing short of a cheaper
plan shows that the rule is wrong.
