"""Data for the energy-centre-dispatch task (development tool).

Writes the shared plant and supply files and each day's status, demand and weather
files: the visible day into environment/data and the verifier's days into tests/days.

Usage: python tools/build_energy_days.py [--task tasks/energy-centre-dispatch]
"""

from __future__ import annotations

import argparse
import json
import math
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PLANT = {
    "engines": [
        {"id": "GE1", "rated_kwe": 1200,
         "part_load": [{"kwe": 600, "fuel_kw": 1705, "ht_heat_kw": 835, "lt_heat_kw": 118},
                       {"kwe": 900, "fuel_kw": 2275, "ht_heat_kw": 1110, "lt_heat_kw": 158},
                       {"kwe": 1200, "fuel_kw": 2870, "ht_heat_kw": 1290, "lt_heat_kw": 201}],
         "fuel_basis": "net CV",
         "generator": {"rated_kva": 1500, "power_factor": 0.95, "control": "fixed power factor, overexcited"},
         "auxiliary_kwe": 32, "maintenance_gbp_per_mwhe": 11.0, "start_cost_gbp": 38.0},
        {"id": "GE2", "rated_kwe": 800,
         "part_load": [{"kwe": 400, "fuel_kw": 1180, "ht_heat_kw": 590, "lt_heat_kw": 83},
                       {"kwe": 600, "fuel_kw": 1570, "ht_heat_kw": 780, "lt_heat_kw": 110},
                       {"kwe": 800, "fuel_kw": 1990, "ht_heat_kw": 900, "lt_heat_kw": 139}],
         "fuel_basis": "net CV",
         "generator": {"rated_kva": 1000, "power_factor": 0.95, "control": "fixed power factor, overexcited"},
         "auxiliary_kwe": 24, "maintenance_gbp_per_mwhe": 12.5, "start_cost_gbp": 27.0},
    ],
    "boilers": [
        {"id": "B1", "max_kw": 2000, "efficiency": 0.905, "efficiency_basis": "gross CV"},
        {"id": "B2", "max_kw": 2000, "efficiency": 0.83, "efficiency_basis": "gross CV"},
    ],
    "electric_chillers": [
        {"id": "EC1", "max_kw": 1400,
         "cop_by_condenser_entering_c": [[18, 7.4], [22, 6.5], [26, 5.6], [30, 4.7], [34, 3.9]]},
        {"id": "EC2", "max_kw": 1000,
         "cop_by_condenser_entering_c": [[18, 5.8], [22, 5.2], [26, 4.6], [30, 4.0], [34, 3.4]]},
    ],
    "absorption_chillers": [
        {"id": "AC1", "max_kw": 800, "cop": 0.71, "auxiliary_kwe_per_kw": 0.022, "hot_water_in_min_c": 85},
    ],
    "cooling_towers": {"approach_k": 4.0, "min_leaving_water_c": 21.0,
                       "heat_rejection_kw_by_wet_bulb_c": [[14, 4000], [18, 3500], [22, 2850]]},
    "heat_circuits": {
        "engine_ht": {"flow_c": 90, "return_c": 70,
                      "from": ["GE1 jacket water and exhaust", "GE2 jacket water and exhaust"],
                      "to": ["AC1 generator", "PHE1"]},
        "engine_lt": {"flow_c": 40, "return_c": 35,
                      "from": ["GE1 intercooler", "GE2 intercooler"],
                      "to": ["GE1 LT radiator", "GE2 LT radiator"]},
        "lthw": {"flow_c": 80, "return_c": 60, "from": ["PHE1", "B1", "B2"], "to": ["hospital buildings"],
                 "loss_kw": 75},
    },
    "pv": {"inverter_ac_kw": 280},
}

SUPPLY = {
    "electricity": {
        "import_capacity_kva": 1220,
        "export_limit_kw": 250,
        "import_rates_p_per_kwh": {
            "weekday": [
                {"from": "00:00", "to": "07:00", "rate": 13.8},
                {"from": "07:00", "to": "16:00", "rate": 22.6},
                {"from": "16:00", "to": "19:00", "rate": 41.5},
                {"from": "19:00", "to": "24:00", "rate": 22.6},
            ],
            "weekend": [
                {"from": "00:00", "to": "07:00", "rate": 13.8},
                {"from": "07:00", "to": "24:00", "rate": 22.6},
            ],
        },
        "export_rate_p_per_kwh": 5.9,
    },
    "gas": {"rate_p_per_kwh": 4.35, "billing_basis": "gross CV", "gross_to_net_cv_ratio": 1.108},
}


