"""Deterministic least-cost dispatch, with complete-day engine commitment.

For a fixed adjacent part-load segment of each engine and a condenser-water
operating mode, all constraints are linear except the two-dimensional grid
apparent-power circle. Supporting half-planes give LP lower bounds; violated
circle points add exact separating cuts until the actual circle is satisfied.

All adjacent segment combinations are examined, without mixing non-adjacent
performance points. Dynamic programming over the engine on/off states then
finds the least-cost full day, including the stated midnight state and starts.
"""

from __future__ import annotations

import copy
import itertools
import math
import warnings

import numpy as np
from scipy.optimize import OptimizeWarning, linprog

from .data import DayData
from .plant import Plant
from .tariff import Tariff, minutes

DT_H = 0.5
GRID_TOL_KVA = 1e-7
CHECK_TOL = 3e-6
COST_TOL = 1e-8


def _available(day: DayData, unit: str, hhmm: str) -> bool:
    """A held half-hour loading is unavailable if any part overlaps an outage."""
    begin, end = minutes(hhmm), minutes(hhmm) + 30
    for outage in day.status.get("outages", []):
        if outage["unit"] != unit:
            continue
        a, b = minutes(outage["from"]), minutes(outage["to"])
        intervals = [(a, b)] if a <= b else [(a, 1440), (0, b)]
        if any(max(begin, lo) < min(end, hi) for lo, hi in intervals):
            return False
    return True


def _unit_ids(plant: Plant, tariff: Tariff) -> list[str]:
    ids = [x.id for group in (plant.engines, plant.boilers, plant.electric_chillers,
                              plant.absorption_chillers) for x in group]
    ids += plant.tower_cells + [plant.pv_id] + plant.phe_ids
    ids += [x for targets in plant.lt_radiators.values() for x in targets]
    ids += list(plant.circuits)
    if tariff.gas_entry:
        ids.append(tariff.gas_entry["id"])
    return sorted(set(ids))


def _operating_cost(day: DayData, plant: Plant, tariff: Tariff, t: int, loading: dict):
    gas_kw, gross_entry_kw, maintenance = 0.0, 0.0, 0.0
    for engine in plant.engines:
        p = loading["engines_kwe"][engine.id]
        fuel = engine.fuel(p)
        gas_kw += tariff.billed_gas(fuel, engine.fuel_basis)
        if engine.id in tariff.gas_entry_units:
            gross_entry_kw += tariff.gross_gas(fuel, engine.fuel_basis)
        maintenance += p * engine.maintenance
    for boiler in plant.boilers:
        fuel = boiler.fuel(loading["boilers_kw"][boiler.id])
        gas_kw += tariff.billed_gas(fuel, boiler.fuel_basis)
        if boiler.id in tariff.gas_entry_units:
            gross_entry_kw += tariff.gross_gas(fuel, boiler.fuel_basis)
    gas_kwh = DT_H * gas_kw
    cost = gas_kwh * tariff.gas_rate + DT_H * (
        maintenance + loading["import_kw"] * tariff.import_rate(day.starts[t])
        - loading["export_kw"] * tariff.export_rate
    )
    return float(cost), float(gas_kwh), float(gross_entry_kw)


