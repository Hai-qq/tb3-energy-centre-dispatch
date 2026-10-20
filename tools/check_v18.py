"""Reproducible development gates; no changes to the submitted verifier.

Runs the actual test functions against independently generated plans. A day's MILP
is solved once per invocation and reused for the development matrix, with its data
hash recorded. The canonical pytest/eval_energy runs remain a separate cross-check.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAYS = ["visible", "h1", "h2", "h3", "h4"]
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hash(path: Path) -> dict[str, str]:
    return {str(f.relative_to(path)): file_hash(f) for f in sorted(path.rglob("*"))
            if f.is_file() and "__pycache__" not in f.parts and f.suffix != ".pyc"}


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def default_apps() -> dict[str, Path]:
    out = {
        "oracle": ROOT / "tasks/energy-centre-dispatch/solution/app",
        "strong-v16-claude": ROOT / "results/v16-trials/ecd16-run2-claude/app",
    }
    for model in ("claude", "codex"):
        out[f"patched-v17-{model}"] = ROOT / f"results/checks-v18/opponents/ecd17-run2-{model}-parts/app"
    for model in ("claude", "codex"):
        for n in range(1, 4):
            out[f"v17-run{n}-{model}"] = ROOT / f"results/v17-trials/ecd17-run{n}-{model}/app"
    blind = ROOT / "results/checks-v18/blind/app"
    if blind.exists():
        out["blind"] = blind
    return out


def check_app(name, app, days, tests, out: Path, timeout: float) -> dict:
    folder = out / name
    folder.mkdir(parents=True, exist_ok=True)
    result = {"app": str(app.relative_to(ROOT)) if app.is_relative_to(ROOT) else str(app),
              "source_sha256": tree_hash(app), "days": {}, "passed": True}
    funcs = [(n, f) for n, f in vars(tests).items()
             if n.startswith("test_") and n != "test_same_plan_every_time" and callable(f)]
    for day_name, day in days.items():
        dr = {"runs": [], "failures": {}}
        plans = []
        for repeat in range(2):
            plan_path = folder / f"{day_name}{'.rerun' if repeat else ''}.json"
            cmd = [sys.executable, str(app / "dispatch.py"), "--data", str(day.folder),
                   "--output", str(plan_path)]
            start = time.monotonic()
            try:
                run = subprocess.run(cmd, capture_output=True, text=True, env=ENV,
                                     timeout=timeout, start_new_session=True)
                elapsed = time.monotonic() - start
                log = "$ " + " ".join(cmd) + "\n" + run.stdout + run.stderr
                (folder / f"{day_name}.{repeat}.log").write_text(log)
                dr["runs"].append({"returncode": run.returncode, "seconds": elapsed})
                if run.returncode != 0:
                    raise RuntimeError(f"exit {run.returncode}: " + run.stderr[-2000:])
                plans.append(json.loads(plan_path.read_text()))
                dr["runs"][-1]["sha256"] = file_hash(plan_path)
            except Exception as exc:
                dr["failures"][f"execution_{repeat}"] = f"{type(exc).__name__}: {exc}"
                plans.append(None)
        if plans[0] is not None:
            try:
                flows = day.true_flows(plans[0])
                dr["cost_gbp"] = float(flows["cost"].sum())
                dr["milp_gbp"] = day.optimum["cost"]
                dr["delta_gbp"] = dr["cost_gbp"] - dr["milp_gbp"]
                case = (day, plans[0], flows)
                for test_name, func in funcs:
                    try:
                        func(case)
                    except Exception:
                        dr["failures"][test_name] = traceback.format_exc()
            except Exception:
                dr["failures"]["flows"] = traceback.format_exc()
        if plans[0] is None or plans[1] is None or any(
                plans[0].get(k) != plans[1].get(k) for k in ("date", "periods", "summary")):
            dr["failures"]["test_same_plan_every_time"] = "missing plan or unequal JSON output"
        dr["passed"] = not dr["failures"]
        result["passed"] &= dr["passed"]
        result["days"][day_name] = dr
        print(f"{name} {day_name}: {'PASS' if dr['passed'] else 'FAIL'} "
              f"delta={dr.get('delta_gbp', 'n/a')} " + ", ".join(dr["failures"]), flush=True)
        write_json(folder / "result.json", result)
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", type=Path, default=ROOT / "tasks/energy-centre-dispatch")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--apps", nargs="*", help="Names from default matrix; omit for all existing apps")
    ap.add_argument("--app", action="append", default=[], help="Additional NAME=PATH entries")
    ap.add_argument("--mutants", action="store_true")
    ap.add_argument("--mutant-names", nargs="+", help="Selected mutants when --mutants is set")
    ap.add_argument("--gate-v18", action="store_true", help="Exit 1 unless the measured B/E/F matrix gates pass")
    ap.add_argument("--timeout", type=float, default=120.0)
    args = ap.parse_args()
    args.task, args.out = args.task.resolve(), args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(args.task / "tests"))
    reference = importlib.import_module("reference")
    tests = importlib.import_module("test_plans")
    import numpy as np
    import scipy

    metadata = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "command": sys.argv, "python": platform.python_version(),
                "numpy": np.__version__, "scipy": scipy.__version__,
                "task": str(args.task), "test_sha256": file_hash(args.task / "tests/test_plans.py"),
                "reference_sha256": file_hash(args.task / "tests/reference.py"), "days": {}}
    days = {}
    for name in DAYS:
        folder = args.task / "tests/days" / name
        day = reference.Day(folder)
        t0 = time.monotonic()
        optimum = day.least_cost()
        metadata["days"][name] = {"sha256": tree_hash(folder), "milp_gbp": optimum["cost"],
                                 "milp_seconds": time.monotonic() - t0}
        day.folder, day.optimum = folder, optimum
        day.least_cost = lambda optimum=optimum: optimum
        days[name] = day
        write_json(args.out / "milp" / f"{name}.json", optimum)
        print(f"MILP {name}: {optimum['cost']:.9f}", flush=True)
    write_json(args.out / "metadata.json", metadata)

    all_apps = default_apps()
    all_apps["oracle"] = args.task / "solution/app"
    for entry in args.app:
        name, path = entry.split("=", 1)
        all_apps[name] = Path(path).resolve()
    names = args.apps if args.apps is not None else list(all_apps)
    if args.mutants and args.apps is None:
        names = []
    results = {}
    for name in names:
        app = all_apps[name]
        if not (app / "dispatch.py").exists():
            print(f"SKIP absent {name}: {app}", flush=True)
            results[name] = {"skipped": "app absent"}
            continue
        results[name] = check_app(name, app, days, tests, args.out, args.timeout)
        write_json(args.out / "matrix.json", results)

    if args.mutants:
        import energy_mutants as mutants
        for name in args.mutant_names or list(mutants.MUTANTS):
            changes = mutants.MUTANTS[name]
            target = args.out / "mutant_apps" / name
            shutil.copytree(args.task / "solution/app", target, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            for filename, old, new in changes:
                file = target / filename
                src = file.read_text()
                assert src.count(old) == 1, (name, filename, old)
                file.write_text(src.replace(old, new))
            # Execution-fault mutants are intentionally killed after a short development timeout.
            limit = 2.0 if name == "hangs_after_writing" else args.timeout
            results[name] = check_app(name, target, days, tests, args.out, limit)
            write_json(args.out / "matrix.json", results)
            shutil.rmtree(target)
        caught = sum(not v.get("passed", False) for v in results.values())
        print(f"MUTANTS {caught}/{len(results)} caught", flush=True)
        if caught != len(results):
            raise SystemExit(1)

    if args.gate_v18:
        def complete(name):
            return name in results and len(results[name].get("days", {})) == len(DAYS)

        oracle = results.get("oracle", {})
        gates = {
            "B_five_days": complete("oracle") and oracle.get("passed", False)
                and all(abs(v.get("delta_gbp", float("inf"))) < .001
                        for v in oracle.get("days", {}).values()),
            "E1_strongest_defeated": complete("strong-v16-claude")
                and any(not v["passed"] for k, v in results["strong-v16-claude"]["days"].items()
                        if k != "visible"),
            "E2_patched_defeated": all(complete(f"patched-v17-{m}")
                and not results[f"patched-v17-{m}"].get("passed", True) for m in ("claude", "codex")),
            "E3_blind_measured": complete("blind"),
            "F_six_originals_fail": all(complete(f"v17-run{n}-{m}")
                and not results[f"v17-run{n}-{m}"].get("passed", True)
                for n in range(1, 4) for m in ("claude", "codex")),
        }
        write_json(args.out / "gates.json", gates)
        print("MEASURED GATES " + json.dumps(gates), flush=True)
        # Classification of *why* a strong adversary failed is a separate review;
        # even True E1/E2 here is not a claim of fair reasoning difficulty.
        raise SystemExit(0 if all(gates.values()) else 1)


if __name__ == "__main__":
    main()
