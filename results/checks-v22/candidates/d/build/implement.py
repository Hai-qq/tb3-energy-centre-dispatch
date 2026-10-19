"""Build D once from an rsync copy of S; source paths are the supplied visible files."""
from pathlib import Path
import json
import shutil

B = Path(__file__).resolve().parent
T = B.parent / 'task'
ROOT = B.parents[4]
SUPPLIED = Path('/private/tmp/claude-501/-Users-haiy-qq-Desktop----klavis/a70e7eab-ed43-4fbc-8c31-1d0858956a32/scratchpad/v22-prechecks/d/visible/app')

def edit(path, changes):
    s = path.read_text()
    for old, new in changes:
        assert s.count(old) == 1, (path, old, s.count(old))
        s = s.replace(old, new)
    path.write_text(s)

for p in [T/'environment/data/plant.json', *sorted((T/'tests/days').glob('*/plant.json'))]:
    shutil.copyfile(SUPPLIED/'data/plant.json', p)
shutil.copyfile(SUPPLIED/'planner/plant.py', T/'environment/planner/plant.py')

p = T/'solution/app/planner/plant.py'
v15 = (ROOT/'archive/energy-centre-dispatch-v15/solution/app/planner/plant.py').read_text()
old = p.read_text()
seg = old[old.index('    def segments('):old.index('    def fuel(')]
newseg = v15[v15.index('    def segments('):v15.index('    def fuel(')]
edit(p, [
('        self.heat_kw = np.array([p["ht_heat_kw"] for p in pts], dtype=float)',
 '        self.exhaust_kw = np.array([p["exhaust_heat_kw"] for p in pts], dtype=float)\n'
 '        self.heat_kw = np.array([p["jacket_water_heat_kw"] for p in pts], dtype=float) + self.exhaust_kw'),
(seg, newseg),
('        self.engines = [Engine(x) for x in d["engines"]]',
 '''        self.engines = [Engine(x) for x in d["engines"]]
        # Physical source endpoints and the bypass field determine HT dependencies.
        sources = {item for circuit in d["heat_circuits"].values() for item in circuit["from"]}
        self.engine_jacket, self.engine_exhaust = {}, {}
        for e, spec in zip(self.engines, d["engines"]):
            self.engine_jacket[e.id] = tuple(item for item in sources
                                           if item == f"{e.id} jacket water heat exchanger")
            self.engine_exhaust[e.id] = next(item for item in sources
                                             if item == f"{e.id} exhaust heat exchanger"
                                             and spec.get("exhaust_heat_exchanger", {}).get("bypass"))
            assert self.engine_jacket[e.id], "missing mandatory jacket-water outlet"''')])

p = T/'solution/app/planner/optimize.py'
edit(p, [
('for item in (engine.id, f"{engine.id} intercooler", f"{engine.id} jacket water and exhaust")',
 'for item in (engine.id, f"{engine.id} intercooler") + plant.engine_jacket[engine.id]'),
('    pieces = [e.segments()[s] for e, s in zip(plant.engines, seg) if s is not None]',
 '''    pieces = [e.segments(_available(day, plant.engine_exhaust[e.id], day.starts[t]))[s]
              for e, s in zip(plant.engines, seg) if s is not None]'''),
('    n = iX + 1', '    iY = iX + 1  # recoverable exhaust diverted to the stack\n    n = iY + 1'),
('(lo, hi, f0, fs, h0, hs)', '(lo, hi, f0, fs, h0, hs, x0, xs)'),
('    row[iB:iB + nB] = 1.0\n    A_eq.append(row)',
 '    row[iB:iB + nB] = 1.0\n    row[iY] = -1.0\n    A_eq.append(row)'),
('    # the absorption chillers are fired from the engine circuit only;',
 '''    # The modulating diverters can reject any amount up to available exhaust heat.
    bounds[iY] = (0.0, None)
    row = np.zeros(n)
    for j, piece in enumerate(pieces):
        row[j] = -piece[7]
    row[iY] = 1.0
    A_ub.append(row)
    b_ub.append(sum(piece[6] for piece in pieces))
    # the absorption chillers are fired from the engine circuit only;'''),
('    if _available(day, "PHE1", day.starts[t]):',
 '    row[iY] = 1.0\n    if _available(day, "PHE1", day.starts[t]):')])

