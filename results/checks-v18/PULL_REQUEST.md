## Status: E is not met; this is an audit and coverage candidate

v17's six recorded failures rest on a narrow component-availability gap. This
change tests whether fixed visible files and different hidden inputs can defeat
the strongest existing implementations without adding an ambiguous requirement.
The experiments did not establish such a defeat: v16 Claude run2 and the two
minimally component-patched v17 run2 apps still pass all 55 v18 tests. This PR
must not be treated as meeting the stable six-failure target.

## Changes

- Keep instruction.md and all environment files byte-identical to v8.1.
- Repair reference handling for literal HT component names, overlapping PV
  outages, positive AC duty at the common-header boundary, and physically
  consistent warmer common-water plans. Preserve the previously accepted
  auxiliary-heat and partial-PV interpretations.
- Match the oracle to the reference MILP's stricter auxiliary-heat convention.
- Replace h2's isolated low-reactive-power point with a feasible night profile;
  add HT-source/AC-generator availability coverage and nested PV maintenance.
- Add two semantic mutants, a reproducible development matrix, a differential
  fuzzer and evidence-bound fresh-day generation/verification.
- Retain minimal opponent patches, the frozen visible-only surrogate, candidate
  probes, rejected candidates, source audits and raw evidence under checks-v18.

## Validation

- Oracle: 55/55; five-day maximum absolute cost delta £0.000276853.
- Fresh seeds 2026/2403/87123: 16 days each, all passed. Independent regeneration
  and rerun of all 48: all passed, max £0.000456374 absolute delta and 6.195931s.
- Full canonical mutant run: **41/41 caught, exit0**. Every classification is
  recorded in RELEASE_STATUS.json and final-mutants.log.
- E1/E2: **not met**, all three strong apps pass 55/55; patched apps also pass
  the frozen v17 baseline. The gate intentionally exits1.
- E3: frozen surrogate passes visible and fails four hidden availability checks
  on both versions. F: all six original v17 deliveries still fail on v18.
- Differential fuzz: 480 attempts, 375 valid feasible days, including317 using
  the unmodified v17 reference;1125 feasible app/day runs;130 distinct MILP cost
  checks; no valid strong-opponent failure.104 infeasible and one invalid-date
  input were excluded and retained in the audit trail.
- Independent fairness regressions passed. Continuous-header and strict MILP
  costs agree on all five scored days. Conditional radiator failures were
  rejected because the fixed specification does not uniquely imply that rule.
- One additional row-order probe reverses all demand/weather records without
  changing their timestamped values: all three strong apps still pass. An
  isolated start-count example exposes the reference's demand-order assumption;
  it is not used as an opponent failure or added to the 480-draw corpus.

No fresh subscription-model trials, Harbor/Docker execution or TB3 CI review
were run here. The first fresh attempt exposed two stale input-directory
mismatches; raw failures, diagnosis, unique-draw-path repair and full successful
reruns are retained, with the underlying filesystem cause explicitly unresolved.

See results/checks-v18/README.md, ANALYSIS.md, LOG.md and RELEASE_STATUS.json.

Publication recovery preserved the exact tested Git tree. The final additional
row-order outputs were rerun after cleanup and are explicitly identified as new
executions. The follow-up evidence commit changes no task behavior. See
PUBLISHING.md and publication-verification.json for integrity checks.
