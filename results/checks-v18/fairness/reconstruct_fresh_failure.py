"""Regenerate the printed fresh-day scenarios into isolated directories."""
from __future__ import annotations

import json
from pathlib import Path
import random
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import fresh_days as F

results = []
for seed, stop in [(2026, 4), (2403, 7)]:
    rng = random.Random(seed)
    accepted = 0
    attempts = 0
    events = []
    while accepted < stop:
        attempts += 1
        spec, base = F.draw(rng, F.SEASONS[accepted % len(F.SEASONS)])
        target = HERE / "fresh-reconstructed" / f"seed-{seed}" / f"attempt-{attempts:03d}"
        F.B.write_day(target, spec)
        assert json.loads((target / "status.json").read_text())["date"] == spec["date"]
        if F.check_inputs(target):
            events.append({"attempt": attempts, "date": spec["date"], "accepted": False, "reason": "input"})
            continue
        try:
            plan = F.Day(target).least_cost()
        except RuntimeError:
            events.append({"attempt": attempts, "date": spec["date"], "accepted": False, "reason": "MILP infeasible"})
            continue
        accepted += 1
        event = {"attempt": attempts, "ordinal": accepted, "date": spec["date"], "accepted": True,
                 "reference_cost": plan["cost"], "status": spec["status"], "folder": str(target.relative_to(ROOT))}
        events.append(event)
        print(json.dumps({"seed": seed, **event}), flush=True)
        if accepted == stop:
            final = HERE / "fresh-reconstructed" / f"seed-{seed}" / f"f{accepted}"
            shutil.copytree(target, final, dirs_exist_ok=True)
            (final / "spec.json").write_text(json.dumps(spec, indent=2) + "\n")
    results.append({"seed": seed, "events": events})
    (HERE / "reconstruct_fresh_failure.json").write_text(json.dumps(results, indent=2) + "\n")
