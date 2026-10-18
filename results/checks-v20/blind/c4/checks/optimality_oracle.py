"""Independent full-day MILP lower-bound oracle, without planner imports.

Unlike the application (enumerated per-period convex solves followed by DP),
this model selects all engine segments, condenser regimes and starts in one
mixed-integer program.  Piecewise curves use disaggregated segment binaries
and bounded interpolation weights.  Supporting circle cuts yield a rigorous
lower bound; a supplied feasible plan is certified by its gap to that bound.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

from verify_plan import available, billed, inputs, interpolate, rate_for


def combine(*terms):
    result = {}
    for scale, expression in terms:
        for index, coefficient in expression.items():
            result[index] = result.get(index, 0.0) + scale * coefficient
    return {index: coefficient for index, coefficient in result.items() if coefficient}


class Model:
    def __init__(self):
        self.names, self.lower, self.upper, self.cost, self.integer = [], [], [], [], []
        self.rows, self.row_lower, self.row_upper = [], [], []

    def variable(self, name, lower=0.0, upper=math.inf, cost=0.0, integer=0):
        index = len(self.names)
        self.names.append(name)
        self.lower.append(lower)
        self.upper.append(upper)
        self.cost.append(cost)
        self.integer.append(integer)
        return {index: 1.0}

    def objective(self, expression, multiplier):
        for index, coefficient in expression.items():
            self.cost[index] += multiplier * coefficient

    def constraint(self, expression, lower=-math.inf, upper=math.inf):
        self.rows.append(expression)
        self.row_lower.append(lower)
        self.row_upper.append(upper)

    def solve(self, seconds):
        row_indices, col_indices, values = [], [], []
        for row, expression in enumerate(self.rows):
            for column, value in expression.items():
                row_indices.append(row)
                col_indices.append(column)
                values.append(value)
        matrix = coo_matrix((values, (row_indices, col_indices)), shape=(len(self.rows), len(self.names))).tocsc()
        return milp(np.array(self.cost), integrality=np.array(self.integer),
                    bounds=Bounds(np.array(self.lower), np.array(self.upper)),
                    constraints=LinearConstraint(matrix, np.array(self.row_lower), np.array(self.row_upper)),
                    options={'mip_rel_gap': 1e-10, 'time_limit': seconds, 'presolve': True})


def dot(expression, x):
    return sum(coefficient * x[index] for index, coefficient in expression.items())


def build(folder):
    plant, supply, status, demand, weather = inputs(folder)
    model = Model()
    grid = []
    prior = None
    ct = plant['cooling_towers']
    ht_circuit = plant['heat_circuits']['engine_ht']
    lthw = plant['heat_circuits']['lthw']
    condenser = plant['heat_circuits']['condenser_water']
    for t, (site, wx) in enumerate(zip(demand, weather)):
        start = f'{t // 2:02d}:{30 * (t % 2):02d}'
        prefix = f'{t}:'
        online, powers = [], []
        ht = {}
        auxiliary = {}
        q_generated = {}
        for engine in plant['engines']:
            lt_sinks = [sink for circuit in plant['heat_circuits'].values()
                        if engine['id'] + ' intercooler' in circuit['from'] for sink in circuit['to']]
            usable = (available(status, engine['id'], start)
                      and any(available(status, sink, start) for sink in lt_sinks)
                      and any(source.startswith(engine['id'] + ' ') for source in ht_circuit['from']))
            on, power, fuel, heat = {}, {}, {}, {}
            for segment, (lo, hi) in enumerate(zip(engine['part_load'], engine['part_load'][1:])):
                z = model.variable(prefix + engine['id'] + f':segment{segment}', upper=int(usable), integer=1)
                fraction = model.variable(prefix + engine['id'] + f':fraction{segment}', upper=int(usable))
                model.constraint(combine((1, fraction), (-1, z)), upper=0)
                on = combine((1, on), (1, z))
                power = combine((1, power), (lo['kwe'], z), (hi['kwe'] - lo['kwe'], fraction))
                fuel = combine((1, fuel), (lo['fuel_kw'], z), (hi['fuel_kw'] - lo['fuel_kw'], fraction))
                heat = combine((1, heat), (lo['ht_heat_kw'], z), (hi['ht_heat_kw'] - lo['ht_heat_kw'], fraction))
            model.constraint(on, upper=1)
            model.constraint(power, upper=min(engine['rated_kwe'], engine['generator']['rated_kva'] * engine['generator']['power_factor']))
            online.append(on)
            powers.append(power)
            ht = combine((1, ht), (1, heat))
            auxiliary = combine((1, auxiliary), (engine['auxiliary_kwe'], on))
            sign = -1 if 'underexcited' in engine['generator']['control'] else 1
            reactive = sign * math.sqrt(1 / engine['generator']['power_factor']**2 - 1)
            q_generated = combine((1, q_generated), (reactive, power))
            model.objective(fuel, 0.5 * supply['gas']['rate_p_per_kwh'] / 100 * billed(1.0, engine['fuel_basis'], supply['gas']))
            model.objective(power, 0.5 * engine['maintenance_gbp_per_mwhe'] / 1000)
            starting = model.variable(prefix + engine['id'] + ':start', upper=1, cost=engine['start_cost_gbp'])
            if prior is None:
                initial = int(engine['id'] in status.get('running_at_midnight', []))
                model.constraint(combine((1, starting), (-1, on)), lower=-initial)
            else:
                model.constraint(combine((1, starting), (-1, on), (1, prior[len(online) - 1])), lower=0)
        prior = online
        boiler_heat = {}
        for boiler in plant['boilers']:
            upper = boiler['max_kw'] if available(status, boiler['id'], start) and boiler['id'] in lthw['from'] else 0
            output = model.variable(prefix + boiler['id'], upper=upper)
            boiler_heat = combine((1, boiler_heat), (1, output))
            model.objective(output, 0.5 * supply['gas']['rate_p_per_kwh'] / 100
                            * billed(1.0 / boiler['efficiency'], boiler['efficiency_basis'], supply['gas']))
        base_temp = max(float(wx['wet_bulb_c']) + ct['approach_k'], ct['min_leaving_water_c'])
        permissible = {a['id'] for a in plant['absorption_chillers']
                       if available(status, a['id'], start)
                       and a['id'] + ' generator' in ht_circuit['to']
                       and a['id'] + ' absorber and condenser' in condenser['from']
                       and ht_circuit['flow_c'] >= a['hot_water_in_min_c']}
        temperatures = sorted({base_temp, *(max(base_temp, a['cooling_water_in_min_c'])
                                           for a in plant['absorption_chillers'] if a['id'] in permissible)})
        choices, cooling, chiller_power, absorber_heat, rejection = {}, {}, {}, {}, {}
        for r, temperature in enumerate(temperatures):
            selected = model.variable(prefix + f'CW{r}', lower=int(len(temperatures) == 1), upper=1,
                                      integer=int(len(temperatures) > 1))
            choices = combine((1, choices), (1, selected))
            cold_power, warm_power = {}, {}
            warmest = max([temperature] + [ch['cop_by_condenser_entering_c'][-1][0]
                                          for ch in plant['electric_chillers']])
            for chiller in plant['electric_chillers']:
                capacity = chiller['max_kw'] if available(status, chiller['id'], start) and chiller['id'] + ' condenser' in condenser['from'] else 0
                output = model.variable(prefix + chiller['id'] + f':CW{r}', upper=capacity)
                model.constraint(combine((1, output), (-capacity, selected)), upper=0)
                reciprocal_cop = 1 / interpolate(chiller['cop_by_condenser_entering_c'], temperature)
                cooling = combine((1, cooling), (1, output))
                cold_power = combine((1, cold_power), (reciprocal_cop, output))
                warm_power = combine((1, warm_power), (1 / interpolate(chiller['cop_by_condenser_entering_c'], warmest), output))
                rejection = combine((1, rejection), (1, output))
            compressor = model.variable(prefix + f'compressor:CW{r}')
            model.constraint(combine((1, compressor), (-1, cold_power)), lower=0)
            model.constraint(combine((1, compressor), (-1, warm_power)), upper=0)
            chiller_power = combine((1, chiller_power), (1, compressor))
            rejection = combine((1, rejection), (1, compressor))
            for absorber in plant['absorption_chillers']:
                capacity = absorber['max_kw'] if absorber['id'] in permissible and absorber['cooling_water_in_min_c'] <= temperature else 0
                output = model.variable(prefix + absorber['id'] + f':CW{r}', upper=capacity)
                model.constraint(combine((1, output), (-capacity, selected)), upper=0)
                cooling = combine((1, cooling), (1, output))
                auxiliary = combine((1, auxiliary), (absorber['auxiliary_kwe_per_kw'], output))
                absorber_heat = combine((1, absorber_heat), (1 / absorber['cop'], output))
                rejection = combine((1, rejection), (1 + 1 / absorber['cop'], output))
        model.constraint(choices, lower=1, upper=1)
        model.constraint(cooling, lower=float(site['cooling_kw']), upper=float(site['cooling_kw']))
        capacity = sum(available(status, cell, start) for cell in ct['cells'] if cell in condenser['to']) * interpolate(
            ct['heat_rejection_kw_per_cell_by_wet_bulb_c'], float(wx['wet_bulb_c']))
        model.constraint(rejection, upper=capacity)
        phe = combine((1, ht), (-1, absorber_heat))
        phe_capacity = 0.0
        for hx in plant['heat_exchangers']:
            if hx['primary_circuit'] == 'engine_ht' and hx['secondary_circuit'] == 'lthw' and available(status, hx['id'], start):
                if hx['id'] in ht_circuit['to'] and hx['id'] in lthw['from']:
                    phe_capacity += (hx['primary_maximum_water_flow_kg_per_s'] * hx['water_specific_heat_kj_per_kg_k']
                                     * (ht_circuit['flow_c'] - ht_circuit['return_c']))
        model.constraint(phe, lower=0, upper=phe_capacity)
        heat_required = float(site['heat_kw']) + lthw['loss_kw']
        model.constraint(combine((1, phe), (1, boiler_heat)), lower=heat_required, upper=heat_required)
        pv_available = min(float(wx['pv_kw']), plant['pv']['inverter_ac_kw']) if available(status, plant['pv']['id'], start) else 0
        pv = model.variable(prefix + 'PV', upper=pv_available)
        imported = model.variable(prefix + 'import', upper=supply['electricity']['import_capacity_kva'],
                                  cost=0.5 * rate_for(supply, status['date'], start))
        exported = model.variable(prefix + 'export', upper=supply['electricity']['export_limit_kw'],
                                  cost=-0.5 * supply['electricity']['export_rate_p_per_kwh'] / 100)
        electricity = combine(*[(1, p) for p in powers], (1, pv), (1, imported), (-1, exported), (-1, auxiliary), (-1, chiller_power))
        model.constraint(electricity, lower=float(site['electricity_kw']), upper=float(site['electricity_kw']))
        grid.append((imported, q_generated, float(site['reactive_kvar'])))
    return model, grid, float(supply['electricity']['import_capacity_kva'])


def certify(folder, candidate_cost, maximum_seconds=150.0, gap_tolerance=0.0002):
    began = time.monotonic()
    model, grid, limit = build(folder)

    def cut(period, np_, nq):
        imported, q_generated, site_q = grid[period]
        model.constraint(combine((np_, imported), (-nq, q_generated)), upper=limit - nq * site_q)

    for t in range(len(grid)):
        for angle in np.linspace(-math.pi / 2, math.pi / 2, 17):
            cut(t, math.cos(angle), math.sin(angle))
    log = []
    best_lower = -math.inf
    for iteration in range(20):
        remaining = maximum_seconds - (time.monotonic() - began)
        if remaining <= 0:
            break
        result = model.solve(min(45.0, remaining))
        if result.x is None:
            raise RuntimeError('independent MILP could not produce a solution: ' + result.message)
        best_lower = max(best_lower, float(result.mip_dual_bound))
        violations = []
        for t, (imported, q_generated, site_q) in enumerate(grid):
            p = dot(imported, result.x)
            q = site_q - dot(q_generated, result.x)
            apparent = math.hypot(p, q)
            if apparent > limit + 2e-8:
                violations.append((t, p / apparent, q / apparent, apparent - limit))
        gap = candidate_cost - best_lower
        log.append(dict(round=iteration + 1, lower_bound_gbp=best_lower,
                        incumbent_gbp=float(result.fun), candidate_gap_gbp=gap,
                        maximum_circle_violation_kva=max((v[3] for v in violations), default=0.0),
                        mip_nodes=int(result.mip_node_count), solver_status=int(result.status)))
        if gap < -gap_tolerance:
            raise AssertionError('independent lower bound exceeds the candidate cost')
        if gap <= gap_tolerance or not violations:
            break
        for t, normal_p, normal_q, _ in violations:
            cut(t, normal_p, normal_q)
    certified = bool(candidate_cost - best_lower <= gap_tolerance)
    return dict(certified=certified, candidate_cost_gbp=candidate_cost,
                lower_bound_gbp=best_lower, absolute_gap_gbp=candidate_cost - best_lower,
                tolerance_gbp=gap_tolerance, seconds=time.monotonic() - began,
                method='full-day disaggregated-segment MILP with supporting kVA-circle cuts',
                variables=len(model.names), binary_variables=sum(model.integer),
                constraints=len(model.rows), rounds=log)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--seconds', type=float, default=150)
    args = parser.parse_args()
    cost = json.loads(args.plan.read_text())['summary']['cost_gbp']
    report = certify(args.data, cost, maximum_seconds=args.seconds)
    payload = json.dumps(report, indent=2) + '\n'
    if args.output:
        args.output.write_text(payload)
    print(payload)
    if not report['certified']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
