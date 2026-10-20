"""Summarize actual persisted evidence; never turn an unmet E gate into success."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import energy_mutants  # noqa: E402


def read(name):
    return json.loads((HERE / name).read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    matrix = read("final-matrix/matrix.json")
    evidence = read("evidence-verification/report.json")
    fuzz = read("fuzz/SUMMARY.json")
    metadata = read("final-matrix/metadata.json")
    reference = ROOT / "tasks/energy-centre-dispatch/tests/reference.py"
    test_plans = reference.with_name("test_plans.py")
    assert digest(reference) == evidence["reference_sha256"] == metadata["reference_sha256"]
    assert digest(test_plans) == metadata["test_sha256"]
    for name, expected in evidence["oracle_sha256"].items():
        assert digest(ROOT / "tasks/energy-centre-dispatch/solution/app" / name) == expected, name
    for name, info in metadata["days"].items():
        folder = ROOT / "tasks/energy-centre-dispatch/tests/days" / name
        for file, expected in info["sha256"].items():
            assert digest(folder / file) == expected, (name, file)

    mutant_lines = re.findall(r"^(\S+)\s+(CAUGHT|MISSED)\b(.*)$",
                             (HERE / "final-mutants.log").read_text(), re.M)
    mutants = {name: {"caught": result == "CAUGHT", "output": detail.strip()}
               for name, result, detail in mutant_lines}
    all_mutants = set(mutants) == set(energy_mutants.MUTANTS) and all(
        row["caught"] for row in mutants.values())
    oracle = matrix["oracle"]
    oracle_max_delta = max(abs(x["delta_gbp"]) for x in oracle["days"].values())
    oracle_max_time = max(run["seconds"] for x in oracle["days"].values() for run in x["runs"])
    fresh = {}
    for seed in (2026, 2403, 87123):
        manifest = read(f"final-fresh-verified/seed-{seed}/manifest.json")
        assert len(manifest["days"]) == 16
        assert manifest["input_hashes_unchanged_after_evaluation"]
        assert manifest["reference.py_sha256"] == digest(reference)
        results = list(manifest["results"].values())
        fresh[str(seed)] = {"days": 16, "all_passed": all(
            not r["failed"] and not r["errors"] for r in results),
            "input_hashes_unchanged": True}
    original_names = [f"v17-run{n}-{model}" for model in ("claude", "codex") for n in (1, 2, 3)]
    gate = read("final-matrix/gates.json")
    result = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "base_commit": "12a1116c5e545b4c30ff43cf8ac6503c9fd14473",
        "task_revision_count": 1,
        "runtime": {"python": "3.13.16", "numpy": "2.3.4", "scipy": "1.17.0", "pytest": "9.1.1"},
        "reference_sha256": digest(reference),
        "test_plans_sha256": digest(test_plans),
        "A_visible_files_unchanged": evidence["A_visible_unchanged"]["files"] == 13,
        "B": {"five_days_pass": oracle["passed"], "max_absolute_cost_delta_gbp": oracle_max_delta,
              "max_official_cli_seconds": oracle_max_time, "fresh": fresh,
              "independent_fresh_replay_days": evidence["fresh_specs_regenerate_exact_bytes"],
              "independent_fresh_all_pass": evidence["fresh_all_passed"],
              "max_fresh_cli_seconds": evidence["max_fresh_cli_seconds"],
              "max_fresh_absolute_cost_delta_gbp": evidence["max_fresh_absolute_cost_delta_gbp"]},
        "C": {"expected": len(energy_mutants.MUTANTS), "observed": len(mutants),
              "caught": sum(x["caught"] for x in mutants.values()), "all_caught": all_mutants,
              "mutants": mutants},
        "D": {"added_requirements": "literal HT-source and AC-generator component availability",
              "review": "fairness/FINAL_REVIEW.md", "new_independent_reasoning_trap": False,
              "existing_ambiguous_physical_readings_remain_accepted": True,
              "official_tb3_ci_review_run": False},
        "E1_strongest_defeated": gate["E1_strongest_defeated"],
        "E2_patched_defeated": gate["E2_patched_defeated"],
        "E3_blind_measured": gate["E3_blind_measured"],
        "F_six_originals_fail": all(not matrix[name]["passed"] for name in original_names),
        "fuzz": {key: fuzz[key] for key in (
            "attempted_days", "valid_draws", "feasible_valid_days", "feasible_app_day_runs",
            "feasible_reference_extension_days", "unique_milp_optimality_cases",
            "feasible_by_season", "opponent_failures_on_feasible_days", "cost_failures")},
        "canonical_pytest_crosscheck": read("canonical_eval.json"),
        "fresh_model_trials_run": 0,
        "promotable_as_stable_six_failures": False,
        "reason": "E1 and E2 are false: all three strong implementations pass v18; no fair semantic defeat found",
    }
    assert result["A_visible_files_unchanged"]
    assert oracle["passed"] and oracle_max_delta < 0.001 and oracle_max_time < 120
    assert all(x["all_passed"] for x in fresh.values()) and evidence["fresh_all_passed"]
    assert all_mutants, "Canonical mutant run is not yet complete or contains a miss"
    assert result["E3_blind_measured"] and result["F_six_originals_fail"]
    (HERE / "RELEASE_STATUS.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in (
        "A_visible_files_unchanged", "E1_strongest_defeated", "E2_patched_defeated",
        "E3_blind_measured", "F_six_originals_fail", "promotable_as_stable_six_failures")}, indent=2))
    print(f"B: oracle 5/5, fresh 48/48; C: {len(mutants)}/{len(mutants)} caught")


if __name__ == "__main__":
    main()
