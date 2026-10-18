"""Reproduce v19 build checks; keep full plans and generated days outside the repo."""

from __future__ import annotations

import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
TASK = ROOT / "tasks/energy-centre-dispatch"
LARGE = Path("/private/tmp/claude-501/-Users-haiy-qq-Desktop----klavis/a70e7eab-ed43-4fbc-8c31-1d0858956a32/scratchpad/codex-v19-build")
DAYS = ["visible", "h1", "h2", "h3", "h4"]
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
RENAMES = {"GE1 LT radiator": "LT radiator 1", "GE2 LT radiator": "LT radiator 2"}
sys.path[:0] = [str(ROOT / "tools"), str(TASK / "tests")]


def write(name, data):
    (OUT / name).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(label, command):
    start = time.monotonic()
    with (OUT / f"{label}.log").open("w") as log:
        result = subprocess.run(command, cwd=ROOT, env=ENV, stdout=log, stderr=subprocess.STDOUT)
    write(f"{label}.command.json", {"command": command, "environment": {k: ENV[k] for k in
          ("PYTHONDONTWRITEBYTECODE", "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS")},
          "returncode": result.returncode, "seconds": time.monotonic() - start})
    print(label, "exit", result.returncode, flush=True)
    assert result.returncode == 0, label


def snapshot():
    paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", "f02497a",
                                     "tasks/energy-centre-dispatch/tests",
                                     "tasks/energy-centre-dispatch/solution/app"], cwd=ROOT, text=True).splitlines()
    for name in paths:
        target = LARGE / "v18-task" / Path(name).relative_to("tasks/energy-centre-dispatch")
        expected = subprocess.check_output(["git", "show", f"f02497a:{name}"], cwd=ROOT)
        if target.exists():
            assert target.read_bytes() == expected, target
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(expected)
    write("baseline-snapshot.json", {"commit": "f02497a", "files": len(paths), "path": str(LARGE / "v18-task")})


def static():
    archive = ROOT / "archive/energy-centre-dispatch-v8.1"
    names = ["instruction.md"] + [str(p.relative_to(TASK)) for p in sorted((TASK / "environment").rglob("*"))
                                   if p.is_file()]
    archived_names = ["instruction.md"] + [str(p.relative_to(archive)) for p in sorted((archive / "environment").rglob("*"))
                                            if p.is_file()]
    assert names == archived_names
    checks = {}
    for name in names:
        before, after = (archive / name).read_bytes(), (TASK / name).read_bytes()
        expected = before
        if name == "environment/data/plant.json":
            for old, new in RENAMES.items():
                assert expected.count(old.encode()) == 1
                expected = expected.replace(old.encode(), new.encode())
            (OUT / "plant-v8.1.diff").write_text("".join(difflib.unified_diff(
                before.decode().splitlines(True), after.decode().splitlines(True),
                fromfile="v8.1/environment/data/plant.json", tofile="v19/environment/data/plant.json")))
        assert after == expected, name
        checks[name] = {"identical_to_v8.1": before == after, "sha256": hashlib.sha256(after).hexdigest()}
    visible = TASK / "tests/days/visible"
    public = TASK / "environment/data"
    assert {p.name: p.read_bytes() for p in visible.iterdir()} == {p.name: p.read_bytes() for p in public.iterdir()}
    old = LARGE / "v18-task"
    data_checks = {}
    for day in DAYS:
        assert (TASK / f"tests/days/{day}/plant.json").read_bytes() == (public / "plant.json").read_bytes()
        for before in sorted((old / f"tests/days/{day}").iterdir()):
            expected = before.read_bytes()
            for a, b in RENAMES.items():
                expected = expected.replace(a.encode(), b.encode())
            after = TASK / f"tests/days/{day}" / before.name
            assert expected == after.read_bytes(), after
            data_checks[f"{day}/{before.name}"] = hashlib.sha256(expected).hexdigest()
    write("A-prime.json", {"passed": True, "public_files": checks, "visible_matches_environment": True,
                           "five_plants_identical": True, "v18_only_names_changed": data_checks})
    print("A-prime PASS", flush=True)


