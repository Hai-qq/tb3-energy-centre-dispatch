# Investigation of the apparent post-fix fresh-day failures

## Result

The two apparent oracle failures were **not reproduced on the accepted days
described by the fresh-run logs**. Those accepted scenarios pass the unchanged
oracle and every case check, with deterministic CLI reruns and absolute cost
gaps below£0.001. Their original output directories instead contained the
immediately preceding rejected draws. Both reference and oracle correctly
report those different days infeasible.

The immediate evidence error is therefore a mismatch between recorded accepted
inputs and inputs later evaluated. The mechanism by which older contents
reappeared is not established. This audit does not claim to have proven a
filesystem implementation bug, process race or fault in `shutil.rmtree`.

## Personally observed discrepancy

| Seed / ordinal | Accepted day printed by original log | Actual original directory when inspected | Reconstructed draw numbers |
|---|---|---|---|
| 2026 / f4 | 2026-08-12; both engines running at midnight; EC2 condenser13:20–15:40 | 2026-06-19; GE1 running; CT2 outage06:40–09:30 | Accepted13, stale contents match rejected12 |
| 2403 / f7 | 2026-08-13; neither engine running; GE1, PV1 and EC1 condenser outages | 2026-09-09; GE1 running; B2, CT2, CT1 and PV1 outages | Accepted14, stale contents match rejected13 |

`fresh_lifecycle_hash_comparison.json` records SHA-256 for all five input files.
In both cases all five original-directory files match the reconstructed
preceding rejected draw. Status, demand and weather differ from the accepted
draw; the immutable plant and supply are naturally identical across both draws.
The original files were read only throughout this audit.

## Reconstruction and numerical/model checks

`reconstruct_fresh_failure.py` starts each RNG from the original seed, uses the
same season selection and input generator, and filters through the current
reference MILP. Crucially, it writes each attempted draw to a unique pathname
under `fairness/fresh-reconstructed/`. It reproduces every accepted ordinal in
the logs through the disputed cases. Its JSON records accepted/rejected status,
dates, full accepted specifications, and reference costs.

`diagnose_oracle_lp.py --reconstructed` then runs the unchanged oracle on the
accepted scenarios. For every one of their48 periods it also takes the reference
MILP's chosen engine states/segments and absorber mode and solves that state
using the oracle's original `linprog(method="highs")`. All96 such comparisons
are feasible. There is no observed presolve failure, equation mismatch, or
strict-AC-auxiliary inconsistency on these inputs.

Running the same diagnosis without `--reconstructed` uses the original stale
folders: reference and oracle both report infeasibility in each. Evidence is
`diagnose_oracle_lp_original.json` and `_reconstructed.json`, with captured
stdout. No oracle or reference source edit was needed.

## Complete CLI checks on the accepted scenarios

`check_reconstructed_oracle.py` runs the actual oracle CLI twice per day,
checks identical JSON output, invokes all ten case-level verifier functions,
and checks the input hashes before/after both runs. It also requires absolute
cost agreement below£0.001, stronger than the ordinary least-cost tolerance.

| Accepted scenario | Recomputed oracle cost (£) | Reference MILP (£) | Delta (£) | Outcome |
|---|---:|---:|---:|---|
| Seed2026 f4 / 2026-08-12 | 5497.061245837400 | 5497.0612868682165 | −0.0000410308166 | All10 case checks, determinism and unchanged-input hashes pass |
| Seed2403 f7 / 2026-08-13 | 6183.069135025900 | 6183.068906860972 | +0.000228164929 | All10 case checks, determinism and unchanged-input hashes pass |

The four complete CLI runs took3.59–5.16 seconds each. These are genuine local
execution results, not Harbor or fresh-model trials. Machine-readable results
are `check_reconstructed_oracle.json`; both plans and process logs are retained
under `reconstructed-oracle/`.

## Reproduction commands

All use the Python3.13.16 environment and pinned NumPy/SciPy/pytest versions.
Set `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1`.

```sh
/workspace/scratch/3a594630faca/ecd-venv/bin/python \
  results/checks-v18/fairness/reconstruct_fresh_failure.py

/workspace/scratch/3a594630faca/ecd-venv/bin/python \
  results/checks-v18/fairness/diagnose_oracle_lp.py --reconstructed

/workspace/scratch/3a594630faca/ecd-venv/bin/python \
  results/checks-v18/fairness/diagnose_oracle_lp.py

/workspace/scratch/3a594630faca/ecd-venv/bin/python \
  results/checks-v18/fairness/check_reconstructed_oracle.py
```

## Peer review of the harness repair

The root agent's new `tools/fresh_days.py` gives each draw a unique name, requires
a new explicitly supplied output directory, records full specifications and
accepted input hashes, and checks those hashes before and after evaluation.
That directly addresses the observed provenance failure without altering the
physics, accepting infeasible draws, or changing the oracle. The script still
requires a feasible reference MILP before accepting a draw and reports failing
case/process results through a nonzero exit status.

This audit reviewed that tool diff. The root agent's subsequent full three-seed
run, rather than this two-day reconstruction, must establish the48-day B gate.
Do not advertise the earlier inconsistent-folder run as a genuine oracle model
failure or as a successful48-day validation.
