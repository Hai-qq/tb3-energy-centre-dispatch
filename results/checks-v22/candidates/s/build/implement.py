"""Reproduce the candidate-only source edits from the copied v19 package."""
from pathlib import Path
import json
import shutil

ROOT = Path(__file__).resolve().parents[5]
TASK = Path(__file__).resolve().parents[1] / 'task'
SOURCE = Path('/private/tmp/claude-501/-Users-haiy-qq-Desktop----klavis/a70e7eab-ed43-4fbc-8c31-1d0858956a32/scratchpad/v22-prechecks/s/visible/app/data/plant.json')
base = ROOT / 'tasks/energy-centre-dispatch'
assert all(p.read_bytes() == (base/'environment/data/plant.json').read_bytes()
           for p in (base/'tests/days').glob('*/plant.json'))
for p in [TASK/'environment/data/plant.json', *(TASK/'tests/days').glob('*/plant.json')]:
    shutil.copyfile(SOURCE, p)

def edit(rel, old, new):
    p = TASK / rel
    s = p.read_text()
    assert s.count(old) == 1, (rel, old)
    p.write_text(s.replace(old, new))

edit('solution/app/planner/plant.py',
     '        self.min_kwe = float(self.kwe[0])',
     '        self.lt_heat_kw = np.array([p["lt_heat_kw"] for p in pts], dtype=float)\n'
     '        self.min_kwe = float(self.kwe[0])')
edit('solution/app/planner/plant.py', '        self.boilers = [Boiler(x) for x in d["boilers"]]', '''        # Secondary rejection circuits receive the outlets of the engine LT circuits.
        radiators = {r["id"]: float(r["max_kw"]) for r in d.get("lt_radiators", [])}
        self.lt_rejection = {}
        for name, circuit in d["heat_circuits"].items():
            sources = tuple(e.id for e in self.engines
                            if set(self.engine_lt_sinks[e.id]) & set(circuit["from"]))
            sinks = {item: radiators[item] for item in circuit["to"] if item in radiators}
            if sources and sinks:
                self.lt_rejection[name] = (sources, sinks)
        self.boilers = [Boiler(x) for x in d["boilers"]]''')
edit('solution/app/planner/optimize.py', '    # electricity: generation + import - export = building + plant auxiliaries + chillers', '''    # LT heat from each engine's current segment shares the in-service radiator capacity.
    for sources, sinks in plant.lt_rejection.values():
        row = np.zeros(n)
        offset = 0.0
        for j, (e, piece) in enumerate(zip(engines, pieces)):
            if e.id in sources:
                low, high = piece[:2]
                qlow, qhigh = np.interp([low, high], e.kwe, e.lt_heat_kw)
                slope = (qhigh - qlow) / (high - low)
                row[j] = slope
                offset += qlow - slope * low
        capacity = sum(kw for item, kw in sinks.items()
                       if _available(day, item, day.starts[t]))
        A_ub.append(row)
        b_ub.append(capacity - offset)
    # electricity: generation + import - export = building + plant auxiliaries + chillers''')
edit('tests/reference.py', '        self.curve, self.q_per_kw = {}, {}',
     '        self.lt_curve = {e["id"]: np.array([p["lt_heat_kw"] for p in e["part_load"]], dtype=float)\n'
     '                         for e in self.engines}\n        self.curve, self.q_per_kw = {}, {}')
edit('tests/reference.py', '        self.running0 = set(self.status["running_at_midnight"])', '''        # Trace engine intercooler -> primary LT outlet -> secondary rejection circuit.
        radiators = {r["id"]: float(r["max_kw"]) for r in self.plant.get("lt_radiators", [])}
        self.lt_sources, self.lt_capacity = {}, {}
        for name, circuit in self.plant["heat_circuits"].items():
            sources = []
            for e in self.engines:
                outlets = {item for c in circuits if f"{e['id']} intercooler" in c["from"]
                           for item in c["to"]}
                if outlets.intersection(circuit["from"]):
                    sources.append(e["id"])
            sinks = [item for item in circuit["to"] if item in radiators]
            if sources and sinks:
                self.lt_sources[name] = sources
                self.lt_capacity[name] = sum(radiators[item] * self.available[item] for item in sinks)
        self.running0 = set(self.status["running_at_midnight"])''')
edit('tests/reference.py', '        out["running_ok"] = np.ones(N, dtype=bool)', '''        out["lt_heat"] = {name: np.zeros(N) for name in self.lt_sources}
        out["lt_capacity"] = {name: cap.copy() for name, cap in self.lt_capacity.items()}
        out["running_ok"] = np.ones(N, dtype=bool)''')
edit('tests/reference.py', '                on = kwe > 0.5', '''                if kwe > 0.0:
                    lt = np.interp(kwe, self.curve[e["id"]][0], self.lt_curve[e["id"]])
                    for name, sources in self.lt_sources.items():
                        if e["id"] in sources:
                            out["lt_heat"][name][t] += lt
                on = kwe > 0.5''')
edit('tests/reference.py', '            rejection = {}', '''            for name, sources in self.lt_sources.items():
                terms = {}
                for g, e in enumerate(eng):
                    if e["id"] not in sources:
                        continue
                    kw = self.curve[e["id"]][0]
                    lt = self.lt_curve[e["id"]]
                    terms[v(t, f"U{g}")] = lt[0]
                    for s in range(len(kw) - 1):
                        terms[v(t, f"D{g}_{s}")] = (lt[s + 1] - lt[s]) / (kw[s + 1] - kw[s])
                add(terms, -np.inf, self.lt_capacity[name][t])
            rejection = {}''')
edit('tests/reference.py', '# or its LT radiator, the only way out for its intercooler heat; a chiller cannot run without its',
     '# or its LT outlet PHE, the only way out for its intercooler heat; a chiller cannot run without its')
with (TASK/'tests/test_plans.py').open('a') as f:
    f.write('''\n\ndef test_lt_heat_rejection(case):
    _, _, flows = case
    for name, heat in flows["lt_heat"].items():
        assert (heat <= flows["lt_capacity"][name] + 0.5).all(), name
''')

p = TASK/'tests/days/h1/status.json'
status = json.loads(p.read_text())
status['outages'].append({'unit': 'LT PHE 1', 'from': '18:10', 'to': '19:20'})
p.write_text(json.dumps(status, indent=2)+'\n')
