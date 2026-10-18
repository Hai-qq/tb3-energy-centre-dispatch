from pathlib import Path
import hashlib, json, shutil, subprocess, sys
R=Path(__file__).resolve().parents[5]
c=sys.argv[1]; root=R/'results/checks-v21/candidates'/c; task=root/'task'; build=root/'build'; base=R/'tasks/energy-centre-dispatch'
sys.path.insert(0,str(task/'tests'))
from reference import Day

def contents(folder):
    return {str(p.relative_to(folder)):p.read_bytes() for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
a,b=contents(base),contents(task)
assert a.keys()==b.keys()
diff=[p for p in a if a[p]!=b[p]]
filename='supply.json' if c=='w' else 'plant.json'
allowed={f'environment/data/{filename}'}
allowed.update(f'tests/days/{d}/{filename}' for d in ['visible','h1','h2','h3','h4'])
allowed.update(['tests/reference.py','tests/test_plans.py', 'solution/app/planner/optimize.py' if c=='w' else 'solution/app/planner/plant.py'])
if c=='p': allowed.update(['tests/days/h1/status.json','tests/days/h3/status.json'])
assert set(diff)==allowed, (set(diff)-allowed,allowed-set(diff))
for rel in [p for p in allowed if p.endswith(filename)]:
    expected=json.loads(a[rel]); actual=json.loads(b[rel])
    if c=='w':
        expected['electricity']['import_rates_p_per_kwh']['weekend'][0]['rate']=5.0
    else:
        for n in (1,2):
            expected['heat_circuits'][f'ge{n}_lt']['pump']=f'LT pump {n}'
            assert list(actual['heat_circuits'][f'ge{n}_lt'])[-1]=='pump'
    assert b[rel]==(json.dumps(expected,indent=2)+'\n').encode(), rel
for rel in ['instruction.md','task.toml','environment/Dockerfile','tests/Dockerfile','tests/test.sh']:
    assert a[rel]==b[rel],rel
report={'passed':True,'changed_files':sorted(diff),'environment_changes':[p for p in diff if p.startswith('environment/')], 'protected_files_unchanged':True}
(build/'gate_a.json').write_text(json.dumps(report,indent=2)+'\n')
print('gate A passed',c,flush=True)
plans=build/'plans'; plans.mkdir(exist_ok=True)
rows=[]
for name in ['visible','h1','h2','h3','h4']:
    path=plans/(name+'.json')
    subprocess.run([sys.executable,str(task/'solution/app/dispatch.py'),'--data',str(task/'tests/days'/name),'--output',str(path)],check=True)
    plan=json.loads(path.read_text()); day=Day(task/'tests/days'/name); optimal=day.least_cost(); flows=day.true_flows(plan)
    total=float(flows['cost'].sum()); gap=total-optimal['cost']
    row={'day':name,'date':str(day.date),'least_cost_gbp':optimal['cost'],'true_flows_cost_gbp':total,'gap_gbp':gap,'passed':abs(gap)<0.001}
    assert row['passed'],row
    rows.append(row); print(row,flush=True)
(build/'costs.json').write_text(json.dumps(rows,indent=2)+'\n')
relaxed=build/'rule-ignored-app'
shutil.copytree(task/'solution/app',relaxed,ignore=shutil.ignore_patterns('__pycache__'), dirs_exist_ok=True)
if c=='w':
    path=relaxed/'planner/optimize.py'; old='directions = (True, False) if tariff.import_rate(day.starts[t]) < tariff.export_rate else (None,)'; new='directions = (None,)'
else:
    path=relaxed/'planner/plant.py'; old='for item in c["to"] + ([c["pump"]] if "pump" in c else []))'; new='for item in c["to"])'
s=path.read_text(); assert s.count(old)==1; path.write_text(s.replace(old,new))
pressure=[]
for name in ['h1'] if c=='w' else ['h1','h3']:
    out=plans/(name+'.rule-ignored.json')
    subprocess.run([sys.executable,str(relaxed/'dispatch.py'),'--data',str(task/'tests/days'/name),'--output',str(out)],check=True)
    plan=json.loads(out.read_text()); fixed=json.loads((plans/(name+'.json')).read_text())
    if c=='w':
        both=[p for p in plan['periods'] if min(p['import_kw'],p['export_kw'])>0.5]
        pressure.append({'day':name,'date':plan['date'],'simultaneous_periods':len(both),'starts':[p['start'] for p in both],'min_import_kw':min(p['import_kw'] for p in both),'min_export_kw':min(p['export_kw'] for p in both)})
        assert len(both)>=6
    else:
        status=json.loads((task/'tests/days'/name/'status.json').read_text()); outage=status['outages'][-1]
        engine='GE1' if name=='h1' else 'GE2'
        def mins(s):
            h,m=map(int,s.split(':')); return h*60+m
        touched=[i for i,p in enumerate(plan['periods']) if mins(p['start'])<mins(outage['to']) and mins(p['start'])+30>mins(outage['from'])]
        row={'day':name,'date':plan['date'],'outage':outage,'engine':engine,'periods':[{ 'start':plan['periods'][i]['start'],'ignored_kwe':plan['periods'][i]['engines_kwe'][engine],'fixed_kwe':fixed['periods'][i]['engines_kwe'][engine]} for i in touched]}
        assert any(x['ignored_kwe']>0.5 for x in row['periods']) and all(x['fixed_kwe']==0.0 for x in row['periods'])
        pressure.append(row)
(build/'rule_pressure.json').write_text(json.dumps(pressure,indent=2)+'\n'); print('pressure',pressure,flush=True)
