"""Certify fixed radiator windows and, if needed, scan same-day replacements."""
from pathlib import Path
import csv
import json
from datetime import datetime, timezone
import numpy as np

B = Path(__file__).resolve().parent
T = B.parent/'task'
result = {}
for folder in sorted((T/'tests/days').iterdir()):
    plant = json.loads((folder/'plant.json').read_text())
    status = json.loads((folder/'status.json').read_text())
    rows = list(csv.DictReader(open(folder/'demand.csv')))
    wx = {datetime.fromisoformat(r['time_utc'].replace('Z', '+00:00')):r for r in csv.DictReader(open(folder/'weather.csv'))}
    dry = np.array([float(wx[datetime.fromisoformat(r['period_start']).astimezone(timezone.utc)]['dry_bulb_c']) for r in rows])
    ahu = np.array([float(r['ahu_heat_kw']) for r in rows])
    circuit = plant['heat_circuits']['ahu_heating']
    f, r = np.array(circuit['flow_c_by_dry_bulb_c']), np.array(circuit['return_c_by_dry_bulb_c'])
    tf, tr = np.interp(dry, f[:,0], f[:,1]), np.interp(dry, r[:,0], r[:,1])
    cap = ahu*np.clip((40-tr)/(tf-tr), 0, 1)
    periods = []
    for t in range(48):
        periods.append({'start': f'{t//2:02d}:{t%2*30:02d}', 'dry_bulb_c':float(dry[t]),
                        'ahu_kw':float(ahu[t]), 'T_f':float(tf[t]), 'T_r':float(tr[t]),
                        'lenient_cap_kw':float(cap[t])})
    windows = []
    for o in status['outages']:
        if not o['unit'].startswith('LT radiator '):
            continue
        eid = next(e['id'] for e in plant['engines'] for c in plant['heat_circuits'].values()
                   if f"{e['id']} intercooler" in c['from'] and o['unit'] in c['to'])
        minimum = next(e['part_load'][0]['lt_heat_kw'] for e in plant['engines'] if e['id']==eid)
        minute = lambda s: int(s[:2])*60+int(s[3:])
        indices = [t for t in range(48) if t*30<minute(o['to']) and t*30+30>minute(o['from'])]
        windows.append({'outage':o, 'engine':eid, 'minimum_lt_kw':minimum,
                        'max_lenient_cap_kw':float(cap[indices].max()),
                        'must_stop':bool((cap[indices]<minimum).all()),
                        'safe_periods':[periods[t]['start'] for t in range(48) if cap[t]<minimum]})
    result[folder.name] = {'periods':periods, 'windows':windows}
(B/'window_probe.json').write_text(json.dumps(result, indent=2)+'\n')
for name, day in result.items():
    print(name, json.dumps(day['windows']))
