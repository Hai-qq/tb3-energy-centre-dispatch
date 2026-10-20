"""Globally least-cost day-ahead dispatch.

For each engine commitment, enumerate its actual performance-table segments and
both directions of metered electricity exchange. Each remaining problem is a
linear program with one convex apparent-power constraint. Supporting cuts solve
that constraint to numerical precision, without a fixed polygon approximation.
A shortest path over commitment states adds every start cost, including midnight.
"""

from __future__ import annotations

import itertools
import math
import time
from copy import deepcopy

import numpy as np
from scipy.optimize import linprog

from .data import DayData
from .plant import Plant
from .tariff import Tariff, _minutes

DT_H = 0.5
GRID_TOL = 1e-7
CHECK_TOL = 3e-6
COST_TIE = 1e-9


def _available(day: DayData, unit: str, hhmm: str) -> bool:
    """An output held for the whole half-hour needs availability throughout it."""
    begin, end = _minutes(hhmm), _minutes(hhmm) + 30
    for outage in day.status.get("outages", []):
        if outage["unit"] != unit:
            continue
        a, b = _minutes(outage["from"]), _minutes(outage["to"])
        intervals = [(a, b)] if a <= b else [(a, 1440), (0, b)]
        if any(begin < stop and end > start for start, stop in intervals):
            return False
    return True


def _engine_available(plant: Plant, engine, available: dict[str, bool]) -> bool:
    if not available[engine.id] or not available["engine_ht"] or engine.id not in plant.ht_engines:
        return False
    paths = plant.lt_paths[engine.id]
    if np.any(engine._lt > 0) and not paths:
        return False
    return all(available[name] and any(available[sink] for sink in sinks) for name, sinks in paths)


def _cold_modes(plant: Plant, wet_bulb: float, available: dict[str, bool]) -> list[float]:
    base = plant.condenser_entering(wet_bulb)
    modes = {base}
    if plant.variable_tower_fans:
        modes.update(max(base, a.cooling_water_in_min_c) for a in plant.absorption_chillers
                     if available[a.id] and a.id in plant.ht_absorbers
                     and available["engine_ht"] and plant.ht_flow_c >= a.hot_water_in_min_c)
    return sorted(modes)


def _conic_lp(c, bounds, aeq, beq, aub, bub, reactive_row, reactive_demand,
              import_index, capacity, deadline):
    """LP lower bounds plus supporting hyperplanes for ||(import,Qnet)|| <= S.

    Every cut contains the entire feasible circle. Thus the returned LP objective
    is a lower bound until the LP optimum itself satisfies the circle. At that
    point the dispatch is also globally optimal for this convex subproblem.
    """
    rows, rhs = list(aub), list(bub)
    for angle in np.linspace(-math.pi / 2, math.pi / 2, 9):
        ci, cq = math.cos(float(angle)), math.sin(float(angle))
        row = cq * reactive_row.copy()
        row[import_index] += ci
        rows.append(row)
        rhs.append(capacity - cq * reactive_demand)
    for _ in range(80):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError("dispatch optimization exceeded its time budget")
        result = linprog(
            c, A_ub=np.asarray(rows), b_ub=np.asarray(rhs),
            A_eq=np.asarray(aeq), b_eq=np.asarray(beq), bounds=bounds,
            method="highs-ds", options={
                "primal_feasibility_tolerance": 1e-9,
                "dual_feasibility_tolerance": 1e-9,
                "time_limit": min(remaining, 10.0),
            },
        )
        if result.status == 2:
            return None
        if not result.success:
            raise RuntimeError(f"continuous dispatch solver failed: {result.message}")
        imported = float(result.x[import_index])
        reactive = float(reactive_demand + reactive_row @ result.x)
        apparent = math.hypot(imported, reactive)
        if apparent <= capacity + GRID_TOL:
            return result
        ci, cq = imported / apparent, reactive / apparent
        row = cq * reactive_row.copy()
        row[import_index] += ci
        rows.append(row)
        rhs.append(capacity - cq * reactive_demand)
    raise RuntimeError("apparent-power constraint did not converge to numerical precision")


