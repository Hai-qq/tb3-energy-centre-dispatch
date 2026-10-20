# Final consistency review

Review snapshot: **2026-10-18 06:49:53 UTC**. This is a new final review; earlier reviews retain their historical state, including the then-pending C2/C4 freezes.

**No material inconsistency found in the current synthesis. The supported outcome is a reproducible negative experimental branch, with zero qualifying v20 candidates.** This finding does not convert completed numerical checks into satisfaction of the user's candidate-adoption gate.

## Scope and method

Read the final `README.md`, `ANALYSIS.md`, `LOG.md`, `MATRICES.md`, `SUMMARY.json`, `prechecks/DECISIONS.json`, and `prechecks/BLIND_RESULTS.md`; compare them with the original upload's acceptance rules and the preserved source/evidence reviews. Read the additional LT design audit for its claimed status. Independently cross-check the raw fixed-day matrices, mutant records, nine fresh manifests, C1 differential summary, all three freeze manifests and before/after proofs. No candidate, model, CLI, test, Docker, Harbor, or formal CI run was performed for this final review. Only this file was written.

## Counts and outcomes

| Item | Independently checked result | Reporting assessment |
|---|---|---|
| Main candidate investigations | Five: C1–C5 | Correct; the additional shared-LT mechanism probe is expressly unqualified and does not become another completed or adopted candidate |
| Complete triple prechecks | C1, C2, C4; six reader reports and three frozen implementations | Complete is distinguished from passed; all three new rules were solved, so all three candidates are rejected |
| Fixed five-day matrices | Eleven applications per full candidate: oracle, two strong historical tools, seven historical failures, and the separately evaluated blind tool | Generated application status, failed-day sets, and maximum recorded CLI times agree with the raw matrices |
| Oracle fixed-day cost comparison | C1 maximum absolute delta £0.000181119163244; C2/C4 £0.000276852054412 each | All below £0.001 under the retained reference convention |
| Mutants | 43/43, 44/44, 44/44; total 131/131 | Correct; these are per-candidate checks, not 131 different new mechanisms |
| Fresh days | Each of C1/C2/C4 has seeds 2026, 2403, 87123 with 16 accepted days each: nine completed passing manifests, 144 candidate-days total | All completion, pass, input-integrity and generated-summary fields agree; all 720 input-file hashes and the recorded reference/test hashes match current files |
| Differential experiment | **C1 only:** 277 draws, 200 accepted, 77 rejected; four applications × 200 days = 800 application/day records | Correct scope; not attributed to C2 or C4 |
| C1 differential outcomes | Oracle 200/0; A16 117/83; A19 0/200; blind 91/109 (pass/fail) | Final summary agrees exactly with the raw summary; A19's additional least-cost failures number 113 |
| C1 input coverage | Winter/spring/summer/autumn 53/66/17/64; all 21 maintenance names | Correct; unequal seasonal acceptance is disclosed |
| Canonical task | Read-only `git diff --exit-code 9db580817b1dc46ac6c500f8c472faaafce0a997 -- tasks/energy-centre-dispatch` returned zero | Reports consistently retain v19 and make no adopted-v20 claim |

The complete `SUMMARY.json` decision section matches `DECISIONS.json`; its C1 differential section matches the preserved differential summary. The raw matrix source manifests additionally supplied **216 file-hash entries**, all of which independently match the referenced applications. This is a file-hash count, not an application count.

## Frozen blind evidence

Independently rehashed **323 C1 + 198 C2 + 307 C4 = 828 declared files**, checked exact file inventories, checked declared byte sizes where present, and matched each `FREEZE.json` SHA256 against both recorded before/after proofs. No discrepancy was found. These 828 files exclude the three manifests themselves, whose hashes were checked separately.

- **C1:** The visible day and all 91 emitted differential plans support new-direction correctness. The other 109 differential failures are preserved old-name rejections. Fixed h1–h4 exit before a plan. These facts correctly lead to rejection of the candidate under the user's new-rule gate.
- **C2:** Final reports explicitly say the hidden-day gas assertions **never ran**, because the old component names caused exit 1. New-rule correctness rests on source/checker/MILP review, the frozen 48-period binding case including boiler fuel, and the parent task's successful two-CLI external replay of that same frozen input. That replay is correctly kept separate from hidden-day success. The initial external diagnostic's metadata error and subsequent new-output rerun remain disclosed; the frozen tool was not repaired.
- **C4:** New PHE assertions pass, with 27 binding periods in external h2. The h1–h4 failures are exclusively the original availability assertion; lower illegal-plan costs are explicitly denied any savings interpretation. The correct branch is HT minus AC driving heat. Its successful new-rule implementation also requires candidate rejection.

The final reports preserve the self-test limits: shared helper/maintenance coverage gaps, C2's restricted seven-case MILP comparison, absent independent infeasibility certificates for the negative self-tests, and incomplete intermediate development archives. Final freeze integrity is not represented as exhaustive archival of every development iteration.

## Fairness, reference scope, and probability

The earlier material reference-scope concern is addressed. B establishes agreement within £0.001 with the independent full-day MILP **under the same retained narrow operating convention**. The broader accepted warm-water, auxiliary-heat and PV interpretations prevent claiming a universal optimum certificate. A positive gap to a cheaper feasible witness still proves suboptimality; its size is demonstrated feasible-plan savings, not an exact global regret over every accepted interpretation. Negative accepted deltas are not presented as errors. C4 retains the explicit fixed 90/70°C operating-temperature condition in D.

The engineering sources and synthetic choices are distinguished: C1's particular contract values and C2/C4's capacities are synthesized parameters; C5 and the additional LT probe retain their specific NHS evidence gap. The additional audit's topology experiment and possible future research do not satisfy A–F or a new prompt precheck.

The probability section now labels its candidate miss-probability intervals as **subjective and uncalibrated**, with no empirical or posterior interpretation. It does not treat 200 fixed-code replays, six reader contexts, or three substitute implementations as target-model trial samples. The conditional independence equation and numerical sensitivity calculations were independently recalculated: 37.3248%, 62.5026%, 80.6954%, 94.1480%; equal single-run pass rate for 95% six-run failure is approximately 0.851244%; the stated C1/C4 and C2 sensitivity endpoints round correctly. Those calculations supply no adoption credit or stable-3+3 guarantee.

## Remaining gates and release boundary

- **No further numerical or model reruns are called for by this consistency audit.** The counts and preserved evidence support the reported negative result.
- No candidate meets the user's adoption gate. C1/C2/C4 are rejected; C3/C5 and the additional LT probe have outstanding qualification work. That cannot be cured by labeling the numerical matrices successful or combining already-rejected mechanisms without fresh prechecks.
- Complete the authorized release bookkeeping: record the actual end time and commit/push/PR outcome, preserving the negative-branch framing and v19 base. This review does not claim that remote publication has already occurred.
- Formal target-model 3+3 trials, Docker/Harbor, and the designated formal static/implementation/CI reviews remain expressly unrun, as requested. They should not appear in the final response as completed gates.

The log's 04:40:50 UTC start and this review snapshot span more than two hours; the supplied experiment chronology does not claim that elapsed time substitutes for qualification. Earlier pending-state reviews are historical records, superseded for final status by the three frozen reviews and the current combined decision.
