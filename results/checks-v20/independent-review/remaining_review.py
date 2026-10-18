from run_review import *
import numpy as np, math

def formal():
 run('formal/tasks-diff',['git','diff','9db5808','HEAD','--','tasks/'])
 run('formal/fresh-diff',['git','diff','9db5808','HEAD','--','tools/fresh_days.py'])
 sys.path.insert(0,str(R/'tools'));import build_energy_days as B
 task=R/'tasks/energy-centre-dispatch'
 save('formal/default-constants.json',{'plant_matches_generator':B.PLANT==json.loads((task/'environment/data/plant.json').read_text()),'supply_matches_generator':B.SUPPLY==json.loads((task/'environment/data/supply.json').read_text())})
 run('formal/fresh-4',[PY,R/'tools/fresh_days.py','--days','4','--seed','2026','--output',D/'formal-fresh-4',task/'solution/app'])
 shutil.copy(D/'formal-fresh-4/manifest.json',O/'formal/fresh-manifest.json')

def sample():
 src=R/'results/checks-v20/candidates/c1/fuzz-200';task=R/'results/checks-v20/candidates/c1/task';target=D/'c1-sample-25-task';(target/'tests').mkdir(parents=True,exist_ok=True)
 manifest=json.loads((src/'manifest.json').read_text());names=sorted(x['id'] for x in manifest['accepted']);assert len(names)==200
 for item in manifest['accepted']:
  for filename,sha in item['input_hashes'].items():
   assert hashlib.sha256((src/'days'/item['id']/filename).read_bytes()).hexdigest()==sha
 ranks=[round(i*199/24) for i in range(25)];selected=[names[i] for i in ranks]
 shutil.copy(task/'tests/reference.py',target/'tests/reference.py')
 txt=(task/'tests/test_plans.py').read_text();needle='DAYS = ["visible", "h1", "h2", "h3", "h4"]';assert txt.count(needle)==1
 (target/'tests/test_plans.py').write_text(txt.replace(needle,'DAYS = '+repr(selected)))
 for n in selected:shutil.copytree(src/'days'/n,target/'tests/days'/n)
 save('sample/selection.json',{'method':'Sort all 200 accepted directory identifiers numerically; choose zero-based ranks round(i*199/24), i=0..24 (nearest integer, Python round); includes endpoints. No application results used in selection.','ranks_zero_based':ranks,'days':selected})
 apps={'oracle':task/'solution/app','strong-v16':R/'results/v16-trials/ecd16-run2-claude/app','strong-v19':R/'results/v19-trials/ecd19-run2-claude/app','blind':R/'results/checks-v20/blind/c1/app'}
 # eval_energy.evaluate uses its original twice-run CLI loop and original pytest entry point.
 adapter=O/'evaluate_set.py'
 allrows={};summary={}
 for tag,app in apps.items():
  j=O/f'sample/{tag}.json'
  run('sample/'+tag,[PY,adapter,target,json.dumps(selected),app,j],task)
  result=json.loads(j.read_text());rows={}
  for n in selected:
   fs=[test for test,ds in result['failed'].items() if n in ds]
   err={k:v for k,v in result['errors'].items() if k in (n,n+'.rerun')}
   passed=not fs and not err;old=json.loads((src/'runs'/n/tag/'result.json').read_text())
   oldtests=sorted(old['failures']);newtests=sorted(fs)
   rows[n]={'passed':passed,'gpt_pro_passed':old['passed'],'agrees':passed==old['passed'],'failed_tests':newtests,'gpt_pro_failed_tests':oldtests,'errors':err}
  allrows[tag]=rows;summary[tag]={'passed':sum(x['passed'] for x in rows.values()),'failed':sum(not x['passed'] for x in rows.values()),'agreement':sum(x['agrees'] for x in rows.values()),'original_summary':json.loads((src/'summary.json').read_text())['apps'][tag]}
 save('sample/day-comparison.json',allrows);save('sample/summary.json',summary)

