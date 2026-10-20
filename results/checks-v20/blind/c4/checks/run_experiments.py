"""Reproducible independent fixtures, feasibility checks, optimality and repeatability.

All generated inputs, witness plans, output plans and results stay under the
c4 delivery directory.  The supplied application data are read but never edited.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from optimality_oracle import certify
from verify_plan import available, billed, check, inputs, interpolate, rate_for

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'app/data'
CASES = ROOT / 'experiments/cases'
PLANT, SUPPLY, ORIGINAL_STATUS, ORIGINAL_DEMAND, ORIGINAL_WX = inputs(BASE)


def spec(**changes):
    value = dict(engines=(0.0, 800.0), boilers=(0.0, 0.0), chillers=(600.0, 0.0),
                 absorption=300.0, imported=700.0, exported=0.0, grid_q=100.0)
    value.update(changes)
    return value


def constant(**changes):
    return lambda t, status, wx: spec(**changes)


def regular_weather(t, wet=18.0):
    return dict(wet_bulb_c=wet, dry_bulb_c=wet + 8,
                pv_kw=max(0, 240 * math.sin(math.pi * (t - 12) / 24)) if 12 <= t <= 36 else 0.0)


def serialise_csv(path, rows, names):
    with path.open('w', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=names)
        writer.writeheader()
        writer.writerows(rows)


def write_inputs(name, start, status, demand, weather, shuffle=False):
    folder = CASES / name / 'data'
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(BASE / 'plant.json', folder / 'plant.json')
    shutil.copyfile(BASE / 'supply.json', folder / 'supply.json')
    (folder / 'status.json').write_text(json.dumps(status, indent=2) + '\n')
    demand_rows = []
    wx_rows = []
    for t, (site, wx) in enumerate(zip(demand, weather)):
        stamp = start + timedelta(minutes=30 * t)
        demand_rows.append(dict(period_start=stamp.isoformat(timespec='minutes'), **site))
        wx_rows.append(dict(time_utc=stamp.astimezone(timezone.utc).isoformat(timespec='minutes').replace('+00:00', 'Z'), **wx))
    # Extra UTC dates must have no positional influence on the selected run.
    for t in range(-24, 0):
        stamp = (start + timedelta(minutes=30 * t)).astimezone(timezone.utc)
        wx_rows.append(dict(time_utc=stamp.isoformat(timespec='minutes').replace('+00:00', 'Z'),
                            dry_bulb_c=-20 + t, wet_bulb_c=-25 + t, pv_kw=0.0))
    for t in range(48, 72):
        stamp = (start + timedelta(minutes=30 * t)).astimezone(timezone.utc)
        wx_rows.append(dict(time_utc=stamp.isoformat(timespec='minutes').replace('+00:00', 'Z'),
                            dry_bulb_c=45 + t, wet_bulb_c=35 + t, pv_kw=0.0))
    if shuffle:
        rng = random.Random(9107)
        rng.shuffle(demand_rows)
        rng.shuffle(wx_rows)
    serialise_csv(folder / 'demand.csv', demand_rows,
                  ['period_start', 'electricity_kw', 'reactive_kvar', 'heat_kw', 'cooling_kw'])
    serialise_csv(folder / 'weather.csv', wx_rows, ['time_utc', 'dry_bulb_c', 'wet_bulb_c', 'pv_kw'])
    return folder


def make_case(name, description, profile, *, date='2026-07-27', offset=1, outages=(),
              initial=(), weather_fn=regular_weather, shuffle=False):
    start = datetime.fromisoformat(date).replace(tzinfo=timezone(timedelta(hours=offset)))
    status = dict(date=date, running_at_midnight=list(initial), outages=list(outages))
    demands, forecasts, periods = [], [], []
    previous = set(initial)
    starts = 0
    for t in range(48):
        wx = weather_fn(t)
        setting = profile(t, status, wx)
        stamp = (start + timedelta(minutes=30*t)).strftime('%H:%M')
        engine_outputs = {e['id']: p for e, p in zip(PLANT['engines'], setting['engines'])}
        boiler_outputs = {b['id']: p for b, p in zip(PLANT['boilers'], setting['boilers'])}
        chiller_outputs = {c['id']: p for c, p in zip(PLANT['electric_chillers'], setting['chillers'])}
        chiller_outputs['AC1'] = setting['absorption']
        cw = max(wx['wet_bulb_c'] + PLANT['cooling_towers']['approach_k'], PLANT['cooling_towers']['min_leaving_water_c'])
        if setting['absorption'] > 0:
            cw = max(cw, PLANT['absorption_chillers'][0]['cooling_water_in_min_c'])
        cw = max(cw, setting.get('condenser_c', cw))
        ht, qgen, aux, gas, maintenance = 0.0, 0.0, 0.0, 0.0, 0.0
        for engine, power in zip(PLANT['engines'], setting['engines']):
            if power:
                ht += interpolate([(p['kwe'], p['ht_heat_kw']) for p in engine['part_load']], power)
                gas += billed(interpolate([(p['kwe'], p['fuel_kw']) for p in engine['part_load']], power), engine['fuel_basis'], SUPPLY['gas'])
                aux += engine['auxiliary_kwe']
            qgen += power * math.sqrt(1 / engine['generator']['power_factor']**2 - 1)
            maintenance += power * engine['maintenance_gbp_per_mwhe'] / 1000
        for boiler, heat in zip(PLANT['boilers'], setting['boilers']):
            gas += billed(heat / boiler['efficiency'], boiler['efficiency_basis'], SUPPLY['gas'])
        absorber = PLANT['absorption_chillers'][0]
        aux += setting['absorption'] * absorber['auxiliary_kwe_per_kw']
        electric_cooling = sum(p / interpolate(ch['cop_by_condenser_entering_c'], cw)
                               for ch, p in zip(PLANT['electric_chillers'], setting['chillers']))
        pv = min(wx['pv_kw'], PLANT['pv']['inverter_ac_kw']) if available(status, PLANT['pv']['id'], stamp) else 0.0
        pv = setting.get('pv_used', pv)
        electricity = sum(setting['engines']) + pv + setting['imported'] - setting['exported'] - aux - electric_cooling
        heat = ht - setting['absorption'] / absorber['cop'] + sum(setting['boilers']) - PLANT['heat_circuits']['lthw']['loss_kw']
        cooling = sum(setting['chillers']) + setting['absorption']
        reactive = setting.get('site_kvar', qgen + setting['grid_q'])
        assert electricity >= -1e-10 and heat >= -1e-10 and cooling >= 0, (name, t, setting, electricity, heat)
        demands.append(dict(electricity_kw=max(0.0, electricity), reactive_kvar=reactive,
                            heat_kw=max(0.0, heat), cooling_kw=cooling))
        forecasts.append(wx)
        running = {key for key, power in engine_outputs.items() if power > 0}
        new_starts = running - previous
        starts += len(new_starts)
        start_cost = sum(e['start_cost_gbp'] for e in PLANT['engines'] if e['id'] in new_starts)
        cost = (0.5 * gas * SUPPLY['gas']['rate_p_per_kwh'] / 100 + 0.5 * maintenance + start_cost
                + 0.5 * setting['imported'] * rate_for(SUPPLY, date, stamp)
                - 0.5 * setting['exported'] * SUPPLY['electricity']['export_rate_p_per_kwh'] / 100)
        periods.append(dict(start=stamp, engines_kwe=engine_outputs, boilers_kw=boiler_outputs,
                            chillers_kw=chiller_outputs, pv_kw=pv, import_kw=setting['imported'], export_kw=setting['exported'],
                            gas_kwh=gas / 2, cost_gbp=cost, grid_ok=True))
        previous = running
    folder = write_inputs(name, start, status, demands, forecasts, shuffle)
    witness = dict(date=date, periods=periods, summary=dict(
        cost_gbp=sum(p['cost_gbp'] for p in periods), gas_kwh=sum(p['gas_kwh'] for p in periods),
        import_kwh=sum(p['import_kw'] for p in periods) / 2, export_kwh=sum(p['export_kw'] for p in periods) / 2,
        engine_starts=starts, grid_ok=True))
    witness_path = folder.parent / 'feasible_witness.json'
    witness_path.write_text(json.dumps(witness, indent=1) + '\n')
    check(folder, witness_path)
    return dict(name=name, description=description, data=str(folder), feasible=True)


def outage(unit, begin='00:00', end='24:00'):
    return dict(unit=unit, **{'from': begin, 'to': end})


def retimed(name, date, offset, shuffle=False):
    start = datetime.fromisoformat(date).replace(tzinfo=timezone(timedelta(hours=offset)))
    status = dict(ORIGINAL_STATUS, date=date)
    demand = [{key: float(row[key]) for key in ['electricity_kw', 'reactive_kvar', 'heat_kw', 'cooling_kw']}
              for row in ORIGINAL_DEMAND]
    wx = [{key: float(row[key]) for key in ['wet_bulb_c', 'dry_bulb_c', 'pv_kw']} for row in ORIGINAL_WX]
    folder = write_inputs(name, start, status, demand, wx, shuffle)
    return dict(name=name, description='Visible physical forecasts retimed to test local tariffs and UTC alignment.', data=str(folder), feasible=True)


def generate():
    CASES.mkdir(parents=True, exist_ok=True)
    cases = []
    folder = CASES / 'visible' / 'data'
    shutil.copytree(BASE, folder, dirs_exist_ok=True)
    cases.append(dict(name='visible', description='Unmodified supplied day.', data=str(folder), feasible=True))
    cases.extend([
        retimed('monday_local_previous_utc_sunday', '2026-07-27', 1),
        retimed('saturday_local_previous_utc_friday', '2026-07-25', 1),
        retimed('offset_plus_14_shuffled', '2026-07-26', 14, True),
        retimed('offset_minus_7_shuffled', '2026-01-05', -7, True),
        retimed('offset_plus_5_30', '2026-01-10', 5.5),
    ])
    cases.append(make_case('cold_absorption', 'The tower fans maintain 22 C for AC while EC COP uses the common inlet.',
                           constant(engines=(0, 600), boilers=(100, 0), chillers=(600, 0), absorption=300, imported=950),
                           date='2026-01-05', offset=0, weather_fn=lambda t: regular_weather(t, wet=8)))
    cases.append(make_case('cold_absorber_outage', 'Cold tower leaving temperature remains 21 C with AC unavailable.',
                           constant(absorption=0, chillers=(900, 0)), outages=[outage('AC1')],
                           weather_fn=lambda t: regular_weather(t, wet=-10)))

    category_outages = [outage('B1', '00:00', '04:00'), outage('EC1', '04:00', '08:00'),
                        outage('AC1', '08:00', '12:00'), outage('CT1', '12:00', '16:00'),
                        outage('PHE1', '16:00', '20:00'), outage('PV1', '20:00', '22:00'),
                        outage('LT radiator 1', '22:00', '24:00')]

    def categories(t, status, wx):
        if t < 8:
            return spec(engines=(0, 0), boilers=(0, 575), chillers=(800, 0), absorption=0, imported=1000)
        if t < 16:
            return spec(boilers=(100, 0), chillers=(0, 700), absorption=400, imported=800)
        if t < 24:
            return spec(engines=(900, 0), chillers=(1200, 200), absorption=0, imported=1000)
        if t < 32:
            return spec(engines=(0, 0), boilers=(875, 0), chillers=(1000, 0), absorption=0, imported=1000)
        if t < 40:
            return spec(engines=(0, 600), boilers=(675, 0), chillers=(300, 0), absorption=553.8)
        if t < 44:
            return spec(engines=(900, 0), imported=600)
        return spec(imported=800)

    cases.append(make_case('every_plant_outage_category', 'Boiler, electric/absorption chiller, tower, PHE, PV and LT radiator outages.', categories,
                           outages=category_outages, weather_fn=lambda t: regular_weather(t, wet=22)))
    partial = [outage('GE1', '00:10', '01:15'), outage('GE2', '23:15', '00:15'),
               outage('EC1', '04:15', '06:10'), outage('PV1', '11:05', '11:40'),
               outage('B1', '13:15', '14:15'), outage('CT1', '17:05', '19:10'),
               outage('AC1', '20:15', '20:40'), outage('PHE1', '22:10', '22:20')]

    def partial_profile(t, status, wx):
        stamp = f'{t // 2:02d}:{30 * (t % 2):02d}'
        engine = 600 if available(status, 'GE2', stamp) and available(status, 'PHE1', stamp) else 0
        absorption = 300 if engine and available(status, 'AC1', stamp) else 0
        phe = (780 if engine else 0) - absorption / 0.71
        boiler = 875 - phe
        return spec(engines=(0, engine), absorption=absorption,
                    boilers=(boiler, 0) if available(status, 'B1', stamp) else (0, boiler),
                    chillers=(600, 0) if available(status, 'EC1', stamp) else (0, 600),
                    imported=600 if engine else 1050, grid_q=150)

    cases.append(make_case('partial_and_midnight_outages', 'Whole-half-hour availability for partial and midnight-wrapping outages.',
                           partial_profile, outages=partial, initial=('GE1', 'GE2')))
    cases.append(make_case('very_hot_flat_table_ends', 'Wet bulb and condenser temperature above the last performance-table points.',
                           constant(engines=(900, 0), boilers=(200, 0), chillers=(1000, 400), absorption=300, imported=950, grid_q=300),
                           weather_fn=lambda t: regular_weather(t, wet=35)))
    ec2_binding = (2850 - 1400 * (1 + 1 / 5.6)) / (1 + 1 / 4.6)
    cases.append(make_case('tower_capacity_boundary', 'Cooling load chosen to bind total condenser heat rejection exactly.',
                           constant(engines=(1200, 0), chillers=(1400, ec2_binding), absorption=0, imported=900),
                           weather_fn=lambda t: regular_weather(t, wet=22)))
    cases.append(make_case('phe_flow_boundary', 'With both boilers unavailable, PHE transfers exactly its 1672 kW hydraulic capacity.',
                           constant(engines=(1200, 800), chillers=(632.22, 0), absorption=367.78, imported=700),
                           outages=[outage('B1'), outage('B2')] ))
    cases.append(make_case('high_heat_and_boiler_merit', 'High heat uses both boiler efficiencies and the PHE capacity.',
                           constant(engines=(1200, 800), boilers=(2000, 403), chillers=(632.22, 0), absorption=367.78, imported=700)))
    cases.append(make_case('reactive_demand_above_connection_rating', 'Generator reactive support permits service when site kvar exceeds the import kVA rating.',
                           constant(engines=(1200, 800), chillers=(1000, 0), absorption=500, imported=1000, grid_q=600)))
    cases.append(make_case('leading_reactive_circle_boundary', 'Overexcited generators can increase an already leading grid reactive flow; true circle is binding.',
                           constant(engines=(900, 600), chillers=(600, 0), absorption=600, imported=200, site_kvar=-700)))
    cases.append(make_case('no_ht_dump_low_heat', 'Very low buildings heat requires all unused HT to flow to the absorption generator.',
                           constant(chillers=(300, 0), absorption=585.75, imported=800)))
    cases.append(make_case('no_towers_no_cooling', 'LT radiators and building heat operate while both cooling-tower cells are unavailable.',
                           constant(engines=(900, 0), chillers=(0, 0), absorption=0, imported=700),
                           outages=[outage('CT1'), outage('CT2')] ))
    cases.append(make_case('pv_export_curtailment', 'Available PV is curtailed just enough to respect the real-power export limit.',
                           constant(engines=(0, 0), boilers=(575, 0), chillers=(0, 0), absorption=0,
                                    imported=0, exported=250, pv_used=250, grid_q=0),
                           outages=[outage('GE1'), outage('GE2')],
                           weather_fn=lambda t: dict(wet_bulb_c=18, dry_bulb_c=24, pv_kw=280)))
    cases.append(make_case('pv_ac_rating', 'PV forecast above inverter rating is clipped to the AC nameplate.',
                           constant(), weather_fn=lambda t: dict(wet_bulb_c=18, dry_bulb_c=24, pv_kw=350)))
    cases.append(make_case('heat_led_cooling_water_modulation',
                           'Heat and outages force GE2 to rated output; warmer common condenser water makes the export limit feasible.',
                           constant(engines=(0, 800), chillers=(700, 0), absorption=0, imported=0,
                                    exported=250, grid_q=0, condenser_c=30),
                           outages=[outage('GE1'), outage('B1'), outage('B2')],
                           weather_fn=lambda t: dict(wet_bulb_c=8, dry_bulb_c=16, pv_kw=0)))
    for duration, name in [(1, 'short_dip_keep_running'), (10, 'long_dip_restart')]:
        start = datetime.fromisoformat('2026-07-27').replace(tzinfo=timezone(timedelta(hours=1)))
        status = dict(date='2026-07-27', running_at_midnight=['GE2'], outages=[outage('GE1')])
        rows = [dict(electricity_kw=150 if 2 <= t < 2 + duration else 900,
                     reactive_kvar=100, heat_kw=0, cooling_kw=400) for t in range(48)]
        wx = [dict(wet_bulb_c=18, dry_bulb_c=25, pv_kw=0) for _ in range(48)]
        folder = write_inputs(name, start, status, rows, wx)
        cases.append(dict(name=name, description='Economic shutdown decision across a low-demand interval with initial engine running.',
                          data=str(folder), feasible=True))

    for seed in range(6):
        rng = random.Random(4400 + seed)
        outage_list = [outage('GE1', '02:15', '04:10'), outage('CT1', '15:15', '17:10'), outage('B2')]
        settings, forecasts = [], []
        status = dict(outages=outage_list)
        for t in range(48):
            stamp = f'{t // 2:02d}:{30 * (t % 2):02d}'
            wx = dict(wet_bulb_c=rng.uniform(-8, 35), dry_bulb_c=43, pv_kw=rng.uniform(0, 280))
            outputs = [rng.uniform(e['part_load'][0]['kwe'], e['rated_kwe']) if rng.random() < 0.6 and available(status, e['id'], stamp) else 0
                       for e in PLANT['engines']]
            ht = sum(interpolate([(p['kwe'], p['ht_heat_kw']) for p in e['part_load']], power)
                     for e, power in zip(PLANT['engines'], outputs) if power)
            if ht:
                phe = rng.uniform(max(75, ht - 800 / 0.71), min(ht, 1672))
            else:
                phe = 0
            absorption = (ht - phe) * 0.71
            cw = max(wx['wet_bulb_c'] + 4, 21, 22 if absorption > 0 else 0)
            tower = sum(available(status, cell, stamp) for cell in ('CT1', 'CT2')) * interpolate(
                PLANT['cooling_towers']['heat_rejection_kw_per_cell_by_wet_bulb_c'], wx['wet_bulb_c'])
            # If only one tower is available, trim absorption by transferring
            # more HT through the PHE (or choose the off-engine witness).
            if absorption * (1 + 1 / 0.71) > tower * 0.8:
                outputs = [0, 0]
                ht = phe = absorption = 0
                cw = max(wx['wet_bulb_c'] + 4, 21)
            remaining = tower - absorption * (1 + 1 / 0.71)
            chiller_outputs = []
            for chiller in PLANT['electric_chillers']:
                coeff = 1 + 1 / interpolate(chiller['cop_by_condenser_entering_c'], cw)
                output = rng.uniform(0, min(chiller['max_kw'], remaining / coeff))
                chiller_outputs.append(output)
                remaining -= coeff * output
            imported = rng.uniform(700, 1100)
            q_limit = math.sqrt(1220**2 - imported**2)
            settings.append(spec(engines=tuple(outputs), boilers=(max(0, 75 - phe) + rng.uniform(50, 800), 0),
                                 chillers=tuple(chiller_outputs), absorption=absorption,
                                 imported=imported, grid_q=rng.uniform(-q_limit, q_limit)))
            forecasts.append(wx)
        cases.append(make_case(f'random_feasible_{seed}', 'Seeded feasible-witness profiles spanning curve interiors, weather and signed reactive power.',
                               lambda t, status, wx, choices=settings: choices[t], date=f'2026-08-{3 + seed:02d}',
                               offset=(5.5 if seed % 2 else -7), outages=outage_list,
                               initial=('GE1',) if seed % 2 else ('GE2',), weather_fn=lambda t, rows=forecasts: rows[t], shuffle=True))

    for name, outage_list, values, message in [
        ('infeasible_reactive', [outage('GE1'), outage('GE2')], (600, 1300, 500, 0), 'no feasible loading'),
        ('infeasible_towers', [outage('CT1'), outage('CT2')], (600, 100, 500, 1), 'no feasible loading'),
        ('infeasible_missing_ht_sink', [outage('B1'), outage('B2')], (600, 100, 0, 0), 'no feasible loading'),
        ('infeasible_electricity', [], (5000, 100, 1000, 0), 'no feasible loading'),
    ]:
        start = datetime.fromisoformat('2026-07-27').replace(tzinfo=timezone.utc)
        status = dict(date='2026-07-27', running_at_midnight=[], outages=outage_list)
        rows = [dict(zip(['electricity_kw', 'reactive_kvar', 'heat_kw', 'cooling_kw'], values)) for _ in range(48)]
        wx = [dict(wet_bulb_c=18, dry_bulb_c=25, pv_kw=0) for _ in range(48)]
        folder = write_inputs(name, start, status, rows, wx)
        cases.append(dict(name=name, description='Deliberately impossible day must fail without a fictitious plan.',
                          data=str(folder), feasible=False, expected_error=message))
    (ROOT / 'experiments/scenarios.json').write_text(json.dumps(cases, indent=2) + '\n')
    return cases


def run(cases, selected=None, oracle=True, repeats=2):
    results = []
    for case in cases:
        name = case['name']
        if selected and name not in selected:
            continue
        folder = Path(case['data'])
        result = dict(name=name, description=case['description'], expected_feasible=case['feasible'], passed=False)
        began = time.monotonic()
        try:
            times = []
            payloads = []
            for repetition in range(repeats):
                output = folder.parent / ('plan.json' if repetition == 0 else f'plan_repeat_{repetition}.json')
                if output.exists():
                    output.unlink()
                started = time.monotonic()
                completed = subprocess.run([sys.executable, str(ROOT / 'app/dispatch.py'), '--data', str(folder), '--output', str(output)],
                                           text=True, capture_output=True, timeout=120)
                times.append(time.monotonic() - started)
                if case['feasible']:
                    assert completed.returncode == 0, completed.stderr
                    payloads.append(output.read_bytes())
                    validation = check(folder, output)
                    result['verification'] = validation
                else:
                    assert completed.returncode != 0
                    assert case['expected_error'] in completed.stderr, completed.stderr
                    assert not output.exists()
            result['application_seconds'] = times
            if case['feasible']:
                assert len(set(payloads)) == 1, 'plan is not byte-identical across runs'
                result['plan_sha256'] = hashlib.sha256(payloads[0]).hexdigest()
                result['byte_identical_repetitions'] = repeats
                plan = json.loads(payloads[0])
                if name == 'short_dip_keep_running':
                    assert plan['periods'][2]['engines_kwe']['GE2'] > 0, 'short economic dip should not cause restart'
                    assert plan['summary']['engine_starts'] == 0
                if name == 'long_dip_restart':
                    assert all(plan['periods'][t]['engines_kwe']['GE2'] == 0 for t in range(2, 12))
                    assert plan['summary']['engine_starts'] == 1
                if oracle:
                    result['optimality'] = certify(folder, plan['summary']['cost_gbp'], maximum_seconds=90)
                    assert result['optimality']['certified'], result['optimality']
                witness_file = folder.parent / 'feasible_witness.json'
                if witness_file.exists():
                    witness_cost = json.loads(witness_file.read_text())['summary']['cost_gbp']
                    assert plan['summary']['cost_gbp'] <= witness_cost + 0.0002
                    result['witness_cost_gbp'] = witness_cost
                    result['improvement_over_witness_gbp'] = witness_cost - plan['summary']['cost_gbp']
            result['passed'] = True
        except Exception as exc:
            result['error'] = str(exc)
        result['total_seconds'] = time.monotonic() - began
        (folder.parent / 'check_result.json').write_text(json.dumps(result, indent=2) + '\n')
        results.append(result)
        print(json.dumps({key: result[key] for key in ('name', 'passed', 'total_seconds')}
                         | ({'error': result['error']} if 'error' in result else {})), flush=True)
    report = dict(passed=all(r['passed'] for r in results), scenarios=len(results), results=results)
    (ROOT / 'experiments/experiment_results.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--only', nargs='*')
    parser.add_argument('--no-oracle', action='store_true')
    parser.add_argument('--repeats', type=int, default=2)
    args = parser.parse_args()
    cases = generate()
    report = run(cases, selected=args.only, oracle=not args.no_oracle, repeats=args.repeats)
    print(json.dumps(dict(passed=report['passed'], scenarios=report['scenarios'])), flush=True)
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
