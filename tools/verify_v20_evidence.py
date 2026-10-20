"""Final read-only consistency checks for retained v20 experiment evidence.

Does not rerun an application or change a task, visible package or blind file.
Writes one new integrity report, refusing to overwrite an earlier report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import check_v18 as K

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/checks-v20"


def read(path):
    return json.loads(path.read_text())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clock-utc", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    target = args.out.resolve()
    assert target.is_relative_to(OUT) and not target.exists()
    baseline = read(OUT / "baseline/task-sha256.json")
    assert K.tree_hash(ROOT / "tasks/energy-centre-dispatch") == baseline
    assert K.tree_hash(OUT / "baseline/task") == baseline
    readers = read(OUT / "prechecks/READERS_SHA256.json")
    for name, digest in readers.items():
        assert K.file_hash(OUT / "prechecks" / name) == digest, name
    result = {"clock_observation_utc": args.clock_utc,
              "canonical_task_and_baseline_identical": True,
              "reader_files_unchanged": len(readers), "candidates": {}}
    for cid in ["c1", "c2", "c4"]:
        folder = OUT / "candidates" / cid
        assert K.tree_hash(folder / "visible") == read(folder / "VISIBLE_SHA256.json")
        meta = read(folder / "gates-r1/metadata.json")
        assert K.tree_hash(folder / "task") == meta["task_hashes"]
        apps = read(folder / "gates-r1/apps.json")
        for name, app in apps.items():
            assert K.tree_hash(ROOT / app["app"]) == app["source_sha256"], (cid, name)
        blind = OUT / "blind" / cid
        entries = read(blind / "FREEZE.json")["files"]
        expected = {name: item["sha256"] if isinstance(item, dict) else item
                    for name, item in entries.items()}
        actual = K.tree_hash(blind)
        actual.pop("FREEZE.json")
        assert actual == expected, cid
        before = read(OUT / "prechecks" / f"{cid}-freeze-before-eval.json")
        after = read(OUT / "prechecks" / f"{cid}-freeze-after-eval.json")
        manifest_sha = K.file_hash(blind / "FREEZE.json")
        assert before["manifest_sha256"] == after["manifest_sha256"] == manifest_sha
        fresh = {}
        for seed in [2026, 2403, 87123]:
            ff = folder / f"fresh-{seed}"
            manifest = read(ff / "manifest.json")
            assert len(manifest["days"]) == 16
            assert manifest["input_hashes_unchanged_after_evaluation"]
            for name, day in manifest["days"].items():
                assert K.tree_hash(ff / "tests/days" / name) == day["sha256"], (cid, seed, name)
            assert manifest["results"] and all(not r["failed"] and not r["errors"]
                                                for r in manifest["results"].values())
            fresh[str(seed)] = {"days": 16, "all_tests_passed": True, "inputs_unchanged": True}
        result["candidates"][cid] = {"visible_unchanged": True, "evaluated_task_unchanged": True,
                                    "all_historical_apps_unchanged": True,
                                    "frozen_blind_files_unchanged": len(expected),
                                    "fresh": fresh}
    for cid in ["c3", "c5"]:
        folder = OUT / "candidates" / cid
        assert K.tree_hash(folder / "visible") == read(folder / "VISIBLE_SHA256.json")
    changed = subprocess.check_output(["git", "diff", "--name-only", "9db580817b1dc46ac6c500f8c472faaafce0a997"],
                                      cwd=ROOT, text=True).splitlines()
    allowed = ("tasks/energy-centre-dispatch/", "tools/", "results/checks-v20/")
    assert all(name.startswith(allowed) for name in changed), changed
    result["tracked_changed_paths_within_allowed_scope"] = True
    result["tracked_changed_paths_at_check"] = changed
    result["scope_note"] = "Tracked diff checked here; exact staged and committed path scope is checked again when publishing."
    K.write_json(target, result)
    print(json.dumps({"canonical_task_unchanged": True, "readers": len(readers),
                      "frozen_blind_files": sum(x["frozen_blind_files_unchanged"] for x in result["candidates"].values()),
                      "fresh_days_verified": 144, "allowed_tracked_scope": True}))


if __name__ == "__main__":
    main()
