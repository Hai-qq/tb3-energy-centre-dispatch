"""Check immutable evidence and replay all 48 accepted fresh inputs at 120 s/day.

The existing fresh run already invokes the canonical pytest suite and repeats
each CLI. This independent pass validates persisted input identity, retains a
plan and per-run timing for every day, and rechecks the actual case functions.
MILP costs are reused only after validating the input/reference hashes to which
the original fresh-run certificates belong.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tasks/energy-centre-dispatch"
CHECKS = ROOT / "results/checks-v18"
SEEDS = [2026, 2403, 87123]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hashes(path):
    return {str(p.relative_to(path)): digest(p) for p in sorted(path.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=CHECKS / "evidence-verification")
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(ROOT / "tools"))
    sys.path.insert(0, str(TASK / "tests"))
    import build_energy_days as B
    R = importlib.import_module("reference")
    T = importlib.import_module("test_plans")
    report = {"command": sys.argv, "reference_sha256": digest(TASK / "tests/reference.py"),
              "oracle_sha256": hashes(TASK / "solution/app"), "fresh": {}}

    # This also checks the absence of newly added visible paths.
    visible = {"instruction.md": digest(TASK / "instruction.md"),
               **{"environment/" + k: v for k, v in hashes(TASK / "environment").items()}}
    archive = ROOT / "archive/energy-centre-dispatch-v8.1"
    original = {"instruction.md": digest(archive / "instruction.md"),
                **{"environment/" + k: v for k, v in hashes(archive / "environment").items()}}
    assert visible == original
    assert not list((TASK / "environment").rglob("*.pyc"))
    report["A_visible_unchanged"] = {"files": len(visible), "sha256": visible}

    metadata = json.loads((CHECKS / "final-matrix/metadata.json").read_text())
    assert metadata["reference_sha256"] == report["reference_sha256"]
    assert metadata["test_sha256"] == digest(TASK / "tests/test_plans.py")
    for name, row in metadata["days"].items():
        assert hashes(TASK / "tests/days" / name) == row["sha256"], name
    report["matrix_inputs_and_verifier_unchanged"] = True

    blind = CHECKS / "blind"
    frozen = json.loads((blind / "FROZEN_SHA256.json").read_text())
    for group in ("runtime_code_files", "input_data_files"):
        for name, value in frozen[group].items():
            assert digest(blind / name) == value, name
    assert digest(blind / "instruction.md") == frozen["instruction_sha256"]
    report["blind_runtime_frozen"] = frozen["runtime_code_sha256"]

    cases = []
    for seed in SEEDS:
        base = CHECKS / "final-fresh-verified" / f"seed-{seed}"
        manifest = json.loads((base / "manifest.json").read_text())
        assert manifest["reference.py_sha256"] == report["reference_sha256"]
        assert manifest["input_hashes_unchanged_after_evaluation"]
        assert len(manifest["days"]) == 16
        assert manifest["results"] and all(not r["failed"] and not r["errors"]
                                           for r in manifest["results"].values())
        for name, row in manifest["days"].items():
            source = base / "tests/days" / name
            expected = row["sha256"]
            assert hashes(source) == expected, (seed, name, "persisted bytes changed")
            replay = args.out / "regenerated" / f"seed-{seed}" / name
            B.write_day(replay, row["spec"])
            assert hashes(replay) == expected, (seed, name, "spec does not regenerate exact bytes")
            cases.append((seed, name, source, row))
    report["fresh_specs_regenerate_exact_bytes"] = len(cases)

    funcs = [(name, f) for name, f in vars(T).items() if name.startswith("test_")
             and name != "test_same_plan_every_time" and callable(f)]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")

    def run(case):
        seed, name, source, certificate = case
        folder = args.out / "runs" / f"seed-{seed}" / name
        folder.mkdir(parents=True)
        cmd = [sys.executable, str(TASK / "solution/app/dispatch.py"), "--data", str(source),
               "--output", str(folder / "plan.json")]
        row = {"input_sha256": certificate["sha256"], "failures": {}}
        start = time.monotonic()
        try:
            process = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=120)
            row["seconds"] = time.monotonic() - start
            (folder / "process.log").write_text("$ " + " ".join(cmd) + "\n" + process.stdout + process.stderr)
            assert process.returncode == 0, process.stderr
            plan = json.loads((folder / "plan.json").read_text())
            day = R.Day(source)
            day.least_cost = lambda: {"cost": certificate["milp_cost_gbp"]}
            flows = day.true_flows(plan)
            row["cost_gbp"] = float(flows["cost"].sum())
            row["delta_gbp"] = row["cost_gbp"] - certificate["milp_cost_gbp"]
            for test_name, function in funcs:
                try:
                    function((day, plan, flows))
                except Exception:
                    row["failures"][test_name] = traceback.format_exc()
            assert hashes(source) == certificate["sha256"]
        except Exception:
            row["seconds"] = time.monotonic() - start
            row["failures"]["execution_or_input_identity"] = traceback.format_exc()
        row["passed"] = not row["failures"]
        return f"{seed}/{name}", row

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for name, row in pool.map(run, cases):
            report["fresh"][name] = row
            print(name, "PASS" if row["passed"] else "FAIL", row["seconds"], flush=True)
            (args.out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    report["fresh_all_passed"] = all(row["passed"] for row in report["fresh"].values())
    report["max_fresh_cli_seconds"] = max(row["seconds"] for row in report["fresh"].values())
    report["max_fresh_absolute_cost_delta_gbp"] = max(abs(row.get("delta_gbp", float("inf")))
                                                       for row in report["fresh"].values())
    (args.out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    assert report["fresh_all_passed"]
    print("EVIDENCE VERIFIED", len(cases), "fresh days; max CLI seconds", report["max_fresh_cli_seconds"])


if __name__ == "__main__":
    main()
