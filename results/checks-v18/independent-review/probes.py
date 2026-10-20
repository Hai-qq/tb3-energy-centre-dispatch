import sys, json, importlib.util, copy, shutil, math, subprocess
from pathlib import Path
from review_driver import ROOT,D,OUT,TASK,ENV,PYTHON,dump,run,threshold
import numpy as np

def load(task,tag):
 spec=importlib.util.spec_from_file_location(tag,task/'tests/reference.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def costs(phase):
 task={'before':D/'original','after':TASK,'v17':ROOT/'archive/energy-centre-dispatch-v17'}[phase]
 R=load(task,'cost_'+phase);rows={}
 for n in ['visible','h1','h2','h3','h4']:
  day=R.Day(task/'tests/days'/n);plan=json.loads((D/'runs'/phase/'eval-oracle'/f'{n}.json').read_text())
  best=day.least_cost();cost=float(day.true_flows(plan)['cost'].sum())
  timings=json.loads((OUT/phase/'eval-oracle.json').read_text())['calls']
  ts=[c['seconds'] for c in timings if '--data' in c['command'] and Path(c['command'][c['command'].index('--data')+1]).name==n]
  rows[n]={'milp_gbp':best['cost'],'recomputed_plan_gbp':cost,'plan_minus_milp_gbp':cost-best['cost'],'max_cli_seconds':max(ts),'within_0001':abs(cost-best['cost'])<.001}
  print(phase,n,rows[n],flush=True)
 dump(OUT/f'{phase}/costs.json',rows)

def updated_report(day,p):
 f=day.true_flows(p)
 for t,row in enumerate(p['periods']):
  row['gas_kwh']=float(f['gas_kwh'][t]);row['cost_gbp']=float(f['cost'][t]);row['grid_ok']=bool(math.hypot(row['import_kw'],day.kvar[t]-f['engine_kvar'][t])<=day.import_kva)
 p['summary'].update(gas_kwh=float(f['gas_kwh'].sum()),cost_gbp=float(f['cost'].sum()),engine_starts=f['starts'],import_kwh=.5*sum(x['import_kw'] for x in p['periods']),export_kwh=.5*sum(x['export_kw'] for x in p['periods']),grid_ok=all(x['grid_ok'] for x in p['periods']))
 return f

def power(day,row,temp):
 return sum(row['chillers_kw'][c['id']]/np.interp(temp,*np.array(c['cop_by_condenser_entering_c']).T) for c in day.plant['electric_chillers'])

def grid(day,p,t,temp,extra=0):
 row=p['periods'][t]
 aux=sum(e['auxiliary_kwe'] for e in day.engines if row['engines_kwe'][e['id']]>.5)+sum(row['chillers_kw'][a['id']]*a['auxiliary_kwe_per_kw'] for a in day.plant['absorption_chillers'])
 net=day.elec[t]+aux+power(day,row,temp)+extra-sum(row['engines_kwe'].values())-row['pv_kw']
 row['import_kw']=float(max(net,0));row['export_kw']=float(max(-net,0))

def check_plan(label,task,n,p,alltests=False):
 folder=D/'probe-plans'/label;folder.mkdir(parents=True,exist_ok=True)
 dump(folder/f'{n}.json',p);dump(folder/f'{n}.rerun.json',p)
 env=dict(ENV,PLANS_DIR=str(folder));log=OUT/'probes'/(label+'.log');log.parent.mkdir(exist_ok=True,parents=True)
 xml=OUT/'probes'/(label+'.xml')
 tests=task/'tests/test_plans.py'
 cmd=[PYTHON,'-m','pytest','-q','-p','no:cacheprovider',f'--junitxml={xml}',str(tests)]
 if alltests:cmd+=['-k',n]
 else:cmd[-1]+=f'::test_electricity_balance[{n}]'
 with log.open('w') as f:
  import shlex
  f.write('$ PLANS_DIR='+str(folder)+' '+shlex.join(cmd)+'\n');f.flush()
  r=subprocess.run(cmd,cwd=task/'tests',env=env,stdout=f,stderr=subprocess.STDOUT)
 import xml.etree.ElementTree as ET
 cases=list(ET.parse(xml).getroot().iter('testcase'))
 failed=[c.get('name') for c in cases if c.find('failure') is not None or c.find('error') is not None]
 return {'command':cmd,'PLANS_DIR':str(folder),'exit_code':r.returncode,'tests':len(cases),'failed':failed}

def probes():
 before=D/'original';after=D/'threshold-001';R=load(before,'probe_before');A=load(after,'probe_after')
 plans={n:json.loads((D/'runs/before/eval-oracle'/f'{n}.json').read_text()) for n in ['visible','h1','h2','h3','h4']}
 day=R.Day(before/'tests/days/h3');candidates=[t for t,p in enumerate(plans['h3']['periods']) if day.cewt[False][t]==21 and p['chillers_kw']['AC1']==0 and day.available['AC1'][t]]
 t=max(candidates,key=lambda t:sum(plans['h3']['periods'][t]['chillers_kw'].values()))
 rows={'selected_day':'h3','period':plans['h3']['periods'][t]['start'],'natural_cewt_c':float(day.cewt[False][t]),'original_chillers_kw':plans['h3']['periods'][t]['chillers_kw'],'threshold':{},'warm_header':{}}
 for name,q,temp,expect in [('ac04_cold',.4,21,[1,1]),('ac_noise_cold',3e-8,21,[1,0]),('ac0005_warm',.005,22,[0,0])]:
  p=copy.deepcopy(plans['h3']);row=p['periods'][t];row['chillers_kw']['AC1']=q;row['chillers_kw']['EC1']-=q
  grid(day,p,t,temp);updated_report(day,p)
  result={}
  for label,task,mod in [('before',before,R),('after',after,A)]:
   result[label]=check_plan(name+'-'+label,task,'h3',p)
   d=mod.Day(task/'tests/days/h3');f=d.true_flows(p)
   residual=sum(row['engines_kwe'].values())+row['pv_kw']+row['import_kw']-row['export_kw']-d.elec[t]-f['aux'][t]-f['ec_elec'][t]
   result[label]['residual_kw']=float(residual)
  result.update(ac1_kw=q,cop_temperature_c=temp,expected_exit_codes=expect,cooling_kw=float(sum(row['chillers_kw'].values())),demand_cooling_kw=float(day.cool[t]))
  result['matches_expected']=[result[k]['exit_code'] for k in ['before','after']]==expect
  rows['threshold'][name]=result
 # Warm interval at same large-EC cold period.
 for name,extra in [('a_within_interval',5),('b_below_minimum',-5)]:
  p=copy.deepcopy(plans['h3']);grid(day,p,t,21,extra);f=updated_report(day,p)
  result=check_plan(name,before,'h3',p,alltests=True)
  r=p['periods'][t];ecmin=power(day,r,21);ecmax=sum(max(r['chillers_kw'][c['id']],0)/c['cop_by_condenser_entering_c'][-1][1] for c in day.plant['electric_chillers'])
  result.update(ec_min_kw=float(ecmin),ec_max_kw=float(ecmax),inferred_kw=float(ecmin+extra),used_kw=float(f['ec_elec'][t]),cost_gbp=float(f['cost'].sum()))
  rows['warm_header'][name]=result
 # Use a genuine oracle period with every electric chiller off; cooling unchanged.
 n='h1';d=R.Day(before/'tests/days'/n);p=copy.deepcopy(plans[n]);j=next(i for i,r in enumerate(p['periods']) if all(r['chillers_kw'][c['id']]==0 for c in d.plant['electric_chillers']))
 p['periods'][j]['import_kw']+=5;updated_report(d,p)
 result=check_plan('c_zero_ec',before,n,p,alltests=True);result.update(day=n,period=p['periods'][j]['start'],chillers_kw=p['periods'][j]['chillers_kw']);rows['warm_header']['c_zero_ec']=result
 dump(OUT/'probes/results.json',rows)
 assert all(x['matches_expected'] for x in rows['threshold'].values()),rows
 assert not rows['warm_header']['a_within_interval']['failed']
 for key in ['b_below_minimum','c_zero_ec']:assert any(x.startswith('test_electricity_balance') for x in rows['warm_header'][key]['failed'])
 # PV union and HT names, using otherwise identical actual-day inputs.
 fixes={}
 for label,outages in [('pv-union',[{'unit':'PV1','from':'12:05','to':'12:15'},{'unit':'PV1','from':'12:10','to':'12:20'}]),('ht-name',[{'unit':'GE1 jacket water and exhaust','from':'12:05','to':'12:20'}])]:
  target=D/'fixture-days'/label;shutil.copytree(before/'tests/days/h3',target)
  status=json.loads((target/'status.json').read_text());status['outages']=outages;dump(target/'status.json',status)
  dd=R.Day(target);j=dd.clock.index(720)
  if label=='pv-union':
   clear=R.Day(before/'tests/days/h3');forecast=float(clear.pv_max[j]);expected=forecast*(1-15/30)
   fixes[label]={'forecast_kw':forecast,'expected_pv_max_kw':expected,'observed_pv_max_kw':float(dd.pv_max[j]),'passed':bool(abs(dd.pv_max[j]-expected)<1e-12)}
  else:fixes[label]={'loaded_without_KeyError':True,'GE1_available_at_1200':bool(dd.available['GE1'][j]),'unavailable_periods':[int(x) for x in np.where(~dd.available['GE1'])[0]],'passed':not bool(dd.available['GE1'][j])}
  fixes[label]['status']=status
 dump(OUT/'probes/reference-fixes.json',fixes);assert all(x['passed'] for x in fixes.values())
 print(json.dumps(rows,indent=2),flush=True);print('PROBES PASSED',flush=True)

if __name__=='__main__':
 if sys.argv[1]=='costs':costs(sys.argv[2])
 else:probes()
