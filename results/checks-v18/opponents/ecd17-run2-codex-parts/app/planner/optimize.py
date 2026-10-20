"""Day-ahead dispatch with exact piecewise plant models and engine start costs.

For each engine commitment, enumerate adjacent part-load segments and the useful
condenser-water regimes. Each resulting problem is convex: linear balances
and a circular apparent-power limit. Supporting cuts enforce that circle to a
numerical tolerance, without replacing it by a fixed polygon. A dynamic program
then chooses the least-cost sequence of commitments, including midnight starts.
"""

from __future__ import annotations

import itertools
import math

import numpy as np
from scipy.optimize import linprog

from .data import DayData
from .plant import EngineSegment, Plant
from .tariff import Tariff

DT_H = 0.5
GRID_TOL = 1e-7  # kVA, also the stopping tolerance for supporting cuts


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _available(day: DayData, unit_id: str, hhmm: str) -> bool:
    """A constant half-hour output must be available throughout the half-hour."""
    start = _minutes(hhmm)
    for outage in day.status.get("outages", []):
        # A named component outage also disables its parent unit.
        if outage["unit"] != unit_id and not outage["unit"].startswith(unit_id + " "):
            continue
        lo, hi = _minutes(outage["from"]), _minutes(outage["to"])
        intervals = [(lo, hi)] if hi >= lo else [(lo, 1440), (0, hi)]
        if any(start < b and start + 30 > a for a, b in intervals):
            return False
    return True


def _circle_lp(c, bounds, a_eq, b_eq, a_ub, b_ub, grid_index, q_row, q_site, kva):
    """Global convex optimum, using LP lower bounds and adaptive circle tangents.

    Q_grid = q_site + q_row @ x. The cuts are necessary conditions for the
    true circle, so an LP optimum inside it is also a global optimum. Refining
    only at violated optima is substantially cheaper than a very fine polygon.
    """
    rows, rhs = list(a_ub), list(b_ub)

    def cut(p_direction, q_direction):
        row = q_direction * q_row.copy()
        row[grid_index] += p_direction
        rows.append(row)
        rhs.append(kva - q_direction * q_site)

    for theta in np.linspace(-math.pi, math.pi, 16, endpoint=False):
        cut(math.cos(theta), math.sin(theta))
    for _ in range(80):
        result = linprog(c, A_ub=np.array(rows), b_ub=np.array(rhs),
                         A_eq=np.array(a_eq) if len(a_eq) else None,
                         b_eq=np.array(b_eq) if len(a_eq) else None, bounds=bounds,
                         method="highs", options={"primal_feasibility_tolerance": 1e-9,
                                                  "dual_feasibility_tolerance": 1e-9})
        if result.status == 2:
            return None
        if not result.success:
            raise RuntimeError(f"dispatch LP failed: {result.message}")
        p = result.x[grid_index]
        q = q_site + q_row @ result.x
        apparent = math.hypot(p, q)
        if apparent <= kva + GRID_TOL:
            return result.x
        cut(p / apparent, q / apparent)
    raise RuntimeError("apparent-power constraint did not converge")


