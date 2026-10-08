# v8 trials: deliverables and verifier output

What each v8 trial left behind, exported from the local Harbor jobs (which are not committed)
by `tools/export_trials.py`:

- `<job>/app/`: the agent's deliverable, `/app/dispatch.py` and `/app/planner`, as Harbor
  collected it at the end of the trial
- `<job>/verifier/`: the verifier's own output, `test-stdout.txt`, `ctrf.json` and `reward.txt`
- `<job>/trial.json`: the trial from Harbor's `result.json` and the job's config: agent and
  version, model and reasoning effort, whether the `/cheat` prompt was appended, timing, tokens,
  exception and reward, and the task files it ran on with their hash
- `MANIFEST.sha256`: SHA-256 of every file here (`shasum -a 256 -c MANIFEST.sha256`)

The agents' transcripts are not included. The six counted standard trials are `ecd8-run{1,2,3}-
{codex,claude}`; the `/cheat` trials are `ecd8-cheat-codex`, `ecd8-cheat2-codex` and
`ecd8-cheat-claude`. `ecd8-run1-codex-overloaded` and `ecd8-run3-claude-NetworkConnectionError1`
were stopped before the agent could work and are not counted.

Every trial ran on the files in `archive/energy-centre-dispatch-v8/` (task hash
`6826dc661e623be8`, as `trial.json` records; Harbor's own checksum of the task folder is there
too). The current task differs from them only in `tests/` and the README: its verifier also
fails a run that exits with an error or does not finish in 150 seconds.

## Re-scoring with the current verifier

```bash
python tools/eval_energy.py results/v8-trials/<job>/app
```

runs a deliverable twice on each of the five days, as the verifier does, and runs the current
tests on its plans. The six counted deliverables, scored again this way:

| Trial | Days failed | Why |
|---|---|---|
| `ecd8-run1-claude` | h1, h3, h4 | connection and least cost on h1 and h4; on h3 the tool exits with an error |
| `ecd8-run1-codex` | h1, h3, h4 | the tool exits with an error on all three (`no feasible loading`) |
| `ecd8-run2-codex` | h1, h3, h4 | the same |
| `ecd8-run2-claude` | h1, h2, h3, h4 | as run 1, and availability on h2 |
| `ecd8-run3-codex` | h1, h3, h4 | the same as runs 1 and 2 |
| `ecd8-run3-claude` | h2, h3, h4 | availability |

These are the days and the reasons of the trials themselves: the revised verifier changes no
outcome. Each tool that exits with an error on a day already wrote no plan for it.
