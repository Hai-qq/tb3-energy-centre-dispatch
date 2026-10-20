from run_review import *
sys.path.insert(0,str(R/'tools'))
import eval_energy as E
E.TASK=Path(sys.argv[1]);E.DAYS=json.loads(sys.argv[2])
r=E.evaluate(Path(sys.argv[3]));save(Path(sys.argv[4]).relative_to(O),r)
raise SystemExit(1 if r['failed'] or r['errors'] else 0)
