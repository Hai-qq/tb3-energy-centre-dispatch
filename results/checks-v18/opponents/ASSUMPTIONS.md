# Audit of the three strongest delivered implementations

Scope: the original `ecd16-run2-claude` delivery and the original two
`ecd17-run2-*` near-passes, with the latter copied here and given only a generic
parent-component outage fix. Original results are not edited. The baseline is
`archive/energy-centre-dispatch-v17`; runtime is Python 3.13.16, NumPy 2.3.4,
SciPy 1.17.0, pytest 9.1.1.

## Minimal patches and baseline proof

`ecd17-run2-codex-parts.patch` adds one prefix condition to `_available`.
`ecd17-run2-claude-parts.patch` makes `Outages.available` inspect both the named
unit and outage names beginning with that unit followed by a space. Neither patch
changes optimization, prices, heat flows, water temperature, reporting, start
costs, tolerances, or case data. These patches apply to every component name of
every parent unit, rather than hard-coding the four v17 hidden failures.

The actual command was:

```sh
ECD_TASK=archive/energy-centre-dispatch-v17 python - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, 'tools')
import eval_energy
for app in [
    'results/v16-trials/ecd16-run2-claude/app',
    'results/checks-v18/opponents/ecd17-run2-codex-parts/app',
    'results/checks-v18/opponents/ecd17-run2-claude-parts/app',
]:
    print(app, eval_energy.evaluate(Path(app).resolve()))
PY
```

All three passed all five days, including the deterministic second execution of
every day. Recorded evaluation times were 40.7655, 38.1620, and 36.2473 seconds
respectively. Raw results are in `v17-baseline.json` and `v17-baseline.log`.

## Assumptions checked

The following identifies assumptions in the source. "Correct for fixed plant"
does not mean it would survive arbitrary changes to `plant.json`: the instruction
expressly says that file does not change. The fuzzer exercises only changing
date/status/demand/weather inputs.

