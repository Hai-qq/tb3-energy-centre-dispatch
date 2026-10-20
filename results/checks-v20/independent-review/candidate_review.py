from run_review import *
import numpy as np
C=['visible','h1','h2','h3','h4']
APPS={'A16':R/'results/v16-trials/ecd16-run2-claude/app','A19':R/'results/v19-trials/ecd19-run2-claude/app'}
def replace(p,old,new):
 s=p.read_text();assert s.count(old)==1,(p,old,s.count(old));p.write_text(s.replace(old,new))
def patch(cid,tag):
 src=APPS[tag];dst=D/f'{cid}-{tag}-rule-only';shutil.copytree(src,dst)
 p=dst/'planner/optimize.py'
 if cid=='c1':
  if tag=='A16':
   replace(p,'    def _solve(self, segs: list[Segment | None], water: _Water) -> Loading | None:', '''    def _solve(self, segs: list[Segment | None], water: _Water) -> Loading | None:
        best = None
        for direction in ((True, False) if self.import_rate < self.tariff.export_rate else (None,)):
            candidate = self._solve_direction(segs, water, direction)
            if candidate is not None and (best is None or _better(
                    (candidate.excess_kva, candidate.cost), (best.excess_kva, best.cost))):
                best = candidate
        return best

    def _solve_direction(self, segs, water, import_only):''')
   replace(p,'        A_eq, b_eq, A_ub, b_ub = [], [], [], []','''        if import_only is True:
            bounds[self.iX] = (0.0, 0.0)
        elif import_only is False:
            bounds[self.iI] = (0.0, 0.0)
        A_eq, b_eq, A_ub, b_ub = [], [], [], []''')
  else:
   replace(p,'def _solve(h: _Half, plant: Plant, tariff: Tariff, run: list[tuple[Engine, Stretch]],','def _solve_direction(h: _Half, plant: Plant, tariff: Tariff, run: list[tuple[Engine, Stretch]],')
   replace(p,'absorbers: list[AbsorptionChiller], excess: bool) -> _Loading | None:', 'absorbers: list[AbsorptionChiller], excess: bool, import_only=None) -> _Loading | None:')
   replace(p,'    A_eq = np.zeros((4, n))','''    if import_only is True:
        bounds[iX] = (0.0, 0.0)
    elif import_only is False:
        bounds[iI] = (0.0, 0.0)
    A_eq = np.zeros((4, n))''')
   needle='def _best(h: _Half, plant: Plant, tariff: Tariff, on: tuple[bool, ...], excess: bool) -> _Loading | None:'
   replace(p,needle,'''def _solve(h, plant, tariff, run, condenser_c, absorbers, excess):
    best = None
    for direction in ((True, False) if h.rate < tariff.export_rate else (None,)):
        candidate = _solve_direction(h, plant, tariff, run, condenser_c, absorbers, excess, direction)
        if candidate is not None and (best is None or candidate.rank < best.rank - 1e-9):
            best = candidate
    return best


'''+needle)
 elif cid=='c2':
  replace(dst/'planner/tariff.py','        gas = supply["gas"]','        gas = supply["gas"]\n        self.review_gas_entry = gas.get("entry")')
  if tag=='A16':
   text='''        entry = tariff.review_gas_entry
        if entry is not None:
            row = np.zeros(n)
            fuel_const = 0.0
            for j, (e, s) in enumerate(zip(plant.engines, segs)):
                if s is not None and e.id in entry["supplies"]:
                    row[self.iP + j] = tariff.billed_gas(s.fuel_slope, e.fuel_basis)
                    fuel_const += tariff.billed_gas(s.fuel_lo - s.fuel_slope * s.lo, e.fuel_basis)
            for j, b in enumerate(plant.boilers):
                if b.id in entry["supplies"]:
                    row[self.iB + j] = tariff.billed_gas(1.0 / b.efficiency, b.fuel_basis)
            put(False, row, entry["maximum_standard_m3_per_hour"] *
                entry["gross_calorific_value_mj_per_standard_m3"] / 3.6 - fuel_const)

'''
   replace(p,'        kq = np.zeros(n)  # reactive power from the generators per kW of their output',text+'        kq = np.zeros(n)  # reactive power from the generators per kW of their output')
  else:
   text='''    entry = tariff.review_gas_entry
    if entry is not None:
        row = np.zeros(n)
        fuel_const = 0.0
        for j, (e, s) in enumerate(run):
            if e.id in entry["supplies"]:
                row[j] = tariff.billed_gas(s.fuel_slope, e.fuel_basis)
                fuel_const += tariff.billed_gas(s.fuel_at_zero, e.fuel_basis)
        for j, b in enumerate(boilers):
            if b.id in entry["supplies"]:
                row[iB + j] = tariff.billed_gas(1.0 / b.efficiency, b.fuel_basis)
        A_ub.append(row)
        b_ub.append(entry["maximum_standard_m3_per_hour"] *
                    entry["gross_calorific_value_mj_per_standard_m3"] / 3.6 - fuel_const)

'''
   replace(p,'    radius = tariff.import_capacity_kva - KVA_MARGIN',text+'    radius = tariff.import_capacity_kva - KVA_MARGIN')
 else:
  pp=dst/'planner/plant.py'
  marker='        self._connect(d["heat_circuits"])' if tag=='A19' else '        recovered = self._read_circuits(d)'
  replace(pp,marker,marker+'''
        self.review_phe_limit = math.inf
        for hx in d.get("heat_exchangers", []):
            circ = d["heat_circuits"][hx["primary_circuit"]]
            self.review_phe_limit = min(self.review_phe_limit,
                hx["primary_maximum_water_flow_kg_per_s"] * hx["water_specific_heat_kj_per_kg_k"] *
                (circ["flow_c"] - circ["return_c"]))''')
  if tag=='A16':replace(p,'bounds[self.iH] = (0.0, None if self.hx_up else 0.0)','bounds[self.iH] = (0.0, plant.review_phe_limit if self.hx_up else 0.0)')
  else:replace(p,'bounds[iH] = (0.0, math.inf if h.exchanger else 0.0)','bounds[iH] = (0.0, plant.review_phe_limit if h.exchanger else 0.0)')
 dif=[]
 for f in sorted(src.rglob('*')):
  if f.is_file() and (dst/f.relative_to(src)).read_bytes()!=f.read_bytes():
   name=str(f.relative_to(src));dif.extend(difflib.unified_diff(f.read_text().splitlines(True),(dst/name).read_text().splitlines(True),fromfile='a/'+name,tofile='b/'+name))
 (O/f'{cid}/{tag}-rule-only.patch').write_text(''.join(dif))
 return dst