def _region(day, plant, tariff, t, active, segments, available, cold_c, exporting, deadline):
    boilers, chillers, absorbers = plant.boilers, plant.electric_chillers, plant.absorption_chillers
    npower, nboil, nechill, nabs = len(active), len(boilers), len(chillers), len(absorbers)
    ib = npower
    ie = ib + nboil
    ia = ie + nechill
    ih = ia + nabs                 # HT-to-LTHW transfer through PHE1
    iw, ipv, ii, ix = ih + 1, ih + 2, ih + 3, ih + 4
    n = ix + 1
    c = np.zeros(n)
    bounds = [(0.0, 0.0)] * n
    fixed_cost = 0.0
    for j, (engine, segment) in enumerate(zip(active, segments)):
        bounds[j] = (segment.low, segment.high)
        c[j] = DT_H * (tariff.gas_rate * tariff.billed_gas(segment.fuel_slope, engine.fuel_basis)
                       + engine.maintenance)
        fixed_cost += DT_H * tariff.gas_rate * tariff.billed_gas(segment.fuel_zero, engine.fuel_basis)
    for j, boiler in enumerate(boilers):
        usable = available[boiler.id] and available["lthw"] and boiler.id in plant.lthw_boilers
        bounds[ib + j] = (0.0, boiler.max_kw if usable else 0.0)
        c[ib + j] = DT_H * tariff.gas_rate * tariff.billed_gas(1 / boiler.efficiency, boiler.fuel_basis)
    for j, chiller in enumerate(chillers):
        usable = available[chiller.id] and available["condenser_water"] and chiller.id in plant.tower_chillers
        bounds[ie + j] = (0.0, chiller.max_kw if usable else 0.0)
    for j, absorber in enumerate(absorbers):
        usable = (available[absorber.id] and available["engine_ht"] and available["condenser_water"]
                  and absorber.id in plant.ht_absorbers and absorber.id in plant.tower_chillers
                  and plant.ht_flow_c >= absorber.hot_water_in_min_c
                  and cold_c >= absorber.cooling_water_in_min_c)
        bounds[ia + j] = (0.0, absorber.max_kw if usable else 0.0)
    heat_load = float(day.heat[t] + plant.lthw_loss_kw)
    phe_available = available["lthw"] and available["engine_ht"] and any(available[u] for u in plant.phe_ids)
    bounds[ih] = (0.0, heat_load if phe_available else 0.0)
    bounds[iw] = (0.0, None)
    pv_available = min(float(day.pv[t]), plant.pv_inverter_kw) if available[plant.pv_id] else 0.0
    bounds[ipv] = (0.0, pv_available)
    bounds[ii] = (0.0, 0.0 if exporting else tariff.import_capacity_kva)
    bounds[ix] = (0.0, tariff.export_limit_kw if exporting else 0.0)
    c[ii] = DT_H * tariff.import_rate(day.starts[t])
    c[ix] = -DT_H * tariff.export_rate

    aeq, beq, aub, bub = [], [], [], []
    row = np.zeros(n)
    row[:npower] = 1.0
    row[ipv], row[ii], row[ix], row[iw] = 1.0, 1.0, -1.0, -1.0
    for j, absorber in enumerate(absorbers):
        row[ia + j] = -absorber.aux_per_kw
    aeq.append(row)
    beq.append(float(day.elec[t]) + sum(e.aux_kwe for e in active))

    # The supplied circuit inventory has NO HT dump. LT radiator heat is not HT
    # heat. All HT output must enter either the absorber generator or the PHE.
    row = np.zeros(n)
    for j, segment in enumerate(segments):
        row[j] = segment.ht_slope
    for j, absorber in enumerate(absorbers):
        row[ia + j] = -1.0 / absorber.cop
    row[ih] = -1.0
    aeq.append(row)
    beq.append(-sum(s.ht_zero for s in segments))

    row = np.zeros(n)
    row[ib:ib + nboil], row[ih] = 1.0, 1.0
    aeq.append(row)
    beq.append(heat_load)
    row = np.zeros(n)
    row[ie:ie + nechill], row[ia:ia + nabs] = 1.0, 1.0
    aeq.append(row)
    beq.append(float(day.cool[t]))

    # A common variable-speed tower circuit can operate at any temperature at or
    # above its coldest setpoint. For fixed chiller outputs, sum(Q/COP(T)) is a
    # continuous nondecreasing function of T. Its attainable values form exactly
    # this interval, even though the individual COP curves are piecewise linear.
    # This is an exact linear representation of total compressor electricity, not
    # independently chosen temperatures or interpolated COP reciprocals.
    warm_c = plant.condenser_upper(cold_c)
    lower, upper = np.zeros(n), np.zeros(n)
    for j, chiller in enumerate(chillers):
        lower[ie + j] = 1 / chiller.cop(cold_c)
        upper[ie + j] = -1 / chiller.cop(warm_c)
    lower[iw], upper[iw] = -1.0, 1.0
    aub.extend((lower, upper))
    bub.extend((0.0, 0.0))

    # EC condenser duty = cooling + compressor power. Absorber duty = cooling +
    # generator heat. The separate LT radiators never load these cooling towers.
    cells = sum(available[cell] for cell in plant.tower_cells) if available["condenser_water"] else 0
    row = np.zeros(n)
    row[iw] = 1.0
    for j, absorber in enumerate(absorbers):
        row[ia + j] = 1 / absorber.cop
    aub.append(row)
    bub.append(plant.tower_capacity(float(day.wet_bulb[t]), cells) - float(day.cool[t]))

    reactive_row = np.zeros(n)
    for j, engine in enumerate(active):
        reactive_row[j] = -engine.q_per_kw
    result = _conic_lp(c, bounds, aeq, beq, aub, bub, reactive_row, float(day.kvar[t]),
                       ii, tariff.import_capacity_kva, deadline)
    if result is None:
        return math.inf, None
    x = result.x
    # At an export ceiling, consuming extra PV solely by warming the tower is an
    # equal-cost degeneracy. Prefer the coldest operation achievable by PV
    # curtailment. No fuel, grid exchange or running cost changes in this step.
    actual_cold = plant.condenser_entering(float(day.wet_bulb[t]))
    for j, absorber in enumerate(absorbers):
        if x[ia + j] > 1e-8:
            actual_cold = max(actual_cold, absorber.cooling_water_in_min_c)
    cold_power = sum(x[ie + j] / ch.cop(actual_cold) for j, ch in enumerate(chillers))
    curtail = min(max(0.0, float(x[ipv])), max(0.0, float(x[iw]) - cold_power))
    x[ipv] -= curtail
    x[iw] -= curtail

    def clean(value):
        value = float(value)
        return 0.0 if abs(value) < 1e-10 else value

    output = {
        "engines_kwe": {engine.id: 0.0 for engine in plant.engines},
        "boilers_kw": {boiler.id: clean(x[ib + j]) for j, boiler in enumerate(boilers)},
        "chillers_kw": {**{ch.id: clean(x[ie + j]) for j, ch in enumerate(chillers)},
                        **{a.id: clean(x[ia + j]) for j, a in enumerate(absorbers)}},
        "pv_kw": clean(x[ipv]),
        "import_kw": clean(x[ii]),
        "export_kw": clean(x[ix]),
    }
    for j, engine in enumerate(active):
        output["engines_kwe"][engine.id] = clean(x[j])
    return float(result.fun) + fixed_cost, output


