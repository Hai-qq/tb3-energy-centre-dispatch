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

Each counted deliverable was scored again in Harbor with v8.1's verifier, the way a trial is
scored (separate verifier image, the tool run as `nobody`, twice on each day):

```bash
scripts/replay_deliverable.sh tasks/energy-centre-dispatch results/v8-trials/<job>/app <job-name>
```

copies the task, puts the deliverable in place of the solution and runs Harbor's oracle agent,
which installs it as the agent left it. The verifier's output of these replays is in
`<job>/replay-v8.1/`. Every replay scored 0 and failed exactly the tests its trial failed:

| Trial | Replay (v8.1) | Days failed | Why |
|---|---|---|---|
| `ecd8-run1-claude` | 5 failed, 40 passed, 10 errors | h1, h3, h4 | connection and least cost on h1 and h4; on h3 the tool exits with an error |
| `ecd8-run1-codex` | 3 failed, 22 passed, 30 errors | h1, h3, h4 | the tool exits with an error on all three (`no feasible loading`) |
| `ecd8-run2-codex` | 3 failed, 22 passed, 30 errors | h1, h3, h4 | the same |
| `ecd8-run2-claude` | 6 failed, 39 passed, 10 errors | h1, h2, h3, h4 | as run 1, and availability on h2 |
| `ecd8-run3-codex` | 3 failed, 22 passed, 30 errors | h1, h3, h4 | the same as runs 1 and 2 |
| `ecd8-run3-claude` | 3 failed, 52 passed | h2, h3, h4 | availability |

The revised verifier changes no outcome: each tool that exits with an error on a day already
wrote no plan for it. `python tools/eval_energy.py results/v8-trials/<job>/app` gives the same
days without Harbor.