p = T/'tests/reference.py'
edit(p, [
('for k in ("kwe", "fuel_kw", "ht_heat_kw"))',
 'for k in ("kwe", "fuel_kw", "jacket_water_heat_kw", "exhaust_heat_kw"))'),
('for part in ("intercooler", "jacket water and exhaust")',
 'for part in ("intercooler", "jacket water heat exchanger", "exhaust heat exchanger")'),
('        for e in self.engines:\n            self.available[e["id"]] &=',
 '        self.exhaust_ok = {}\n        for e in self.engines:\n            self.available[e["id"]] &='),
('            self.available[e["id"]] &= self.available[f"{e[\'id\']} jacket water and exhaust"]',
 '''            self.available[e["id"]] &= self.available[f"{e['id']} jacket water heat exchanger"]
            self.exhaust_ok[e["id"]] = self.available[f"{e['id']} exhaust heat exchanger"]'''),
('keys = ("gas_kwh", "engine_heat",', 'keys = ("gas_kwh", "jacket", "exhaust", "engine_heat",'),
('                    kw, fuel, heat = self.curve[e["id"]]',
 '                    kw, fuel, jacket, exhaust = self.curve[e["id"]]'),
('                    out["engine_heat"][t] += np.interp(kwe, kw, heat)',
 '''                    out["jacket"][t] += np.interp(kwe, kw, jacket)
                    if self.exhaust_ok[e["id"]][t]:
                        out["exhaust"][t] += np.interp(kwe, kw, exhaust)'''),
('            gas = DT_H * (fuel_net * self.gross_net + boiler_gas)',
 '''            # Infer HT recovery from the unchanged output schema, within the physical interval.
            recovered = self.heat[t] + self.lthw_loss - sum(float(q) for q in p["boilers_kw"].values())
            recovered += out["ac_heat"][t]
            out["engine_heat"][t] = np.clip(recovered, out["jacket"][t],
                                             out["jacket"][t] + out["exhaust"][t])
            gas = DT_H * (fuel_net * self.gross_net + boiler_gas)'''),
('+ ["Z", "I", "X"]', '+ ["Z", "I", "X", "Y"]'),
('            heat_terms, gen = {}, {}', '            heat_terms, exhaust_terms, gen = {}, {}, {}'),
('                kw, fuel, heat = self.curve[e["id"]]',
 '''                kw, fuel, jacket, exhaust = self.curve[e["id"]]
                if not self.exhaust_ok[e["id"]][t]:
                    exhaust = np.zeros_like(exhaust)
                heat = jacket + exhaust'''),
('                heat_terms[v(t, f"U{g}")] = heat[0]',
 '                heat_terms[v(t, f"U{g}")] = heat[0]\n                exhaust_terms[v(t, f"U{g}")] = exhaust[0]'),
('                    heat_terms[d] = (heat[s + 1] - heat[s]) / length',
 '                    heat_terms[d] = (heat[s + 1] - heat[s]) / length\n                    exhaust_terms[d] = (exhaust[s + 1] - exhaust[s]) / length'),
('            lthw = dict(heat_terms)\n            absorb = dict(heat_terms)',
 '''            y = v(t, "Y")
            hi[y] = np.inf
            bypass = {y: 1.0}
            bypass.update({i: -x for i, x in exhaust_terms.items()})
            add(bypass, -np.inf, 0.0)
            lthw = dict(heat_terms)
            absorb = dict(heat_terms)
            lthw[y] = absorb[y] = -1.0''')])
# Retain every test function; only replace the HT equality with v15's physical interval check.
p = T/'tests/test_plans.py'
s = p.read_text()
a = s.index('    lthw = flows["engine_heat"]')
b = s.index('\n\ndef test_cooling_balance', a)
v15 = (ROOT/'archive/energy-centre-dispatch-v15/tests/test_plans.py').read_text()
a15 = v15.index('    phe1 = day.heat + day.lthw_loss - boilers')
b15 = v15.index('\n\ndef test_cooling_balance', a15)
p.write_text(s[:a] + v15[a15:b15] + s[b:])
p = T/'tests/days/h2/status.json'
s = json.loads(p.read_text())
for o in s['outages']:
    if o['unit'] == 'GE2 jacket water and exhaust':
        o['unit'] = 'GE2 jacket water heat exchanger'
s['outages'].append({'unit': 'GE1 exhaust heat exchanger', 'from': '12:00', 'to': '14:50'})
p.write_text(json.dumps(s, indent=2)+'\n')