def inspect(cid,task,app,kind):
 ref=module(task/'tests/reference.py',f'ref_{cid}_{kind}');rows={}
 for d in C:
  planpath=D/f'{cid}-{kind}-{d}.json'
  rr=run(f'{cid}/{kind}-plan-{d}',[PY,app/'dispatch.py','--data',task/'tests/days'/d,'--output',planpath],task)
  if rr['returncode']:rows[d]={'exit':rr['returncode']};continue
  plan=json.loads(planpath.read_text());day=ref.Day(task/'tests/days'/d);flows=day.true_flows(plan);best=day.least_cost()['cost']
  cost=float(flows['cost'].sum());row={'least_cost_gbp':best,'true_cost_gbp':cost,'delta_gbp':cost-best}
  if cid=='c1':
   im=np.array([p['import_kw'] for p in plan['periods']]);ex=np.array([p['export_kw'] for p in plan['periods']]);net=im-ex
   row.update(simultaneous_periods=int(((im>.5)&(ex>.5)).sum()),direction_on_boundary_periods=int((np.minimum(im,ex)<1e-4).sum()),import_periods=int((im>.5).sum()),export_periods=int((ex>.5).sum()))
   # Holding each actual net dispatch fixed, the relaxed model could add this to both I/X.
   q=day.kvar-flows['engine_kvar'];head=np.sqrt(np.maximum(0,day.import_kva**2-q*q))
   t=np.minimum(np.maximum(head-im,0),np.maximum(day.export_max-ex,0))
   inv=day.import_rate < day.export_rate
   row.update(inverted_price_periods=int(inv.sum()),profitable_relaxed_extra_trade_periods=int((inv&(t>1)).sum()),relaxed_trade_fixed_dispatch_saving_gbp=float((.5*t*np.maximum(day.export_rate-day.import_rate,0)).sum()))
  elif cid=='c2':
   vol=flows['gas_kwh']*2*3.6/day.supply['gas']['entry']['gross_calorific_value_mj_per_standard_m3'];cap=550
   row.update(maximum_sm3_per_hour=float(vol.max()),binding_periods=int((abs(vol-cap)<.01).sum()),over_limit_periods=int((vol>cap+.1).sum()))
  else:
   phe=flows['engine_heat']-flows['ac_heat'];row.update(maximum_phe_kw=float(phe.max()),binding_periods=int((abs(phe-1672)<.01).sum()),over_limit_periods=int((phe>1673).sum()))
  rows[d]=row
 save(f'{cid}/{kind}-cost-binding.json',rows)
 return rows

