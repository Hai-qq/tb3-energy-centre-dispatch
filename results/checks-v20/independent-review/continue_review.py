from run_review import *
# Sequential fourth group; three mutation groups may run alongside it.
for c in ['c2','c4']:
 run(c+'-driver',[PY,O/'candidate_review.py',c])
for phase in ['formal','sample','probe']:
 run(phase+'-driver',[PY,O/'remaining_review.py',phase])
