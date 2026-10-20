"""Reproducible differential stress tests against the archived v17 reference.

All app imports use isolated package names. Runs invoke each original loader, plant,
tariff, optimizer, and the original serialization precision, then the independent
archived tests. The two v17 apps differ only by their documented component patches.
No task or historical result is modified. Specs, timings, witnesses, and the seed
are retained beneath results/checks-v18/fuzz. A generated day has a feasibility
witness when an app passes every physical check; suspicious cases additionally
receive a whole-day reference MILP. Reference omissions are identified separately.

Usage: PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  python tools/fuzz_v18.py --days 320 --seed 180017 --workers 2
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import importlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import random
import shutil
import signal
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import date, timedelta

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "archive/energy-centre-dispatch-v17"
OUT = ROOT / "results/checks-v18/fuzz"
APPS = {
    "v16_claude": ROOT / "results/v16-trials/ecd16-run2-claude/app",
    "v17_codex_parts": ROOT / "results/checks-v18/opponents/ecd17-run2-codex-parts/app",
    "v17_claude_parts": ROOT / "results/checks-v18/opponents/ecd17-run2-claude-parts/app",
}
MODULES = {}


def module_from_file(name, path, package=False):
    spec = importlib.util.spec_from_file_location(
        name, path, submodule_search_locations=[str(path.parent)] if package else None)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


B = module_from_file("fuzz_v18_builder", BASE / "build_energy_days.py")
R = module_from_file("fuzz_v18_reference", BASE / "tests/reference.py")
# test_plans.py imports its independent reference under this ordinary name.
sys.modules["reference"] = R
T = module_from_file("fuzz_v18_tests", BASE / "tests/test_plans.py")
UNITS = sorted({u["id"] for k in ("engines", "boilers", "electric_chillers", "absorption_chillers")
                for u in B.PLANT[k]} | set(B.PLANT["cooling_towers"]["cells"])
               | {B.PLANT["pv"]["id"]}
               | {n for c in B.PLANT["heat_circuits"].values() for n in c["from"] + c["to"]}
               - {"hospital buildings"})
SEASONS = [("winter", [12, 1, 2], "h2"), ("spring", [3, 4, 5], "h3"),
           ("summer", [6, 7, 8], "h4"), ("autumn", [9, 10, 11], "h3")]
CHECKS = ["test_plan_covers_the_day", "test_units_within_ratings_and_availability",
          "test_electricity_balance", "test_heat_balance", "test_cooling_balance",
          "test_cooling_towers", "test_connection_limits", "test_reported_gas_and_cost",
          "test_reported_import_export_and_grid_flags"]


def hhmm(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def draw(index, seed):
    rng = random.Random(seed + index * 1000003)
    season, months, base = SEASONS[index % 4]
    d = date(2026, rng.choice(months), rng.randint(1, 25))
    if d == date(2026, 10, 25):
        d = date(2026, 10, 24)  # the instruction excludes UK clock-change days
    offset = int(date(2026, 3, 29) < d < date(2026, 10, 25))
    b = B.DAYS[base]
    scenario = (index // 4) % 8
    fe, fh, fc = rng.uniform(.88, 1.08), rng.uniform(.8, 1.15), rng.uniform(.8, 1.15)
    if scenario == 2:  # Low electricity relative to heat: holiday/maintenance load.
        fe, fh, fc = rng.uniform(.48, .72), rng.uniform(1.0, 1.4), rng.uniform(.8, 1.1)
    if scenario == 3:
        fe, fc = rng.uniform(1.02, 1.18), rng.uniform(1.02, 1.2)
    dt = rng.uniform(-4, 4) if scenario == 1 else rng.uniform(-2, 2)
    solar = {"winter": (8.1, 16.1), "spring": (6.2, 19.8),
             "summer": (5.2, 20.8), "autumn": (6.5, 18.5)}[season]
    pv_peak = rng.uniform(35, 280)
    if scenario == 7:
        pv_peak = [0, 280][(index // 32) % 2]
    outages = []
    # Deliberate cyclic coverage includes every component, not only visible-day IDs.
    first = UNITS[index % len(UNITS)]
    count = 1 if scenario in (0, 1, 2) else rng.randint(2, 4)
    names = [first] + rng.choices(UNITS, k=count - 1)
    for k, unit in enumerate(names):
        a = rng.choice([0, 30, 360, 420, 960, 1020, 1410]) if scenario == 6 else rng.randrange(0, 1380)
        dur = rng.choice([1, 5, 10, 15, 29, 30, 31]) if scenario == 5 else rng.choice([30, 60, 90, 120, 240])
        z = min(1440, a + dur)
        outages.append({"unit": unit, "from": hhmm(a), "to": hhmm(z)})
    if scenario == 4:
        a = rng.randrange(240, 1020)
        # Separate, touching, and overlapping intervals of the same component.
        gap = [-10, 0, 5, 31][(index // 32) % 4]
        outages = [{"unit": first, "from": hhmm(a), "to": hhmm(a + 45)},
                   {"unit": first, "from": hhmm(a + 45 + gap), "to": hhmm(a + 100)}]
    spec = dict(date=d.isoformat(), offset=offset, seed=rng.randrange(10**9),
                elec=[(h, v * fe) for h, v in b["elec"]],
                heat=[(h, v * fh) for h, v in b["heat"]],
                cool=[(h, v * fc) for h, v in b["cool"]],
                dry=[(h, v + dt) for h, v in b["dry"]],
                wet=[(h, v + dt) for h, v in b["wet"]],
                sun=solar, pv_peak=pv_peak, cloud=rng.uniform(0, .7),
                kvar_per_kw=rng.choice([.03, .10, .17, .25, .4, .55]),
                status={"running_at_midnight": [e for j, e in enumerate(["GE1", "GE2"])
                                                 if (index // 4) % 4 & (1 << j)],
                        "outages": outages})
    return {"id": f"d{index + 1:04d}", "index": index, "season": season,
            "scenario": scenario, "base": base, "spec": spec}


def check_inputs(folder, expected_spec=None):
    status = json.loads((folder / "status.json").read_text())
    demand = list(csv.DictReader((folder / "demand.csv").open()))
    wx = list(csv.DictReader((folder / "weather.csv").open()))
    problems = []
    if expected_spec is not None:
        expected_status = {"date": expected_spec["date"], **expected_spec["status"]}
        if status != expected_status:
            problems.append("materialized_status_differs_from_spec")
        if any(r["period_start"][:10] != expected_spec["date"] for r in demand):
            problems.append("materialized_demand_date_differs_from_spec")
    if status["date"] in ("2026-03-29", "2026-10-25"):
        problems.append("clock_change_date")
    if len(demand) != 48:
        problems.append("not_48_half_hours")
    if any(float(v) < 0 for r in demand for k, v in r.items() if k != "period_start"):
        problems.append("negative_demand")
    if any(float(r["wet_bulb_c"]) > float(r["dry_bulb_c"]) for r in wx):
        problems.append("wet_above_dry")
    if any(not 0 <= float(r["pv_kw"]) <= 280 for r in wx):
        problems.append("pv_outside_rating")
    for o in status["outages"]:
        if o["unit"] not in UNITS:
            problems.append("unlisted_outage")
        a, b = R._hm(o["from"]), R._hm(o["to"])
        if not 0 <= a < b <= 1440:
            problems.append("invalid_outage_interval")
    return problems


def reference_day(folder):
    """Expose v17's missing jacket/exhaust key; extend only that explicit component.

    The ordinary archived verifier is tried first. If it KeyErrors on either of
    the named engine heat sources, initialize it with those two outages removed,
    then enforce their parent engine availability. Such results are marked
    reference_extension rather than claimed as the unmodified v17 verifier.
    """
    try:
        return R.Day(folder), None
    except KeyError as exc:
        missing = str(exc.args[0])
        allowed = {f"GE{i} jacket water and exhaust" for i in (1, 2)}
        if missing not in allowed:
            raise
        child = folder / "reference_view"
        child.mkdir(exist_ok=True)
        for n in ("plant.json", "supply.json", "weather.csv", "demand.csv"):
            shutil.copy2(folder / n, child / n)
        full = json.loads((folder / "status.json").read_text())
        filtered = {**full, "outages": [o for o in full["outages"] if o["unit"] not in allowed]}
        (child / "status.json").write_text(json.dumps(filtered))
        day = R.Day(child)
        day.status = full
        import numpy as np
        for o in full["outages"]:
            if o["unit"] not in allowed:
                continue
            a, b = R._hm(o["from"]), R._hm(o["to"])
            av = ~np.array([c < b and c + 30 > a for c in day.clock])
            day.available[o["unit"]] = day.available.get(o["unit"], np.ones(48, dtype=bool)) & av
            day.available[o["unit"].partition(" ")[0]] &= av
        shutil.rmtree(child)
        return day, {"kind": "missing_named_engine_component", "raw_exception": repr(exc)}


def load_app(name):
    if name in MODULES:
        return MODULES[name]
    package = "fuzz_app_" + name
    module_from_file(package, APPS[name] / "planner/__init__.py", package=True)
    data, plant, tariff, opt = [importlib.import_module(package + "." + n)
                               for n in ("data", "plant", "tariff", "optimize")]
    MODULES[name] = data, plant, tariff, opt
    return MODULES[name]


def rounded(x, digits):
    if isinstance(x, float):
        return round(x, digits)
    if isinstance(x, dict):
        return {k: rounded(v, digits) for k, v in x.items()}
    if isinstance(x, list):
        return [rounded(v, digits) for v in x]
    return x


def run_app(name, folder):
    data, plant, tariff, opt = load_app(name)
    day = data.load_day(folder)
    pp = plant.Plant(day.plant)
    tt = tariff.Tariff(day.supply, day.first_start if name == "v17_codex_parts" else day.date)
    periods, starts = opt.plan_day(day, pp, tt)
    summary = {"cost_gbp": sum(p["cost_gbp"] for p in periods),
               "gas_kwh": sum(p["gas_kwh"] for p in periods),
               "import_kwh": .5 * sum(p["import_kw"] for p in periods),
               "export_kwh": .5 * sum(p["export_kw"] for p in periods),
               "engine_starts": starts, "grid_ok": all(p["grid_ok"] for p in periods)}
    return rounded({"date": day.date.isoformat(), "periods": periods, "summary": summary},
                   9 if name == "v17_codex_parts" else 3)


def details(day, plan, flows):
    import numpy as np
    s = T.series
    elec = (sum(s(plan, "engines_kwe", e["id"]) for e in day.engines) + s(plan, "pv_kw")
            + s(plan, "import_kw") - s(plan, "export_kw") - day.elec - flows["aux"] - flows["ec_elec"])
    heat = (flows["engine_heat"] - flows["ac_heat"]
            + sum(s(plan, "boilers_kw", b["id"]) for b in day.plant["boilers"])
            - day.heat - day.lthw_loss)
    apparent = np.hypot(s(plan, "import_kw"), day.kvar - flows["engine_kvar"])
    return {"bad_availability_periods": np.where(~flows["running_ok"])[0].tolist(),
            "max_electric_balance_kw": float(abs(elec).max()),
            "max_heat_balance_kw": float(abs(heat).max()),
            "max_tower_excess_kw": float((flows["rejected"] - day.tower_max).max()),
            "max_grid_excess_kva": float((apparent - day.import_kva).max()),
            "recomputed_cost_gbp": float(flows["cost"].sum())}


def alarm_handler(*_):
    raise TimeoutError("app exceeded 120 seconds; excluded as a semantic trap")


def one(job):
    item, out, sample_every = job
    out = Path(out)
    folder = out / "days" / item["id"]
    B.write_day(folder, item["spec"])
    result = {k: item[k] for k in ("id", "index", "season", "scenario", "base")}
    result["input_problems"] = check_inputs(folder, item["spec"])
    result["expected_date"] = item["spec"]["date"]
    result["input_sha256"] = {n: hashlib.sha256((folder / n).read_bytes()).hexdigest()
                              for n in ("plant.json", "supply.json", "status.json", "demand.csv", "weather.csv")}
    result["apps"] = {}
    try:
        day, extension = reference_day(folder)
    except Exception as exc:
        return {**result, "reference_error": repr(exc)}
    result["reference_extension"] = extension
    plans, costs = {}, []
    signal.signal(signal.SIGALRM, alarm_handler)
    for name in APPS:
        start, stderr = time.monotonic(), io.StringIO()
        record = {"failed": []}
        try:
            signal.alarm(120)
            with contextlib.redirect_stderr(stderr):
                plan = run_app(name, folder)
            signal.alarm(0)
            flows = day.true_flows(plan)
            for check in CHECKS:
                try:
                    getattr(T, check)((day, plan, flows))
                except Exception as exc:
                    record["failed"].append(check)
                    record.setdefault("assertions", {})[check] = repr(exc)
            record.update(details(day, plan, flows))
            plans[name] = plan
            costs.append(record["recomputed_cost_gbp"])
        except Exception as exc:
            signal.alarm(0)
            record["exception"] = repr(exc)
        record["elapsed_seconds"] = round(time.monotonic() - start, 6)
        if stderr.getvalue():
            record["stderr"] = stderr.getvalue()[-2500:]
        result["apps"][name] = record
    physically_good = [n for n, r in result["apps"].items() if not r["failed"] and "exception" not in r]
    result["feasible_witnesses"] = physically_good
    suspicious = (len(physically_good) != len(APPS) or
                  bool(costs and max(costs) - min(costs) > max(.5, 2e-4 * min(costs))))
    scheduled_sample = ((item["index"] // 4) + item["index"] % 4) % sample_every == 0
    if suspicious or scheduled_sample:
        start = time.monotonic()
        try:
            best = day.least_cost()
            result["milp"] = {"cost_gbp": float(best["cost"]), "elapsed_seconds": time.monotonic() - start}
            for r in result["apps"].values():
                if "recomputed_cost_gbp" in r:
                    r["regret_gbp"] = r["recomputed_cost_gbp"] - best["cost"]
                    if r["regret_gbp"] > max(.5, 2e-4 * best["cost"]):
                        r["failed"].append("test_least_cost")
        except RuntimeError as exc:
            result["milp"] = {"exception": repr(exc), "elapsed_seconds": time.monotonic() - start}
    has_failure = any(r["failed"] or "exception" in r for r in result["apps"].values())
    if has_failure:
        for name, plan in plans.items():
            (folder / (name + ".plan.json")).write_text(json.dumps(plan, indent=1) + "\n")
        (folder / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    else:
        shutil.rmtree(folder)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=320)
    ap.add_argument("--seed", type=int, default=180017)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--sample-every", type=int, default=16)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--specs", type=Path)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    items = [json.loads(s) for s in args.specs.read_text().splitlines()] if args.specs else [
        draw(i, args.seed) for i in range(args.days)]
    for item in items:
        if "overrides" in item["spec"]:
            item["spec"]["overrides"] = {int(k): v for k, v in item["spec"]["overrides"].items()}
    (args.out / "specs.jsonl").write_text("".join(json.dumps(i, sort_keys=True) + "\n" for i in items))
    meta = {"seed": args.seed, "days": len(items), "python": sys.version, "workers": args.workers,
            "milp_sample_every": args.sample_every,
            "sample_rule": "((index // 4) + index % 4) % N == 0, plus every suspicious case",
            "reference": str(BASE.relative_to(ROOT)), "apps": {k: str(v.relative_to(ROOT)) for k, v in APPS.items()},
            "units": UNITS, "semantics": "original archived v17 except explicitly marked jacket/exhaust extension"}
    (args.out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    start, rows = time.monotonic(), []
    with (args.out / "results.jsonl").open("w") as stream, ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(one, (i, str(args.out), args.sample_every)) for i in items]
        for f in as_completed(futures):
            r = f.result()
            stream.write(json.dumps(r, sort_keys=True) + "\n")
            stream.flush()
            rows.append(r)
            fs = {n: a.get("exception", a["failed"]) for n, a in r.get("apps", {}).items()
                  if a["failed"] or "exception" in a}
            print(f"{len(rows)}/{len(items)} {r['id']} feasible={r.get('feasible_witnesses', [])} failures={fs}", flush=True)
    from collections import Counter
    summary = {**meta, "elapsed_seconds": time.monotonic() - start,
               "seasons": dict(Counter(r["season"] for r in rows)),
               "feasible_days": sum(bool(r.get("feasible_witnesses")) or "cost_gbp" in r.get("milp", {}) for r in rows),
               "reference_extended_days": sum(bool(r.get("reference_extension")) for r in rows),
               "milp_solved": sum("cost_gbp" in r.get("milp", {}) for r in rows),
               "milp_infeasible_or_error": sum("exception" in r.get("milp", {}) for r in rows),
               "app_failure_days": {n: sum(bool(r.get("apps", {}).get(n, {}).get("failed"))
                                           or "exception" in r.get("apps", {}).get(n, {}) for r in rows) for n in APPS}}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
