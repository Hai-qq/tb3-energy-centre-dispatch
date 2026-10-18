from run_review import *
import re, platform
import numpy, scipy, pytest
checks={}
def check(name,value,detail=None):
 checks[name]={'pass':bool(value),'detail':detail};assert value,(name,detail)
def read(p):return json.loads((O/p).read_text())
check('branch',subprocess.check_output(['git','branch','--show-current'],cwd=R,text=True).strip()=='v20-gptpro')
check('head',subprocess.check_output(['git','rev-parse','--short','HEAD'],cwd=R,text=True).strip()=='e903a50')
check('tracked_files_unchanged',subprocess.run(['git','diff','--exit-code','HEAD','--'],cwd=R,capture_output=True).returncode==0)
status=subprocess.check_output(['git','status','--porcelain'],cwd=R,text=True);(O/'git-status.log').write_text(status)
check('git_status_only_delivery',status=='?? results/checks-v20/independent-review/\n',status)
check('formal_tasks_unchanged',subprocess.check_output(['git','diff','9db5808','HEAD','--','tasks/'],cwd=R)==b'')
check('formal_fresh_pass',read('formal/fresh-4.command.json')['returncode']==0)
check('fresh_default_constants',all(read('formal/default-constants.json').values()))
for c in ['c1','c2','c4']:
 t=R/f'results/checks-v20/candidates/{c}/task';bl=R/f'results/checks-v20/blind/{c}'
 fr=json.loads((bl/'FREEZE.json').read_text());bad=[]
 for n,h in fr['files'].items():
  expected=h if isinstance(h,str) else h['sha256']
  if hashlib.sha256((bl/n).read_bytes()).hexdigest()!=expected:bad.append(n)
 check(c+'_freeze_post_run',not bad,{'count':len(fr['files']),'mismatches':bad})
 for tag in ['oracle-eval','fresh-16','A16-rule-only','A19-rule-only','blind-whole-unit','oracle-whole-unit']:
  m=read(c+'/'+tag+'.command.json');check(c+'_'+tag,m['returncode']==0)
 for tag in ['A16-original','A19-original','blind-original']:
  check(c+'_'+tag,read(c+'/'+tag+'.command.json')['returncode']==1)
 oc=read(c+'/oracle-cost-binding.json');check(c+'_oracle_0.001',all(abs(x['delta_gbp'])<.001 for x in oc.values()))
 text=(O/c/'mutants-base.log').read_text();caught=re.findall(r'^(\S+)\s+CAUGHT\b',text,re.M)
 check(c+'_base_42_mutants',len(caught)==42 and len(set(caught))==42 and 'MISSED' not in text and 'Traceback' not in text,len(caught))
 check(c+'_base_mutant_exit',read(c+'/mutants-base.command.json')['returncode']==0)
 ex=read(c+'/mutants-extra-summary.json');check(c+'_extra_mutants',len(ex)==(1 if c=='c1' else 2) and all(x['returncode']==1 for x in ex.values()))
 clean=D/f'{c}-whole-unit-outages-task';diff=[]
 for p in t.rglob('*'):
  if p.is_file() and p.read_bytes()!=(clean/p.relative_to(t)).read_bytes():diff.append(str(p.relative_to(t)))
 check(c+'_isolated_changed_only_status',set(diff)=={f'tests/days/h{i}/status.json' for i in range(1,5)},diff)
 for i in range(1,5):
  a=json.loads((t/f'tests/days/h{i}/status.json').read_text());b=json.loads((clean/f'tests/days/h{i}/status.json').read_text());a['outages']=[o for o in a['outages'] if ' ' not in o['unit']]
  check(c+f'_h{i}_only_removed_space_names',a==b)
 check(c+'_instruction',read(c+'/visible-summary.json')['instruction_identical'])
 check(c+'_test_function_count',len(re.findall(r'^def test_', (t/'tests/test_plans.py').read_text(), re.M))==12)
 fm=read(c+'/fresh-manifest.json');check(c+'_fresh16_manifest',len(fm['days'])==16 and fm['input_hashes_unchanged_after_evaluation'] and all(not x['failed'] and not x['errors'] for x in fm['results'].values()))
 if c!='c1':check(c+'_h2_new_rule_binding',read(c+'/oracle-whole-unit-cost-binding.json')['h2']['binding_periods']>0)
 else:check(c+'_all_hidden_direction_economic_pressure',all(x['profitable_relaxed_extra_trade_periods']>0 for d,x in read(c+'/oracle-whole-unit-cost-binding.json').items() if d!='visible'))
 for tag in ['A16','A19']:check(c+'_'+tag+'_patch_exists',(O/c/(tag+'-rule-only.patch')).stat().st_size>0)
check('25_days_selected',len(read('sample/selection.json')['days'])==25)
check('all_100_sample_agreements',all(x['agrees'] for rows in read('sample/day-comparison.json').values() for x in rows.values()))
check('sample_all_days_replayed',all(len(rows)==25 for rows in read('sample/day-comparison.json').values()))
check('LT_replay_matches',read('lt/replay.json')['matches'])
check('LT_witness',all(read('lt/witness.json')['checks'].values()))
check('LT_48_periods',all(len(read(f'lt/{tag}-periods.json'))==48 for tag in ['A16','A19']))
cache=[str(p.relative_to(R)) for p in R.rglob('__pycache__') if p.is_dir()]
inventory=read('preexisting-cache-inventory.json')
check('only_preexisting_jobs_pycache',set(cache)=={x['path'] for x in inventory['directories']} and all(x['predates_review_creation'] and x['path'].startswith('jobs/') for x in inventory['directories']),inventory)
start=inventory['review_script_creation']
check('no_new_bytecode_cache',all(max([p.stat().st_mtime,p.stat().st_birthtime]+[max(f.stat().st_mtime,f.stat().st_birthtime) for f in p.rglob('*') if f.is_file()])<start for p in (R/x for x in cache)))
text=(O/'README.md').read_text();check('README_sections',all(s in text for s in ['## 1.','## 2. C1','## 2. C2','## 2. C4','## 3.','## 4.','不一致']) and all(text.count('### 2'+x+'.')==3 for x in 'abcdef'))
missing=[]
for dest in re.findall(r'\]\(([^)]+)\)',text):
 if not dest.startswith(('http:','https:','#')) and not (O/dest).exists():missing.append(dest)
# validation.json is written below, so it is expected to be absent on the first validation.
missing=[x for x in missing if x!='validation.json']
check('README_links',not missing,missing)
versions={'python':platform.python_version(),'numpy':numpy.__version__,'scipy':scipy.__version__,'pytest':pytest.__version__}
check('specified_versions',versions=={'python':'3.13.5','numpy':'2.3.4','scipy':'1.17.0','pytest':'9.1.1'},versions)
save('validation.json',{'all_passed':True,'checks':checks,'versions':versions,'git_status':status,'scratch_directory':str(D)})
print(json.dumps({'all_passed':True,'checks':len(checks),'versions':versions,'git_status':status},indent=2))
