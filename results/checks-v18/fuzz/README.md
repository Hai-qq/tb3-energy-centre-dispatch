# Differential evidence for v18

## Result

The three strong implementations produced **no accepted semantic defeat on 375
valid feasible random days**. This is 1,125 feasible app/day runs and 10,125
independent physical/report check invocations. Of those days, **317 use the
unmodified archived v17 reference**; another 58 explicitly extend its missing
engine heat-source component names. The unextended subset alone exceeds the
300-day minimum.

The entire corpus has 480 attempted draws: 375 valid feasible days, 104 days
declared infeasible by the reference MILP, and one excluded UK clock-change day.
The 104 infeasible inputs are retained and **do not count as opponent defeats**.
There are no unclassified failures or reference/witness conflicts.

Whole-day reference MILPs checked costs on **130 distinct feasible inputs**:
109 with the original reference and 21 with the explicitly marked component
extension. Every opponent met the archived cost threshold on all 130. These
are measurements of delivered programs, not an estimate of the probability that
a newly sampled Claude or Codex run will succeed.

The source audit, minimal outage patches, and baseline proof are in
`../opponents/ASSUMPTIONS.md` and `../opponents/v17-baseline.json`. Each of the
three apps passed all 55 archived v17 tests before fuzzing, including a
deterministic second execution of each official day. The random corpus does not
repeat every app/day execution a second time.

## Actual commands and reproducibility

All runs used Python **3.13.16**, NumPy **2.3.4**, SciPy **1.17.0**, and pytest
**9.1.1**. The Python executable was
`/workspace/scratch/3a594630faca/ecd-venv/bin/python`. Commands below use `python`
to denote that executable. `OPENBLAS_NUM_THREADS=1`, `OMP_NUM_THREADS=1`, and
`PYTHONDONTWRITEBYTECODE=1` were set for these runs.

```sh
python tools/fuzz_v18.py --days 384 --seed 180017 --workers 2 \
  --out results/checks-v18/fuzz/main

python results/checks-v18/fuzz/make_supplement.py
python tools/fuzz_v18.py \
  --specs results/checks-v18/fuzz/supplement-specs.jsonl \
  --seed 180018 --workers 2 --sample-every 4 \
  --out results/checks-v18/fuzz/supplement

python results/checks-v18/fuzz/cost_spotchecks.py --batch main
python results/checks-v18/fuzz/audit_retained_inputs.py
python results/checks-v18/fuzz/summarize_fuzz.py
```

The main and supplementary batches took 1,945.8124 and 479.7709 seconds
respectively with two worker processes. They ran sequentially. Console logs are
`main-run.log`, `supplement-run.log`, and `main-cost-spotchecks.log`.

The main generator initially admitted 2026-10-25 in `main/d0372`. This date is a
UK clock-change day, excluded by the instruction. All three programs passed the
raw case, but the result is excluded from every valid/feasible conclusion. The
generator now avoids that date. To reproduce the **original inputs exactly**,
use the retained specs, rather than regenerating that original draw from the
now-corrected generator:

```sh
python tools/fuzz_v18.py --specs results/checks-v18/fuzz/main/specs.jsonl \
  --seed 180017 --workers 2 --out results/checks-v18/fuzz/main-replay
```

The replay flags the clock date in its own result. It also uses the current
balanced sample schedule. Original main workers used `index % 16 == 0`, plus
all suspicious cases; that schedule was biased toward winter. The separately
executed `cost_spotchecks.py` corrects the evidence coverage by selecting every
fourth feasible input **within each season**, independent of agreement between
the apps. It ran 72 checks, with no reference errors or cost failures. Their
union with the original 43 main MILP optima and 24 supplementary optima is the
130 distinct inputs reported above.

## Coverage and independent checks

| Season | Valid feasible days | Distinct MILP cost checks |
|---|---:|---:|
| Winter | 98 | 42 |
| Spring | 109 | 33 |
| Summer | 57 | 23 |
| Autumn | 111 | 32 |
| **Total** | **375** | **130** |

All four initial engine states occur on feasible days: neither engine (101),
GE1 only (96), GE2 only (99), and both engines (79). The primary draw families
vary seasonal date and weather, ordinary and high demand, low electricity
relative to heat, reactive demand, clear/cloudy/zero/rated PV, one or several
outages, repeated outages, and separate/touching/overlapping intervals. The
supplement uses one outage and conservative demand within backup capacities;
its 96 draws were selected **without looking at opponent outcomes**.

The duration coverage includes 1, 5, 10, 15, 29, 30, 31, 60, 90, 120 and 240
minutes, plus boundary-clipped intervals. Some intervals cross half-hour and
tariff boundaries or finish at 24:00. All 21 named equipment/component outage
names occur on feasible days:

| Outage name | Occurrences on feasible inputs |
|---|---:|
| AC1 | 40 |
| AC1 absorber and condenser | 32 |
| AC1 generator | 30 |
| B1 | 40 |
| B2 | 29 |
| CT1 | 25 |
| CT2 | 27 |
| EC1 | 32 |
| EC1 condenser | 31 |
| EC2 | 28 |
| EC2 condenser | 32 |
| GE1 | 30 |
| GE1 LT radiator | 26 |
| GE1 intercooler | 29 |
| GE1 jacket water and exhaust | 34 |
| GE2 | 22 |
| GE2 LT radiator | 31 |
| GE2 intercooler | 34 |
| GE2 jacket water and exhaust | 29 |
| PHE1 | 16 |
| PV1 | 37 |

`hospital buildings` is deliberately excluded from maintenance-name generation.
It is a destination, rather than an identified maintainable piece of equipment;
closing it while requiring positive building demand has no unique declared
meaning.