def interp_hourly(points: list[tuple[float, float]], h: float) -> float:
    """Piecewise-linear profile through (hour, value) points, wrapping at 24 h."""
    pts = sorted(points)
    pts = [(pts[-1][0] - 24, pts[-1][1])] + pts + [(pts[0][0] + 24, pts[0][1])]
    for (h0, v0), (h1, v1) in zip(pts, pts[1:]):
        if h0 <= h <= h1:
            return v0 + (v1 - v0) * (h - h0) / (h1 - h0)
    raise ValueError(h)


# day specs: local date, UTC offset (hours), demand profiles (hour, kW), weather profiles, status
DAYS = {
    "visible": dict(
        date="2026-07-21", offset=1, seed=11,
        elec=[(0, 1260), (5, 1230), (7, 1480), (9, 1780), (12, 1830), (15, 1850), (17, 1780), (20, 1540), (23, 1320)],
        heat=[(0, 250), (4, 240), (6, 470), (8, 520), (10, 360), (14, 300), (18, 380), (21, 420), (23, 280)],
        cool=[(0, 460), (5, 420), (8, 800), (11, 1350), (14, 1700), (16, 1780), (18, 1550), (21, 950), (23, 600)],
        dry=[(0, 15.5), (5, 13.8), (9, 19.5), (13, 24.5), (15, 26.0), (17, 25.2), (20, 21.5), (23, 17.5)],
        wet=[(0, 13.0), (5, 12.2), (9, 14.8), (13, 16.8), (15, 17.6), (17, 17.4), (20, 15.9), (23, 14.0)],
        sun=(5.0, 21.0), pv_peak=268, cloud=0.03,
        status={"running_at_midnight": ["GE1"], "outages": [{"unit": "GE1", "from": "07:00", "to": "11:00"},
                                                          {"unit": "B2", "from": "00:00", "to": "24:00"}]},
    ),
    "h1": dict(
        date="2026-08-08", offset=1, seed=12,
        elec=[(0, 1250), (5, 1220), (8, 1450), (11, 1820), (13, 1950), (14, 1965), (15, 1915), (16, 1830), (16.5, 1790), (18, 1780), (20, 1500), (23, 1300)],
        heat=[(0, 230), (5, 220), (7, 430), (9, 400), (12, 290), (17, 300), (20, 360), (23, 250)],
        cool=[(0, 520), (6, 480), (10, 1300), (13, 1950), (16, 2150), (18, 2050), (20, 1600), (22, 900), (23, 650)],
        dry=[(0, 17.5), (5, 15.8), (9, 22.0), (13, 28.5), (16, 30.2), (19, 27.0), (23, 19.5)],
        wet=[(0, 14.6), (5, 13.8), (9, 17.0), (13, 19.8), (16, 20.8), (19, 19.8), (23, 15.8)],
        sun=(5.5, 20.5), pv_peak=262, cloud=0.08,
        status={"running_at_midnight": ["GE1", "GE2"], "outages": [{"unit": "GE1", "from": "11:20", "to": "17:00"}]},
    ),
    "h2": dict(
        date="2026-01-14", offset=0, seed=13,
        elec=[(0, 1300), (5, 1280), (7, 1560), (9, 1950), (12, 1990), (16, 2050), (18, 2010), (21, 1650), (23, 1400)],
        heat=[(0, 2250), (4, 2350), (6, 3150), (8, 3300), (11, 2800), (15, 2650), (18, 2950), (21, 2700), (23, 2400)],
        cool=[(0, 190), (8, 230), (13, 270), (18, 240), (23, 200)],
        dry=[(0, 2.5), (6, 1.4), (10, 4.0), (14, 6.2), (18, 4.6), (23, 3.0)],
        wet=[(0, 1.6), (6, 0.8), (10, 2.7), (14, 4.1), (18, 3.3), (23, 2.1)],
        sun=(8.2, 16.2), pv_peak=120, cloud=0.25,
        status={"running_at_midnight": ["GE1", "GE2"], "outages": [{"unit": "GE2", "from": "12:45", "to": "17:00"},
                                                                 {"unit": "B1", "from": "06:10", "to": "08:40"}]},
    ),
    "h3": dict(
        date="2026-04-20", offset=1, seed=14,
        elec=[(0, 1220), (5, 1200), (7, 1450), (9, 1780), (12, 1820), (16, 1800), (19, 1600), (22, 1350)],
        heat=[(0, 900), (4, 980), (6, 1550), (8, 1500), (11, 980), (14, 820), (17, 1000), (20, 1150), (23, 950)],
        cool=[(0, 320), (7, 360), (10, 700), (13, 1020), (15, 1100), (18, 850), (21, 480), (23, 360)],
        dry=[(0, 8.5), (5, 7.0), (9, 11.5), (13, 16.0), (16, 17.2), (19, 14.0), (23, 10.0)],
        wet=[(0, 7.0), (5, 6.0), (9, 9.0), (13, 11.6), (16, 12.2), (19, 10.8), (23, 8.0)],
        sun=(6.0, 20.0), pv_peak=245, cloud=0.2,
        status={"running_at_midnight": [], "outages": [{"unit": "GE2 LT radiator", "from": "10:40", "to": "14:20"},
                                                     {"unit": "EC1", "from": "13:40", "to": "16:20"}]},
    ),
    "h4": dict(
        date="2026-07-29", offset=1, seed=15,
        elec=[(0, 1300), (5, 1270), (7, 1520), (9, 1880), (12, 1960), (15, 2000), (17, 1930), (20, 1650), (23, 1380)],
        heat=[(0, 240), (4, 230), (6, 450), (8, 500), (10, 340), (14, 280), (18, 360), (21, 400), (23, 270)],
        cool=[(0, 700), (5, 640), (8, 1050), (11, 1600), (14, 1900), (16, 1960), (18, 1850), (21, 1300), (23, 900)],
        dry=[(0, 21.0), (5, 19.0), (9, 25.5), (13, 31.0), (15, 33.0), (17, 32.0), (20, 27.5), (23, 23.0)],
        wet=[(0, 16.8), (5, 16.0), (9, 18.6), (13, 20.6), (15, 21.3), (17, 21.0), (20, 19.5), (23, 17.6)],
        sun=(5.2, 20.8), pv_peak=255, cloud=0.05,
        status={"running_at_midnight": ["GE1"], "outages": [{"unit": "PHE1", "from": "06:20", "to": "09:40"},
                                                          {"unit": "EC2", "from": "10:10", "to": "11:50"}]},
    ),
}


