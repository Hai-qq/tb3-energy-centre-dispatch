import os, sys, json, shutil, hashlib, subprocess, time, runpy, importlib.util, platform, shlex
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
ROOT=Path('/Users/haiy_qq/Desktop/工作/klavis')
D=Path(os.environ.get("ECD_REVIEW_WORK", '/private/tmp/claude-501/-Users-haiy-qq-Desktop----klavis/a70e7eab-ed43-4fbc-8c31-1d0858956a32/scratchpad/codex-v18-verify'))
OUT=ROOT/'results/checks-v18/independent-review'
TASK=ROOT/'tasks/energy-centre-dispatch'
ENV=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',TMPDIR=str(D))
os.environ.update(ENV)
sys.dont_write_bytecode=True
PYTHON=str(D/'venv/bin/python')
def dump(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,default=str)+'\n')
def hashes(p):
 return {str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(p.rglob('*')) if f.is_file()}
def run(label,args,task=None):
 env=ENV.copy()
 if task:env['ECD_TASK']=str(task)
 log=OUT/(label+'.log');log.parent.mkdir(parents=True,exist_ok=True)
 cmd=[PYTHON,*map(str,args)];start=time.monotonic()
 with log.open('w') as f:
  f.write('$ '+(('ECD_TASK='+shlex.quote(str(task))+' ') if task else '')+shlex.join(cmd)+'\n');f.flush()
  p=subprocess.run(cmd,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT)
 row={'command':cmd,'ECD_TASK':str(task) if task else None,'exit_code':p.returncode,'seconds':time.monotonic()-start}
 dump(OUT/(label+'.command.json'),row)
 print(label,p.returncode,round(row['seconds'],2),flush=True)
 return row
def apps():
 a={'oracle':TASK/'solution/app','strong-v16-claude':ROOT/'results/v16-trials/ecd16-run2-claude/app'}
 for m in ['claude','codex']:a['patched-v17-'+m]=ROOT/f'results/checks-v18/opponents/ecd17-run2-{m}-parts/app'
 for n in range(1,4):
  for m in ['claude','codex']:a[f'v17-run{n}-{m}']=ROOT/f'results/v17-trials/ecd17-run{n}-{m}/app'
 return a

def observed_eval(label,app,task):
 # Invoke the original entry via runpy. Intercept only subprocess calls to retain
 # timing/output/plans/JUnit before its TemporaryDirectory is cleaned up.
 folder=D/'runs'/label;folder.mkdir(parents=True,exist_ok=True)
 saved_run=subprocess.run;calls=[]
 def observed(cmd,*args,**kwargs):
  start=time.monotonic()
  try:p=saved_run(cmd,*args,**kwargs)
  except subprocess.TimeoutExpired:
   calls.append({'command':cmd,'seconds':time.monotonic()-start,'timeout':True});raise
  row={'command':cmd,'seconds':time.monotonic()-start,'exit_code':p.returncode}
  if '--output' in cmd:
   target=Path(cmd[cmd.index('--output')+1]);stem=target.stem
   (folder/(stem+'.log')).write_text('$ '+shlex.join(cmd)+'\n'+(p.stdout or '')+(p.stderr or ''))
   if target.exists():shutil.copy2(target,folder/target.name)
  elif 'pytest' in cmd:
   (folder/'pytest.log').write_text((p.stdout or '')+(p.stderr or ''))
   for c in cmd:
    if str(c).startswith('--junitxml='):
     shutil.copy2(str(c).split('=',1)[1],folder/'report.xml')
  calls.append(row);return p
 os.environ['ECD_TASK']=str(task)
 subprocess.run=observed
 sys.argv=[str(ROOT/'tools/eval_energy.py'),str(app)]
 rc=0
 try:runpy.run_path(sys.argv[0],run_name='__main__')
 except SystemExit as e:rc=e.code or 0
 finally:subprocess.run=saved_run
 import xml.etree.ElementTree as ET
 cases=list(ET.parse(folder/'report.xml').getroot().iter('testcase'))
 failures={};errors={}
 for case in cases:
  for kind in ['failure','error']:
   e=case.find(kind)
   if e is not None:failures[case.get('name')]={'kind':kind,'message':e.get('message'),'text':e.text}
 for call in calls:
  if '--output' in call['command'] and (call.get('timeout') or call.get('exit_code')):errors[Path(call['command'][call['command'].index('--output')+1]).stem]=call
 dump(OUT/(label+'.json'),{'task':str(task),'app':str(app),'exit_code':rc,'tests':len(cases),'passed':len(cases)-len(failures),'failures':failures,'execution_errors':errors,'calls':calls,'artifacts':str(folder)})
 for name in ['pytest.log','report.xml']:shutil.copy2(folder/name,OUT/(label+'.'+name))
 raise SystemExit(rc)