class _PeriodModel:
    def __init__(self, day: DayData, plant: Plant, tariff: Tariff, t: int):
        self.day, self.plant, self.tariff, self.t = day, plant, tariff, t
        self.available = {unit: _available(day, unit, day.starts[t])
                          for unit in _unit_ids(plant, tariff)}
        self.nP = len(plant.engines)
        self.iB = self.nP
        self.iE = self.iB + len(plant.boilers)
        self.iA = self.iE + len(plant.electric_chillers)
        self.iPV = self.iA + len(plant.absorption_chillers)
        self.iG, self.iI = self.iPV + 1, self.iPV + 2
        self.iW = self.iI + 1  # total electric-chiller compressor power
        self.n = self.iW + 1
        self.q_vector = np.zeros(self.n)
        for j, engine in enumerate(plant.engines):
            self.q_vector[j] = -engine.kvar_per_kwe
        self.q_constant = float(day.kvar[t])
        self.grid_kva = tariff.import_capacity_kva
        # A shared cache of valid supporting planes accelerates all the load
        # regimes of this period. No approximation changes the feasible circle.
        self.circle_normals = [
            (math.cos(2 * math.pi * k / 32), math.sin(2 * math.pi * k / 32))
            for k in range(32)
        ]
        self.base_cewt = plant.condenser_entering(float(day.wet_bulb[t]))
        self.water_modes = [self.base_cewt]
        if plant.tower_variable_speed:
            for absorber in plant.absorption_chillers:
                if self.absorber_available(absorber):
                    temp = max(self.base_cewt, absorber.cooling_water_in_min_c)
                    if temp not in self.water_modes:
                        self.water_modes.append(temp)
        self.water_modes.sort()
        count = sum(self.available[c] for c in plant.tower_cells)
        self.tower_limit = plant.tower_capacity(float(day.wet_bulb[t]), count)
        if not self.available.get("condenser_water", True):
            self.tower_limit = 0.0
        self.pv_limit = min(float(day.pv[t]), plant.pv_rating) if self.available[plant.pv_id] else 0.0
        self.gas_limit = tariff.gas_entry_gross_kw
        if tariff.gas_entry and not self.available[tariff.gas_entry["id"]]:
            self.gas_limit = 0.0

    def engine_available(self, engine) -> bool:
        return (self.available[engine.id] and self.available.get("engine_ht", True)
                and all(self.available[x] for x in self.plant.lt_radiators[engine.id])
                and all(self.available[x] for x in self.plant.lt_circuits[engine.id]))

    def absorber_available(self, absorber) -> bool:
        return (self.available[absorber.id]
                and self.available.get("engine_ht", True)
                and self.plant.ht_flow_c >= absorber.hot_water_in_min_c
                and absorber.id + " generator" in self.plant.circuits["engine_ht"]["to"])

    def key(self):
        d, t = self.day, self.t
        return (float(d.elec[t]), float(d.kvar[t]), float(d.heat[t]), float(d.cool[t]),
                float(d.wet_bulb[t]), self.pv_limit, self.tariff.import_rate(d.starts[t]),
                tuple(self.available.items()))

    def _linear_conic(self, c, Aeq, beq, Aub, bub, bounds):
        a_ub = list(Aub)
        b_ub = list(bub)
        for nx, ny in self.circle_normals:
            row = ny * self.q_vector.copy()
            row[self.iG] += nx
            a_ub.append(row)
            b_ub.append(self.grid_kva - ny * self.q_constant)
        options = {
            "presolve": True,
            "primal_feasibility_tolerance": 1e-9,
            "dual_feasibility_tolerance": 1e-9,
            "threads": 1, "parallel": False, "random_seed": 0,
        }
        for _ in range(100):
            with warnings.catch_warnings():
                # SciPy forwards these documented HiGHS options verbatim.
                warnings.filterwarnings("ignore", message="Unrecognized options detected.*",
                                        category=OptimizeWarning)
                result = linprog(c, A_ub=np.asarray(a_ub), b_ub=np.asarray(b_ub),
                                 A_eq=np.asarray(Aeq), b_eq=np.asarray(beq),
                                 bounds=bounds, method="highs-ds", options=options)
            if result.status == 2:
                return None
            if not result.success:
                raise RuntimeError(f"LP solver failed at {self.day.starts[self.t]}: {result.message}")
            p = float(result.x[self.iG])
            q = float(self.q_constant + self.q_vector @ result.x)
            norm = math.hypot(p, q)
            if norm <= self.grid_kva + GRID_TOL_KVA:
                return result
            nx, ny = p / norm, q / norm
            row = ny * self.q_vector.copy()
            row[self.iG] += nx
            a_ub.append(row)
            b_ub.append(self.grid_kva - ny * self.q_constant)
            self.circle_normals.append((nx, ny))
        raise RuntimeError(f"grid-constraint refinement did not converge at {self.day.starts[self.t]}")

    def solve(self, regime: tuple[int, ...], cewt: float):
        d, plant, tariff, t, n = self.day, self.plant, self.tariff, self.t, self.n
        if not self.available.get("lthw", True) and d.heat[t] + plant.lthw_loss_kw > CHECK_TOL:
            return None
        c, fuel_gross, ht = np.zeros(n), np.zeros(n), np.zeros(n)
        bounds = [(0.0, 0.0)] * n
        ht_const, gross_const, aux = 0.0, 0.0, 0.0
        for j, (engine, segment_index) in enumerate(zip(plant.engines, regime)):
            if segment_index < 0:
                continue
            if not self.engine_available(engine):
                return None
            segment = engine.segments[segment_index]
            bounds[j] = (segment.lower, segment.upper)
            c[j] = DT_H * (tariff.billed_gas(segment.fuel_slope, engine.fuel_basis)
                            * tariff.gas_rate + engine.maintenance)
            if engine.id in tariff.gas_entry_units:
                fuel_gross[j] = tariff.gross_gas(segment.fuel_slope, engine.fuel_basis)
                gross_const += tariff.gross_gas(segment.fuel_intercept, engine.fuel_basis)
            ht[j] = segment.ht_slope
            ht_const += segment.ht_intercept
            aux += engine.aux_kwe
        for j, boiler in enumerate(plant.boilers):
            k = self.iB + j
            bounds[k] = (0.0, boiler.max_kw if self.available[boiler.id] else 0.0)
            c[k] = DT_H * tariff.billed_gas(1.0 / boiler.efficiency, boiler.fuel_basis) * tariff.gas_rate
            if boiler.id in tariff.gas_entry_units:
                fuel_gross[k] = tariff.gross_gas(1.0 / boiler.efficiency, boiler.fuel_basis)
        for j, chiller in enumerate(plant.electric_chillers):
            bounds[self.iE + j] = (0.0, chiller.max_kw if self.available[chiller.id] else 0.0)
        for j, absorber in enumerate(plant.absorption_chillers):
            allowed = self.absorber_available(absorber) and cewt >= absorber.cooling_water_in_min_c
            bounds[self.iA + j] = (0.0, absorber.max_kw if allowed else 0.0)
        bounds[self.iPV] = (0.0, self.pv_limit)
        bounds[self.iG] = (-tariff.export_limit_kw, self.grid_kva)
        bounds[self.iI] = (0.0, self.grid_kva)
        bounds[self.iW] = (0.0, None)
        # Import epigraph: I=max(G,0). Positive tariff spread makes simultaneous
        # import/export impossible, and the reported exchange is always net.
        c[self.iG] = DT_H * tariff.export_rate
        c[self.iI] = DT_H * (tariff.import_rate(d.starts[t]) - tariff.export_rate)

        Aeq, beq, Aub, bub = [], [], [], []
        electricity = np.zeros(n)
        electricity[:self.nP] = 1.0
        electricity[self.iPV] = electricity[self.iG] = 1.0
        electricity[self.iW] = -1.0
        reject = np.zeros(n)
        reject[self.iW] = 1.0
        absorption_heat = np.zeros(n)
        power_low, power_high = np.zeros(n), np.zeros(n)
        power_low[self.iW], power_high[self.iW] = -1.0, 1.0
        highest_temp = max([cewt] + [float(ch._t[-1]) for ch in plant.electric_chillers])
        if not plant.tower_variable_speed:
            highest_temp = cewt
        for j, chiller in enumerate(plant.electric_chillers):
            reject[self.iE + j] = 1.0
            power_low[self.iE + j] = 1.0 / chiller.cop(cewt)
            power_high[self.iE + j] = -1.0 / chiller.cop(highest_temp)
        # These two inequalities are the exact common-temperature attainable
        # power interval, not a relaxation mixing separate condenser loops.
        Aub.extend((power_low, power_high))
        bub.extend((0.0, 0.0))
        for j, absorber in enumerate(plant.absorption_chillers):
            electricity[self.iA + j] = -absorber.aux_per_kw
            absorption_heat[self.iA + j] = 1.0 / absorber.cop
            # Refrigeration heat, generator heat and the machine's auxiliary
            # electrical work all ultimately leave through its condenser loop.
            reject[self.iA + j] = 1.0 + 1.0 / absorber.cop + absorber.aux_per_kw
        Aeq.append(electricity)
        beq.append(float(d.elec[t]) + aux)
        heat = ht - absorption_heat
        for j in range(len(plant.boilers)):
            heat[self.iB + j] = 1.0
        Aeq.append(heat)
        beq.append(float(d.heat[t]) + plant.lthw_loss_kw - ht_const)
        # Nonnegative PHE transfer: boilers cannot supply the absorption generator.
        Aub.append(absorption_heat - ht)
        bub.append(ht_const)
        if not any(self.available[x] for x in plant.phe_ids):
            Aeq.append(ht - absorption_heat)
            beq.append(-ht_const)
        cooling = np.zeros(n)
        cooling[self.iE:self.iPV] = 1.0
        Aeq.append(cooling)
        beq.append(float(d.cool[t]))
        Aub.append(reject)
        bub.append(self.tower_limit)
        if math.isfinite(self.gas_limit):
            Aub.append(fuel_gross)
            bub.append(self.gas_limit - gross_const)
        imported = np.zeros(n)
        imported[self.iG], imported[self.iI] = 1.0, -1.0
        Aub.append(imported)
        bub.append(0.0)
        result = self._linear_conic(c, Aeq, beq, Aub, bub, bounds)
        if result is None:
            return None
        x = result.x
        clean = lambda value: 0.0 if abs(float(value)) < 1e-10 else float(value)
        grid = clean(x[self.iG])
        loading = {
            "engines_kwe": {e.id: clean(x[j]) for j, e in enumerate(plant.engines)},
            "boilers_kw": {b.id: clean(x[self.iB + j]) for j, b in enumerate(plant.boilers)},
            "chillers_kw": {
                **{ch.id: clean(x[self.iE + j]) for j, ch in enumerate(plant.electric_chillers)},
                **{a.id: clean(x[self.iA + j]) for j, a in enumerate(plant.absorption_chillers)},
            },
            "pv_kw": clean(x[self.iPV]),
            "import_kw": max(grid, 0.0),
            "export_kw": max(-grid, 0.0),
        }
        cost, gas_kwh, gross_kw = _operating_cost(d, plant, tariff, t, loading)
        loading["gas_kwh"], loading["cost_gbp"] = gas_kwh, cost
        actual_temperature = plant.condenser_temperature(float(d.wet_bulb[t]),
                                                       loading["chillers_kw"], float(x[self.iW]))
        loading["grid_ok"] = self.check(loading, actual_temperature, gross_kw)
        return cost, loading

    def check(self, loading, cewt, gross_kw):
        """Check the actual interpolated outputs, rather than LP coefficients."""
        plant, d, t, tariff = self.plant, self.day, self.t, self.tariff
        p = [loading["engines_kwe"][e.id] for e in plant.engines]
        ht = sum(e.ht_heat(v) for e, v in zip(plant.engines, p))
        boilers = sum(loading["boilers_kw"].values())
        ac_heat = sum(a.heat_in(loading["chillers_kw"][a.id]) for a in plant.absorption_chillers)
        ec_power = sum(loading["chillers_kw"][ch.id] / ch.cop(cewt) for ch in plant.electric_chillers)
        ac_power = sum(loading["chillers_kw"][a.id] * a.aux_per_kw for a in plant.absorption_chillers)
        aux = sum(e.aux_kwe for e, v in zip(plant.engines, p) if v > 0)
        cooling = sum(loading["chillers_kw"].values())
        grid = loading["import_kw"] - loading["export_kw"]
        qgrid = float(d.kvar[t]) - sum(e.kvar_per_kwe * v for e, v in zip(plant.engines, p))
        residuals = {
            "electricity": abs(sum(p) + loading["pv_kw"] + grid - d.elec[t] - aux - ec_power - ac_power),
            "heat": abs(ht + boilers - ac_heat - d.heat[t] - plant.lthw_loss_kw),
            "cooling": abs(cooling - d.cool[t]),
            "HT source": max(ac_heat - ht, 0.0),
            "tower": max(cooling + ec_power + ac_heat + ac_power - self.tower_limit, 0.0),
            "gas entry": max(gross_kw - self.gas_limit, 0.0),
            "grid": max(math.hypot(grid, qgrid) - tariff.import_capacity_kva, 0.0),
            "export": max(loading["export_kw"] - tariff.export_limit_kw, 0.0),
        }
        for name, residual in residuals.items():
            if residual > CHECK_TOL:
                raise RuntimeError(f"{name} residual {residual:.9g} at {d.starts[t]}")
        return True

    def all_states(self):
        size = 1 << self.nP
        costs, loads = np.full(size, math.inf), [None] * size
        choices = [([-1] + list(range(len(e.segments)))) if self.engine_available(e) else [-1]
                   for e in self.plant.engines]
        for regime in itertools.product(*choices):
            state = sum((1 << j) for j, k in enumerate(regime) if k >= 0)
            for cewt in self.water_modes:
                solution = self.solve(regime, cewt)
                if solution is None:
                    continue
                cost, loading = solution
                if cost < costs[state] - COST_TOL:
                    costs[state], loads[state] = cost, loading
        return costs, loads


