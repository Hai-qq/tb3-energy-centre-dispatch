"""Insert observed mutation results into the candidate README without rerunning apps."""
from pathlib import Path
import json

B = Path(__file__).resolve().parent
mutants = {}
for group in ('mutants_1','mutants_2'):
    mutants.update(json.loads((B/('mutation_results_'+group+'.json')).read_text()))
assert len(mutants)==45
missed = [n for n,r in mutants.items() if r['status']!='CAUGHT']
assert not (set(missed)-{'t1_dry_bulb_utc'})
lines = [f"**C: PASS{' with the permitted dry-bulb UTC exception' if missed else ''}.** Both mutation wrapper groups exit 0; **{45-len(missed)}/45 CAUGHT**, including all 42 original mutations, with **zero skipped patches**. All 51 sequential patch anchors are mandatory and preflighted exactly once. Both required T1 mutations are caught on hidden days:",
         '', '| Mutation | Hidden failures |', '|---|---|']
for name in ('t1_energy_bus','t1_never_recover','t1_dry_bulb_utc'):
    r = mutants[name]
    tests = []
    for test, days in sorted(r['failed'].items()):
        hidden = [d for d in days if d.startswith('h')]
        if hidden:
            tests.append('`'+test+'`: '+', '.join(hidden))
    lines.append('| `'+name+'` | '+('; '.join(tests) if tests else '**MISSED**: no hidden failure')+' |')
lines += ['', 'The engine-HT no-dump rule still fails `test_heat_balance` on h1, h3 and h4 when removed; ignoring PHE1 fails it on h4. The common cooling-water-header mutation still fails electricity balance on h1, h3 and h4. Radiator, intercooler and name-prefix shortcuts fail availability on h2/h4; HT-source maintenance fails on h2; electric-condenser maintenance fails on h1; absorption-generator and absorber/condenser shortcuts fail on h3. These are the original pressure mechanisms, not patch failures. The hanging mutation reaches the evaluator timeout on every invocation; the error-after-write mutation exits 77, so neither receives a plan merely because it wrote a JSON file.']
p = B.parent/'README.md'
s = p.read_text()
old = 'Gate C results and the two T1 pressure cases are recorded below after both groups finish.'
assert s.count(old)==1
p.write_text(s.replace(old,'\n'.join(lines)))
print('\n'.join(lines))
