"""Days that took no part in building or tuning the task (development tool).

Draws days at random (seeded): a date of 2026 without a clock change, in winter, in spring or
autumn and in summer twice in turn, the demand and weather profiles of the task's day of that
season scaled and shifted, the engines running at
midnight, and one to four planned outages of any item that plant.json names, at times off the
half-hour. A day is kept only if its inputs pass checks against the plant's data (ratings,
names, times, a full day of half-hours) and a plan meets it (the reference MILP solves); the
task's own five days are put through the same checks first. Each tool given is then run twice
on every kept day and judged by the task's own tests.

Usage: python tools/fresh_days.py [--days 8] [--seed 2026] <app_root> [<app_root> ...]
The days are written to tools/out/fresh/tests/days/.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tasks" / "energy-centre-dispatch"
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(TASK / "tests"))
import build_energy_days as B  # noqa: E402
import eval_energy as E  # noqa: E402
from reference import Day  # noqa: E402

UNITS = ["GE1", "GE2", "B1", "B2", "EC1", "EC2", "AC1", "PHE1", "GE1 LT radiator", "GE2 LT radiator",
         "CT1", "CT2", "PV1"]


def last_sunday(year: int, month: int) -> date:
    d = date(year, month + 1, 1) - timedelta(days=1)
    while d.weekday() != 6:
        d -= timedelta(days=1)
    return d


SEASONS = [("h2", (12, 1, 2)), ("h3", (3, 4, 5, 10, 11)), ("summer", (6, 7, 8, 9)), ("summer", (6, 7, 8, 9))]


def draw(rng: random.Random, season: tuple[str, tuple[int, ...]]) -> tuple[dict, str]:
    summer_from, summer_to = last_sunday(2026, 3), last_sunday(2026, 10)
    d = summer_from
    while d in (summer_from, summer_to) or d.month not in season[1]:
        d = date(2026, 1, 1) + timedelta(days=rng.randrange(365))
    base = rng.choice(["visible", "h1", "h4"]) if season[0] == "summer" else season[0]
    b = B.DAYS[base]
    fe, fh, fc, dt = rng.uniform(0.92, 1.08), rng.uniform(0.85, 1.15), rng.uniform(0.85, 1.15), rng.uniform(-2, 2)
    outages = []
    for unit in rng.sample(UNITS, rng.randint(1, 4)):
        a = rng.randrange(0, 1380, 10)
        z = min(1440, a + rng.randrange(60, 370, 10))
        outages.append({"unit": unit, "from": f"{a // 60:02d}:{a % 60:02d}", "to": f"{z // 60:02d}:{z % 60:02d}"})
    spec = dict(
        date=d.isoformat(), offset=1 if summer_from < d < summer_to else 0, seed=rng.randrange(10**6),
        elec=[(h, v * fe) for h, v in b["elec"]], heat=[(h, v * fh) for h, v in b["heat"]],
        cool=[(h, v * fc) for h, v in b["cool"]],
        dry=[(h, v + dt) for h, v in b["dry"]], wet=[(h, v + dt) for h, v in b["wet"]],
        sun=b["sun"], pv_peak=min(b["pv_peak"] * rng.uniform(0.8, 1.1), B.PLANT["pv"]["inverter_ac_kw"]),
        cloud=rng.uniform(0.0, 0.3),
        status={"running_at_midnight": [e for e in ("GE1", "GE2") if rng.random() < 0.5], "outages": outages},
    )
    return spec, base


def check_inputs(folder: Path) -> list[str]:
    """What is wrong with a day's input files, judged against its plant and supply files."""
    problems = []
    plant = json.loads((folder / "plant.json").read_text())
    if plant != B.PLANT or json.loads((folder / "supply.json").read_text()) != B.SUPPLY:
        problems.append("plant.json or supply.json differ from the task's")
    names = {u["id"] for k in ("engines", "boilers", "electric_chillers", "absorption_chillers") for u in plant[k]}
    names |= set(plant["cooling_towers"]["cells"]) | {plant["pv"]["id"]}
    names |= {x for c in plant["heat_circuits"].values() for x in c["from"] + c["to"]}
    status = json.loads((folder / "status.json").read_text())
    if not set(status["running_at_midnight"]) <= {e["id"] for e in plant["engines"]}:
        problems.append("running_at_midnight names a unit that is not an engine")

    def minutes(hhmm: str) -> int:
        h, m = hhmm.split(":")
        return int(h) * 60 + int(m)

    for o in status["outages"]:
        if o["unit"] not in names:
            problems.append(f"outage of {o['unit']!r}, which plant.json does not name")
        if not 0 <= minutes(o["from"]) < minutes(o["to"]) <= 1440:
            problems.append(f"outage of {o['unit']} from {o['from']} to {o['to']}")
    demand = list(csv.DictReader(open(folder / "demand.csv")))
    starts = [r["period_start"] for r in demand]
    if len(demand) != 48 or len({s[-6:] for s in starts}) != 1 or not starts[0].startswith(status["date"] + "T00:00"):
        problems.append("demand.csv is not 48 half-hours of the plan date at one UTC offset")
    if any(float(v) < 0 for r in demand for k, v in r.items() if k != "period_start"):
        problems.append("negative demand")
    weather = list(csv.DictReader(open(folder / "weather.csv")))
    inverter = plant["pv"]["inverter_ac_kw"]
    if any(not 0.0 <= float(r["pv_kw"]) <= inverter for r in weather):
        problems.append(f"PV forecast outside 0 to {inverter} kW (the inverter's rating)")
    if any(float(r["wet_bulb_c"]) > float(r["dry_bulb_c"]) for r in weather):
        problems.append("wet bulb above dry bulb")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=8)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("apps", nargs="+")
    args = ap.parse_args()
    rng = random.Random(args.seed)
    out = ROOT / "tools" / "out" / "fresh"
    shutil.rmtree(out, ignore_errors=True)
    for d in ["visible", "h1", "h2", "h3", "h4"]:
        problems = check_inputs(TASK / "tests" / "days" / d)
        assert not problems, (d, problems)
    print("the task's five days pass the input checks")
    names: list[str] = []
    while len(names) < args.days:
        spec, base = draw(rng, SEASONS[len(names) % len(SEASONS)])
        name = f"f{len(names) + 1}"
        folder = out / "tests" / "days" / name
        B.write_day(folder, spec)
        problems = check_inputs(folder)
        if problems:
            print(f"discarded a drawn day: {'; '.join(problems)}")
            shutil.rmtree(folder)
            continue
        try:
            Day(folder).least_cost()
        except RuntimeError:
            shutil.rmtree(folder)
            continue
        names.append(name)
        st = spec["status"]
        print(f"{name}: {spec['date']} {date.fromisoformat(spec['date']):%a} ({base} profile), running at midnight "
              f"{st['running_at_midnight']}, outages " + ", ".join(f"{o['unit']} {o['from']}-{o['to']}" for o in st["outages"]))
    tests = (TASK / "tests" / "test_plans.py").read_text()
    days_line = 'DAYS = ["visible", "h1", "h2", "h3", "h4"]'
    assert tests.count(days_line) == 1
    (out / "tests" / "test_plans.py").write_text(tests.replace(days_line, f"DAYS = {names!r}"))
    shutil.copy(TASK / "tests" / "reference.py", out / "tests" / "reference.py")
    E.TASK, E.DAYS = out, names
    for app in args.apps:
        r = E.evaluate(Path(app).resolve(), quiet=True)
        bad = sorted({d for days in r["failed"].values() for d in days}, key=lambda n: int(n[1:]))
        fails = "; ".join(f"{k.replace('test_', '')}:{','.join(v)}" for k, v in sorted(r["failed"].items()))
        print(f"{len(bad)}/{len(names)} days failed  {app}  {fails}", flush=True)


if __name__ == "__main__":
    main()