For each emitted plan the harness calls the app's own loader, plant parser,
tariff code and optimizer, reproduces its original JSON precision, then invokes
the archived independent tests for coverage, ratings/availability, electricity,
heat, cooling, tower duty, connection limits, gas/cost reporting and grid flags.
It reconstructs true flows before checking, without trusting the plan's totals.
Every physical difference, exception, or substantial cross-app cost difference
receives an independent whole-day MILP in addition to scheduled cost samples.

| Program | Failures on 375 feasible days | Cost failures / 130 | Largest positive cost excess over comparator | Maximum measured app/day time |
|---|---:|---:|---:|---:|
| v16 Claude run 2 | 0 | 0 | £0.01955005 | 21.902674 s |
| v17 Codex run 2 + component patch | 0 | 0 | £0.01173446 | 32.336147 s |
| v17 Claude run 2 + component patch | 0 | 0 | £0.01188188 | 10.350664 s |

The cost comparator retains v17's stricter absorption-auxiliary tower load,
while its physical checks accept the documented alternative. Consequently a
plan may legitimately be cheaper than this comparator. The table reports
positive cost excess, **not absolute disagreement with a uniquely specified
physical optimum**. Small numerical differences are never promoted as new
traps. The £0.001 standard-answer requirement is checked separately by the
parent task; these are opponent measurements.

## Failure classification and source-confirmed causes

**104 infeasible random combinations.** Every reference solve reported HiGHS
Status 8, "The problem is infeasible." Each Claude returned a plan exceeding the
grid bound on 85 of those days and raised a no-feasible-loading error on 19.
Codex raised a no-feasible-loading error on all 104. The Claude source explicitly
allows a penalized grid-excess variable and minimizes excess before cost; its
day-wide DP raises only when no thermal loading exists. Its emitted grid
violations range from 2.3723 to 1,357.6354 kVA. Thus these are infeasible demand
and outage combinations, followed by different error-reporting policies. They
are not evidence of an exploitable misunderstanding.

**Missing reference component names.** Archived v17 raises `KeyError` on
`GE1 jacket water and exhaust` and `GE2 jacket water and exhaust`. All three
opponents already propagate these component outages correctly. The harness first
records the raw exception, then extends availability for only those two names
and their parent engines. Eighty valid attempted inputs used this extension;
58 were feasible. Every such record has `reference_extension`, and none is
described as an unmodified v17 pytest pass.

**Warmer condenser water: three deliberately constructed probes.** The 500 and
550 kW low-electricity cases make the two Claude implementations switch an
engine off, whereas Codex keeps both engines running and raises the common water
temperature to absorb power and avoid a subsequent start. On the 550 kW case,
Codex costs £6,014.361415 versus the archived comparator's £6,034.446099. Its
water temperature is 24.259259°C and tower duty 844 kW. The archived verifier
incorrectly reports a 13.158879 kW electricity error because it only considers
the natural temperature and AC floor. `verify_water.py` independently reconstructs
the common temperature from the COP curves; both low-electricity Codex plans
then pass all nine physical/report checks. This is a reference acceptance gap
and a difference in the two Claude optimizers. It is **not** a valid defeat of
patched Codex and therefore cannot satisfy E2. The 600 kW control case passes
all three programs without changing the verifier. Raw cases, plans and outputs
are in `water-probes/`.

**Hot LT radiator: a conditional falsification, rejected for fairness.**
`probe_hot_radiator.py` actually tested a 42°C-peak dry-bulb day. All three
opponents pass ordinary v17 at about £3,524.4878. If both engines are forced off
at dry bulb ≥40°C, all three fail seven half-hour availability checks and a
separate MILP gives £4,261.517430. A ≥35°C threshold gives seventeen failures and
£5,528.366710. An independently constructed engines-off witness is feasible
under both rules, with 61.6666 kVA grid spare at the worst half-hour. However,
the fixed visible data does not uniquely establish untreated dry-air rejection
or make the nominal 40/35°C circuit temperatures hard limits. The earlier v13
design stated radiator duty/limits explicitly, but those fields were removed.
This candidate was rejected rather than silently adding an undeclared rule.
`radiator-probe/` contains the exact inputs, plans, witness and conditional
reference outputs.

## Evidence integrity and limits

`SUMMARY.json` is the aggregate; `classification.jsonl` classifies every primary
and supplementary attempt. Each batch retains `specs.jsonl`, `results.jsonl`,
metadata and console output, including failed draws. Emitted plans for failures
and their inputs are retained. These records allow cases to be regenerated
without modifying historical results or current task data.

The post-run input audit compared 344 retained completed folders with exact
regeneration: every demand/weather CSV is byte-identical, and every JSON object
is identical. The original main `status.json` key order differs from replay of
the sorted JSONL spec; the audit records both hashes and content equality.
There are **zero input-content mismatches**. Successful folders already removed
by the harness are listed as outside this post-run audit, rather than being
retroactively claimed as hashed. Current fuzzer code adds expected status/date
checks and input SHA256 metadata for future runs.
`input-guard-validation.json` records the actual guard check on a retained case:
the correct spec produces no problems, while a deliberately wrong expected date
triggers both the status and demand-date guards without modifying the input.

The four-day smoke run and the deliberately conditional water/radiator probes
are kept separately and excluded from the 480-draw/375-feasible totals. No new
Harbor, Docker or real-model trial was run here. This corpus and source review
support the conclusion that the already complete strong solvers are resistant
to additional hidden RHS data under the fixed determinate model. They do not
prove absence of every possible unknown bug or establish a model pass rate.
