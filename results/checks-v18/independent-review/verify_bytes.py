from pathlib import Path
import json
ROOT=Path('/Users/haiy_qq/Desktop/工作/klavis')
OUT=ROOT/'results/checks-v18/independent-review'
TASK=ROOT/'tasks/energy-centre-dispatch'
ARCHIVE=ROOT/'archive/energy-centre-dispatch-v8.1'
record=json.loads((OUT/'A.json').read_text())
checks={name:(TASK/name).read_bytes()==(ARCHIVE/name).read_bytes() for name in record['visible']}
assert all(checks.values())
record['literal_byte_comparison']=checks
(OUT/'A.json').write_text(json.dumps(record,indent=2)+'\n')
print('Literal byte comparison:',len(checks),'of',len(checks),'identical.')