def prepare():
 assert not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT).strip()
 before=hashes(TASK/'tests/days')
 r=subprocess.run([PYTHON,'tools/build_energy_days.py'],cwd=ROOT,env=ENV,capture_output=True,text=True)
 after=hashes(TASK/'tests/days');status=subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)
 OUT.mkdir(parents=True,exist_ok=False)
 (OUT/'rebuild.log').write_text('$ '+PYTHON+' tools/build_energy_days.py\n'+r.stdout+r.stderr+'git status --porcelain:\n'+status)
 dump(OUT/'rebuild.json',{'exit_code':r.returncode,'before':before,'after':after,'unchanged':before==after,'status':status})
 assert before==after and not status.strip()
 orig=ROOT/'archive/energy-centre-dispatch-v8.1'
 visible={};baseline={}
 for base,result in [(TASK,visible),(orig,baseline)]:
  result['instruction.md']=hashlib.sha256((base/'instruction.md').read_bytes()).hexdigest()
  result.update({'environment/'+k:v for k,v in hashes(base/'environment').items()})
 fixed={f'{day}/{f}':(TASK/'tests/days'/day/f).read_bytes()==(TASK/'environment/data'/f).read_bytes() for day in ['visible','h1','h2','h3','h4'] for f in ['plant.json','supply.json']}
 dump(OUT/'A.json',{'visible':visible,'v8.1':baseline,'same':visible==baseline,'fixed_plant_supply':fixed})
 assert visible==baseline and all(fixed.values())
 (OUT/'v18-source.diff').write_bytes(subprocess.check_output(['git','diff','12a1116','HEAD','--','tasks/','tools/'],cwd=ROOT))
 import numpy,scipy,pytest
 dump(OUT/'runtime.json',{'python':platform.python_version(),'executable':sys.executable,'numpy':numpy.__version__,'scipy':scipy.__version__,'pytest':pytest.__version__,'environment':{k:ENV[k] for k in ['PYTHONDONTWRITEBYTECODE','OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','TMPDIR']}})
 shutil.copy2(D/'pip-install.log',OUT/'pip-install.log')
 for name in ['original','no-inference','threshold-001']:
  target=D/name;shutil.copytree(TASK,target)
  file=target/'tests/reference.py';s=file.read_text()
  if name=='no-inference':
   old='ec_used = float(np.clip(inferred, ec_min, max(ec_min, ec_max)))';assert s.count(old)==1;s=s.replace(old,'ec_used = ec_min')
  if name=='threshold-001':s=threshold(s)
  file.write_text(s)
 print('PREPARED',flush=True)

def threshold(s):
 old='''            # The inlet-temperature requirement applies to any positive AC duty;
            # the rating tolerance must not change the COP regime of other units.
            absorbing = any(float(p["chillers_kw"][a["id"]]) > 1e-9 for a in self.plant["absorption_chillers"])'''
 new='''            # 0.01 kW is above solver numerical noise but far below any
            # meaningful AC duty; the rating tolerance must not change the COP regime.
            absorbing = any(float(p["chillers_kw"][a["id"]]) > 0.01 for a in self.plant["absorption_chillers"])'''
 assert s.count(old)==1;return s.replace(old,new)

def batch(phase):
 jobs=[]
 task=TASK
 for name,app in apps().items():jobs.append((phase+'/eval-'+name,[str(D/'review_driver.py'),'eval',phase+'/eval-'+name,str(app),str(task)],task))
 if phase=='before':
  for name,app in apps().items():
   if name.startswith(('strong','patched')):jobs.append(('v17/eval-'+name,[str(D/'review_driver.py'),'eval','v17/eval-'+name,str(app),str(ROOT/'archive/energy-centre-dispatch-v17')],ROOT/'archive/energy-centre-dispatch-v17'))
  for seed in [2026,2403,87123]:jobs.append((f'fresh-{seed}', ['tools/fresh_days.py','--days','16','--seed',str(seed),'--output',str(D/f'fresh-{seed}'),str(TASK/'solution/app')],None))
  sys.path.insert(0,str(ROOT/'tools'));import energy_mutants as M
  names=list(M.MUTANTS)
  for mode in ['original','no-inference']:
   for shard in range(4):jobs.append((f'{mode}/mutants-{shard}', ['tools/energy_mutants.py',*names[shard::4]],D/mode))
 else:jobs.append(('after/mutants-all',['tools/energy_mutants.py'],TASK))
 with ThreadPoolExecutor(max_workers=4) as pool:
  fs=[pool.submit(run,*job) for job in jobs]
  for f in as_completed(fs):f.result()
 if phase=='before':
  for seed in [2026,2403,87123]:shutil.copy2(D/f'fresh-{seed}/manifest.json',OUT/f'fresh-{seed}.manifest.json')
 print('BATCH DONE '+phase,flush=True)

if __name__=='__main__':
 mode=sys.argv[1]
 if mode=='prepare':prepare()
 elif mode=='eval':observed_eval(sys.argv[2],Path(sys.argv[3]),Path(sys.argv[4]))
 elif mode=='batch':batch(sys.argv[2])