def write_day(folder: Path, spec: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    rng = random.Random(spec["seed"])
    d = date.fromisoformat(spec["date"])
    tz = timezone(timedelta(hours=spec["offset"]))
    (folder / "plant.json").write_text(json.dumps(PLANT, indent=2) + "\n")
    (folder / "supply.json").write_text(json.dumps(SUPPLY, indent=2) + "\n")
    (folder / "status.json").write_text(json.dumps({"date": spec["date"], **spec["status"]}, indent=2) + "\n")

    lines = ["period_start,electricity_kw,reactive_kvar,heat_kw,cooling_kw"]
    for t in range(48):
        h = t / 2 + 0.25
        start = datetime(d.year, d.month, d.day, t // 2, 30 * (t % 2), tzinfo=tz)
        e = interp_hourly(spec["elec"], h) * (1 + rng.uniform(-0.015, 0.015))
        q = interp_hourly(spec["heat"], h) * (1 + rng.uniform(-0.03, 0.03))
        c = interp_hourly(spec["cool"], h) * (1 + rng.uniform(-0.03, 0.03))
        r = e * spec.get("kvar_per_kw", 0.17) * (1 + rng.uniform(-0.04, 0.04))
        lines.append(f"{start.isoformat(timespec='minutes')},{e:.1f},{r:.1f},{q:.1f},{c:.1f}")
    (folder / "demand.csv").write_text("\n".join(lines) + "\n")

    # forecast run issued 12:00 UTC the day before, 48 hours of half-hour averages
    run = datetime(d.year, d.month, d.day, 12, tzinfo=timezone.utc) - timedelta(days=1)
    lines = ["time_utc,dry_bulb_c,wet_bulb_c,pv_kw"]
    sr, ss = spec["sun"]  # local solar day (hours, local clock)
    for i in range(96):
        tu = run + timedelta(minutes=30 * i)
        hl = ((tu + timedelta(hours=spec["offset"])).hour + (tu.minute + 15) / 60) % 24
        db = interp_hourly(spec["dry"], hl) + rng.uniform(-0.3, 0.3)
        wb = min(db - 0.3, interp_hourly(spec["wet"], hl) + rng.uniform(-0.2, 0.2))
        if sr < hl < ss:
            x = math.sin(math.pi * (hl - sr) / (ss - sr))
            pv = spec["pv_peak"] * x ** 1.3 * (1 - spec["cloud"] * rng.random())
        else:
            pv = 0.0
        lines.append(f"{tu.strftime('%Y-%m-%dT%H:%MZ')},{db:.1f},{wb:.1f},{pv:.1f}")
    (folder / "weather.csv").write_text("\n".join(lines) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default=str(ROOT / "tasks" / "energy-centre-dispatch"))
    args = ap.parse_args()
    task = Path(args.task)
    for name, spec in DAYS.items():
        folder = task / "environment" / "data" if name == "visible" else task / "tests" / "days" / name
        write_day(folder, spec)
        print("wrote", folder)


if __name__ == "__main__":
    main()