def probe():
 rows=[]
 for tag,app in [('A16',R/'results/v16-trials/ecd16-run2-claude/app'),('A19',R/'results/v19-trials/ecd19-run2-claude/app')]:
  for key in list(sys.modules):
   if key=='planner' or key.startswith('planner.'):del sys.modules[key]
  sys.path.insert(0,str(app))
  from planner.data import load_day
  from planner.plant import Plant
  from planner.tariff import Tariff
  from planner.optimize import plan_day
  day=load_day(R/'tasks/energy-centre-dispatch/environment/data')
  for field,value in [('elec',1250),('kvar',450),('heat',2000),('cool',500),('pv',0),('wet_bulb',18),('dry_bulb',24)]:getattr(day,field)[:]=value
  circuits=day.plant['heat_circuits'];del circuits['ge1_lt'];del circuits['ge2_lt']
  circuits['engine_lt']={'flow_c':40,'return_c':35,'from':['GE1 intercooler','GE2 intercooler'],'to':['LT radiator 1','LT radiator 2'],'branches':'parallel, individually isolatable'}
  day.plant['lt_radiators']=[{'id':f'LT radiator {i}','maximum_heat_rejection_kw':220.0} for i in (1,2)]
  day.status['running_at_midnight']=['GE1'];day.status['outages']=[{'unit':'LT radiator 1','from':'12:00','to':'14:00'}]
  started=time.monotonic();periods,starts=plan_day(day,Plant(day.plant),Tariff(day.supply,day.date))
  totals=[sum(float(np.interp(p['engines_kwe'][e['id']],[r['kwe'] for r in e['part_load']],[r['lt_heat_kw'] for r in e['part_load']])) if p['engines_kwe'][e['id']]>0 else 0 for e in day.plant['engines']) for p in periods]
  row={'app':tag,'elapsed_s':time.monotonic()-started,'cost_gbp':sum(p['cost_gbp'] for p in periods),'starts':starts,'period_1200':periods[24],'grid_failed_periods':sum(not p['grid_ok'] for p in periods),'lt_outage_window_kw':totals[24:28],'maximum_lt_kw':max(totals)}
  rows.append(row);save(f'lt/{tag}-periods.json',periods);sys.path.pop(0)
 # Recalculate the witness from unchanged raw engineering data, not literals from the claimed certificate.
 p=json.loads((R/'tasks/energy-centre-dispatch/environment/data/plant.json').read_text());s=json.loads((R/'tasks/energy-centre-dispatch/environment/data/supply.json').read_text());g=p['engines'][0];b=p['boilers'][0];ec=p['electric_chillers'][0]
 def interp(q,key):return float(np.interp(q,[r['kwe'] for r in g['part_load']],[r[key] for r in g['part_load']]))
 ge1=1200.;boiler=785.;cool=500.;lt=interp(ge1,'lt_heat_kw');ht=interp(ge1,'ht_heat_kw');tower=p['cooling_towers'];cw=max(18+tower['approach_k'],tower['min_leaving_water_c']);cop=float(np.interp(cw,*np.array(ec['cop_by_condenser_entering_c']).T));grid=1250+g['auxiliary_kwe']+cool/cop-ge1;pf=g['generator']['power_factor'];q=450-ge1*math.sqrt(1-pf*pf)/pf;cap=2*float(np.interp(18,*np.array(tower['heat_rejection_kw_per_cell_by_wet_bulb_c']).T));loss=p['heat_circuits']['lthw']['loss_kw']
 cert={'lt_kw':lt,'available_lt_capacity_kw':220,'ht_kw':ht,'lthw_delivered_kw':ht+boiler-loss,'electric_cop':cop,'grid_p_kw':grid,'grid_q_kvar':q,'grid_s_kva':math.hypot(grid,q),'tower_kw':cool+cool/cop,'tower_capacity_kw':cap,'condenser_water_c':cw,'checks':{'engine_part_load':g['part_load'][0]['kwe']<=ge1<=g['part_load'][-1]['kwe'],'engine_rating':ge1<=g['rated_kwe'],'generator_rating':ge1/pf<=g['generator']['rated_kva'],'boiler_rating':0<=boiler<=b['max_kw'],'chiller_rating':0<=cool<=ec['max_kw'],'electric_balance':abs(ge1+grid-1250-g['auxiliary_kwe']-cool/cop)<1e-8,'heat_balance':abs(ht+boiler-loss-2000)<1e-8,'cooling_balance':cool==500,'tower_capacity':cool+cool/cop<=cap,'import_capacity':math.hypot(grid,q)<=s['electricity']['import_capacity_kva'],'export_capacity':max(-grid,0)<=s['electricity']['export_limit_kw'],'lt_remaining_capacity':lt<=220,'initial_running_state':day.status['running_at_midnight']==['GE1'],'outage_avoided_by_parallel_branch':day.status['outages']==[{'unit':'LT radiator 1','from':'12:00','to':'14:00'}] and lt<=220},'periods_certified':48,'engines':{'GE1':ge1,'GE2':0},'boilers':{'B1':boiler,'B2':0},'chillers':{'EC1':cool,'EC2':0,'AC1':0}}
 save('lt/witness.json',cert)
 old=json.loads((R/'results/checks-v20/research/shared-lt-root-replay.json').read_text())['records'];diff=[]
 def compare(a,b,path):
  if isinstance(a,dict):
   for k in a:
    if k not in ['elapsed_s','probe']:compare(a[k],b[k],path+'/'+k)
  elif isinstance(a,list):
   for i,(x,y) in enumerate(zip(a,b)):compare(x,y,path+'/'+str(i))
  elif isinstance(a,(int,float)) and not isinstance(a,bool):
   if abs(a-b)>1e-7:diff.append([path,a,b])
  elif a!=b:diff.append([path,a,b])
 for i in (0,1):compare(rows[i],old[i],rows[i]['app'])
 for k in old[2]:
  if k!='certificate':compare(cert[k],old[2][k],'witness/'+k)
 save('lt/replay.json',{'records':rows,'comparison_excluding_runtime':diff,'matches':not diff,'all_witness_checks_pass':all(cert['checks'].values())})
if __name__=='__main__':
 {'formal':formal,'sample':sample,'probe':probe}[sys.argv[1]]()
