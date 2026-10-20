# What the evidence can and cannot say about v17 pass probability

## Direct evidence and its provenance

**Historical model trials:** v17 has three completed Opus runs and three completed
GPT runs, all scored zero. Their saved deliverables, verifier output and review
summaries are in `results/v17-trials/` and `results/analysis-v17/`. This audit did
not run either model. `HARDENING.md` says the external reviewer previously solved
v8.1 with Opus twice in three trials; the corresponding external trajectories
are not in this repository, so that report cannot be audited down to code here.

**Personally executed artifact replay:** the following command replayed eight
older completed artifacts, twice per day, against the frozen v17 verifier:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  /workspace/scratch/3a594630faca/ecd-venv/bin/python \
  results/checks-v18/fairness/replay_same_visible_history.py
```

All eight fail. Exact failure names and process errors are in
`same_visible_history_replayed.json` and `.stdout.txt`. These are eight
**re-evaluated artifacts, not eight independent new model trials**.

| Artifact cohort | Personally replayed artifacts | Result under frozen v17 |
|---|---:|---|
| v8 Opus runs1–3 | 3 | 0/3; run3 fails only component availability on h1–h4 |
| v8 GPT runs1–3 | 3 | 0/3; cold-header infeasibility remains on h1,h3,h4, and h2 has availability failures |
| unchanged v8 Opus rerun | 1 | 0/1; header and component failures |
| v16 Opus run1 | 1 | 0/1; fails only component availability on h1–h4 |

The v8 instruction, plant data and shipped Python source are identical to v17's;
there is one literal visible-file difference: `environment/Dockerfile` changes
`python:3.13-slim-bookworm` to the same image with a pinned digest. v8.1, v16 and
v17's 13 visible files compare byte-for-byte equal. This is therefore a closely
matched artifact cohort, with an explicit image-pin qualification for v8.

Combining these replays with the root agent's v16 run2 and v17 replays gives the
following **descriptive** artifact outcomes under the same v17 scoring rule:
Opus 1/9, GPT 0/6. Those fractions are useful for describing the artifacts in hand
and must not be promoted to future pass-rate estimates. They have not been
sampled under a pre-registered fixed-version protocol.

## What the completed implementations reveal

- v17 Opus run1 spends about133 minutes and understands the header but rejects
  component names; run2 spends28 minutes, solves the optimization and misses
  the component mapping; run3 spends28 minutes and retains both major gaps.
- v17 GPT run2 spends11 minutes and solves everything except component mapping;
  runs1/3 spend9/10 minutes and retain cold-header and component errors.
- The v16 Opus run2 implementation derives parts directly from every thermal
  endpoint. It is an existence proof that the unchanged visible input permits
  this model family to produce a solution that survives the v17 tests. It also
  handles upstream HT endpoint names better than the v17 reference does.
- The personally replayed v8 Opus run3 already solves the header and full-day
  quantitative model; its only v17 gap is parts, despite being authored several
  rounds earlier. Multiple “nearby” implementations are one local correction
  away from passing. The question is how often an agent decides to make that
  correction, not whether a conventional solver can perform the optimization.

These observations are supported by final code and replay results. Historical
agent claims such as “120 made-up days” or “an independent optimizer agrees” in
`official-v8.md` are claims in the recorded closing messages; their original
scratch validation scripts are unavailable here and were not independently
reproduced. They show the agent's stopping judgment, not externally verified
coverage.

## A numerical estimate, with honest uncertainty

If a single planning number is necessary, use **Opus about20% and GPT about10%
per fresh v17 run**, with broad qualitative planning ranges of roughly
**10–30% for Opus and 3–15% for GPT**. These are subjective risk estimates, not
confidence intervals. Opus has both a passing same-visible-input artifact and
several near misses; GPT has a near miss and a passing v15 artifact, but v15's
visible convention fields are a confounder. There is insufficient evidence to
distinguish, for example,5% from15% reliably for either model.

The statistical uncertainty is much wider than those planning ranges. With
zero successes in three independent fixed-version trials, the exact one-sided
95% upper bound for a model's success probability is

\[
p_{95}=1-0.05^{1/3}=0.6315968501.
\]

The data alone does not even rule out63% at that confidence level. To show prior
sensitivity without hiding it, `audit_checks.py` computes two illustrative
Bayesian models from the same0/3 observation:

| Prior for each model's pass rate | Posterior mean | Equal-tail95% interval | Predictive probability its next3 all fail | Predictive probability next3+3 all fail, independent model priors |
|---|---:|---:|---:|---:|
| Uniform Beta(1,1) | 20.0% | 0.63%–60.24% | 57.14% | 32.65% |
| Jeffreys Beta(0.5,0.5) | 12.5% | 0.015%–53.56% | 72.19% | 52.11% |

The last column integrates over posterior uncertainty; it is not obtained by
raising one minus the posterior mean to a power. These calculations are a
sensitivity illustration under an idealized binomial model, not a claim that
either prior describes these model/tool sessions accurately.

For fixed assumed pass probabilities, the next six all fail with probability
`(1-p_Opus)^3 * (1-p_GPT)^3`:

| Assumed Opus pass probability | Assumed GPT pass probability | Probability next3+3 all fail |
|---:|---:|---:|
| 5% | 2% | 80.70% |
| 10% | 5% | 62.50% |
| 15% | 5% | 52.65% |
| 20% | 10% | 37.32% |
| 25% | 15% | 25.91% |
| 30% | 10% | 25.00% |

Thus “all six happened to fail” is entirely compatible with a substantial chance
that the reviewer sees a pass. The development objective can be to reduce known
failure-escape mechanisms, but the archive does not justify calling v17 stable.

## Why pooling every historical trial would be misleading

1. **The task changes.** v9–v15 modify visible hardware or convention fields;
   they are not draws from the v17 prompt distribution. Adding explicit fields
   changes how carefully agents inspect both the new and old issues.
2. **Rounds stop after a pass.** `HARDENING.md` records sequential stopping and
   choices to run only Opus in several rounds. A pooled “since v9” percentage
   treats a selected development sequence as one fixed experiment.
3. **The task is tuned on previous artifacts.** Hidden days and component names
   were selected after observing the weaknesses of the same artifact pool. A
   replay demonstrates regression coverage, not out-of-sample difficulty.
4. **Reference corrections change old outcomes.** v16 run2's historical reward
   remains0 in `trial.json`, but the author correctly treats it as a pass after
   resolving AC auxiliary heat ambiguity. The v12 original verification timed
   out while building the verifier image, yet its replay passed. Those must not
   be counted as genuine wrong-answer failures.
5. **Infrastructure interruptions are excluded.** The archived
   `ApiOverloadedError`, `ApiRateLimitError`, `NetworkConnectionError` and
   verifier-image timeout are not new examples of domain reasoning failure.
6. **Artifacts and model runs are different observations.** Re-running an
   already-written implementation300 times is strong evidence about that
   program's coverage, but adds zero independent observations to the model's
   probability of writing a different implementation tomorrow.

The closest fair empirical statement is therefore: v17's prescribed development
3+3 all failed; a known same-visible-input solution passes; matched artifact
replays concentrate failures on one missing component-mapping step; and the
fresh-run success rate remains poorly measured. v18 cannot earn a numerical
stability claim merely by failing this archive's selected programs.
