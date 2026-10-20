# v19 against the current TB3 rubric (36 criteria)

Checked on 2026-10-20 against `harbor-framework/terminal-bench` at `cac7593` (main, 2026-10-20). Since the previous check at `bf4c125`, upstream has made three changes:
- the rubric gained a nonblocking advisory, `effective_instruction_length`, and moved concision out of `instruction_concision`;
- the static checks gained two scripts, CPU parallelism (an advisory) and compose volumes;
- the review stage now copies in a word-count helper.

`ci/tb3/` and `tools/stage_review.py` mirror all three.

The task reviewed is v19 with one addition: a `difficulty_explanation` field in `task.toml`'s `[metadata]`. Its text is the task README's "Difficulty explanation", word for word. CI's trajectory review reads this field (the `difficulty_crux` criterion in `ci/tb3/trial-analysis.toml`), and the rubric's `task_toml_schema` lists it among the expected fields. No agent sees `task.toml`'s metadata, and the verifier does not use it. So the trials, which ran before the field was added, ran on everything this version gives the agent and the verifier. The task hash, computed as under "Reproducing" in the repository README, is `9a92bbace1766bde`; v19 as trialled is `05f58dca0b55b63f`.

| Check | Result |
|---|---|
| Static checks, CI's step at `cac7593` (`scripts/run_static_checks.sh`) | 28 of 28 pass, the two new ones included ([log](static-checks-cac7593.log), [comment](static-checks-cac7593-comment.md)) |
| Rubric review, claude-code with Sonnet 5, CI's prompt and the 36-criterion rubric (`scripts/run_review.sh`, job `ecd19-review-36`) | 35 pass, 1 not applicable (`artifact_efficiency`), 0 fail, 0 warn ([verdicts](review-verdicts.json)) |

## Criterion by criterion

The middle column is the automated reviewer's verdict. The last column is our own reading of the task against the criterion, with the evidence it rests on.

| # | Criterion | Reviewer | Our reading |
|---|---|---|---|
| 1 | verifiable | pass | A pytest suite against an independent reference model and a whole-day MILP. No LLM judge. Verifier tools are baked into `tests/Dockerfile` (static check "Verifier tooling baked"). |
| 2 | solvable | pass | Oracle reward 1, 55 of 55 tests (`oracle/`). The solution is within GBP 0.0003 of the MILP on all five days, and 48 fresh days pass (HARDENING.md, v19). |
| 3 | difficult | pass | The difficulty is plant knowledge. An engine cannot run with no sink for its heat, and the absorption chiller's cooling water can be held at its minimum. Neither is a trick: both are the trade's practice (README, "Fairness of v19"). |
| 4 | interesting | pass | Day-ahead dispatch of a hospital trigeneration centre is paid work for energy centre engineers and consultants. |
| 5 | outcome_verified | pass | Only the plan is graded: its balances, limits, reported figures, repeatability and cost. |
| 6 | anti_cheat_robustness | pass | Separate verifier image. Hidden days and the reference model are readable by root only. The tool runs as `nobody` on private copies of each day. CI's trajectory review found no reward hacking in any of the 26 trials of v17 to v19, all 14 v19 trials included (`results/analysis-v17/` to `analysis-v19/`). |
| 7 | task_security | pass | No network use, credentials or obfuscated code in the task's files. |
| 8 | functional_verification | pass | The tests run the tool and recompute every figure. Nothing matches source text. |
| 9 | deterministic_reproducible | pass | Images pinned by digest; NumPy and SciPy pinned. The tool runs twice per day and the plans must match. |
| 10 | essential_difficulty | pass | The failures in the trials are on the header and on part outages ("Failure analysis", v19), not on the output format. |
| 11 | test_instruction_alignment | pass | Every test traces to the instruction's requirements. This is where a human reviewer is most likely to push back: the hidden days test two judgements the visible day does not exercise. The evidence that the visible files settle both is in README, "Fairness of v19". |
| 12 | novel | pass | A synthetic plant with its own couplings; no textbook problem matches it. |
| 13 | agentic | pass | The tool has to be read, run and repaired across several modules. |
| 14 | reviewable | pass | The reference model, the solution and the README's explanations let a non-specialist check the claims. |
| 15 | instruction_concision | pass | Human-written, absolute paths, and no hint at the bugs. |
| 16 | effective_instruction_length | pass (advisory) | 411 words by the upstream helper, and no requirement documents beyond the data files. |
| 17 | solution_quality | pass | `solve.sh` installs the repaired tool and runs it. Nothing is precomputed. |
| 18 | separate_verifier_configured | pass | `environment_mode = "separate"`; the artifacts are `/app/dispatch.py` and `/app/planner`. |
| 19 | environment_hygiene | pass | The agent's image holds no tests or solution; test-only packages are in `tests/Dockerfile`. |
| 20 | structured_data_schema | pass | The plan's format is the shipped tool's, documented in its docstring, and must be kept. |
| 21 | typos | pass | None found. |
| 22 | difficulty_explanation_quality | pass | The README section covers three things: the core difficulty, where the data comes from, and who does this work. The same text is now in `task.toml`. |
| 23 | solution_explanation_quality | pass | Matches the diff between the shipped tool and `solution/app`. |
| 24 | verification_explanation_quality | pass | The tolerances are justified in three ways: rounding and tangent-approximation errors, an alternative-algorithm solution within GBP 0.0003, and every planted bug and each of the 27 half-fixes failing a test. The 27 are v19's: 42 mutants, of which 27 are half-fixes (HARDENING.md, v19). |
| 25 | category_and_tags | pass | Operations / Energy. |
| 26 | task_name | pass | `energy-centre-dispatch`. |
| 27 | resource_configuration | pass | 2 CPUs and 4 GB; the agent has 8 hours and the verifier 30 minutes (static check "Task timeout cap" passes). The tool needs about a second a day. |
| 28 | task_readme | pass | All four required sections and a metadata summary. |
| 29 | expert_time_estimate | pass | 4 hours, consistent with the difficulty explanation. |
| 30 | task_toml_schema | pass | Only expected fields, `difficulty_explanation` included. |
| 31 | no_extraneous_files | pass | Only the task's own files. |
| 32 | artifact_efficiency | not applicable | The artifacts are the small repaired tool itself. |
| 33 | verifier_execution_isolation | pass | `test.sh` locks `/logs/verifier`, runs the tool as `nobody` with a time limit, kills that user's processes afterwards, and writes the reward as root. |
| 34 | ctrf_reporting | pass | `pytest --ctrf /logs/verifier/ctrf.json`. |
| 35 | do_not_modify_enforced | pass | Only the tool is collected; the verifier supplies its own copy of every day's data. |
| 36 | binary_reward | pass | 0 or 1 from pytest's exit status. |

## What the rubric does not cover

The rubric does not ask whether the task was shaped by its own trials. It was: every version from v4 to v19 was revised in light of the previous version's trials. README ("How the task came about" and "Fairness of v19") discloses this and sets out the checks against it.
