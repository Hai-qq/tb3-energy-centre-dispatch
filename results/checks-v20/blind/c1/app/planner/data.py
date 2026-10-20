"""Read a complete local day and join its forecast by absolute start time."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np


@dataclass
class DayData:
    date: date
    plant: dict
    supply: dict
    status: dict
    starts: list[str]
    first_start: datetime
    elec: np.ndarray
    kvar: np.ndarray
    heat: np.ndarray
    cool: np.ndarray
    dry_bulb: np.ndarray
    wet_bulb: np.ndarray
    pv: np.ndarray


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _timestamp(value: str, source: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.utcoffset() is None:
        raise ValueError(f"{source}: timestamp needs a UTC offset: {value}")
    return result


def _numbers(rows: list[dict], key: str, *, nonnegative: bool = False) -> np.ndarray:
    values = np.asarray([float(row[key]) for row in rows], dtype=float)
    if not np.all(np.isfinite(values)):
        raise ValueError(f"{key}: values must be finite")
    if nonnegative and np.any(values < 0):
        raise ValueError(f"{key}: values must be nonnegative")
    return values


def load_day(folder: Path) -> DayData:
    folder = Path(folder)
    plant = json.loads((folder / "plant.json").read_text())
    supply = json.loads((folder / "supply.json").read_text())
    status = json.loads((folder / "status.json").read_text())
    plan_date = date.fromisoformat(status["date"])

    pairs = [(_timestamp(row["period_start"], "demand.csv"), row)
             for row in _read_csv(folder / "demand.csv")]
    pairs.sort(key=lambda pair: pair[0])
    if len(pairs) != 48:
        raise ValueError(f"demand.csv: expected 48 half-hours, found {len(pairs)}")
    first = pairs[0][0]
    if first.date() != plan_date or first.hour or first.minute or first.second or first.microsecond:
        raise ValueError("demand.csv must begin at local midnight of status.json's date")
    offset = first.utcoffset()
    for t, (stamp, _) in enumerate(pairs):
        expected = first + timedelta(minutes=30 * t)
        if (stamp.date() != plan_date or stamp.utcoffset() != offset
                or stamp != expected or stamp.second or stamp.microsecond):
            raise ValueError(f"demand.csv: missing, repeated or invalid local half-hour {expected.isoformat()}")
    demand = [row for _, row in pairs]

    # A local summer day includes some UTC times on the previous date. Neither
    # CSV order nor a UTC calendar-date filter identifies the matching forecast.
    wanted = {stamp.astimezone(timezone.utc) for stamp, _ in pairs}
    forecast = {}
    for row in _read_csv(folder / "weather.csv"):
        stamp = _timestamp(row["time_utc"], "weather.csv").astimezone(timezone.utc)
        if stamp in wanted:
            if stamp in forecast:
                raise ValueError(f"weather.csv: duplicate forecast at {stamp.isoformat()}")
            forecast[stamp] = row
    missing = sorted(wanted - forecast.keys())
    if missing:
        raise ValueError(f"weather.csv: no forecast for {missing[0].isoformat()}")
    weather = [forecast[stamp.astimezone(timezone.utc)] for stamp, _ in pairs]

    return DayData(
        date=plan_date,
        plant=plant,
        supply=supply,
        status=status,
        starts=[stamp.strftime("%H:%M") for stamp, _ in pairs],
        first_start=first,
        elec=_numbers(demand, "electricity_kw", nonnegative=True),
        kvar=_numbers(demand, "reactive_kvar"),
        heat=_numbers(demand, "heat_kw", nonnegative=True),
        cool=_numbers(demand, "cooling_kw", nonnegative=True),
        dry_bulb=_numbers(weather, "dry_bulb_c"),
        wet_bulb=_numbers(weather, "wet_bulb_c"),
        pv=_numbers(weather, "pv_kw", nonnegative=True),
    )