def _loading(day: DayData, plant: Plant, tariff: Tariff, t: int,
             segments: tuple[EngineSegment | None, ...], cewt: float):
    """One convex loading problem, with engine segments and water temperature fixed."""
    engines = [(e, s) for e, s in zip(plant.engines, segments) if s is not None]
    boilers, chillers, absorbers = plant.boilers, plant.electric_chillers, plant.absorption_chillers
    n_p, n_b, n_e, n_a = len(engines), len(boilers), len(chillers), len(absorbers)
    i_b, i_e, i_a = n_p, n_p + n_b, n_p + n_b + n_e
    i_pv, i_ht, i_grid, i_charge, i_power = range(i_a + n_a, i_a + n_a + 5)
    n = i_power + 1
    hhmm = day.starts[t]
    available = lambda unit: _available(day, unit, hhmm)
    c = np.zeros(n)
    bounds = [(0.0, 0.0)] * n
    q_row = np.zeros(n)
    for j, (e, s) in enumerate(engines):
        c[j] = DT_H * (tariff.billed_gas(s.fuel_slope, e.fuel_basis) * tariff.gas_rate
                        + e.maintenance)
        bounds[j] = (s.low, s.high)
        q_row[j] = -e.kvar_per_kw
    for j, b in enumerate(boilers):
        c[i_b + j] = DT_H * tariff.billed_gas(1.0 / b.efficiency, b.fuel_basis) * tariff.gas_rate
        bounds[i_b + j] = (0.0, b.max_kw if available(b.id) else 0.0)
    cops = [ch.cop(cewt) for ch in chillers]
    hot = max([cewt] + [ch.cop_flat_from_c for ch in chillers])
    hot_cops = [ch.cop(hot) for ch in chillers]
    for j, ch in enumerate(chillers):
        bounds[i_e + j] = (0.0, ch.max_kw if available(ch.id) else 0.0)
    for j, a in enumerate(absorbers):
        can_run = (available(a.id) and a.id in plant.ht_absorbers
                   and cewt >= a.cooling_water_in_min_c)
        bounds[i_a + j] = (0.0, a.max_kw if can_run else 0.0)
    bounds[i_pv] = (0.0, min(max(0.0, day.pv[t]), plant.pv_max_kw)
                    if available(plant.pv_id) else 0.0)
    heat_required = float(day.heat[t] + plant.lthw_loss_kw)
    bounds[i_ht] = (0.0, heat_required if any(available(hx) for hx in plant.heat_exchangers) else 0.0)
    bounds[i_grid] = (-tariff.export_limit_kw, tariff.import_capacity_kva)
    bounds[i_charge] = (None, None)
    bounds[i_power] = (0.0, None)
    c[i_charge] = DT_H

    a_eq, b_eq, a_ub, b_ub = [], [], [], []
    # Generation and signed grid exchange cover site and energy-centre electrical loads.
    row = np.zeros(n)
    row[:n_p] = 1.0
    row[i_pv] = row[i_grid] = 1.0
    row[i_power] = -1.0
    for j, a in enumerate(absorbers):
        row[i_a + j] = -a.aux_per_kw
    a_eq.append(row)
    b_eq.append(day.elec[t] + sum(e.aux_kwe for e, _ in engines))

    # The HT header has exactly two destinations: absorption generators and PHE1.
    row = np.zeros(n)
    for j, (_, s) in enumerate(engines):
        row[j] = s.ht_slope
    row[i_ht] = -1.0
    for j, a in enumerate(absorbers):
        row[i_a + j] = -1.0 / a.cop
    a_eq.append(row)
    b_eq.append(-sum(s.ht_at_zero for _, s in engines))
    # PHE1 and boilers supply the buildings and the specified distribution loss.
    row = np.zeros(n)
    row[i_ht] = 1.0
    row[i_b:i_b + n_b] = 1.0
    a_eq.append(row)
    b_eq.append(heat_required)

    row = np.zeros(n)
    row[i_e:i_e + n_e] = 1.0
    row[i_a:i_a + n_a] = 1.0
    a_eq.append(row)
    b_eq.append(day.cool[t])

    # All electric COP curves decrease continuously with common water temperature.
    # For fixed cooling outputs, their total electrical input therefore attains
    # EVERY value between these two linear endpoint expressions. This models fan
    # control exactly without a nonlinear temperature variable. In ordinary import
    # operation the minimum wins; warmer water can also absorb unavoidable generation
    # when the export limit and reactive demand require engines to remain running.
    row = np.zeros(n)
    for j, cop in enumerate(cops):
        row[i_e + j] = 1.0 / cop
    row[i_power] = -1.0
    a_ub.append(row)
    b_ub.append(0.0)
    row = np.zeros(n)
    for j, cop in enumerate(hot_cops):
        row[i_e + j] = -1.0 / cop
    row[i_power] = 1.0
    a_ub.append(row)
    b_ub.append(0.0)

    # Condensers reject the cooling duty PLUS compressor work or generator heat.
    row = np.zeros(n)
    row[i_e:i_e + n_e] = 1.0
    row[i_power] = 1.0
    for j, a in enumerate(absorbers):
        row[i_a + j] = 1.0 + 1.0 / a.cop
    a_ub.append(row)
    cells = sum(available(cell) for cell in plant.tower_cells)
    b_ub.append(plant.tower_capacity(day.wet_bulb[t], cells))

    # Convex tariff on SIGNED exchange precludes simultaneous import and export.
    import_rate = tariff.import_rate(hhmm)
    if import_rate < tariff.export_rate:
        raise ValueError("import rate must be at least the export rate")
    for rate in (import_rate, tariff.export_rate):
        row = np.zeros(n)
        row[i_grid], row[i_charge] = rate, -1.0
        a_ub.append(row)
        b_ub.append(0.0)

    x = _circle_lp(c, bounds, a_eq, b_eq, a_ub, b_ub, i_grid, q_row,
                   float(day.kvar[t]), tariff.import_capacity_kva)
    if x is None:
        return math.inf, None
    out = {
        "engines_kwe": {e.id: 0.0 for e in plant.engines},
        "boilers_kw": {b.id: max(0.0, float(x[i_b + j])) for j, b in enumerate(boilers)},
        "chillers_kw": {**{ch.id: max(0.0, float(x[i_e + j])) for j, ch in enumerate(chillers)},
                        **{a.id: max(0.0, float(x[i_a + j])) for j, a in enumerate(absorbers)}},
        "pv_kw": max(0.0, float(x[i_pv])),
        "import_kw": max(0.0, float(x[i_grid])),
        "export_kw": max(0.0, float(-x[i_grid])),
    }
    for j, (e, _) in enumerate(engines):
        out["engines_kwe"][e.id] = float(x[j])
    # Recalculate metered fuel and the bill from the dispatch, using all table points.
    gas = sum(tariff.billed_gas(e.fuel(out["engines_kwe"][e.id]), e.fuel_basis)
              for e in plant.engines)
    gas += sum(tariff.billed_gas(b.fuel(out["boilers_kw"][b.id]), b.fuel_basis)
               for b in boilers)
    out["gas_kwh"] = DT_H * gas
    maintenance = sum(e.maintenance * out["engines_kwe"][e.id] for e in plant.engines)
    cost = (out["gas_kwh"] * tariff.gas_rate
            + DT_H * (out["import_kw"] * import_rate - out["export_kw"] * tariff.export_rate
                      + maintenance))
    out["cost_gbp"] = cost
    net_q = day.kvar[t] - sum(e.kvar_per_kw * out["engines_kwe"][e.id] for e in plant.engines)
    out["grid_ok"] = bool(math.hypot(out["import_kw"] - out["export_kw"], net_q)
                          <= tariff.import_capacity_kva + 2 * GRID_TOL
                          and out["export_kw"] <= tariff.export_limit_kw + GRID_TOL)
    return cost, out


