"""Local-clock tariffs, calorific-value conversions and the gas-entry rating."""

from __future__ import annotations

from datetime import datetime
import math


def minutes(hhmm: str) -> int:
    h, m = (int(x) for x in hhmm.split(":"))
    if not (0 <= h <= 24 and 0 <= m < 60 and (h < 24 or m == 0)):
        raise ValueError(f"invalid local clock time: {hhmm}")
    return 60 * h + m


class Tariff:
    def __init__(self, supply: dict, day_start: datetime):
        el = supply["electricity"]
        self.weekend = day_start.weekday() >= 5
        self._bands = el["import_rates_p_per_kwh"]["weekend" if self.weekend else "weekday"]
        self.export_rate = float(el["export_rate_p_per_kwh"]) / 100.0
        self.import_capacity_kva = float(el["import_capacity_kva"])
        self.export_limit_kw = float(el["export_limit_kw"])
        gas = supply["gas"]
        self.gas_rate = float(gas["rate_p_per_kwh"]) / 100.0
        self.gas_basis = gas["billing_basis"]
        self.gross_per_net = float(gas["gross_to_net_cv_ratio"])
        if self.gross_per_net <= 0 or self.import_capacity_kva <= 0 or self.export_limit_kw < 0:
            raise ValueError("invalid electricity capacity or calorific-value ratio")
        self.gas_entry = gas.get("entry")
        self.gas_entry_units = set(self.gas_entry["supplies"]) if self.gas_entry else set()
        # Both volume and CV refer to the stated standard conditions.
        # MJ/h divided by 3.6 gives kWh/h: an instantaneous gross-CV limit.
        self.gas_entry_gross_kw = (
            float(self.gas_entry["maximum_standard_m3_per_hour"])
            * float(self.gas_entry["gross_calorific_value_mj_per_standard_m3"]) / 3.6
            if self.gas_entry else math.inf
        )
        if self.gas_entry_gross_kw < 0:
            raise ValueError("invalid gas-entry capacity")
        for band in self._bands:
            if float(band["rate"]) / 100 < self.export_rate:
                raise ValueError("import tariff must be no less than the export tariff")

    def import_rate(self, hhmm: str) -> float:
        minute = minutes(hhmm)
        matches = []
        for band in self._bands:
            begin, end = minutes(band["from"]), minutes(band["to"])
            if ((begin <= minute < end) if begin <= end else (minute >= begin or minute < end)):
                matches.append(float(band["rate"]) / 100.0)
        if len(matches) != 1:
            raise ValueError(f"expected one import rate at {hhmm}; found {len(matches)}")
        return matches[0]

    def convert_gas(self, kw: float, source: str, target: str) -> float:
        if source == target:
            return float(kw)
        if source == "net CV" and target == "gross CV":
            return float(kw) * self.gross_per_net
        if source == "gross CV" and target == "net CV":
            return float(kw) / self.gross_per_net
        raise ValueError(f"cannot convert {source!r} to {target!r}")

    def billed_gas(self, kw: float, basis: str) -> float:
        return self.convert_gas(kw, basis, self.gas_basis)

    def gross_gas(self, kw: float, basis: str) -> float:
        return self.convert_gas(kw, basis, "gross CV")