def candidate(cid):
 task=R/f'results/checks-v20/candidates/{cid}/task';(O/cid).mkdir(exist_ok=True)
 base=R/'tasks/energy-centre-dispatch';diff=[];fields=[]
 def jd(a,b,path=''):
  if type(a)!=type(b):fields.append({'path':path,'before':a,'after':b});return
  if isinstance(a,dict):
   for k in sorted(a.keys()|b.keys()):
    if k not in a or k not in b:fields.append({'path':path+'/'+k,'before':a.get(k),'after':b.get(k)})
    else:jd(a[k],b[k],path+'/'+k)
  elif isinstance(a,list) and len(a)==len(b):
   for i,(x,y) in enumerate(zip(a,b)):jd(x,y,path+f'/{i}')
  elif a!=b:fields.append({'path':path,'before':a,'after':b})
 names=sorted({str(p.relative_to(base/'environment')) for p in (base/'environment').rglob('*') if p.is_file()}|{str(p.relative_to(task/'environment')) for p in (task/'environment').rglob('*') if p.is_file()})
 for n in names:
  a=base/'environment'/n;b=task/'environment'/n
  if not a.exists() or not b.exists() or a.read_bytes()!=b.read_bytes():
   diff.extend(difflib.unified_diff(a.read_text().splitlines(True) if a.exists() else [],b.read_text().splitlines(True) if b.exists() else [],fromfile='formal/'+n,tofile=cid+'/'+n))
   if n.endswith('.json'):jd(json.loads(a.read_text()) if a.exists() else None,json.loads(b.read_text()) if b.exists() else None,n)
 (O/cid/'environment.diff').write_text(''.join(diff));save(f'{cid}/visible-summary.json',{'instruction_identical':(base/'instruction.md').read_bytes()==(task/'instruction.md').read_bytes(),'fields':fields,'environment_file_count':len(names)})
 frozen=R/f'results/checks-v20/blind/{cid}';f=json.loads((frozen/'FREEZE.json').read_text());bad=[]
 for n,h in f['files'].items():
  expected=h if isinstance(h,str) else h['sha256'];p=frozen/n
  if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:bad.append(n)
 save(f'{cid}/freeze.json',{'file_count':len(f['files']),'declared_count':f.get('file_count'),'mismatches':bad,'freeze_sha256':hashlib.sha256((frozen/'FREEZE.json').read_bytes()).hexdigest()})
 run(f'{cid}/oracle-eval',[PY,R/'tools/eval_energy.py',task/'solution/app'],task)
 inspect(cid,task,task/'solution/app','oracle')
 run(f'{cid}/fresh-16',[PY,R/'tools/fresh_days.py','--days','16','--seed','2026','--output',D/f'{cid}-fresh-16',task/'solution/app'],task)
 shutil.copy(D/f'{cid}-fresh-16/manifest.json',O/cid/'fresh-manifest.json')
 for tag,app in APPS.items():
  run(f'{cid}/{tag}-original',[PY,R/'tools/eval_energy.py',app],task)
  patched=patch(cid,tag)
  run(f'{cid}/{tag}-rule-only',[PY,R/'tools/eval_energy.py',patched],task)
 run(f'{cid}/blind-original',[PY,R/'tools/eval_energy.py',frozen/'app'],task)
 clean=D/f'{cid}-whole-unit-outages-task';shutil.copytree(task,clean)
 removed={}
 for d in C[1:]:
  p=clean/'tests/days'/d/'status.json';s=json.loads(p.read_text());removed[d]=[o for o in s['outages'] if ' ' in o['unit']];s['outages']=[o for o in s['outages'] if ' ' not in o['unit']];p.write_text(json.dumps(s,indent=2)+'\n')
 save(f'{cid}/removed-outages.json',removed)
 run(f'{cid}/blind-whole-unit',[PY,R/'tools/eval_energy.py',frozen/'app'],clean)
 run(f'{cid}/oracle-whole-unit',[PY,R/'tools/eval_energy.py',clean/'solution/app'],clean)
 inspect(cid,clean,clean/'solution/app','oracle-whole-unit')
 inspect(cid,clean,frozen/'app','blind-whole-unit')
if __name__=='__main__':candidate(sys.argv[1])