def matrix():
    import numpy as np
    import reference
    import test_plans
    from check_v18 import check_app

    old_ref = load_module("reference_v18", LARGE / "v18-task/tests/reference.py")
    days, invariance = {}, {}
    for name in DAYS:
        day = reference.Day(TASK / f"tests/days/{name}")
        old = old_ref.Day(LARGE / f"v18-task/tests/days/{name}")
        old_availability = {RENAMES.get(k, k): v for k, v in old.available.items()}
        for k, value in old_availability.items():
            assert np.array_equal(value, day.available[k]), (name, k)
        extra = sorted(set(day.available) - old_availability.keys())
        assert extra == ["hospital buildings"], extra
        for key in vars(old).keys() - {"plant", "status", "available"}:
            def equal(a, b):
                if isinstance(a, dict):
                    return a.keys() == b.keys() and all(equal(a[k], b[k]) for k in a)
                if isinstance(a, (tuple, list)):
                    return len(a) == len(b) and all(equal(x, y) for x, y in zip(a, b))
                return bool(np.array_equal(a, b))
            assert equal(getattr(old, key), getattr(day, key)), (name, key)
        optimum, old_optimum = day.least_cost(), old.least_cost()
        assert optimum == old_optimum, name
        day.folder, day.optimum = TASK / f"tests/days/{name}", optimum
        day.least_cost = lambda optimum=optimum: optimum
        days[name] = day
        invariance[name] = {"all_existing_availability_equal": True, "other_model_attributes_equal": True,
                            "added_available_names": extra, "milp_full_result_identical": True,
                            "milp_gbp": optimum["cost"]}
        print("v18/v19 model identical", name, optimum["cost"], flush=True)
    apps = {"oracle": TASK / "solution/app"}
    apps.update({p.parent.name: p for p in sorted((ROOT / "results/v18-trials").glob("*/app"))})
    assert len(apps) == 7
    apps.update({"ecd16-run2-claude": ROOT / "results/v16-trials/ecd16-run2-claude/app",
                 "ecd17-run2-claude-parts": ROOT / "results/checks-v18/opponents/ecd17-run2-claude-parts/app",
                 "ecd17-run2-codex-parts": ROOT / "results/checks-v18/opponents/ecd17-run2-codex-parts/app"})
    results = {}
    full = LARGE / "matrix"
    for name, app in apps.items():
        assert (app / "dispatch.py").is_file(), app
        results[name] = check_app(name, app, days, test_plans, full, 150.0)
        write("matrix.json", results)
    assert results["oracle"]["passed"]
    assert all(abs(d["delta_gbp"]) < .001 for d in results["oracle"]["days"].values())
    assert all(not results[p.parent.name]["passed"] for p in (ROOT / "results/v18-trials").glob("*/app"))
    for name, day in days.items():
        plan = json.loads((full / f"oracle/{name}.json").read_text())
        old = old_ref.Day(LARGE / f"v18-task/tests/days/{name}")
        before, after = old.true_flows(plan), day.true_flows(plan)
        assert all(np.array_equal(before[k], after[k]) for k in before)
        old_plan = LARGE / f"v18-oracle-{name}.json"
        subprocess.run([sys.executable, str(LARGE / "v18-task/solution/app/dispatch.py"), "--data",
                        str(LARGE / f"v18-task/tests/days/{name}"), "--output", str(old_plan)],
                       env=ENV, check=True, capture_output=True, timeout=150)
        assert json.loads(old_plan.read_text()) == plan
        invariance[name].update(true_flows_identical=True, oracle_plan_identical=True)
    write("v18-invariance.json", invariance)
    print("B matrix and F PASS", flush=True)


def topology():
    from reference import Day
    plant_module = load_module("solution_plant", TASK / "solution/app/planner/plant.py")
    sys.path.insert(0, str(TASK / "solution/app"))
    from planner.optimize import _engine_can_run

    source = TASK / "tests/days/visible"
    folder = LARGE / "topology-probe"
    shutil.copytree(source, folder, dirs_exist_ok=True)
    plant = json.loads((folder / "plant.json").read_text())
    circuits = plant["heat_circuits"]
    circuits["renamed_circuit"] = circuits.pop("ge1_lt")
    circuits["renamed_circuit"]["to"] = ["Remote cooler east", "Remote cooler west"]
    (folder / "plant.json").write_text(json.dumps(plant))
    status = json.loads((folder / "status.json").read_text())
    evidence = []
    for sink in circuits["renamed_circuit"]["to"]:
        status["outages"] = [{"unit": sink, "from": "10:10", "to": "10:20"}]
        (folder / "status.json").write_text(json.dumps(status))
        day = Day(folder)
        assert not day.available["GE1"][20]
        assert day.available["GE1"][19] and day.available["GE1"][21]
        assert day.available["GE2"].all()
        p = plant_module.Plant(plant)
        # _engine_can_run only reads status, so avoid relying on a data-loader interface.
        data = type("Status", (), {"status": status})()
        assert not _engine_can_run(data, p, p.engines[0], "10:00")
        assert _engine_can_run(data, p, p.engines[0], "10:30")
        assert _engine_can_run(data, p, p.engines[1], "10:00")
        evidence.append({"outage": sink, "reference_and_solution_disable_GE1_only": True})
    write("topology-probe.json", {"passed": True, "renamed_circuit": True, "multiple_outlets": evidence})


def fresh():
    for seed in (2026, 2403, 87123):
        target = LARGE / f"fresh-{seed}"
        run(f"fresh-{seed}", [sys.executable, "tools/fresh_days.py", "--days", "16", "--seed", str(seed),
                              "--output", str(target), "tasks/energy-centre-dispatch/solution/app"])
    fresh_summary()