def _period(day: DayData, plant: Plant, tariff: Tariff, t: int, on: tuple[bool, ...],
            *, available=None, deadline=None):
    if available is None:
        available = {unit: _available(day, unit, day.starts[t]) for unit in sorted(plant.known_units)}
    if deadline is None:
        deadline = time.monotonic() + 110.0
    if not available["lthw"]:
        return math.inf, None
    active = [e for e, running in zip(plant.engines, on) if running]
    if any(not _engine_available(plant, e, available) for e in active):
        return math.inf, None
    best_cost, best = math.inf, None
    for segments in itertools.product(*(engine.segments for engine in active)):
        for cold_c in _cold_modes(plant, float(day.wet_bulb[t]), available):
            for exporting in (False, True):
                cost, loading = _region(day, plant, tariff, t, active, segments, available,
                                        cold_c, exporting, deadline)
                if cost < best_cost - COST_TIE:
                    best_cost, best = cost, loading
    return best_cost, best


def _check_and_bill(day, plant, tariff, t, output, previous):
    """Reconstruct physics and the bill from the actual dispatch, not LP costs."""
    engines = output["engines_kwe"]
    boilers = output["boilers_kw"]
    chillers = output["chillers_kw"]
    available = {u: _available(day, u, day.starts[t]) for u in sorted(plant.known_units)}
    on = tuple(engines[e.id] > 1e-7 for e in plant.engines)
    errors = []
    gas_kw, maintenance, start_charge, starts = 0.0, 0.0, 0.0, 0
    ht_heat, qnet, engine_aux = 0.0, float(day.kvar[t]), 0.0
    for j, engine in enumerate(plant.engines):
        power = engines[engine.id]
        if on[j]:
            if (power < engine.min_kwe - CHECK_TOL or power > engine.max_kwe + CHECK_TOL
                    or not _engine_available(plant, engine, available)):
                errors.append(f"{engine.id} availability/rating")
            engine_aux += engine.aux_kwe
            if not previous[j]:
                starts += 1
                start_charge += engine.start_cost
        elif abs(power) > CHECK_TOL:
            errors.append(f"{engine.id} off output")
        ht_heat += engine.ht_heat(power)
        qnet -= engine.q_per_kw * power
        gas_kw += tariff.billed_gas(engine.fuel(power), engine.fuel_basis)
        maintenance += power * engine.maintenance
    for boiler in plant.boilers:
        heat = boilers[boiler.id]
        maximum = boiler.max_kw if available[boiler.id] else 0.0
        if heat < -CHECK_TOL or heat > maximum + CHECK_TOL:
            errors.append(f"{boiler.id} availability/rating")
        gas_kw += tariff.billed_gas(boiler.fuel(heat), boiler.fuel_basis)
    absorption_heat, absorber_aux = 0.0, 0.0
    cold = plant.condenser_entering(float(day.wet_bulb[t]))
    for absorber in plant.absorption_chillers:
        cooling = chillers[absorber.id]
        maximum = absorber.max_kw if available[absorber.id] else 0.0
        if cooling < -CHECK_TOL or cooling > maximum + CHECK_TOL:
            errors.append(f"{absorber.id} availability/rating")
        if cooling > CHECK_TOL:
            if plant.ht_flow_c < absorber.hot_water_in_min_c or absorber.id not in plant.ht_absorbers:
                errors.append(f"{absorber.id} hot-water supply")
            cold = max(cold, absorber.cooling_water_in_min_c)
        absorption_heat += absorber.heat_in(cooling)
        absorber_aux += absorber.aux_per_kw * cooling
    phe_heat = ht_heat - absorption_heat
    if phe_heat < -CHECK_TOL:
        errors.append("absorber heat exceeds HT production")
    if not any(available[u] for u in plant.phe_ids) and abs(phe_heat) > CHECK_TOL:
        errors.append("PHE outage")
    if abs(phe_heat + sum(boilers.values()) - day.heat[t] - plant.lthw_loss_kw) > CHECK_TOL:
        errors.append("HT/LTHW balance")
    if abs(sum(chillers.values()) - day.cool[t]) > CHECK_TOL:
        errors.append("cooling balance")
    compressor = (sum(engines.values()) + output["pv_kw"] + output["import_kw"]
                  - output["export_kw"] - day.elec[t] - engine_aux - absorber_aux)
    low_power, high_power = 0.0, 0.0
    for chiller in plant.electric_chillers:
        cooling = chillers[chiller.id]
        maximum = chiller.max_kw if available[chiller.id] else 0.0
        if cooling < -CHECK_TOL or cooling > maximum + CHECK_TOL:
            errors.append(f"{chiller.id} availability/rating")
        low_power += cooling / chiller.cop(cold)
        high_power += cooling / chiller.cop(plant.condenser_upper(cold))
    if compressor < low_power - CHECK_TOL or compressor > high_power + CHECK_TOL:
        errors.append("electrical/COP balance")
    cells = sum(available[u] for u in plant.tower_cells) if available["condenser_water"] else 0
    if day.cool[t] + compressor + absorption_heat > plant.tower_capacity(float(day.wet_bulb[t]), cells) + CHECK_TOL:
        errors.append("cooling tower capacity")
    pv_limit = min(float(day.pv[t]), plant.pv_inverter_kw) if available[plant.pv_id] else 0.0
    if output["pv_kw"] < -CHECK_TOL or output["pv_kw"] > pv_limit + CHECK_TOL:
        errors.append("PV availability/inverter")
    if (min(output["import_kw"], output["export_kw"]) < -CHECK_TOL
            or min(output["import_kw"], output["export_kw"]) > CHECK_TOL
            or output["export_kw"] > tariff.export_limit_kw + CHECK_TOL):
        errors.append("metered exchange direction/export limit")
    grid_ok = math.hypot(output["import_kw"], qnet) <= tariff.import_capacity_kva + CHECK_TOL
    if not grid_ok:
        errors.append("import apparent power")
    if errors:
        raise RuntimeError(f"internal dispatch validation failed at {day.starts[t]}: {', '.join(errors)}")
    output["gas_kwh"] = DT_H * gas_kw
    output["cost_gbp"] = (DT_H * (gas_kw * tariff.gas_rate + maintenance
                                  + output["import_kw"] * tariff.import_rate(day.starts[t])
                                  - output["export_kw"] * tariff.export_rate) + start_charge)
    output["grid_ok"] = bool(grid_ok)
    return on, starts


