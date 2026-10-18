"""Verify a declared blind freeze without executing or editing the blind app.

Run only after that agent explicitly declares completion. The declared manifest
digest is a required argument; observed clock time is recorded separately from
any timestamp generated inside the agent's execution environment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/checks-v20"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", choices=["c1", "c2", "c4"], required=True)
    ap.add_argument("--sha256", required=True)
    ap.add_argument("--phase", choices=["before-eval", "after-eval"], required=True)
    ap.add_argument("--clock-utc", required=True, help="Actual clock tool observation, not an inferred timestamp")
    args = ap.parse_args()
    folder = OUT / "blind" / args.candidate
    manifest_path = folder / "FREEZE.json"
    assert digest(manifest_path) == args.sha256, "manifest differs from agent's declaration"
    manifest = json.loads(manifest_path.read_text())
    entries = manifest["files"]
    assert isinstance(entries, dict) and entries, "expected a nonempty file mapping"
    files = {k: v["sha256"] if isinstance(v, dict) else v for k, v in entries.items()}
    if "file_count" in manifest:
        assert len(files) == manifest["file_count"]
    for relative, expected in files.items():
        path = folder / relative
        assert path.resolve().is_relative_to(folder.resolve()), relative
        assert path.is_file() and digest(path) == expected, relative
        if isinstance(entries[relative], dict) and "bytes" in entries[relative]:
            assert path.stat().st_size == entries[relative]["bytes"], relative
    actual = {str(p.relative_to(folder)) for p in folder.rglob("*")
              if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}
    assert actual == set(files) | {"FREEZE.json"}, sorted(actual ^ (set(files) | {"FREEZE.json"}))
    target = OUT / "prechecks" / f"{args.candidate}-freeze-{args.phase}.json"
    assert not target.exists(), "preserve previous verification instead of overwriting it"
    result = {
        "candidate": args.candidate,
        "phase": args.phase,
        "clock_observation_utc": args.clock_utc,
        "manifest_sha256": args.sha256,
        "file_count_verified": len(files),
        "source_and_selftest_artifacts_unchanged": True,
        "unexpected_files": [],
        "app_sha256": {k.removeprefix("app/"): v for k, v in files.items() if k.startswith("app/")},
    }
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"{args.candidate} {args.phase}: {len(files)} frozen files verified")


if __name__ == "__main__":
    main()
