"""Build-only boundary checks; no extra hidden grading test is introduced."""
from pathlib import Path
import csv
import json
import shutil
import sys
import tempfile
import numpy as np

B = Path(__file__).resolve().parent
T = B.parent/'task'
sys.path.insert(0, str(T/'tests'))
from reference import Day
sys.path.insert(0, str(T/'solution/app'))
from planner.plant import Plant

results = []
with tempfile.TemporaryDirectory(prefix='t1-model-') as tmp:
    folder = Path(tmp)/'day'
    shutil.copytree(T/'tests/days/visible', folder)
    status = json.loads((folder/'status.json').read_text())
    status['outages'] = []
    (folder/'status.json').write_text(json.dumps(status))
    weather = list(csv.DictReader(open(folder/'weather.csv')))
    for dry, expected_f, expected_r, expected_fraction, expected_strict in (
            (-10.0,55.0,45.0,0.0,0.0), (2.0,50.0,45-5*16/21,0.0,0.0),
            (10.0,42.0,45-13*16/21,(40-(45-13*16/21))/(42-(45-13*16/21)),0.0),
            (17.0,35.0,45-20*16/21,1.0,1.0), (24.0,34.0,29.0,1.0,1.0)):
        for r in weather:
            r['dry_bulb_c'] = str(dry)
        with (folder/'weather.csv').open('w', newline='') as f:
            w=csv.DictWriter(f,list(weather[0])); w.writeheader(); w.writerows(weather)
        day = Day(folder)
        plant = Plant(day.plant)
        assert np.allclose(day.ahu_flow_c, expected_f)
        assert np.allclose(day.ahu_return_c, expected_r)
        assert np.allclose(day.ahu_len_fraction, expected_fraction)
        assert np.allclose(day.ahu_strict_cap, day.ahu*expected_strict)
        assert plant.ahu_recovery_fraction(dry,40.0) == expected_strict
        results.append({'dry_bulb_c':dry,'T_f':expected_f,'T_r':expected_r,
                        'lenient_fraction':expected_fraction,'strict_fraction':expected_strict})

    # Isolate topology and actual segment interpolation from planner choices.
    day = Day(folder)
    periods = []
    for t in range(48):
        periods.append({'engines_kwe':{e['id']:750.0 if i==0 else 0.0 for i,e in enumerate(day.engines)},
                        'boilers_kw':{b['id']:0.0 for b in day.plant['boilers']},
                        'chillers_kw':{c['id']:0.0 for k in ('electric_chillers','absorption_chillers') for c in day.plant[k]},
                        'pv_kw':0.0,'import_kw':0.0,'export_kw':0.0})
    plan = {'periods':periods}
    f = day.true_flows(plan)
    expected_lt = 118+(158-118)*(750-600)/(900-600)
    assert np.allclose(f['lt_heat'],expected_lt)
    assert np.allclose(f['R_len'],np.minimum(day.ahu,expected_lt))
    phe = day.lt_routes[day.engines[0]['id']][1][0]
    status['outages'] = [{'unit':phe,'from':'00:10','to':'00:20'}]
    (folder/'status.json').write_text(json.dumps(status))
    day = Day(folder)
    f = day.true_flows(plan)
    assert day.available[day.engines[0]['id']].all(), 'PHE outage leaves radiator available'
    assert f['R_len'][0]==0.0 and f['R_strict'][0]==0.0
    assert f['R_len'][1]>0.0
    results.append({'available_PHE_only':True,'part_load_LT_interpolation_kw':expected_lt,
                    'off_engine_LT_kw':0.0,'PHE_outage_blocks_recovery_only':True})

(B/'model_checks.json').write_text(json.dumps({'passed':True,'checks':results},indent=2)+'\n')
print(json.dumps({'passed':True,'checks':results},indent=2))
