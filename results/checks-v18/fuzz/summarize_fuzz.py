"""Count valid, feasible, ambiguous and rejected differential-test evidence.

Primary and supplementary random batches are separated from the deliberately
conditional warmer-water and radiator probes. Raw records are never edited.
"""

from collections import Counter, defaultdict
from datetime import date
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
APPS = ("v16_claude", "v17_codex_parts", "v17_claude_parts")


def last_sunday(month):
    from datetime import timedelta
    d = date(2026, month + 1, 1) - timedelta(days=1)
    while d.weekday() != 6:
        d -= timedelta(days=1)
    return d.isoformat()


clock_dates = {last_sunday(3), last_sunday(10)}
records, costs = [], {}
for batch in ("main", "supplement"):
    root = OUT / batch
    specs = {r["id"]: r for s in (root / "specs.jsonl").read_text().splitlines() if (r := json.loads(s))}
    for s in (root / "results.jsonl").read_text().splitlines():
        row = json.loads(s)
        item = specs[row["id"]]
        invalid = list(row.get("input_problems", []))
        if item["spec"]["date"] in clock_dates:
            invalid.append("clock_change_date")
        feasible = bool(row.get("feasible_witnesses")) or "cost_gbp" in row.get("milp", {})
        failed = {a: row.get("apps", {}).get(a, {}).get("failed", []) for a in APPS}
        exceptions = {a: row.get("apps", {}).get(a, {}).get("exception") for a in APPS}
        if invalid:
            category = "invalid_input_excluded"
        elif "reference_error" in row:
            category = "reference_error_requires_review"
        elif not feasible and "exception" in row.get("milp", {}):
            category = "reference_infeasible_excluded"
        elif feasible and "exception" in row.get("milp", {}):
            category = "feasible_witness_reference_conflict"
        elif feasible and any(failed[a] or exceptions[a] for a in APPS):
            category = "feasible_difference_requires_review"
        elif feasible:
            category = "all_opponents_passed"
        else:
            category = "undetermined"
        full = {"batch": batch, "id": row["id"], "category": category, "invalid_reasons": invalid,
                "feasible": feasible, "season": row["season"], "spec": item["spec"], "result": row}
        records.append(full)
        if "cost_gbp" in row.get("milp", {}) and not invalid:
            costs[(batch, row["id"])] = {"source": "in_batch", "best": row["milp"]["cost_gbp"],
                                         "season": row["season"], "apps": row["apps"],
                                         "reference_extension": bool(row.get("reference_extension"))}
    extra = root / "cost-spotchecks.jsonl"
    if extra.exists():
        for s in extra.read_text().splitlines():
            row = json.loads(s)
            if "best_cost_gbp" in row:
                costs[(batch, row["id"])] = {"source": "independent_stratified_spotcheck",
                                             "best": row["best_cost_gbp"], "season": row["season"],
                                             "apps": row["opponents"],
                                             "reference_extension": bool(row.get("reference_extension"))}

valid = [r for r in records if not r["invalid_reasons"]]
feasible = [r for r in valid if r["feasible"]]
checks = Counter(r["category"] for r in records)
outages = Counter(o["unit"] for r in valid for o in r["spec"]["status"]["outages"])
feasible_outages = Counter(o["unit"] for r in feasible for o in r["spec"]["status"]["outages"])
initial = Counter("+".join(r["spec"]["status"]["running_at_midnight"]) or "none" for r in feasible)
duration = Counter()
for r in valid:
    for o in r["spec"]["status"]["outages"]:
        def minute(s):
            h, m = s.split(":")
            return int(h) * 60 + int(m)
        duration[minute(o["to"]) - minute(o["from"])] += 1
app_failures = {a: [f"{r['batch']}/{r['id']}" for r in feasible
                     if r["result"]["apps"][a]["failed"] or "exception" in r["result"]["apps"][a]] for a in APPS}
timing = {a: max(r["result"]["apps"][a]["elapsed_seconds"] for r in valid if a in r["result"].get("apps", {}))
          for a in APPS}
cost_failures = defaultdict(list)
max_regret = {a: float("-inf") for a in APPS}
for (batch, name), check in costs.items():
    for a, r in check["apps"].items():
        actual = r.get("recomputed_cost_gbp", r.get("cost_gbp"))
        if actual is None:
            continue
        regret = actual - check["best"]
        max_regret[a] = max(max_regret[a], regret)
        if regret > max(.5, 2e-4 * check["best"]):
            cost_failures[a].append(f"{batch}/{name}")
summary = {
    "attempted_days": len(records), "valid_draws": len(valid), "feasible_valid_days": len(feasible),
    "valid_app_day_runs": sum(len(r["result"].get("apps", {})) for r in valid),
    "feasible_app_day_runs": sum(len(r["result"].get("apps", {})) for r in feasible),
    "categories": dict(checks), "feasible_by_season": dict(Counter(r["season"] for r in feasible)),
    "feasible_midnight_states": dict(initial), "outage_name_counts": dict(outages),
    "feasible_outage_name_counts": dict(feasible_outages), "outage_duration_minutes_counts": dict(sorted(duration.items())),
    "reference_extension_days": sum(bool(r["result"].get("reference_extension")) for r in valid),
    "feasible_reference_extension_days": sum(bool(r["result"].get("reference_extension")) for r in feasible),
    "unique_milp_optimality_cases": len(costs),
    "unique_milp_original_reference_cases": sum(not c["reference_extension"] for c in costs.values()),
    "unique_milp_extended_reference_cases": sum(c["reference_extension"] for c in costs.values()),
    "milp_optimality_cases_by_season": dict(Counter(c["season"] for c in costs.values())),
    "opponent_failures_on_feasible_days": app_failures,
    "cost_failures": {a: cost_failures[a] for a in APPS}, "max_cost_regret_gbp": max_regret,
    "max_app_elapsed_seconds": timing,
    "excluded_invalid_cases": [f"{r['batch']}/{r['id']}" for r in records if r["invalid_reasons"]],
    "needs_review": [f"{r['batch']}/{r['id']}" for r in records if "review" in r["category"] or "conflict" in r["category"]],
    "interpretation": "random-case agreement is not a measured probability of a newly sampled model succeeding",
}
(OUT / "SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n")
(OUT / "classification.jsonl").write_text("".join(json.dumps({k: v for k, v in r.items() if k not in ("spec", "result")},
                                                             sort_keys=True) + "\n" for r in records))
print(json.dumps(summary, indent=2))
assert len(feasible) >= 320, "required feasible-day coverage has not yet been reached"