def _period(day: DayData, plant: Plant, tariff: Tariff, t: int, on: tuple[bool, ...]):
    """Cheapest feasible loading for one commitment, including every curve segment."""
    hhmm = day.starts[t]
    for e, running in zip(plant.engines, on):
        if running and (not _available(day, e.id, hhmm)
                        or any(not _available(day, radiator, hhmm)
                               for radiator in plant.lt_radiators[e.id])):
            return math.inf, None
    base_temp = plant.condenser_entering(day.wet_bulb[t])
    # Slower tower fans can satisfy the absorption chiller's minimum inlet temperature.
    # Each threshold admits another absorber. Within each regime the electric
    # chillers' total power spans the full attainable water-temperature range.
    temperatures = sorted({base_temp} | {
        max(base_temp, a.cooling_water_in_min_c) for a in plant.absorption_chillers
        if a.id in plant.ht_absorbers and _available(day, a.id, hhmm)
    })
    choices = [e.segments if running else [None] for e, running in zip(plant.engines, on)]
    best_cost, best = math.inf, None
    for segments in itertools.product(*choices):
        for temp in temperatures:
            cost, loading = _loading(day, plant, tariff, t, segments, temp)
            if cost < best_cost:
                best_cost, best = cost, loading
    return best_cost, best


def plan_day(day: DayData, plant: Plant, tariff: Tariff) -> tuple[list[dict], int]:
    combos = list(itertools.product((False, True), repeat=len(plant.engines)))
    midnight = tuple(e.id in day.status.get("running_at_midnight", []) for e in plant.engines)
    previous_cost = {midnight: 0.0}
    backtrack, loadings = [], []
    for t in range(len(day.starts)):
        costs, parents, dispatches = {}, {}, {}
        for on in combos:
            operating_cost, loading = _period(day, plant, tariff, t, on)
            if loading is None:
                continue
            best_cost, best_prev = math.inf, None
            for prev, prev_cost in previous_cost.items():
                starts_cost = sum(e.start_cost for e, was_on, now_on in zip(plant.engines, prev, on)
                                  if now_on and not was_on)
                cost = prev_cost + operating_cost + starts_cost
                if cost < best_cost:
                    best_cost, best_prev = cost, prev
            costs[on], parents[on], dispatches[on] = best_cost, best_prev, loading
        if not costs:
            raise RuntimeError(f"no feasible loading at {day.starts[t]}")
        previous_cost = costs
        backtrack.append(parents)
        loadings.append(dispatches)

    on = min(previous_cost, key=previous_cost.get)
    sequence = []
    for t in reversed(range(len(day.starts))):
        sequence.append(on)
        on = backtrack[t][on]
    sequence.reverse()
    periods, starts, prev = [], 0, midnight
    for t, on in enumerate(sequence):
        loading = loadings[t][on]
        started = [e for e, was_on, now_on in zip(plant.engines, prev, on) if now_on and not was_on]
        starts += len(started)
        loading["cost_gbp"] += sum(e.start_cost for e in started)
        periods.append({"start": day.starts[t], **loading})
        prev = on
    return periods, starts
