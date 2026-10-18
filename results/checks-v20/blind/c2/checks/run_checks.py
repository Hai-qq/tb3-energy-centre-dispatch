"""Run self-generated full-day cases, billing audits and deterministic replays."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
from pathlib import Path
import subprocess
import sys
import time

import numpy
import scipy

from check_plan import check_plan, read_input
from generate_cases import ROOT, DATA, create_cases


def execute(data, output, seed=0):
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = str(seed)
    begin = time.perf_counter()
    result = subprocess.run([sys.executable, str(ROOT / "app" / "dispatch.py"),
                             "--data", str(data), "--output", str(output)],
                            capture_output=True, text=True, timeout=120, env=env)
    return result, time.perf_counter() - begin


def run():
    cases, infeasible = create_cases()
    results = []
    output_root = ROOT / "experiments" / "plans"
    output_root.mkdir(parents=True, exist_ok=True)
    original_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in DATA.iterdir() if p.is_file()}
    for name, folder in cases.items():
        output = output_root / f"{name}.json"
        result, elapsed = execute(folder, output)
        if result.returncode:
            raise AssertionError(f"{name} unexpectedly failed:\n{result.stdout}\n{result.stderr}")
        audit = check_plan(folder, output)
        record = {"name": name, "seconds": elapsed, **audit}
        results.append(record)
        print(json.dumps({"name": name, "seconds": round(elapsed, 3), "valid": True,
                          "cost_gbp": audit["summary"]["cost_gbp"],
                          "starts": audit["summary"]["engine_starts"]}), flush=True)
    for name, folder in infeasible.items():
        output = output_root / f"{name}.json"
        if output.exists():
            output.unlink()
        result, elapsed = execute(folder, output)
        if result.returncode == 0 or "no feasible loading" not in result.stderr or output.exists():
            raise AssertionError(f"{name}: expected a clear infeasibility failure, got {result.returncode}\n{result.stderr}")
        results.append({"name": name, "seconds": elapsed, "expected_infeasibility": True,
                        "diagnostic": result.stderr.splitlines()[-1]})
        print(json.dumps({"name": name, "seconds": round(elapsed, 3), "expected_infeasibility": True}), flush=True)

    # Identical local operating data produce identical decisions under every UTC
    # offset and every weekday; weekends must also agree with one another.
    read = lambda name: json.loads((output_root / f"{name}.json").read_text())
    base = read("visible")
    for name in ("monday_plus_one", "monday_plus_five_half", "winter_zero_offset"):
        shifted = read(name)
        assert shifted["periods"] == base["periods"], f"{name}: alignment/local weekday changed dispatch"
        assert shifted["summary"] == base["summary"]
    assert read("saturday_plus_one")["periods"] == read("sunday_minus_five")["periods"]
    assert read("saturday_plus_one")["summary"]["cost_gbp"] < base["summary"]["cost_gbp"]
    assert read("startup_bridge")["summary"]["engine_starts"] == 0
    assert all(p["engines_kwe"]["GE2"] >= 400 for p in read("startup_bridge")["periods"])
    assert read("startup_midnight_off")["summary"]["engine_starts"] == 1
    assert all(sum(p["engines_kwe"].values()) == 0 for p in read("no_ht_dump")["periods"])
    assert any(p["pv_kw"] < 280 for p in read("pv_curtailment")["periods"][20:30])
    assert max(p["gas_kwh"] for p in read("gas_binding")["periods"]) >= 3025 - 1e-5
    assert next(r for r in results if r["name"] == "tower_binding")["metrics"]["min_tower_headroom_kw"] < 1e-5
    assert next(r for r in results if r["name"] == "warmer_water_export")["metrics"]["water_above_absorber_minimum_periods"] > 0

    # Analytic independent nonlinear optimum for a binding grid circle. GE1 is
    # unavailable. GE2's fuel/heat marginal costs make its rated output cheapest;
    # the grid cap then fixes the minimum necessary absorption duty. Extra
    # absorption would burn more boiler gas than its displaced EC power saves
    # even in the peak tariff. EC1 is strictly more efficient than EC2.
    q = 600 - 800 * math.tan(math.acos(.95))
    imported = math.sqrt(1220**2 - q*q)
    a = (1850 + 24 + 1000/5.6 - 800 - imported) / (1/5.6 - .022)
    boiler = 975 + a/.71 - 900
    analytic = {"GE2_kwe": 800, "import_kw": imported, "AC1_kw": a, "B1_kw": boiler}
    for p in read("grid_circle")["periods"]:
        assert abs(p["engines_kwe"]["GE2"] - 800) < 2e-5
        assert abs(p["import_kw"] - imported) < 2e-5
        assert abs(p["chillers_kw"]["AC1"] - a) < 2e-5
        assert abs(p["boilers_kw"]["B1"] - boiler) < 2e-5
        assert abs(p["chillers_kw"]["EC2"]) < 2e-5

    # Verify byte-for-byte determinism in fresh interpreters with different hash
    # seeds; repeat the nonlinear case as well as the visible day.
    replays = []
    for name in ("visible", "grid_circle", "warmer_water_export", "random_witness_307", "random_witness_891"):
        target = output_root / f"{name}-replay.json"
        result, elapsed = execute(cases[name], target, seed=987654321)
        assert result.returncode == 0, result.stderr
        same = target.read_bytes() == (output_root / f"{name}.json").read_bytes()
        assert same, f"{name}: non-deterministic serialization"
        replays.append({"name": name, "byte_identical": same, "seconds": elapsed,
                        "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in DATA.iterdir() if p.is_file()}
    assert original_hashes == after, "source data files changed"
    report = {"runtime": {"python": platform.python_version(), "numpy": numpy.__version__, "scipy": scipy.__version__},
              "cases": results, "determinism": replays, "analytic_grid_case": analytic,
              "unchanged_source_data_sha256": after,
              "passed": len(results), "maximum_case_seconds": max(r["seconds"] for r in results)}
    (ROOT / "experiments" / "checks-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": len(results), "replays": len(replays),
                      "max_seconds": report["maximum_case_seconds"]}), flush=True)


if __name__ == "__main__":
    run()
