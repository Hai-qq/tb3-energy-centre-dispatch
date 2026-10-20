# Dispatch command gateway: prototype spec (option B, minimal)

What a task built on this would tell the agent, in brief.

The energy centre's dispatch plan reaches the plant through a gateway. A plan has an epoch
(a number that grows with every new plan) and an ordered list of commands, each with an id:

```json
{"epoch": 2, "commands": [{"id": "e2-01", "device": "GE1", "action": "raise", "kw": 150}, ...]}
```

`raise` and `lower` are pulses to the engine governor: each one moves the output by `kw` from
wherever it is, so applying one twice moves it twice.

The gateway is run as

    python gateway.py --plan PLAN --state-dir DIR --device URL

It must get every command of its plan applied once, in order, and exit 0 when every command
has a final result. It may be killed at any moment and is then started again with the same
arguments. A new plan is put into force by starting a gateway with the new plan (and a state
directory of its own); the old gateway may still be running, or stalled, when that happens.

The plant controller's API (`--device`):

- `POST /command` with `{"id", "epoch", "action", "kw"}`. The controller applies the command
  unless it has already seen this id (it then answers with the first result and does nothing)
  or it has already applied a command of a later epoch (it answers `stale` and does nothing).
  Answer: `{"result": "applied" | "stale", "duplicate": bool, "output_kw": float}`.
- `GET /command/<id>`: `{"result": "applied" | "stale" | "unknown"}`.
- `GET /state`: `{"output_kw": float, "epoch": int}`.

The controller never forgets a result and never restarts. Between it and the gateway, any
request or answer may be lost, and a request may arrive late, after later ones.

Required, whatever the failures:

1. No command is applied twice, and the controller sees only the plan's command ids.
2. Once the controller has applied a command of epoch N, no command of an earlier epoch is
   applied.
3. Every command of the newest plan is applied exactly once, in plan order, and its gateway exits
   0. A command of an older plan is either applied before the newer plan's first command or
   never.
