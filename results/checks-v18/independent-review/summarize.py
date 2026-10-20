import sys,json,re,shutil,hashlib
from review_driver import *

def parse_lines(files):
 rows={}
 for file in files:
  for line in file.read_text().splitlines():
   m=re.match(r'^(\S+)\s+(CAUGHT|MISSED)\s+(.*)$',line)
   if not m:continue
   name,caught,rest=m.groups();parts=rest.split('  ',1);tests={}
   for token in parts[0].split('; '):
    if ':' in token:
     t,days=token.split(':',1);tests[t]=days.split(',')
   rows[name]={'caught':caught=='CAUGHT','failed':tests,'errors':parts[1].strip() if len(parts)>1 else '', 'raw':line,'log':str(file.relative_to(OUT))}
 return rows

def summary():
 before=parse_lines(sorted((OUT/'original').glob('mutants-*.log')))
 off=parse_lines(sorted((OUT/'no-inference').glob('mutants-*.log')))
 final=parse_lines([OUT/'after/mutants-all.log']) if (OUT/'after/mutants-all.log').exists() else {}
 release=json.loads((ROOT/'results/checks-v18/RELEASE_STATUS.json').read_text())
 reduced={};changed={};gptdiff={};afterdiff={}
 for name,on in before.items():
  if name not in off:continue
  pairs=lambda row:{(t,d) for t,ds in row['failed'].items() for d in ds}
  a,b=pairs(on),pairs(off[name]);lost=sorted(b-a);gained=sorted(a-b)
  if lost:reduced[name]={'removed_when_inference_on':lost,'added_when_inference_on':gained,'on_test_day_count':len(a),'off_test_day_count':len(b),'on_distinct_days':sorted({d for t,d in a}),'off_distinct_days':sorted({d for t,d in b})}
  if a!=b:changed[name]={'removed':lost,'added':gained}
  expected=release['C']['mutants'][name]['output'].split('  ',1)[0]
  ex={}
  for token in expected.split('; '):
   if ':' in token:
    t,ds=token.split(':',1);ex[t]=ds.split(',')
  if a!=pairs({'failed':ex}):gptdiff[name]={'independent':on['failed'],'GPT_Pro':ex}
  if name in final and (a!=pairs(final[name]) or on['caught']!=final[name]['caught']):afterdiff[name]={'before':on['failed'],'after':final[name]['failed']}
 result={'before':before,'inference_off':off,'after':final,'caught_counts':{k:sum(x['caught'] for x in v.values()) for k,v in [('before',before),('inference_off',off),('after',final)]},'total_counts':{'before':len(before),'inference_off':len(off),'after':len(final)},'reduced_with_inference':reduced,'all_inference_differences':changed,'GPT_Pro_failure_matrix_differences':gptdiff,'threshold_failure_matrix_differences':afterdiff}
 dump(OUT/'mutants-summary.json',result)
 matrix={}
 for phase in ['before','after','v17']:
  matrix[phase]={}
  for file in sorted((OUT/phase).glob('eval-*.json')):
   if file.name.endswith('.command.json'):continue
   row=json.loads(file.read_text());matrix[phase][file.stem.removeprefix('eval-')]={'exit_code':row['exit_code'],'tests':row['tests'],'passed':row['passed'],'failed':list(row['failures']),'execution_errors':row['execution_errors']}
 dump(OUT/'evaluation-matrix.json',matrix)
 print(json.dumps({'counts':result['caught_counts'],'totals':result['total_counts'],'reduced':reduced,'GPTdiff':gptdiff,'threshold_diff':afterdiff},indent=2))

if __name__=='__main__':summary()
