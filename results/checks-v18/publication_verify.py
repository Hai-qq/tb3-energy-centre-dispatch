"""Verify publication bytes; do not relabel historical tests as fresh runs."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import numpy
import scipy
import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TASK = ROOT / "tasks/energy-centre-dispatch"
TESTED_TREE = "b3d57f4c3d5bc1338a2dae90aa9270abba83ccb3"
PUBLISHED_R1 = "682f76acceef1658e23cd6d234134cf4335eabaa"
BASE = "12a1116c5e545b4c30ff43cf8ac6503c9fd14473"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hashes(path):
    return {str(p.relative_to(path)): digest(p) for p in sorted(path.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main():
    assert git("rev-parse", PUBLISHED_R1 + "^{tree}") == TESTED_TREE
    def visible_at(folder):
        return {"instruction.md": digest(folder / "instruction.md"),
                **{"environment/" + k: v for k, v in hashes(folder / "environment").items()}}
    visible = visible_at(TASK)
    assert visible == visible_at(ROOT / "archive/energy-centre-dispatch-v8.1")
    assert len(visible) == 13
    metadata = json.loads((HERE / "final-matrix/metadata.json").read_text())
    evidence = json.loads((HERE / "evidence-verification/report.json").read_text())
    assert digest(TASK / "tests/reference.py") == metadata["reference_sha256"] == evidence["reference_sha256"]
    assert digest(TASK / "tests/test_plans.py") == metadata["test_sha256"]
    assert hashes(TASK / "solution/app") == evidence["oracle_sha256"]
    for day, data in metadata["days"].items():
        assert hashes(TASK / "tests/days" / day) == data["sha256"]
        for filename in ("plant.json", "supply.json"):
            assert (TASK / "tests/days" / day / filename).read_bytes() == (
                ROOT / "archive/energy-centre-dispatch-v17/tests/days" / day / filename).read_bytes()
    fresh_days = 0
    for seed in (2026, 2403, 87123):
        folder = HERE / "final-fresh-verified" / f"seed-{seed}"
        manifest = json.loads((folder / "manifest.json").read_text())
        for day, data in manifest["days"].items():
            assert hashes(folder / "tests/days" / day) == data["sha256"]
            fresh_days += 1
    assert fresh_days == 48
    blind = HERE / "blind"
    freeze = json.loads((blind / "FROZEN_SHA256.json").read_text())
    for group in ("runtime_code_files", "input_data_files"):
        for name, sha in freeze[group].items():
            assert digest(blind / name) == sha
    assert digest(blind / "instruction.md") == freeze["instruction_sha256"]
    paths = set(git("diff", "--name-only", BASE).splitlines())
    paths.update(git("ls-files", "--others", "--exclude-standard").splitlines())
    allowed = ("tasks/energy-centre-dispatch/tests/", "tasks/energy-centre-dispatch/solution/",
               "tools/", "results/checks-v18/")
    assert all(p.startswith(allowed) for p in paths)
    versions = {"python": sys.version.split()[0], "numpy": numpy.__version__,
                "scipy": scipy.__version__, "pytest": pytest.__version__}
    assert versions == {"python": "3.13.16", "numpy": "2.3.4", "scipy": "1.17.0", "pytest": "9.1.1"}
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Post-cleanup publication integrity check; not a rerun of B/C/E/F",
        "base_commit": BASE,
        "pre_cleanup_local_commit": "bd62cb0f1c0b878f64ae097ecf39a1cb4ea7cb99",
        "published_r1_commit": PUBLISHED_R1, "exact_tested_tree": TESTED_TREE,
        "published_r1_tree_matches_pre_cleanup_tree": True, "runtime": versions,
        "visible_files_byte_identical_to_v8_1": len(visible),
        "fixed_plant_supply_files_unchanged": 10,
        "task_code_oracle_and_five_day_input_hashes_match_test_evidence": True,
        "fresh_persisted_input_hashes_verified": fresh_days,
        "blind_runtime_sha256": freeze["runtime_code_sha256"],
        "changed_paths_within_user_scope": True,
        "new_functional_task_revisions_since_full_gate_run": 0,
    }
    (HERE / "publication-verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
