"""Evaluate every K test and summarize rule-specific tests, with an outage control."""
from pathlib import Path
import argparse
from datetime import datetime
import json
import os
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[5]
B = Path(__file__).resolve().parent
T = B.parent/'task'
os.environ.update(PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',ECD_TASK=str(T),ECD_RUN_TIMEOUT='120')
sys.path.insert(0,str(ROOT/'tools'))
import eval_energy as E

RULES = {'W':'test_single_connection_direction', 'P':'test_lt_pump_outages',
         'C2':'test_shared_gas_entry', 'C4':'test_phe_primary_water_flow',
         'S':'test_lt_heat_rejection'}
DAYS = ['visible','h1','h2','h3','h4']

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('app',type=Path)
    ap.add_argument('--output',type=Path)
    args = ap.parse_args()
    app = args.app.resolve()
    out = args.output.resolve() if args.output else B/('rules-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    out.mkdir(parents=True,exist_ok=False)
    assert (app/'dispatch.py').is_file(), app
    control = out/'without_old_component_outages'
    shutil.copytree(T,control,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    removed = {}
    for name in DAYS[1:]:
        path = control/'tests/days'/name/'status.json'
        status = json.loads(path.read_text())
        removed[name] = [o for o in status['outages'] if ' ' in o['unit'] and not re.fullmatch(r'LT (?:pump|PHE|radiator) \d+',o['unit'])]
        status['outages'] = [o for o in status['outages'] if o not in removed[name]]
        path.write_text(json.dumps(status,indent=2)+'\n')
    test_names = re.findall(r'^def (test_\w+)\(', (T/'tests/test_plans.py').read_text(),re.M)
    report = {'app':str(app),'task':str(T),'removed_outages':removed,'variants':{}}
    lines = [f'App: {app}']
    for label,task in [('K',T),('without_old_component_outages',control)]:
        E.TASK = task
        result = E.evaluate(app,quiet=True,timeout=120)
        # Canonical pytest imports this variant's reference.py, recomputing its MILP.
        tests = {n:{d:d not in result['failed'].get(n,[]) for d in DAYS} for n in test_names}
        rules = {r:{'test':n,'days':tests[n],'passed':all(tests[n].values())} for r,n in RULES.items()}
        passed = not result['failed'] and not result['errors']
        report['variants'][label] = {'passed':passed,'tests':tests,'rules':rules,**result}
        lines.append(f'{label}: {"PASS" if passed else "FAIL"}')
        for r,row in rules.items():
            bad = [d for d,v in row['days'].items() if not v]
            lines.append(f'  {r} ({row["test"]}): '+('PASS on all days' if not bad else 'FAIL on '+', '.join(bad)))
        if result['errors']:
            lines.append('  Execution errors: '+json.dumps(result['errors'],ensure_ascii=False))
        (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    lines.append('A rule test failing because no plan was produced is an execution/compatibility failure, not a measured physical violation.')
    summary = '\n'.join(lines)+'\n'
    (out/'summary.txt').write_text(summary)
    print(json.dumps(report,indent=2))
    print(summary)
    raise SystemExit(0 if all(v['passed'] for v in report['variants'].values()) else 1)

if __name__ == '__main__':
    main()
