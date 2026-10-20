"""Independent physical/accounting checker; imports no planner code.

Usage: python checks/verify_plan.py --data app/data --plan experiments/visible_plan.json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

TOL = 2e-5


def minutes(value):
    hours, mins = map(int, value.split(':'))
    return 60 * hours + mins


def available(status, name, start):
    left, right = minutes(start), minutes(start) + 30
    for outage in status.get('outages', []):
        if outage['unit'] == name:
            begin, end = minutes(outage['from']), minutes(outage['to'])
            pieces = [(begin, end)] if begin <= end else [(0, end), (begin, 1440)]
            if any(begin < right and end > left for begin, end in pieces):
                return False
    return True


def interpolate(points, x):
    if x <= points[0][0]:
        return float(points[0][1])
    if x >= points[-1][0]:
        return float(points[-1][1])
    for (left, yl), (right, yr) in zip(points, points[1:]):
        if left <= x <= right:
            return yl + (yr - yl) * (x - left) / (right - left)
    raise AssertionError('interpolation failed')


def inputs(folder):
    folder = Path(folder)
    plant = json.loads((folder / 'plant.json').read_text())
    supply = json.loads((folder / 'supply.json').read_text())
    status = json.loads((folder / 'status.json').read_text())
    with (folder / 'demand.csv').open(newline='') as fh:
        demand = sorted(csv.DictReader(fh), key=lambda r: datetime.fromisoformat(r['period_start']))
    with (folder / 'weather.csv').open(newline='') as fh:
        weather = {datetime.fromisoformat(r['time_utc']).astimezone(timezone.utc): r for r in csv.DictReader(fh)}
    aligned = [weather[datetime.fromisoformat(r['period_start']).astimezone(timezone.utc)] for r in demand]
    return plant, supply, status, demand, aligned


def rate_for(supply, date_string, start):
    weekend = datetime.fromisoformat(date_string).weekday() >= 5
    bands = supply['electricity']['import_rates_p_per_kwh']['weekend' if weekend else 'weekday']
    now = minutes(start)
    for band in bands:
        begin, end = minutes(band['from']), minutes(band['to'])
        if (begin <= now < end) if begin <= end else (now >= begin or now < end):
            return band['rate'] / 100
    raise AssertionError('missing tariff band')


def billed(value, basis, gas):
    if basis == gas['billing_basis']:
        return value
    if basis == 'net CV' and gas['billing_basis'] == 'gross CV':
        return value * gas['gross_to_net_cv_ratio']
    if basis == 'gross CV' and gas['billing_basis'] == 'net CV':
        return value / gas['gross_to_net_cv_ratio']
    raise AssertionError('unknown gas basis')


def check(folder, plan_file):
    plant, supply, status, demands, weather = inputs(folder)
    plan = json.loads(Path(plan_file).read_text())
    assert set(plan) == {'date', 'periods', 'summary'}, 'top-level format changed'
    assert plan['date'] == status['date']
    assert len(plan['periods']) == len(demands) == 48
    previous = set(status.get('running_at_midnight', []))
    total_starts = 0
    totals = dict(cost_gbp=0.0, gas_kwh=0.0, import_kwh=0.0, export_kwh=0.0)
    worst = dict(electricity_kw=0.0, heat_kw=0.0, cooling_kw=0.0,
                 cost_gbp=0.0, gas_kwh=0.0, grid_kva_excess=0.0)
    maximum = dict(tower_rejection_kw=0.0, phe_kw=0.0, apparent_import_kva=0.0, condenser_entering_c=0.0)
    counters = dict(interior_engine_loads=0, cold_absorber_periods=0, curtailment_periods=0,
                    grid_binding_periods=0, phe_binding_periods=0, tower_binding_periods=0,
                    modulated_cooling_water_periods=0)
    expected_keys = {'start', 'engines_kwe', 'boilers_kw', 'chillers_kw', 'pv_kw',
                     'import_kw', 'export_kw', 'gas_kwh', 'cost_gbp', 'grid_ok'}
    for t, (period, demand, wx) in enumerate(zip(plan['periods'], demands, weather)):
        label = f"period {t} {period['start']}"
        assert set(period) == expected_keys, label + ': period format changed'
        start = datetime.fromisoformat(demand['period_start']).strftime('%H:%M')
        assert period['start'] == start
        assert set(period['engines_kwe']) == {e['id'] for e in plant['engines']}
        assert set(period['boilers_kw']) == {b['id'] for b in plant['boilers']}
        assert set(period['chillers_kw']) == {c['id'] for c in plant['electric_chillers'] + plant['absorption_chillers']}
        for collection in ('engines_kwe', 'boilers_kw', 'chillers_kw'):
            for value in period[collection].values():
                assert math.isfinite(value) and value >= -TOL, label + ': invalid unit output'
        for key in ('pv_kw', 'import_kw', 'export_kw', 'gas_kwh'):
            assert math.isfinite(period[key]) and period[key] >= -TOL, label + ': invalid flow'
        assert math.isfinite(period['cost_gbp'])
        generation = 0.0
        ht = 0.0
        q_generated = 0.0
        auxiliary = 0.0
        maintenance = 0.0
        gas_kw = 0.0
        running = set()
        for engine in plant['engines']:
            output = period['engines_kwe'][engine['id']]
            assert output <= engine['rated_kwe'] + TOL, label + ': engine overloaded'
            if output > TOL:
                running.add(engine['id'])
                assert output >= engine['part_load'][0]['kwe'] - TOL, label + ': engine below minimum'
                assert available(status, engine['id'], start), label + ': engine outage'
                assert any(s.startswith(engine['id'] + ' ') for s in plant['heat_circuits']['engine_ht']['from'])
                sinks = []
                for circuit in plant['heat_circuits'].values():
                    if engine['id'] + ' intercooler' in circuit['from']:
                        sinks.extend(circuit['to'])
                assert any(available(status, radiator, start) for radiator in sinks), label + ': LT rejection unavailable'
                auxiliary += engine['auxiliary_kwe']
                knots = engine['part_load']
                ht += interpolate([(p['kwe'], p['ht_heat_kw']) for p in knots], output)
                gas_kw += billed(interpolate([(p['kwe'], p['fuel_kw']) for p in knots], output), engine['fuel_basis'], supply['gas'])
                if not any(abs(output - p['kwe']) < 1e-3 for p in knots):
                    counters['interior_engine_loads'] += 1
            generation += output
            maintenance += output * engine['maintenance_gbp_per_mwhe'] / 1000
            generator = engine['generator']
            assert output / generator['power_factor'] <= generator['rated_kva'] + TOL, label + ': generator overloaded'
            sign = -1 if 'underexcited' in generator['control'] else 1
            q_generated += sign * output * math.sqrt(1 / generator['power_factor']**2 - 1)
        boiler_heat = 0.0
        for boiler in plant['boilers']:
            output = period['boilers_kw'][boiler['id']]
            assert output <= boiler['max_kw'] + TOL, label + ': boiler overloaded'
            assert output <= TOL or available(status, boiler['id'], start), label + ': boiler outage'
            assert output <= TOL or boiler['id'] in plant['heat_circuits']['lthw']['from']
            boiler_heat += output
            gas_kw += billed(output / boiler['efficiency'], boiler['efficiency_basis'], supply['gas'])
        towers = plant['cooling_towers']
        base_cw = max(float(wx['wet_bulb_c']) + towers['approach_k'], towers['min_leaving_water_c'])
        cw = base_cw
        for absorber in plant['absorption_chillers']:
            if period['chillers_kw'][absorber['id']] > 1e-10:
                cw = max(cw, absorber['cooling_water_in_min_c'])
        if cw > base_cw + 1e-7:
            counters['cold_absorber_periods'] += 1
        # Independently recover the common condenser-water temperature from
        # the reported electrical balance.  All cooling-water settings above
        # the active plant's minimum are possible with modulating tower fans.
        absorber_aux = sum(a['auxiliary_kwe_per_kw'] * period['chillers_kw'][a['id']]
                           for a in plant['absorption_chillers'])
        required_compressor = (generation + period['pv_kw'] + period['import_kw'] - period['export_kw']
                               - float(demand['electricity_kw']) - auxiliary - absorber_aux)

        def electrical_at(temperature):
            return sum(period['chillers_kw'][ch['id']] / interpolate(ch['cop_by_condenser_entering_c'], temperature)
                       for ch in plant['electric_chillers'])

        warmest = max([cw] + [ch['cop_by_condenser_entering_c'][-1][0] for ch in plant['electric_chillers']])
        assert electrical_at(cw) - TOL <= required_compressor <= electrical_at(warmest) + TOL, label + ': impossible shared condenser temperature'
        if required_compressor > electrical_at(cw) + 1e-7:
            counters['modulated_cooling_water_periods'] += 1
            lower, upper = cw, warmest
            for _ in range(65):
                middle = (lower + upper) / 2
                if electrical_at(middle) < required_compressor:
                    lower = middle
                else:
                    upper = middle
            cw = (lower + upper) / 2
        chiller_electricity, cooling, generator_heat, rejection = 0.0, 0.0, 0.0, 0.0
        for chiller in plant['electric_chillers']:
            output = period['chillers_kw'][chiller['id']]
            assert output <= chiller['max_kw'] + TOL, label + ': electric chiller overloaded'
            assert output <= TOL or available(status, chiller['id'], start), label + ': electric chiller outage'
            assert output <= TOL or chiller['id'] + ' condenser' in plant['heat_circuits']['condenser_water']['from']
            electricity = output / interpolate(chiller['cop_by_condenser_entering_c'], cw)
            chiller_electricity += electricity
            rejection += output + electricity
            cooling += output
        for absorber in plant['absorption_chillers']:
            output = period['chillers_kw'][absorber['id']]
            assert output <= absorber['max_kw'] + TOL, label + ': absorption chiller overloaded'
            assert output <= TOL or available(status, absorber['id'], start), label + ': absorption chiller outage'
            if output > TOL:
                assert absorber['id'] + ' generator' in plant['heat_circuits']['engine_ht']['to']
                assert absorber['id'] + ' absorber and condenser' in plant['heat_circuits']['condenser_water']['from']
                assert plant['heat_circuits']['engine_ht']['flow_c'] >= absorber['hot_water_in_min_c']
                assert cw >= absorber['cooling_water_in_min_c']
            generator_heat += output / absorber['cop']
            rejection += output + output / absorber['cop']
            auxiliary += output * absorber['auxiliary_kwe_per_kw']
            cooling += output
        phe = ht - generator_heat
        capacity = 0.0
        for exchanger in plant['heat_exchangers']:
            if (exchanger['primary_circuit'] == 'engine_ht' and exchanger['secondary_circuit'] == 'lthw'
                    and available(status, exchanger['id'], start)):
                primary = plant['heat_circuits'][exchanger['primary_circuit']]
                secondary = plant['heat_circuits'][exchanger['secondary_circuit']]
                if exchanger['id'] in primary['to'] and exchanger['id'] in secondary['from']:
                    capacity += (exchanger['primary_maximum_water_flow_kg_per_s']
                                 * exchanger['water_specific_heat_kj_per_kg_k']
                                 * (primary['flow_c'] - primary['return_c']))
        assert phe >= -TOL, label + ': absorber is not supplied by available engine HT'
        assert phe <= capacity + TOL, label + ': PHE flow limit exceeded'
        heat_residual = phe + boiler_heat - float(demand['heat_kw']) - plant['heat_circuits']['lthw']['loss_kw']
        assert abs(heat_residual) <= TOL, label + ': missing heat or an unconnected HT dump'
        tower_capacity = sum(available(status, cell, start) for cell in towers['cells']
                             if cell in plant['heat_circuits']['condenser_water']['to']) * interpolate(
                                 towers['heat_rejection_kw_per_cell_by_wet_bulb_c'], float(wx['wet_bulb_c']))
        assert rejection <= tower_capacity + TOL, label + ': cooling tower overloaded'
        cooling_residual = cooling - float(demand['cooling_kw'])
        assert abs(cooling_residual) <= TOL, label + ': cooling balance'
        pv_max = min(float(wx['pv_kw']), plant['pv']['inverter_ac_kw']) if available(status, plant['pv']['id'], start) else 0.0
        assert period['pv_kw'] <= pv_max + TOL, label + ': PV exceeds available AC output'
        if period['pv_kw'] < pv_max - 1e-4:
            counters['curtailment_periods'] += 1
        electric_residual = (generation + period['pv_kw'] + period['import_kw'] - period['export_kw']
                             - float(demand['electricity_kw']) - auxiliary - chiller_electricity)
        assert abs(electric_residual) <= TOL, label + ': electrical balance'
        assert min(period['import_kw'], period['export_kw']) <= TOL, label + ': simultaneous import/export'
        grid_q = float(demand['reactive_kvar']) - q_generated
        apparent = math.hypot(period['import_kw'], grid_q)
        assert apparent <= supply['electricity']['import_capacity_kva'] + TOL, label + ': apparent-power connection limit'
        assert period['export_kw'] <= supply['electricity']['export_limit_kw'] + TOL, label + ': export limit'
        assert period['grid_ok'] is True
        starts = running - previous
        total_starts += len(starts)
        start_cost = sum(e['start_cost_gbp'] for e in plant['engines'] if e['id'] in starts)
        gas_kwh = gas_kw / 2
        cost = (gas_kwh * supply['gas']['rate_p_per_kwh'] / 100 + maintenance / 2 + start_cost
                + period['import_kw'] / 2 * rate_for(supply, status['date'], start)
                - period['export_kw'] / 2 * supply['electricity']['export_rate_p_per_kwh'] / 100)
        assert abs(period['gas_kwh'] - gas_kwh) <= TOL, label + ': metered gas mismatch'
        assert abs(period['cost_gbp'] - cost) <= TOL, label + ': billed cost mismatch'
        previous = running
        totals['cost_gbp'] += cost
        totals['gas_kwh'] += gas_kwh
        totals['import_kwh'] += period['import_kw'] / 2
        totals['export_kwh'] += period['export_kw'] / 2
        for key, residual in [('electricity_kw', electric_residual), ('heat_kw', heat_residual),
                              ('cooling_kw', cooling_residual), ('cost_gbp', period['cost_gbp'] - cost),
                              ('gas_kwh', period['gas_kwh'] - gas_kwh)]:
            worst[key] = max(worst[key], abs(residual))
        worst['grid_kva_excess'] = max(worst['grid_kva_excess'], apparent - supply['electricity']['import_capacity_kva'])
        maximum['tower_rejection_kw'] = max(maximum['tower_rejection_kw'], rejection)
        maximum['phe_kw'] = max(maximum['phe_kw'], phe)
        maximum['apparent_import_kva'] = max(maximum['apparent_import_kva'], apparent)
        maximum['condenser_entering_c'] = max(maximum['condenser_entering_c'], cw)
        counters['grid_binding_periods'] += abs(apparent - supply['electricity']['import_capacity_kva']) < 1e-3
        counters['phe_binding_periods'] += capacity > 0 and abs(phe - capacity) < 1e-3
        counters['tower_binding_periods'] += tower_capacity > 0 and abs(rejection - tower_capacity) < 1e-3
    assert set(plan['summary']) == {'cost_gbp', 'gas_kwh', 'import_kwh', 'export_kwh', 'engine_starts', 'grid_ok'}
    for key, value in totals.items():
        assert abs(plan['summary'][key] - value) <= TOL, f'summary {key}'
    assert plan['summary']['engine_starts'] == total_starts
    assert plan['summary']['grid_ok'] is True
    return dict(passed=True, periods=len(demands), engine_starts=total_starts,
                recomputed_summary=totals, maximum_residuals=worst, maxima=maximum, coverage=counters)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = check(args.data, args.plan)
    report = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.write_text(report)
    print(report)


if __name__ == '__main__':
    main()
