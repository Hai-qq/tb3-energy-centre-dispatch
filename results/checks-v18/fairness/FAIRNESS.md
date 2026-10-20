# Independent fairness audit of the frozen v17 task

This audit uses `archive/energy-centre-dispatch-v17/`, rather than a moving copy of
`tasks/`, so subsequent v18 edits cannot change its findings. The frozen reference
SHA-256 is `6f4a64c8d66334be60e50f7813f85aec2beb9f3d9a78049553809b1e6766c69d`.
Historical claims below are explicitly distinguished from experiments executed in
this audit. No new model trial, Harbor trial, Docker run or external CI was run.

## Personally executed checks

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  /workspace/scratch/3a594630faca/ecd-venv/bin/python \
  results/checks-v18/fairness/audit_checks.py
```

The command exits 0 on Python 3.13.16, NumPy 2.3.4 and the installed SciPy 1.17.0.
Machine-readable results are `audit_checks.json`, and captured output is
`audit_checks.stdout.txt`. The script creates its temporary fixtures only within
this directory. It checks 13 visible files byte-for-byte against v8.1; manually
recomputes gas, cost, auxiliaries, heat, cooling rejection and starts; probes every
component dependency that v17 implements; checks interval overlap and boundaries;
and demonstrates the verifier gaps below.

### Material findings

1. **The constant-output convention is actually visible.** It is not merely an
   assertion in the reference model. The module docstring of
   `environment/dispatch.py` states:

   > Writes, for each half-hour of the plan date (local time), the output of every unit,
   > held for the whole half-hour, the grid exchange, the gas burned (kWh, as billed) and the
   > cost (GBP, including the starts of engines started in that half-hour), with day totals
   > in `summary`.

   Thus a controllable unit with a 10-minute outage cannot supply a smaller positive
   output continuously for the whole half-hour. For each of the eight implemented
   component names, outages 10:10–10:20, 12:30–13:00 and 14:20–14:40 correctly disable
   the owning unit at 10:00, 12:30, 14:00 and 14:30, and no other periods. Endpoints
   such as 13:00 are handled as exclusive. Multiple outage records are unioned for
   controllable units. No new ambiguity is needed to retain that rule.

2. **Overlapping PV outages produce a confirmed false-rejection risk.** PV has a
   distinct reasonable interpretation because `weather.csv` explicitly contains
   half-hour averages. v17 accepts prorated PV for a partial outage but adds outage
   durations instead of unioning their intervals. On the visible profile at 12:00,
   forecast PV is 257.8 kW. Records 12:05–12:15 and 12:10–12:20 remove 15 distinct
   minutes, leaving 128.9 kW average. v17 counts 20 minutes and caps the plan at
   85.933333 kW. The gap is **42.966667 kW**. This is a reference defect, not a fair
   opponent weakness. Keeping PV off for the whole period remains accepted.

3. **Two literal component names are missing from v17's reference inventory.**
   Outages of `GE1 jacket water and exhaust` and `GE2 jacket water and exhaust`
   each raise `KeyError` in `Day.__init__`. These exact strings occur in visible
   `plant.json`. By contrast, the strongest v16 deliverable derives the parts list
   from every circuit endpoint and includes both. Adding these names would repair
   coverage but does not defeat that deliverable. `hospital buildings` is also an
   endpoint, but taking buildings out is not a meaningful independent maintenance
   instruction while retaining their positive demand; it should not be used as a
   hidden trap.

4. **The AC mode tolerance is not physically continuous.** At frozen h3 00:00,
   a plan with AC1 = 0.4 kW and EC1 = 1000 kW requires 22°C condenser water. Its
   EC1 power is 153.846154 kW. Because `true_flows` uses `AC1 > 0.5` to select the
   warm regime, it recomputes 148.698885 kW: **5.147269 kW** below the physically
   consistent value, larger than the 1 kW balance tolerance. This could make a
   correct small-positive-AC plan fail. It is a numerical-boundary defect and must
   not be presented as a new reasoning trap under criterion E.

5. **v17 deliberately accepts two different cooling-tower models.**
   `true_flows` omits AC auxiliary heat from rejection, while `least_cost` includes
   it. That protects both readings of auxiliary heat disposal but means the
   benchmark is the stricter model's minimum, rather than the unique minimum of
   every accepted plan. The root agent separately executed the current oracle
   and reported h1 at £5.812224697746 and h4 at £14.878995913985 below the strict
   benchmark; the README's claimed absolute gap under £0.001 is therefore not
   established by the archive prose. These figures are **root-agent experiments,
   not this audit's own replay**. v18 can choose the stricter accepted convention
   in its oracle to meet B without claiming the ambiguity disappeared.

6. **Economic warming of the condenser header is an unresolved model boundary.**
   See the separate discussion below. It should not be used to manufacture a
   claim of unambiguous difficulty, and one of the required adversaries already
   implements it.

## Requirement inventory

The following inventory covers the fields in `instruction.md`, `plant.json`,
`supply.json`, the visible input schema and shipped tool, and every assertion in
`test_plans.py`. “Verified” names a personally run check when available; code
inspection alone is labelled as such. Fixed plant properties cannot be activated
by a new hidden date when the plant itself is immutable.

| Requirement / information | Visible source and consequence | Verifier / audit result |
|---|---|---|
| CLI accepts `--data` and `--output`; writes the existing JSON shape | Instruction gives exact command; shipped `dispatch.py` defines date, periods, unit maps, grid, gas, cost and summary | `test_plan_covers_the_day`, reporting tests; inspected. No extra output field may be required. |
| Date and 48 timestamped local half-hours | `status.date`, `demand.period_start`, instruction says each half-hour and no clock change | `test_plan_covers_the_day`; reference checks 48 source rows and date. The supplied rows are ordered; an external CSV sorting guarantee is not explicitly stated. See the later `../order-probe/FAIRNESS.md` audit before using permutations as difficulty. Do not add DST dates. |
| Weather is keyed by the same instant, UTC rather than local date | Instruction says weather averages by UTC start; demand includes local start/offset | Reference `astimezone(UTC)` join; inspected. Four seasons are valid probes; a changed schema or conflicting duplicate timestamp is not. |
| Import tariff weekday/weekend uses local plan date | `time_basis: local time`, weekday/weekend bands | Reference `date.weekday`; inspected. BST Monday/Saturday probes are fair. |
| Tariff band endpoints | Explicit `from`/`to`, e.g. 16:00–19:00; per-half-hour start | Reference uses half-open bands; inspected. No unstated holiday calendar or Capacity Market charge exists. |
| Pence/kWh to GBP, 0.5 hour energy, MWhe maintenance units | Tariff keys and `maintenance_gbp_per_mwhe`, per-half-hour plan | Manual example gives 2756.18 kWh gas and £160.41883 including one GE2 start; PASS. |
| Engine minimum output versus off | Instruction says part-load points run minimum to rated; tables begin at GE1 600, GE2 400 kWe | `running_ok` enforces off or minimum-through-rated. Three-point interpolation manually checked at GE1 750 kWe. |
| All part-load knots matter | Instruction says linear between points and flat beyond ends | Manual GE1 750 kWe gives fuel 1990 kW and HT 972.5 kW, not the end-to-end line; PASS. |
| Engine fuel is net CV; billing is gross CV | `fuel_basis: net CV`, gas `billing_basis: gross CV`, ratio 1.108 | Multiply engine fuel by 1.108; manual arithmetic PASS. |
| Boiler efficiency is already gross CV | B1 0.905, B2 0.83, `efficiency_basis: gross CV` | B1 905/B2 830 kW each consume 1000 kW gross; no extra ratio; PASS. |
| Boiler maximum output 2000 kW, no stated minimum | Explicit `max_kw`; no boiler part-load/minimum/ramp data | `running_ok` direct bounds; inspected. Cannot invent turndown or ramp constraints. |
| Engine auxiliary power is per running engine | GE1 32, GE2 24 kWe; demand excludes listed auxiliaries | Manual auxiliary calculation adds 56 kWe for two running engines, not proportional to their loading; PASS. |
| Absorber auxiliary power scales with cooling output | `auxiliary_kwe_per_kw: 0.022` | At AC1 355 kW, auxiliary 7.81 kWe; total 63.81 kWe in manual example; PASS. |
| Tower fans and pumps already in site electricity | Instruction explicitly includes them in demand | No additional fan curve or arbitrary pump auxiliary can be introduced; inspected. |
| Generator fixed PF, overexcited | `power_factor: 0.95`, `control: fixed power factor, overexcited` | Subtract generator Q = P sqrt(1−PF²)/PF from whole-site Q; manual arithmetic and signed-Q check PASS. |
| Generator kVA rating | 1500/1000 kVA with 1200/800 kWe, fixed PF | Maximum actual 1263.157895/842.105263 kVA, both below rating; **redundant** for this immutable plant. |
| Negative net Q is still apparent power | PF field plus connection kVA; Q enters squared norm | At site 50 kvar and engines 2000 kWe, netQ −607.368210 kvar; import cap 1058.066093 kW. Ignoring Q's negative side overestimates by 161.933907 kW; PASS. |
| Import capacity is 1220 kVA | `import_capacity_kva: 1220` | `hypot(import,Q)`; polygon maximum radial excess 0.046455631 kVA < 0.5 kVA tolerance. Cannot count polygon/tolerance effects as reasoning failures. |
| Export is at most 250 kW | `export_limit_kw: 250`; export paid 5.9 p/kWh | `test_connection_limits`; inspected. |
| Signed export kVA versus import-only kVA | Wording says import capacity and separate active export limit | On the five actual v17 days, siteQ in 50–352.1 kvar; even worst export is bounded by 656.807539 kVA. The two readings are observationally identical here. Avoid activating the distinction with extreme Q as a new trap. |
| No profitable simultaneous import/export | Every fixed import band exceeds export rate | At an exact optimum both cannot be positive: reducing both preserves net balance and lowers cost. No extra binary is mathematically required. |
| Full-day start costs, including midnight initial state | `start_cost_gbp`, `running_at_midnight`, tool docstring says starts are in the period's cost | Manual already-on GE1/new GE2 case counts one £27 start; PASS. DP/MILP links days only through starts. |
| No unstated minimum up/down time or ramping | Instruction reports excessive starts but supplies only start costs | New minimum-up/ramping assumptions would not be uniquely recoverable and cannot be introduced. |
| HT heat goes only to AC1 or PHE1 | `engine_ht.from` names engine HT streams; `to` is exactly `AC1 generator`, `PHE1`; instruction says complete graph | Heat equality/no dump, nonnegative PHE1 flow; inspected. Exhaust bypass hardware is absent and cannot be presumed. |
| LT intercooler heat is not useful HT | 40/35°C loops lead solely to each LT radiator | Reference omits LT from useful heat; manually checked engine HT 1562.5 kW for GE1 750/GE2 400; PASS. |
| AC1 must be driven from engine HT | `engine_ht.to: AC1 generator`; boilers only feed LTHW | Nonnegative HT remainder in reference; inspected. Boiler backfeed to AC1 is unsupported by topology and by 80°C < 85°C minimum. |
| AC hot-water temperature requirement | Engine HT flow 90°C, absorber minimum inlet 85°C | Always met for the fixed plant; **not an unused hidden-day axis**. Flow rates/capacity of PHE1 are not given; cannot invent them. |
| Heat supplied to buildings includes LTHW loss | `lthw.loss_kw: 75`, demand is at buildings | Equality adds 75 kW; inspected and used by manual physical reading. |
| PHE1 outage blocks its flow, not automatically every engine | Shared engine HT also feeds AC1 | Reference forces engineHT−ACdrive=0 while PHE1 out. Engines may run if AC1 absorbs all HT; blanket engine shutdown would be wrong. |
| Chilled-water outputs meet demand | Named coolers and forecast cooling kW | `test_cooling_balance`; inspected. No chilled-store or dumping circuit exists. |
| EC output ratings and COP vs entering condenser water | EC1 1400, EC2 1000 kW; explicit COP tables | At 22°C, EC1 650/6.5=100 kWe and EC2 520/5.2=100 kWe; manual PASS. |
| Natural coldest header and AC minimum | Towers approach 4 K, leaving minimum 21°C, variable-speed fans; AC inlet ≥22°C | v17 uses max(wet+4,21), and at least22 with AC. Small-positive AC mode threshold is a confirmed reference defect. Reachable higher setpoints are discussed below. |
| All chillers see one condenser-water circuit | One `condenser_water` circuit lists EC1, EC2 and AC1 | EC COP changes with the shared header; inspected/manual warm-COP calculation PASS. Independent per-chiller header temperatures are unsupported. |
| Cooling towers reject driving energy too | Condenser endpoints plus conservation of energy, specified COPs | Manual example: EC cooling+compressor work and AC cooling+drive sum 2225 kW; PASS. AC auxiliary heat location is ambiguous and v17 accepts both models. |
| Tower capacity per available cell vs wet bulb | Per-cell table and CT1/CT2 IDs | Interpolation and available-cell sum; inspected. Flat ends are expressly stated, so linear extrapolation is wrong. |
| PV forecast and inverter cap | `pv.inverter_ac_kw:280`; loader describes forecast AC output | Forecast beyond280 violates correct-data promise; not a fair trap. Reference does not clip but all supplied forecasts stay bounded. Strong adversaries already clip. |
| PV curtailment | Output format has `pv_kw`, fixed export limit, no must-take clause | Validator allows any nonnegative PV up to forecast; strict reference fixes available PV. If a future input needs curtailment, fixed-PV reference could incorrectly claim infeasibility. Do not confuse that with an opponent failure. |
| Plant outage names include circuit components | Instruction says all plant/connections listed and `status` holds planned plant outages | Eight implemented part dependencies tested PASS; two literal HT source names are omitted by reference and cause `KeyError`. |
| Any touching outage disables constant unit output | Visible dispatch docstring quoted above | Eight component cases, partial and full intervals, multi-record union and endpoints manually tested PASS. |
| Two simultaneous tower outages | Both cells unavailable means zero rejection capacity | Forces zero cooling unless another specified rejection path exists (none here). Positive demand then makes the input infeasible; cannot be a hidden hard case by itself. |
| Partial PV outage alternative | Weather is an average; fixed-period dispatch wording pulls the other way | v17 accepts all-off and service-minute averages. Overlapping intervals need union; confirmed defect. |
| Every reported figure is consistent | Instruction says every figure consistent with operation; schema specifies units | Gas, cost, engine starts, import/export totals, grid flags are independently recomputed. Manual arithmetic PASS; no new output schema. |
| Deterministic rerun and execution limit | Instruction: same plan each time, two minutes, only Python3.13/NumPy/SciPy | Dedicated repeatability test and execution wrapper; runtime/determinism are required, but adversarial hardware slowness is not an admissible new trap. |
| Least-cost tolerance | Instruction asks least-cost; reference permits max(£0.5,0.02%) | Fair numerical allowance; benchmark currently chooses the stricter of two auxiliary/PV readings. Matching one relaxed model does not necessarily mean absolute £0.001 gap to strict MILP. |

## Deliberately warmer condenser water

The v17 Codex run2 deliverable already models this explicitly. In
`planner/optimize.py`, `_loading`, it introduces an aggregate electric-chiller
power between the sum computed at the coldest admissible header and the sum at
the flat end of every COP table (34°C for this plant). For fixed chiller outputs,
both COPs decrease continuously with a common header temperature. Consequently
their summed power is continuous and monotone, and every power between those
endpoints corresponds to a common reachable temperature **if** the control model
permits the entire temperature interval. The representation is mathematically
sound under that assumption; it does not improperly give each chiller its own
temperature. Recorded import/export plus unit outputs implicitly determines the
aggregate chiller power, so the absent temperature field does not itself make
the arithmetic uncheckable.

There is nevertheless a distinction between two reasonable engineering models:

- Model 1 controls the header to its coldest admissible operating target,
  increased to the minimum required by an operating absorber. This is the model
  adopted by the current reference and the strongest v16 implementation.
- Model 2 treats VSD tower operation as a freely selectable condenser-water
  temperature over the entire relevant COP interval. That can deliberately
  consume compulsory generation when export is constrained, especially if
  generator reactive support requires engines to remain online. Codex run2 uses
  this model.

Visible data says `fans: variable speed`, `approach_k:4.0`,
`min_leaving_water_c:21.0`, and the COP tables flatten after34°C. It gives neither
fan minimum speed/turnoff behaviour nor a controllable setpoint interval or
the tower-control policy. The data supports warming to protect AC1 under v17's
intended idealization; it does not independently establish that every economic
setpoint up to34°C is part of the plant's allowed scheduling controls. External
tower guidance cannot add an absent site control specification.

**Recommendation:** preserve or broaden acceptance for demonstrably physically
consistent warmer plans, but do not claim that forcing a coldest-target
implementation to lose money is a uniquely implied new trap. If the desired
future task genuinely optimizes that control, state the allowed control range
and reporting convention in the visible data, then retest as a visibly changed
task. Under the present no-visible-change requirement this mechanism carries
fairness risk. It also cannot make the patched v17 Codex run2 fail, since that
adversary already implements it.

## Still-unused consequences and limits of a data-only hardening

Useful probes that remain legitimate include upstream/later component names,
multiple disjoint maintenance intervals, outage time boundaries, PHE1 outages
with AC1 as the only HT sink, flat-end COP/tower tables in very cold/hot weather,
alternating electricity/heat conditions near start-cost decisions, all four
midnight engine states, and reactive export with normal positive site kvar.
Each is derived from explicit fields, but all follow the same piecewise-linear
balances and one-step engine-state transition already implemented by the
strongest artifact. Their being legitimate does not establish that they are new
failure mechanisms.

Do not add: emissions/CHPQA/Capacity Market charges absent from tariff; engine
ramp/minimum-up/minimum-down data absent from plant; thermodynamic redesign or
extra heat-dump equipment; site control ranges absent from tower data; failure
on duplicate/unknown invalid data; fractional timing conventions that contradict
the visible dispatch docstring; tiny positive AC values used to trigger the
verifier tolerance discontinuity; or cases whose only separation is a solver's
circle approximation or deliberate time budget pressure.

The strongest v16 implementation was inspected directly: its component list is
derived from circuit endpoints; unit outputs use exact adjacent segments;
loading uses LPs and adaptive circle cuts; full-day DP includes initial state
and starts; multiple outages are unioned; PV is bounded and curtailable;
temperature choices are natural/AC minimum; and AC auxiliary rejection is
included with fallback only when no strict plant loading exists. A hidden day
can expose a real missing control interpretation or a reference bug, but a
correct equivalent optimization is not defeated merely by more combinations of
already modelled data. The 300-day differential experiments should be read as
falsification attempts, not statistical certification of all possible inputs.