| Topic | v16 Claude | patched v17 Claude | patched v17 Codex | Assessment |
|---|---|---|---|---|
| Half-hour identity | Parses/sorts offset-aware instants; validates a whole local day | Same local-day approach | Validates 48 consecutive offset-aware times with one offset | Correct for generated format; alternate timestamp syntax is not a semantic difficulty candidate |
| Weather join | UTC instant dictionary; later duplicate wins | UTC instant join | UTC instant join, rejects duplicate timestamps | Every generated date/weather row is joined by instant; duplicate forecast rows have no declared precedence, so a duplicate-row trap would be unfair |
| Weekday/weekend and bands | Date weekday, local clock | Date weekday, local clock | Local first instant weekday, local clock | Correct; no clock-change day is generated |
| Engine minimum/rated output | Off or one adjacent segment; sorted table | Same, all adjacent pairs | Off or one adjacent segment | Correct for the fixed nonconvex tables; never interpolates across an off-to-minimum segment |
| Gross/net gas conversion | Uses basis and ratio | Uses basis and ratio | Uses basis and ratio | Correct multiplication for engines, gross-CV boilers unchanged |
| Engine reactive output | `sqrt(1-pf²)/pf`, overexcited positive | Same via tangent | Same via tangent | Correct fixed 0.95 overexcited generators; changing the fixed control field is outside scope |
| Start costs | Day-wide DP, actual midnight state | Day-wide DP, actual midnight state | Day-wide DP, actual midnight state | Correct; no undeclared minimum up/down time is invented |
| Unit auxiliaries | Fixed on-engine load, proportional AC load | Same | Same | Correct with towers/pumps already in site demand |
| Recovered heat | Derives recoverable streams from circuit destinations | Builds all source/sink circuit balances | Fixed HT stream and explicit PHE/AC paths | All agree for the actual plant; LT radiator heat is not supplied to buildings or towers |
| HT dumping | Allowed only if a circuit explicitly has a dump; this plant has none | Equality at every hot circuit | HT equality to PHE/AC | Correct for the declared complete topology |
| Boiler heat driving AC | PHE hot-side and LTHW separate | Circuit incidence enforces separation | Explicit separate HT and LTHW balances | Correct topology has no boiler-to-AC route; the stated 80°C LTHW is also below AC's 85°C inlet requirement |
| Heat-network loss | Adds fixed 75 kW | Circuit loss constant | Adds fixed 75 kW | Correct declared model; changing losses with demand would add an undeclared rule |
| PHE outage | Engine heat must all drive AC | PHE variable becomes zero | PHE bound becomes zero | Correct; an outage need not disable all CHP if AC can take all recovered heat |
| LT radiator outage | Generic endpoint dependency | LT heat balance plus unavailable radiator | Explicit radiator dependency plus generic patch | Correct |
| Engine source component outage | Generic endpoint ownership includes intercooler **and jacket water/exhaust** | Generic patch now disables parent | Generic patch now disables parent | Extending hidden outages to unused source names cannot defeat these three implementations |
| Chiller condenser / AC generator outage | All prefixed endpoints are parent dependencies | Generic patch | Generic patch | Correct after minimal repairs |
| Multiple outages | Union of all spans, including overlap | Union of all spans | Loops all spans | No first-record/last-record simplification |
| Partial/out-of-boundary outage | Any overlap disables a constant dispatch | Same | Same | Matches archived interpretation for all nonzero valid intervals |
| PV | Curtailable from zero up to forecast/inverter; zero for outage overlap | Same | Same | All are at least as flexible as reference; partial PV outage averaging is an explicitly accepted alternative, not an allowed new trap |
| Natural condenser temperature | `max(wet+4,21)` | Same | Same | Correct minimum |
| AC/shared-water interaction | Adds AC's 22°C floor for all chillers | Same | Same | All three fixed the existing header mistake |
| Other warmer-water operation | Enumerates only natural temperature and AC minima | Same and expressly discards warmer solutions with no AC | Allows every common temperature through the flat-COP endpoint | **A real difference, tested below; cannot be treated as a Codex failure using the old reference** |
| Tower rejection | Counts AC auxiliary heat, with a fallback when all hard thermal options are infeasible | Omits AC auxiliary heat | Omits AC auxiliary heat | Both readings were deliberately accepted in v17; a day feasible under only one reading must not silently make the other mandatory |
| Tower rating | Wet-bulb interpolation times available cells | Same | Same | Correct fixed rating table and its stated flat tails |
| Dry-bulb temperature | Loaded, unused by optimizer | Same | Same | No explicit LT-radiator dry-air duty curve or maximum coolant temperature in fixed data; a conditional heat-wave witness is tested below |
| Grid geometry | Circle uses nonnegative import and signed net Q | Optimizer uses import; final `grid_ok` uses signed exchange | Optimizer and report use signed exchange | Import/export interpretation is a possible fairness distinction; no new trap should demand one reading by constructing very high-Q net-export conditions |
| Import/export tariff | Positive/negative flows with import dearer than export | Same | Convex signed-exchange epigraph | Equivalent for fixed tariff, no arbitrage or omitted half-hour factor |
| Solver discretization | Adaptive circle cuts, adjacent segment enumeration | Adaptive cuts, adjacent segments | Adaptive cuts, adjacent segments | Actual geometry is at least as accurate as the archived one-degree MILP polygon; numerical margins are excluded as a difficulty mechanism |
| Whole-day optimization | DP over four commitment states | Same | Same | Exhaustive optimization within each implementation's physical model; overnight state and future restart cost are coupled correctly |
| Reporting precision | Three decimals | Three decimals | Nine decimals | Fuzzer uses original precision; tolerance-only deviations are not counted as conceptual failures |

## A tested physical distinction: warmer water can avoid a restart

The source is explicit about its limitation. v17 Claude's `best` contains:

> holding the water warmer only makes sense with an absorber running

The v16 implementation likewise builds a temperature list from the natural
temperature plus absorption-chiller minima only. Codex includes a continuous
compressor-power variable bounded by the power at the lowest and highest useful
water temperatures; because both fixed COP curves decrease continuously, every
intermediate total compressor input is attainable by a common water temperature.

