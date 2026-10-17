# Peer review: narrow v18 fairness repairs

This records the reasoning before the root agent applied its single revision.
The completed independent diff review and personally run post-fix checks are in
`FINAL_REVIEW.md`. Full B/C/E/F evaluation remains the root agent's responsibility.

## Recommendation

Accept bounded reconstruction of electric-chiller power as a fairness repair,
subject to the invariants below. It verifies the existence of one common
condenser-water temperature consistent with all output figures. It does not
grant arbitrary extra electrical consumption. Preserve the original coldest
control model's cost bound so that a reasonable fixed-target implementation is
not failed solely for declining a newly inferred control policy.

Also repair overlapping PV outage union, the omitted literal HT component
names, and the small-positive-AC mode threshold. Making the oracle use the
accepted strict auxiliary-heat convention is a consistency repair for criterion
B, not a new source of difficulty.

## Primary TB3 basis inspected directly

Read-only checkout:
`/workspace/scratch/3a594630faca/tb3-guidelines`, commit
`2e29ca91d5f1cb6fb60924bf867acc755565c044` (verified with `git rev-parse HEAD`).

| Primary document | Applicable rule | Consequence for this change |
|---|---|---|
| `CONTRIBUTING.md`, Task Quality | Correct completion and verifier success should coincide | A physically consistent recorded plan cannot be rejected solely because the reference picked a narrower unstated operating policy. |
| `docs/prompts/task-proposal.md`, Well-specified | Two reasonable readers should construct compatible verifiers; essential information cannot be left to guessing | The authentic warm-header Codex witness demonstrates a real interpretation mismatch, not a hypothetical concern. |
| `docs/prompts/task-implementation.toml`, `verifiable` | Verifier must be deterministic, efficient and reliable | Deterministic algebraic interval checking is suitable; ad hoc special-casing a saved artifact is not. |
| Same file, `outcome_verified` | Judge the delivered outcome, not the chosen algorithm or workflow | Inferring an unreported control's existence is legitimate when the submitted schema reports only aggregate powers. |
| Same file, `essential_difficulty` | Difficulty must come from reasoning rather than precision or clerical details | The0.4kW AC threshold bug, interval endpoint rounding and reference exceptions must not be counted as task hardness. |
| Same file, `test_instruction_alignment` | Assertions must follow the instruction/referenced context without adding requirements | Do not require a new header-temperature field or mandatory arbitrary warming. |
| `docs/prompts/trial-analysis.toml`, `task_specification` and `near_miss` | Distinguish meaningful wrong answers from implicit expectations and threshold-driven misses | Reclassify/reject apparent new failures caused by the current reference's narrow CW reconstruction; do not use them to advertise E success. |

The `well-specified` discussion is in the proposal document; it is not a named
criterion in this checkout's implementation TOML. This audit did not run TB3's
automated rubric or trial review and does not claim their approval.

## Why bounded inference is physically sufficient here

For fixed nonnegative outputs `q1,q2`, define

\[
g(T)=q_1/\mathrm{COP}_1(T)+q_2/\mathrm{COP}_2(T).
\]

For this immutable plant, both COPs are positive, continuous and nonincreasing
in the same condenser-water temperature. Their tables are explicitly linear
between knots and flat beyond their endpoints. Therefore `g` is continuous and
nondecreasing. Let

\[
T_{min}=\max(T_{wb}+4,21,22\mathbf{1}_{AC1>\epsilon}),\qquad
T_{max}=\max(T_{min},34).
\]

The lower-temperature expression means including22°C in the maximum when AC1
is positive; it does not impose0°C otherwise. Both EC tables are flat by34°C.
Consequently every aggregate compressor input between
`g(Tmin)` and `g(Tmax)` corresponds to at least one **single common** temperature
by continuity. No independent EC temperatures, fictitious electric heater or
unbounded electrical sink have been introduced.

The plan's implied compressor input is

\[
P_{EC}^{implied}=P_{GE1}+P_{GE2}+P_{PV}+P_{import}-P_{export}
-P_{site}-P_{engine\ aux}-P_{AC\ aux}.
\]

The unit powers, auxiliary parameters, site demand, PV, and grid exchange must
continue to pass their existing independent checks. Checking whether this
implied quantity falls inside the physically achievable interval is a constraint
test over an unreported control, not unconditional trust in a reported import.

The implementation should project to the interval:

```python
projected_ec = np.clip(implied_ec, minimum_ec, maximum_ec)
```

Then electricity balance compares the **original reported supply** against
`site + true_aux + projected_ec`. The remaining balance residual equals the
distance outside the attainable interval. It must still fail beyond the
existing1kW allowance. This formulation also handles legitimate rounding just
above the hot endpoint: using the cold endpoint as a fallback would create an
artificial discontinuity of tens of kW.