def fresh_summary():
    summaries = {}
    total = dict.fromkeys(RENAMES.values(), 0)
    for seed in (2026, 2403, 87123):
        target = LARGE / f"fresh-{seed}"
        assert json.loads((OUT / f"fresh-{seed}.command.json").read_text())["returncode"] == 0
        manifest = json.loads((target / "manifest.json").read_text())
        assert len(manifest["days"]) == 16
        assert all(not (r["errors"] or r["failed"]) for r in manifest["results"].values())
        counts = {sink: sum(o["unit"] == sink for d in manifest["days"].values()
                           for o in d["spec"]["status"]["outages"]) for sink in RENAMES.values()}
        for sink, count in counts.items():
            total[sink] += count
        shutil.copyfile(target / "manifest.json", OUT / f"fresh-{seed}.manifest.json")
        summaries[str(seed)] = {"accepted_days": len(manifest["days"]), "draws": len(manifest["draws"]),
                                "radiator_outages": counts, "results": manifest["results"],
                                "large_artifacts": str(target)}
        write("fresh-summary.json", summaries)
    assert all(total.values()), total
    print("fresh 48/48 PASS; aggregate radiator outages", total, flush=True)


def deliveries():
    from eval_energy import evaluate
    apps = {p.parent.name: p for p in sorted((ROOT / "results/v18-trials").glob("*/app"))}
    apps.update({"ecd16-run2-claude": ROOT / "results/v16-trials/ecd16-run2-claude/app",
                 "ecd17-run2-claude-parts": ROOT / "results/checks-v18/opponents/ecd17-run2-claude-parts/app",
                 "ecd17-run2-codex-parts": ROOT / "results/checks-v18/opponents/ecd17-run2-codex-parts/app"})
    results = {}
    for name, app in apps.items():
        start = time.monotonic()
        result = evaluate(app, quiet=True)
        result.update(seconds=time.monotonic() - start, app=str(app.relative_to(ROOT)),
                      passed_tests=55 - sum(len(v) for v in result["failed"].values()), total_tests=55)
        results[name] = result
        print(name, result["passed_tests"], "/55", result["errors"], result["failed"], flush=True)
        write("canonical-deliveries.json", results)
    assert all(results[name]["failed"] for name in results if name.startswith("ecd18-"))


def integrity():
    exact = {"tools/build_energy_days.py", "tools/energy_mutants.py", "tools/fresh_days.py",
             "tasks/energy-centre-dispatch/tests/reference.py"}
    prefixes = ("tasks/energy-centre-dispatch/tests/days/", "tasks/energy-centre-dispatch/solution/",
                "tasks/energy-centre-dispatch/environment/data/", "results/checks-v19/build/")
    status = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT, text=True)
    changed = [line[3:] for line in status.splitlines()]
    assert all(p in exact or p.startswith(prefixes) for p in changed), changed
    forbidden = ["tasks/energy-centre-dispatch/instruction.md", "tasks/energy-centre-dispatch/environment/planner",
                 "tasks/energy-centre-dispatch/environment/dispatch.py"]
    diff = subprocess.check_output(["git", "diff", "--", *forbidden], cwd=ROOT, text=True)
    assert not diff
    whitespace = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert whitespace.returncode == 0, whitespace.stdout + whitespace.stderr
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
    head = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    assert (branch, head) == ("v19", "f02497a")
    for scope in (ROOT / "tools", TASK, OUT):
        assert not list(scope.rglob("__pycache__")), scope
    import energy_mutants
    assert len(energy_mutants.MUTANTS) == 42
    for name, changes in energy_mutants.MUTANTS.items():
        for filename, old, new in changes:
            text = (energy_mutants.SOL / filename).read_text()
            assert text.count(old) == 1, (name, filename)
            compile(text.replace(old, new), filename, "exec")
    for filename in changed:
        p = ROOT / filename
        if p.suffix == ".py":
            compile(p.read_text(), filename, "exec")
    (OUT / "final-checks.log").write_text("$ git status --porcelain --untracked-files=all\n" + status
        + "$ git diff -- " + " ".join(forbidden) + "\n" + diff + "$ git diff --check\n"
        + whitespace.stdout + whitespace.stderr)
    write("final-integrity.json", {"passed": True, "branch": branch, "head": head,
          "all_changes_in_allowed_scope": True, "forbidden_diff_empty": True, "diff_check_passed": True,
          "no_caches_in_tools_task_or_build": True, "historical_jobs_caches": "See existing-caches.json; left untouched",
          "all_42_mutant_replacements_match_once_and_compile": True, "changed_python_sources_compile": True,
          "changed_source_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in changed
                                    if not p.startswith("results/")}})
    print("final integrity PASS", flush=True)


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "static":
        static()
        topology()
    elif mode == "matrix":
        matrix()
    elif mode == "fresh":
        fresh()
    elif mode == "fresh-summary":
        fresh_summary()
    elif mode == "canonical":
        run("canonical-eval", [sys.executable, "tools/eval_energy.py", "tasks/energy-centre-dispatch/solution/app"])
    elif mode == "mutants":
        run("canonical-mutants", [sys.executable, "tools/energy_mutants.py"])
    elif mode == "deliveries":
        deliveries()
    elif mode == "snapshot":
        snapshot()
    elif mode == "integrity":
        integrity()
    else:
        raise ValueError(mode)
