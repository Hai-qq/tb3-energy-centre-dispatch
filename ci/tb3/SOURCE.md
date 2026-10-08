# Files copied from Terminal-Bench

Copied unchanged from https://github.com/harbor-framework/terminal-bench (Apache License 2.0;
the `terminal-bench-3` repository name redirects there), first at commit
`1dcda8716784493721921c23e4bc7f7d988b4494` (main, 2026-09-28). Each file is identical at
`bf4c1255fe70237aecd03a14b0fab9f01afca6b4` (main, 2026-10-07), the commit the task was last
checked against.

| file | upstream path | used for |
|---|---|---|
| hack-trial-prompt.md | docs/prompts/hack-trial-prompt.md | /cheat trials (appended to the instruction) |
| trial-analysis.txt | docs/prompts/trial-analysis.txt | trajectory review instruction (`tools/stage_analysis.py`) |
| trial-analysis.toml | docs/prompts/trial-analysis.toml | trajectory review criteria |
| trial-analysis-job.txt | docs/prompts/trial-analysis-job.txt | `harbor analyze` job summary prompt (CONTRIBUTING) |
| task-implementation.toml | docs/prompts/task-implementation.toml | implementation rubric review |
| task-proposal.md | docs/prompts/task-proposal.md | proposal self-review |
| harbor-run-defaults.yml | .github/harbor-run-defaults.yml | CI defaults for /run and /cheat |
| harbor-version | .github/harbor-version | pinned Harbor version |

Mirrored rather than copied, each with its local changes listed in its own header:

| file here | upstream |
|---|---|
| `scripts/run_static_checks.sh` | the "Run all static checks" step of `.github/workflows/static-checks.yml`, run unchanged from a checkout |
| `tools/stage_review.py` | `scripts/review/stage_task.py` |
| `tools/stage_analysis.py` | `scripts/ci/stage_hosted_analysis.py` |
