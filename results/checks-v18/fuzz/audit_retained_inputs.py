"""Compare retained completed case files with their exact deterministic specs.

This is a post-run audit, not a claim that removed successful input folders were
hashed while the original main/supplement workers ran. New fuzz runs retain such
hashes directly in each result. Unique case IDs prevent rejected-draw path reuse.
"""

import hashlib
import json
from pathlib import Path
import sys
import tempfile

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import fuzz_v18 as F

FILES = ("plant.json", "supply.json", "status.json", "demand.csv", "weather.csv")
checks, absent = [], []
with tempfile.TemporaryDirectory(prefix="retained-audit-", dir=OUT) as tmp:
    fresh = Path(tmp)
    for batch in ("main", "supplement"):
        folder = OUT / batch
        specs = {r["id"]: r for x in (folder / "specs.jsonl").read_text().splitlines()
                 if (r := json.loads(x))}
        completed = [json.loads(x) for x in (folder / "results.jsonl").read_text().splitlines()]
        for row in completed:
            name = row["id"]
            retained = folder / "days" / name
            if not all((retained / n).exists() for n in FILES):
                absent.append(f"{batch}/{name}")
                continue
            spec = specs[name]["spec"]
            if "overrides" in spec:
                spec["overrides"] = {int(k): v for k, v in spec["overrides"].items()}
            F.B.write_day(fresh, spec)
            record = {"batch": batch, "id": name, "files": {}}
            for filename in FILES:
                actual = (retained / filename).read_bytes()
                expected = (fresh / filename).read_bytes()
                semantic_match = (json.loads(actual) == json.loads(expected)
                                  if filename.endswith(".json") else actual == expected)
                record["files"][filename] = {
                    "matches_spec_bytes": actual == expected,
                    "matches_spec_content": semantic_match,
                    "actual_sha256": hashlib.sha256(actual).hexdigest(),
                    "expected_sha256": hashlib.sha256(expected).hexdigest(),
                }
            checks.append(record)

report = {
    "audit_scope": "post-run, completed cases whose five generated inputs are still retained",
    "checked_completed_folders": len(checks),
    "removed_success_cases_not_postchecked": absent,
    "byte_mismatch_note": "The sorted JSONL spec reorders dictionary keys in original main status.json; parsed JSON equality is the input-content check. CSV data is compared byte-for-byte.",
    "byte_mismatch_file_count": sum(not c["matches_spec_bytes"] for r in checks for c in r["files"].values()),
    "mismatches": [{"batch": r["batch"], "id": r["id"],
                    "files": [n for n, c in r["files"].items() if not c["matches_spec_content"]]}
                   for r in checks if not all(c["matches_spec_content"] for c in r["files"].values())],
    "checks": checks,
}
(OUT / "retained-input-audit.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({k: v for k, v in report.items() if k not in ("checks", "removed_success_cases_not_postchecked")}, indent=2))
assert not report["mismatches"], "retained case no longer matches the deterministic input spec"
