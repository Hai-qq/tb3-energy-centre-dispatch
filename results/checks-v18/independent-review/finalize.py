import sys,json,time,hashlib
from review_driver import *
from write_report import write_report

def finalize():
 command=OUT/'after/mutants-all.command.json'
 while not command.exists():time.sleep(5)
 meta=json.loads(command.read_text());assert meta['exit_code']==0,meta
 # Write README and copy exact review helper sources, then validate the whole scope.
 write_report()
 initial=json.loads((OUT/'rebuild.json').read_text())['before']
 assert hashes(TASK/'tests/days')==initial
 copyhash=json.loads((OUT/'task-copy-provenance.json').read_text())['copies']['original']['sha256']
 current=hashes(TASK)
 differences=[k for k in sorted(set(copyhash)|set(current)) if current.get(k)!=copyhash.get(k)]
 assert differences==['tests/reference.py'],differences
 assert (TASK/'tests/reference.py').read_text()==threshold((D/'original/tests/reference.py').read_text())
 status=subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)
 diff=subprocess.check_output(['git','diff','--','tasks/'],cwd=ROOT,text=True)
 tracked=subprocess.check_output(['git','diff','--name-only'],cwd=ROOT,text=True).splitlines()
 assert tracked==['tasks/energy-centre-dispatch/tests/reference.py'],tracked
 lines=status.splitlines();assert len(lines)==2,status
 assert ' M tasks/energy-centre-dispatch/tests/reference.py' in lines,status
 assert '?? results/checks-v18/independent-review/' in lines,status
 bytecode=[str(p.relative_to(ROOT)) for base in [TASK,OUT] for p in base.rglob('__pycache__')]
 assert not bytecode,bytecode
 direct=json.loads((OUT/'acceptance/eval-oracle.command.json').read_text());assert direct['exit_code']==0
 (OUT/'git-status.txt').write_text('$ git status --porcelain\n'+status)
 (OUT/'task.diff').write_text('$ git diff -- tasks/\n'+diff)
 result={'command':[sys.executable,str(D/'finalize.py')],'eval_energy_direct_exit_code':direct['exit_code'],'energy_mutants_no_arguments_exit_code':meta['exit_code'],'mutants_caught':41,'mutants_total':41,'git_status':status,'tracked_changes':tracked,'task_tree_differences':differences,'tests_days_hashes_match_initial':True,'reference_exactly_one_threshold_and_comment_replacement':True,'bytecode_directories_in_task_and_new_results':bytecode,'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()}
 dump(OUT/'final-validation.json',result)
 (OUT/'finalize.py').write_text((D/'finalize.py').read_text())
 # Local Markdown links: every referenced local file must exist.
 import re
 missing=[]
 for target in re.findall(r'\]\(([^)]+)\)',(OUT/'README.md').read_text()):
  if not target.startswith(('http:','https:','#')) and not (OUT/target).exists():missing.append(target)
 assert not missing,missing
 print('FINAL VERIFIED',json.dumps(result,indent=2),flush=True)
if __name__=='__main__':finalize()