The counterexample is a spring weekday: wet bulb 12°C, no PV, 2,000 kW building
heat, 700 kW chilled water, and both engines initially running. Site electricity
is 1,800 kW throughout the day except for one half-hour at 16:00. Three values of
the low half-hour were actually run: 500, 550, and 600 kW. The step is an
engineering stress case, not claimed as a measured NHS hospital trace.

| 16:00 site kW | v16 Claude total £ | patched v17 Claude £ | patched Codex £ | Archived MILP £ | Archived verdict for Codex |
|---:|---:|---:|---:|---:|---|
| 500 | 6032.973436 | 6032.973436 | 6014.361415 | 6032.974469 | Electricity balance error 63.158879 kW |
| 550 | 6034.445059 | 6034.445059 | 6014.361415 | 6034.446099 | Electricity balance error 13.158879 kW |
| 600 | 6014.655569 | 6014.655569 | 6014.656602 | 6014.656602 | Pass |

At 550 kW the Codex plan at 16:00 is:

```json
{
  "engines_kwe": {"GE1": 600.0, "GE2": 400.0},
  "boilers_kw": {"B1": 650.0, "B2": 0.0},
  "chillers_kw": {"EC1": 0.0, "EC2": 700.0, "AC1": 0.0},
  "pv_kw": 0.0, "import_kw": 0.0, "export_kw": 250.0
}
```

Electric balance requires 144 kW compressor input:
`1000 - 250 - 550 - (32+24) = 144`. EC2 therefore needs COP `700/144 =
4.861111111`, which its 22–26°C table attains at **24.259259259°C**. This is above
both the natural 21°C minimum and the AC minimum; AC is off. Tower rejection is
844 kW against 4,000 kW available. Heat closes exactly:
`835+590+650 = 2000+75`. The next half-hour keeps GE2 on and avoids its £27 start.

`../fuzz/verify_water.py` reconstructs that one common water temperature by
bisection against the actual COP tables, then recomputes all nine archived
physical/report tests. Both the 500 and 550 kW witnesses pass all nine. The
stored output is `../fuzz/water-probes/water-physics.json`; the 500 kW witness
requires 32.611683849°C and 894 kW tower rejection.

**What this proves:** there is a real operational possibility excluded by the
two discrete-water implementations, and the archived verifier also excludes it.
The observed Codex failure is therefore not an honest win for difficulty. A
verifier accepting the common warmer-water state would accept this Codex plan.
The experiment does not by itself establish a physically authoritative range of
all fan setpoints: the fixed files provide no fan-curve/control-range detail.
It also does not defeat the strongest patched Codex model as required by E2.

## A second tested distinction, rejected: a very hot LT radiator

The fixed LT circuits list `flow_c: 40`, `return_c: 35`, with the engine
intercooler as their sole source and the named LT radiator as sole sink. If those
are fixed operating temperatures and the radiator rejects to untreated outdoor
air, outdoor air at or above 40°C cannot take away positive intercooler heat.
Indeed, achieving a 35°C return with a finite dry-air radiator is impossible at
an air temperature of at least 35°C. None of the three strong implementations
uses dry-bulb temperature in dispatch.

`../fuzz/probe_hot_radiator.py` actually generated and ran a 42°C-peak heat-wave
case: approximately 1,000 kW active electricity, 1,200 kW building heat, 700 kW
cooling, no PV, and wet bulb peaking at 23°C. All three apps pass the nine ordinary
v17 checks and cost approximately £3,524.4878. Two explicitly labelled model
extensions were then solved independently:

| Conditional rule | Independent MILP optimum £ | Each of the three opponents fails availability in |
|---|---:|---|
| Both engines unavailable when dry bulb ≥40°C | 4261.517430 | Periods 26–32, seven half-hours |
| Both engines unavailable when dry bulb ≥35°C | 5528.366710 | Periods 20–36, seventeen half-hours |

An independently constructed witness keeps both engines off all day, supplies
heat from B1, and supplies cooling from EC1. It passes all nine physical/report
checks under both extensions, with 61.6666 kVA spare at the most loaded grid
half-hour. The cases are therefore not made impossible to manufacture failures.

