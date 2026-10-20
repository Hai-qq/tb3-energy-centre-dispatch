# CSV row-order probe: new execution after environment recovery

**All three strong programs pass. This is not an E defeat.** The original,
uncommitted `order-probe/` outputs were lost when the working environment was
cleaned during publication. `run.py` was recovered from the complete source in
the earlier conversation. The old logs and result files were **not recreated**.
Every plan, result, timing and console log now in this directory comes from the
new execution below.

The new run started at **2026-10-17 11:00:43.123763 UTC** and finished at
**11:01:07.132584 UTC**, taking **24.008590 seconds** including the reference
MILP, input/loader checks and three sequential app CLI executions. It used
Python **3.13.16**, NumPy **2.3.4**, SciPy **1.17.0** and pytest **9.1.1**.

## Exactly one equivalent day

The probe reverses the visible day's **48 demand rows and 96 weather rows**
together. The headers, each row's exact bytes, every timestamp/value and the
three JSON files remain unchanged. Sorting the copied rows by their actual UTC
timestamp recreates the original CSV bytes exactly. Only this new directory is
written; task, tools and earlier evidence files are unchanged.

All three demand loaders sort before optimizing: the two Claudes sort parsed
timestamps, while Codex sorts their strings, equivalent for the fixed same-offset
ISO representation. Every weather loader joins a UTC-instant dictionary to the
demand times. Loading the original and reversed data gives identical electricity,
reactive demand, heat, cooling, dry bulb, wet bulb, PV, starts, first start, date
and status for all three programs.

Each actual saved app CLI receives the reversed files, with a 120-second
deadline. The independent archived v17 reference receives a copied input
normalized by timestamp, because its own demand reader retains file order.
Physical balances, start chronology and costs are therefore checked in real
chronological order; no reference code is changed.

| App | Exit | Physical/report checks | Recomputed daily cost | New CLI seconds |
|---|---:|---:|---:|---:|
| v16 Claude run 2 | 0 | 9/9 | £6303.56040919005 | 6.562836 |
| v17 Codex run 2 + parts patch | 0 | 9/9 | £6303.56031942643 | 5.358665 |
| v17 Claude run 2 + parts patch | 0 | 9/9 | £6303.56040919005 | 5.826048 |

The normalized independent whole-day MILP costs **£6303.56031942655**. All three
plans pass the cost threshold. This is one equivalent-day check kept outside
the 480-draw random corpus; its counts remain unchanged.

## Command and current-source evidence

The actual new execution used this command from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /workspace/scratch/3a594630faca/ecd-venv/bin/python \
  results/checks-v18/order-probe/rerun.py
```

The wrapper runs the recovered `run.py` exactly once, writes the new `run.log`,
and records UTC timestamps, versions and current source hashes in
`rerun-metadata.json`. The recovered probe script SHA-256 is
`104edd1b74ea79d48631ea1e52ab9129b779ba9d4e32c924ae8124f5d216389d`.
The metadata additionally hashes the wrapper, harness, archived reference/tests
and every Python source file in the three saved apps.

`result.json` contains source input hashes, row-integrity assertions, loader
equivalence, exact app commands, costs and verdicts. The three complete newly
emitted plans and both copied input variants are retained. The machine verdicts
are `all_passed: true` and `E_success: false`.