def plan_day(day: DayData, plant: Plant, tariff: Tariff) -> tuple[list[dict], int]:
    deadline = time.monotonic() + 110.0
    engine_ids = {e.id for e in plant.engines}
    running = set(day.status.get("running_at_midnight", []))
    if running - engine_ids:
        raise ValueError(f"unknown engines running at midnight: {sorted(running - engine_ids)}")
    for outage in day.status.get("outages", []):
        if outage["unit"] not in plant.known_units:
            raise ValueError(f"unknown outage unit: {outage['unit']}")
        _minutes(outage["from"])
        _minutes(outage["to"])
    initial = tuple(e.id in running for e in plant.engines)
    states = list(itertools.product((False, True), repeat=len(plant.engines)))
    nstates = len(states)
    transition = np.zeros((nstates, nstates))
    transition_starts = np.zeros((nstates, nstates), dtype=int)
    for i, before in enumerate(states):
        for j, after in enumerate(states):
            newly_on = [engine for engine, a, b in zip(plant.engines, before, after) if b and not a]
            transition[i, j] = sum(e.start_cost for e in newly_on)
            transition_starts[i, j] = len(newly_on)

    all_costs, all_loadings, cache = [], [], {}
    for t in range(len(day.starts)):
        available = {u: _available(day, u, day.starts[t]) for u in sorted(plant.known_units)}
        key = (float(day.elec[t]), float(day.kvar[t]), float(day.heat[t]), float(day.cool[t]),
               float(day.wet_bulb[t]), float(day.pv[t]), tariff.import_rate(day.starts[t]),
               tuple(available.values()))
        if key not in cache:
            costs, loadings = [], []
            for state in states:
                cost, loading = _period(day, plant, tariff, t, state, available=available, deadline=deadline)
                costs.append(cost)
                loadings.append(loading)
            cache[key] = (costs, loadings)
        costs, loadings = cache[key]
        if not any(math.isfinite(cost) for cost in costs):
            raise RuntimeError(f"no feasible loading at {day.starts[t]}; demand cannot be met within plant/connection limits")
        all_costs.append(costs)
        all_loadings.append(loadings)

    previous_cost = np.full(nstates, math.inf)
    previous_count = np.full(nstates, 10 ** 9, dtype=int)
    initial_index = states.index(initial)
    previous_cost[initial_index], previous_count[initial_index] = 0.0, 0
    back = np.full((len(day.starts), nstates), -1, dtype=int)
    for t, costs in enumerate(all_costs):
        current_cost = np.full(nstates, math.inf)
        current_count = np.full(nstates, 10 ** 9, dtype=int)
        for j, cost in enumerate(costs):
            if not math.isfinite(cost):
                continue
            for i in range(nstates):
                candidate = float(previous_cost[i] + transition[i, j] + cost)
                count = int(previous_count[i] + transition_starts[i, j])
                if (candidate < current_cost[j] - COST_TIE
                        or (math.isfinite(candidate) and abs(candidate - current_cost[j]) <= COST_TIE
                            and count < current_count[j])):
                    current_cost[j], current_count[j], back[t, j] = candidate, count, i
        previous_cost, previous_count = current_cost, current_count
    final = min(range(nstates), key=lambda j: (previous_cost[j], previous_count[j], j))
    optimum = float(previous_cost[final])
    path = []
    for t in reversed(range(len(day.starts))):
        path.append(final)
        final = int(back[t, final])
    path.reverse()
    periods, total_starts, before = [], 0, initial
    for t, state_index in enumerate(path):
        output = deepcopy(all_loadings[t][state_index])
        before, starts = _check_and_bill(day, plant, tariff, t, output, before)
        total_starts += starts
        periods.append({"start": day.starts[t], **output})
    reported_cost = math.fsum(period["cost_gbp"] for period in periods)
    if abs(reported_cost - optimum) > 1e-6:
        raise RuntimeError("the reconstructed daily bill does not match the optimized objective")
    return periods, total_starts