**Why this still does not satisfy D or E:** the visible data does not specify
whether the radiator has adiabatic/precooled air, nor whether the 40/35°C values
are fixed limits or nominal design temperatures. The earlier v13 design had
explicit radiator duty conditions and limits; those conditions were removed
from the fixed visible files. Imposing them now as an unseen rule admits another
reasonable reading. The independent fairness review rejected promotion for
that reason. This is a successful conditional falsification of all three apps,
but it is **not** reported as a valid opponent defeat. Full inputs, three plans,
the engines-off witness, MILP results, and console output are retained under
`../fuzz/radiator-probe/` and `../fuzz/radiator-probe.log`.

## Why the existing determinate model is difficult to harden with data alone

There is a conditional completeness argument, stronger than simply observing
no random failures. For the fixed plant, v16 enumerates all four commitment
states, every adjacent engine segment, and both water regimes used by the
archived reference. Its LP includes every declared balance and relevant bound.
Its day-wide dynamic program handles the only declared temporal coupling,
engine starts. Date, status, demand, and weather changes alter coefficients,
bounds, and prices within those enumerated models; they do not add a new state
dimension or omitted physical equation. Generic endpoint dependencies already
include the unused engine source names.

The material discrepancies identified against the reference are the documented
auxiliary-heat alternative, curtailable PV, exact circle versus polygon and
safety margins, the warmer-water possibility omitted by both the reference and
the discrete-water solver, and the conditional radiator assumption above.
Numerical-margin failures and imposing an ambiguous interpretation are excluded
by the user's acceptance rules. This is not a proof that arbitrary source code
contains no unknown bug, but it explains why changing hidden RHS data does not
reliably create a new *understanding* failure in this already complete model.
The differential corpus supplies direct execution evidence for the conclusion.

## Directions excluded from claims of success

- Tiny positive AC outputs near the 0.5 kW "on" threshold, LP polygon error,
  three-decimal rounding, and safety margins: numerical/tolerance mechanisms.
- A loop outage or destination closure not naming one of the listed equipment
  components (for example `hospital buildings` with positive building demand):
  no unique operational interpretation from the fixed file.
- Duplicate weather rows, conflicting offsets, equal from/to clocks, omitted
  timestamps, or inventing a new outage date-time syntax: input-schema disputes,
  not an unambiguous consequence of this plant.
- A capacity problem that is infeasible even for the independent reference:
  no valid opponent failure, even when one delivery writes a least-overload plan.
- Making AC auxiliary heat count one particular way, or requiring PV averaging:
  both are known deliberately accepted ambiguities in v17.
- Increasing apparent-power stress only enough to exploit a 0.001 kVA reserve:
  explicitly excluded by E1 and by this analysis.

## Differential testing

`tools/fuzz_v18.py` uses archived build/model/test code under isolated module
names. Each app runs its own data loader, plant, tariff, and optimizer; its
original JSON rounding is reproduced before independent checks. Nine physical
and reporting tests run on every emitted plan. MILP cost checks run on scheduled
samples and every physical/cross-model difference. Specs are deterministic and
retained as JSONL, including unsuccessful draws; each failure retains all inputs
and the emitted plans. The completed run attempted 480 draws: 375 valid feasible
days, 104 reference-infeasible draws, and one excluded clock-change date. All
three opponents pass every feasible day; 130 distinct feasible inputs also pass
independent whole-day MILP cost checks. Of the 375 feasible days, 317 use the
unmodified archived reference and 58 use the explicitly marked extension below.
Final counts, exact commands, input audits and root-cause categories are reported
in `../fuzz/README.md` and `../fuzz/SUMMARY.json`.

The archived reference omits the two `GE* jacket water and exhaust` keys. When a
draw includes one, the raw KeyError is recorded; only those keys are then added
with generic parent-engine availability so the three opponents can be compared.
These records are marked `reference_extension`; they are never presented as an
unmodified v17 pytest pass. This omission is a verifier defect, not an opponent
weakness.