def _period(day: DayData, plant: Plant, tariff: Tariff, t: int, on: tuple[bool, ...]):
    model = _PeriodModel(day, plant, tariff, t)
    costs, loads = model.all_states()
    state = sum((1 << j) for j, yes in enumerate(on) if yes)
    return float(costs[state]), loads[state]


def plan_day(day: DayData, plant: Plant, tariff: Tariff) -> tuple[list[dict], int]:
    known = set(_unit_ids(plant, tariff))
    for outage in day.status.get("outages", []):
        if outage["unit"] not in known:
            raise ValueError(f"outage names an unknown unit: {outage['unit']}")
    engine_ids = {e.id for e in plant.engines}
    initial_ids = set(day.status.get("running_at_midnight", []))
    if not initial_ids <= engine_ids:
        raise ValueError("running_at_midnight names a non-engine unit")
    initial = sum((1 << j) for j, e in enumerate(plant.engines) if e.id in initial_ids)
    count = 1 << len(plant.engines)
    stage_costs, stage_loads, cache = [], [], {}
    for t in range(len(day.starts)):
        model = _PeriodModel(day, plant, tariff, t)
        key = model.key()
        if key not in cache:
            cache[key] = model.all_states()
        costs, loads = cache[key]
        if not np.isfinite(costs).any():
            raise RuntimeError(f"no feasible loading at {day.starts[t]}: plant, heat, cooling, gas or grid limits")
        stage_costs.append(costs)
        stage_loads.append(loads)

    # No minimum up/down time, ramp restriction or shutdown cost is specified.
    # The only temporal coupling is the actual OFF -> ON start charge.
    start_charge = np.zeros((count, count))
    new_starts = np.zeros((count, count), dtype=int)
    for previous in range(count):
        for current in range(count):
            for j, engine in enumerate(plant.engines):
                if current & (1 << j) and not previous & (1 << j):
                    start_charge[previous, current] += engine.start_cost
                    new_starts[previous, current] += 1
    costs = np.full(count, math.inf)
    starts = np.full(count, 10**9, dtype=int)
    costs[initial], starts[initial] = 0.0, 0
    predecessor = np.full((len(day.starts), count), -1, dtype=int)
    for t, running_cost in enumerate(stage_costs):
        next_cost, next_starts = np.full(count, math.inf), np.full(count, 10**9, dtype=int)
        for current in range(count):
            if not math.isfinite(running_cost[current]):
                continue
            for previous in range(count):
                if not math.isfinite(costs[previous]):
                    continue
                candidate = costs[previous] + start_charge[previous, current] + running_cost[current]
                number = starts[previous] + new_starts[previous, current]
                if (candidate < next_cost[current] - COST_TOL
                        or (abs(candidate - next_cost[current]) <= COST_TOL and number < next_starts[current])):
                    next_cost[current], next_starts[current] = candidate, number
                    predecessor[t, current] = previous
        costs, starts = next_cost, next_starts
    final = min(range(count), key=lambda state: (costs[state], starts[state], state))
    selected = [0] * len(day.starts)
    state = final
    for t in range(len(day.starts) - 1, -1, -1):
        selected[t] = state
        state = int(predecessor[t, state])
    periods, previous = [], initial
    for t, current in enumerate(selected):
        loading = copy.deepcopy(stage_loads[t][current])
        loading["cost_gbp"] += float(start_charge[previous, current])
        periods.append({"start": day.starts[t], **loading})
        previous = current
    return periods, int(starts[final])
