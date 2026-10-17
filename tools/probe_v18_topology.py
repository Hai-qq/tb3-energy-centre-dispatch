"""Candidate probes for explicitly named, previously untested upstream parts.

The frozen v17 reference omits the two HT-source names. fuzz_v18.reference_day
reports this omission explicitly and extends only their owning-engine outage.
No archived code/data is edited; this is not a claim that v17 itself passed.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import fuzz_v18 as F

ROOT = Path(__file__).resolve().parents[1]


def main():
    out = ROOT / "results/checks-v18/candidates/topology"
    out.mkdir(parents=True, exist_ok=True)
    probes = [
        ("upstream_ht", "h2", "GE2 jacket water and exhaust", "18:20", "18:40"),
        ("absorber_generator", "h3", "AC1 generator", "12:40", "12:50"),
        ("upstream_ge1", "h2", "GE1 jacket water and exhaust", "18:20", "18:40"),
    ]
    results = []
    for index, (name, base, unit, start, end) in enumerate(probes):
        spec = copy.deepcopy(F.B.DAYS[base])
        spec["status"]["outages"].append({"unit": unit, "from": start, "to": end})
        item = {"id": name, "index": index, "base": base,
                "season": "winter" if base == "h2" else "spring", "scenario": "upstream_part",
                "spec": spec}
        (out / f"{name}.spec.json").write_text(json.dumps(item, indent=2) + "\n")
        result = F.one((item, out, 1))
        results.append(result)
        (out / "results.json").write_text(json.dumps(results, indent=2) + "\n")
        print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