Since heat rejected by electric chillers is cooling output plus compressor
input, adjust rejection by `projected_ec - previous_ec`, or reconstruct it from
the final power once. Do not add the new input on top of the old compressor
work. Gas, engine reactive power, startup/maintenance and tariffs are unaffected.

### Required invariants and remaining limits

1. The monotonicity proof assumes nonnegative cooling outputs. Existing unit
   tolerance permits small negative rounding; clip these tiny negative values
   for the interval construction or explicitly document how the existing
   sub-kW allowance contains them. A materially negative cooling output still
   fails `running_ok`.
2. No running EC means an interval of exactlyzero. A claimed additional5kW
   electrical sink must fail. Turning a chiller off must not retain its electrical
   range.
3. Any positive AC output above a noise threshold forces the22°C lower bound.
   `>1e-9` is suitable for zero-output solver noise in this setting; it fixes the
   current physically meaningful0.4kW case. The threshold is a numerical guard,
   not a new turndown model.
4. The upper endpoint must be the end of every COP table, or the natural lower
   temperature if that is already warmer. Hardcoding34°C is valid only because
   this task explicitly freezes this plant. Do not extrapolate COP below its
   last listed value.
5. Availability, ratings, heat/cooling balances, PV bounds, true signed-Q
   connection checks, reported gas/cost/starts, determinism and cost quality
   remain independent requirements. Inference cannot replace these checks.
6. If the inferred power is outside the interval, projection is not a waiver:
   the unmodified electricity-balance residual must enforce the range. Check
   both below-minimum and above-maximum violations by5kW.
7. Cost remains compared to the stricter coldest-target model. That is an
   intentionally conservative **acceptance bound** across policy readings, not
   the mathematically exact optimum of the broadened warm-control feasible set.
   Report B's absolute MILP agreement separately from this policy acceptance.
   The subsequent independent envelope-MILP experiment found exactly equal
   coldest-target and continuous-header optima on all five actual v17 days and
   all five final v18 days. On the unpromoted witness day they differ by
   £20.08468395921136. The remaining distinction is therefore real, but this
   specific relaxation adds no optimality gap on the five scored days under the
   same auxiliary-heat and PV conventions. See `warm_envelope_benchmark*.json`.
8. The current loose auxiliary-heat treatment still permits either AC pump
   heat interpretation. Narrowing that tolerance into a new heat model would
   reintroduce the v16 ambiguity.
9. Simultaneous import and export cannot create a free advantage under the
   fixed tariff because every import rate exceeds export credit. Existing
   import/export limits and billing checks must remain active.

## Authentic independent witness

`check_water_witness.py` was personally run and verifies all48periods of the
saved patched-Codex plan from `fuzz/water-probes/days/w1` under the continuous
header interpretation. At16:00:

- GE1/GE2 are600/400kWe; EC2 supplies700kW; AC1 and EC1 are off.
- Site electricity is550kW, site reactive demand93.5kvar, export250kW.
- Compressor input inferred from balance is144kW; one common header at
  **24.259259°C** gives precisely that input on EC2's supplied COP curve.
- Cooling towers reject844kW, below4000kW. Signed apparent grid flow is
  343.236891kVA, below1220kVA.
- The frozen v17 reference insists on21°C and recomputes130.841121kW, giving a
  spurious13.158879kW electricity-balance error.
- Recomputed whole-day cost is£6014.361415012319. The saved v16 plan reports
  £6034.446, a difference of£20.084584988. That comparison is a real arithmetic
  saving; this audit does not claim an independent optimality certificate for
  the broader control model.

Files: `water_witness_checked.json`, `.stdout.txt`, and
`check_water_witness.py`.

## Minimal regressions supplied

`acceptance_regressions.py` checks11 cases. It tests the interval geometry
independently, then compares the selected reference's electricity classification.
The baseline run against frozenv17 found six disagreement cases, saved in
`acceptance_regressions_v17.json` and `.stdout.txt`.

| Case | Intended result |
|---|---|
| Natural header | Accept |
| Warmer26°C header without AC | Accept as a policy alternative |
| Both ECs with one common27.3°C header | Accept; demonstrates common-temperature feasibility |
| AC0.4kW at22°C | Accept |
| AC0.4kW but electricity computed at21°C | Reject; warm floor violated by5.147kW |
| Implied compressor input5kW below its minimum | Reject |
| Implied compressor input5kW above its maximum | Reject |
| No EC cooling but claimed5kW compressor input | Reject |
| Hot endpoint plus0.001kW rounding | Accept under existing balance allowance |
| Cold endpoint minus0.001kW rounding | Accept under existing balance allowance |
| Actual patched-Codex warm witness, all48periods | Accept |

After the root applies the task fix, run:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  /workspace/scratch/3a594630faca/ecd-venv/bin/python \
  results/checks-v18/fairness/acceptance_regressions.py \
  --require-fixed --label v18
```

These are targeted EC-envelope regressions. They complement, and do not replace,
the complete oracle,48fresh-day, mutation, adversary and six-artifact regression
gates required by the user.
