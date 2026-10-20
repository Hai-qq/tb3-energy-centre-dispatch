# Prototype: dispatch command gateway (option B, minimal)

A falsification test, run on 2026-10-15 before building anything larger: with the plant
controller's API as in [`SPEC.md`](SPEC.md) (durable idempotency by command id, fencing by plan
epoch, a status query), does a textbook gateway already meet every requirement?

- `harness.py`: the controller (an HTTP server) and six scenarios with faults at fixed points:
  a lost answer, a gateway killed after the controller applied its command, a gateway killed
  with its request in flight, and two takeovers by a newer plan, one with the old gateway stalled
  and its request arriving after the new plan has run, one with the old gateway restarted by a
  watchdog after the new plan has run. The controller's own record is checked against SPEC.md's
  three requirements.
- `gateways/naive.py`: the kind of code a first version has (a fresh id for each retry, no
  epoch, a command given up after three tries).
- `gateways/standard.py`: a textbook gateway (an outbox in SQLite, the plan's ids as
  idempotency keys, the plan's epoch as the fencing token, and "ask the controller, then resend
  under the same id" after any failure), about 50 lines.

```
python harness.py gateways/naive.py      # fails ack_lost, takeover_with_late_request, takeover_after_lost_ack
python harness.py gateways/standard.py   # passes all six
```

**Result: the textbook gateway passes every scenario.** Once the controller offers what an
exactly-once outcome needs (durable deduplication, fencing, a status query), the gateway's part
is a well-known pattern that frontier models write without trouble. Weakening the API makes the
requirements either impossible (no deduplication and no way to ask) or solvable by another
well-known pattern (per-epoch sequence numbers and a high-water mark). Moving the difficulty into
safe ordering across devices turns it into a precisely specified planning problem, the kind the
earlier tasks in this repository showed the models formulate and check by themselves. By the
rule set before the test, this direction is dropped in this form.
