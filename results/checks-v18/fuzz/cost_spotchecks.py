"""Independent MILP spot checks even where every opponent agrees.

Select every fourth feasible input within EACH season (sorted by case index),
regenerate it from the retained spec, solve the archived MILP, and compare the
stored independently recomputed opponent costs. Thus agreement between apps is
not treated as proof of optimality. This script does not need the deleted success
plans or any app import/execution and writes no historical or task files.
"""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
import fuzz_v18 as F

ap = argparse.ArgumentParser()
ap.add_argument("--batch", default="main")
args = ap.parse_args()
out = Path(__file__).resolve().parent
batch = out / args.batch
specs = {r["id"]: r for s in (batch / "specs.jsonl").read_text().splitlines() if (r := json.loads(s))}
rows = [json.loads(s) for s in (batch / "results.jsonl").read_text().splitlines()]
by_season = defaultdict(list)
for row in sorted(rows, key=lambda r: r["index"]):
    if row.get("input_problems") or specs[row["id"]]["spec"]["date"] in ("2026-03-29", "2026-10-25"):
        continue
    if row.get("feasible_witnesses"):
        by_season[row["season"]].append(row)
chosen = [r for season in sorted(by_season) for r in by_season[season][::4]]
checks = []
with (batch / "cost-spotchecks.jsonl").open("w") as stream:
    for i, row in enumerate(chosen):
        name = row["id"]
        folder = out / "cost-tmp" / name
        spec = specs[name]["spec"]
        if "overrides" in spec:
            spec["overrides"] = {int(k): v for k, v in spec["overrides"].items()}
        F.B.write_day(folder, spec)
        day, extension = F.reference_day(folder)
        start = time.monotonic()
        r = {"id": name, "season": row["season"], "reference_extension": extension}
        try:
            best = float(day.least_cost()["cost"])
            r["best_cost_gbp"] = best
            r["threshold_gbp"] = max(.5, 2e-4 * best)
            r["opponents"] = {}
            for app, result in row["apps"].items():
                if "recomputed_cost_gbp" in result:
                    actual = result["recomputed_cost_gbp"]
                    r["opponents"][app] = {"cost_gbp": actual, "regret_gbp": actual - best,
                                            "fails": actual - best > r["threshold_gbp"]}
        except RuntimeError as exc:
            r["reference_exception"] = repr(exc)
        r["elapsed_seconds"] = time.monotonic() - start
        stream.write(json.dumps(r, sort_keys=True) + "\n")
        stream.flush()
        checks.append(r)
        shutil.rmtree(folder)
        print(f"{i+1}/{len(chosen)} {name} {r.get('best_cost_gbp', r.get('reference_exception'))}", flush=True)
summary = {"batch": args.batch, "selection": "every fourth feasible case separately in each season",
           "checks": len(checks), "seasons": dict(Counter(r["season"] for r in checks)),
           "reference_errors": [r["id"] for r in checks if "reference_exception" in r],
           "failures": {app: [r["id"] for r in checks if r.get("opponents", {}).get(app, {}).get("fails")]
                        for app in F.APPS}}
(batch / "cost-spotcheck-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2), flush=True)
