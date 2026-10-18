"""Read and align a complete, local, 48-period operating day."""

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


def _timestamp(value: str, description: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid {description}: {value!r}") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{description} must include its UTC offset: {value!r}")
    return dt


def _values(rows: list[dict], name: str, nonnegative: bool = False) -> np.ndarray:
    values = np.asarray([float(row[name]) for row in rows], dtype=float)
    if not np.all(np.isfinite(values)):
        raise ValueError(f"{name} contains a non-finite number")
    if nonnegative and np.any(values < 0):
        raise ValueError(f"{name} must not be negative")
    return values


def load_day(folder: Path) -> DayData:
    plant = json.loads((folder / "plant.json").read_text())
    supply = json.loads((folder / "supply.json").read_text())
    status = json.loads((folder / "status.json").read_text())
    plan_date = date.fromisoformat(status["date"])

    dated_demand = [(_timestamp(r["period_start"], "demand period"), r)
                    for r in _read_csv(folder / "demand.csv")]
    dated_demand.sort(key=lambda item: item[0])
    if len(dated_demand) != 48:
        raise ValueError(f"demand has {len(dated_demand)} periods; a day requires 48")
    first = dated_demand[0][0]
    midnight = first.replace(hour=0, minute=0, second=0, microsecond=0)
    if first.date() != plan_date:
        raise ValueError("demand date does not match status.json")
    for index, (dt, _) in enumerate(dated_demand):
        expected = midnight + timedelta(minutes=30 * index)
        if (dt.date() != plan_date or dt.utcoffset() != first.utcoffset()
                or dt != expected or dt.hour != expected.hour or dt.minute != expected.minute):
            raise ValueError("demand must contain every local half-hour once, without a clock change")

    weather = {}
    for row in _read_csv(folder / "weather.csv"):
        instant = _timestamp(row["time_utc"], "weather time").astimezone(timezone.utc)
        if instant in weather:
            raise ValueError(f"duplicate weather forecast time: {instant.isoformat()}")
        weather[instant] = row
    wx = []
    for dt, _ in dated_demand:
        instant = dt.astimezone(timezone.utc)
        if instant not in weather:
            raise ValueError(f"missing weather forecast for {dt.isoformat()} ({instant.isoformat()})")
        wx.append(weather[instant])
    demand = [row for _, row in dated_demand]
    return DayData(
        date=plan_date, plant=plant, supply=supply, status=status,
        starts=[dt.strftime("%H:%M") for dt, _ in dated_demand], first_start=first,
        elec=_values(demand, "electricity_kw", True),
        kvar=_values(demand, "reactive_kvar"),
        heat=_values(demand, "heat_kw", True),
        cool=_values(demand, "cooling_kw", True),
        dry_bulb=_values(wx, "dry_bulb_c"), wet_bulb=_values(wx, "wet_bulb_c"),
        pv=_values(wx, "pv_kw", True),
    )
