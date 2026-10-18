from pathlib import Path
import os, sys, json, subprocess, shutil, hashlib, difflib, importlib.util, time
R=Path(__file__).resolve().parents[3]
O=Path(__file__).resolve().parent
D=Path('/private/tmp/claude-501/-Users-haiy-qq-Desktop----klavis/a70e7eab-ed43-4fbc-8c31-1d0858956a32/scratchpad/codex-v20-review')
PY=Path('/private/tmp/claude-501/-Users-haiy-qq-Desktop----klavis/a70e7eab-ed43-4fbc-8c31-1d0858956a32/scratchpad/codex-v18-verify/venv/bin/python')
ENV=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
D.mkdir(parents=True,exist_ok=True)
def save(name,obj):
 p=O/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def run(name,args,task=None,extra=None):
 env=ENV.copy();tmp=D/('tmp-'+name.split('/')[0]);tmp.mkdir(exist_ok=True);env['TMPDIR']=str(tmp)
 if task:env['ECD_TASK']=str(task)
 else:env.pop('ECD_TASK',None)
 if extra:env.update(extra)
 cmd=[str(a) for a in args];p=O/(name+'.log');p.parent.mkdir(parents=True,exist_ok=True)
 start=time.monotonic()
 with p.open('w') as f:r=subprocess.run(cmd,cwd=R,env=env,stdout=f,stderr=subprocess.STDOUT)
 meta={'command':cmd,'ECD_TASK':str(task) if task else None,'TMPDIR':str(tmp),'env':{k:env[k] for k in ('PYTHONDONTWRITEBYTECODE','OPENBLAS_NUM_THREADS','OMP_NUM_THREADS')},'returncode':r.returncode,'seconds':time.monotonic()-start,'log':str(p.relative_to(O))}
 save(name+'.command.json',meta);print(name,r.returncode,flush=True);return meta

def module(path,name):
 sp=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(sp);sys.modules[name]=m;sp.loader.exec_module(m);return m

def extras(cid):
 # Mutation texts copied verbatim from check_v20.extras; evaluation uses eval_energy/pytest.
 sys.path.insert(0,str(R/'tools'))
 import check_v20
 return check_v20.extras(cid)

def mutations(cid):
 task=R/f'results/checks-v20/candidates/{cid}/task'
 run(f'{cid}/mutants-base',[PY,R/'tools/energy_mutants.py'],task)
 sys.path.insert(0,str(R/'tools'))
 import eval_energy as E
 E.TASK=task
 rows={}
 for name,changes in extras(cid).items():
  app=D/f'{cid}-mutant-{name}';shutil.copytree(task/'solution/app',app)
  for f,old,new in changes:
   p=app/f;s=p.read_text();assert s.count(old)==1,(name,f,s.count(old));p.write_text(s.replace(old,new))
  # use the unmodified eval_energy CLI, including original pytest entry point
  r=run(f'{cid}/mutant-extra-{name}',[PY,R/'tools/eval_energy.py',app],task)
  rows[name]=r
 save(f'{cid}/mutants-extra-summary.json',rows)

if __name__=='__main__':
 os.environ.update({k:ENV[k] for k in ('PYTHONDONTWRITEBYTECODE','OPENBLAS_NUM_THREADS','OMP_NUM_THREADS')})
 if sys.argv[1]=='mutants':mutations(sys.argv[2])
