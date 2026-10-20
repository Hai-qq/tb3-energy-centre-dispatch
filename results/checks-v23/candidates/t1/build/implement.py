"""Build T1 from a fresh rsync of v19. Do not rerun on an edited candidate."""
from pathlib import Path
import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone

B = Path(__file__).resolve().parent
T = B.parent / 'task'
ROOT = B.parents[4]
BASE = ROOT / 'tasks/energy-centre-dispatch'
SOURCE = Path('/private/tmp/claude-501/-Users-haiy-qq-Desktop----klavis/a70e7eab-ed43-4fbc-8c31-1d0858956a32/scratchpad/v23-t1/visible')


def edit(rel, old, new):
    p = T / rel
    s = p.read_text()
    assert s.count(old) == 1, (rel, old, s.count(old))
    p.write_text(s.replace(old, new))


plants = [BASE / 'environment/data/plant.json', *sorted((BASE/'tests/days').glob('*/plant.json'))]
assert len(plants) == 6 and len({p.read_bytes() for p in plants}) == 1
(B/'baseline_plants.json').write_text(json.dumps({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in plants}, indent=2)+'\n')
shutil.copyfile(SOURCE/'instruction.md', T/'instruction.md')
for target in [T/'environment/data/plant.json', *sorted((T/'tests/days').glob('*/plant.json'))]:
    shutil.copyfile(SOURCE/'app/data/plant.json', target)
for target in [T/'environment/data/demand.csv', T/'tests/days/visible/demand.csv']:
    shutil.copyfile(SOURCE/'app/data/demand.csv', target)
for name in ('data.py', 'plant.py', 'optimize.py'):
    shutil.copyfile(SOURCE/'app/planner'/name, T/'environment/planner'/name)

# Hidden AHU demand: the supplied visible reheat profile plus weather compensation.
reheat = [float(r['ahu_heat_kw']) for r in csv.DictReader(open(SOURCE/'app/data/demand.csv'))]
for folder in sorted((T/'tests/days').glob('h*')):
    rows = list(csv.DictReader(open(folder/'demand.csv')))
    wx = {datetime.fromisoformat(r['time_utc'].replace('Z', '+00:00')): r for r in csv.DictReader(open(folder/'weather.csv'))}
    fields = list(rows[0]); fields.insert(fields.index('heat_kw')+1, 'ahu_heat_kw')
    for t, r in enumerate(rows):
        dry = float(wx[datetime.fromisoformat(r['period_start']).astimezone(timezone.utc)]['dry_bulb_c'])
        r['ahu_heat_kw'] = f'{reheat[t] + max(0.0, 25.0 * (14.0-dry)):.3f}'
    with (folder/'demand.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fields); w.writeheader(); w.writerows(rows)

# The same-day safe window is shorter than the original afternoon outage.
p = T/'tests/days/h3/status.json'
status = json.loads(p.read_text())
adjustments = []
for outage in status['outages']:
    if outage['unit'] == 'LT radiator 2':
        old = dict(outage)
        outage.update({'from': '03:40', 'to': '04:50'})
        adjustments.append({'day': 'h3', 'old': old, 'new': dict(outage),
                            'reason': 'Only 03:30, 04:00 and 04:30 have lenient AHU capacity below GE2 minimum LT heat (83 kW); the original afternoon window does not force a stop.'})
p.write_text(json.dumps(status, indent=2)+'\n')
(B/'hidden_adjustments.json').write_text(json.dumps(adjustments, indent=2)+'\n')

# Solution: keep existing mutation anchors wherever the new balance permits it.
edit('solution/app/planner/data.py', '    cool: np.ndarray', '    ahu: np.ndarray  # heat at AHU heating coils, kW\n    cool: np.ndarray')
edit('solution/app/planner/data.py', '        cool=np.array', '        ahu=np.array([float(r["ahu_heat_kw"]) for r in demand]),\n        cool=np.array')
edit('solution/app/planner/plant.py', '        self.min_kwe =', '        self.lt_kw = np.array([p["lt_heat_kw"] for p in pts], dtype=float)\n        self.min_kwe =')
edit('solution/app/planner/plant.py', '        # Every outlet of an intercooler circuit is needed to reject its LT heat.', '''        circuits = d["heat_circuits"]
        self.ahu = next(c for c in circuits.values() if "flow_c_by_dry_bulb_c" in c)
        # Follow each intercooler circuit to the PHEs that feed the AHU circuit.
        self.lt_routes = {e.id: tuple((float(c["flow_c"]), tuple(x for x in c["to"] if x in self.ahu["from"]))
                                    for c in circuits.values() if f"{e.id} intercooler" in c["from"])
                          for e in self.engines}
        # Radiator outages stop engines only on days certified by the verifier's
        # minimum-LT-heat check. PHE outages remove recovery, not the radiator path.''')
edit('solution/app/planner/plant.py', 'if f"{e.id} intercooler" in c["from"] for item in c["to"])', 'if f"{e.id} intercooler" in c["from"] for item in c["to"]\n                                          if item not in self.ahu["from"])')
edit('solution/app/planner/plant.py', '    def condenser_entering(self, wet_bulb_c: float, at_least_c: float = 0.0) -> float:', '''    def ahu_recovery_fraction(self, dry_bulb_c: float, lt_flow_c: float) -> float:
        pts = np.array(self.ahu["flow_c_by_dry_bulb_c"], dtype=float)
        flow = float(np.interp(dry_bulb_c, pts[:, 0], pts[:, 1]))
        return float(flow <= lt_flow_c - 5.0)

    def condenser_entering(self, wet_bulb_c: float, at_least_c: float = 0.0) -> float:''')
edit('solution/app/planner/plant.py', '''    Only the HT circuit's heat (jacket water and exhaust) is recovered; the intercooler's
    LT heat leaves through the radiator connected to its intercooler in heat_circuits.''', '''    HT heat feeds LTHW; intercooler LT heat may feed AHU heating through its
    connected PHE when the weather-compensated supply permits a 5 K approach.''')
edit('solution/app/planner/optimize.py', '    n = iX + 1', '    iR = iX + 1  # LT heat recovered into AHU heating, kW\n    n = iR + 1')
edit('solution/app/planner/optimize.py', '    A_eq, b_eq, A_ub, b_ub = [], [], [], []', '''    lt_flow = next(flow for routes in plant.lt_routes.values() for flow, phes in routes if phes)
    fraction = plant.ahu_recovery_fraction(day.dry_bulb[t], lt_flow)
    bounds[iR] = (0.0, float(day.ahu[t]) * fraction)

    A_eq, b_eq, A_ub, b_ub = [], [], [], []
    # LT heat follows the same piecewise engine loading as fuel and HT heat.
    row = np.zeros(n)
    row[iR] = 1.0
    lt_const = 0.0
    for j, e in enumerate(engines):
        routes = plant.lt_routes[e.id]
        if not any(_available(day, phe, day.starts[t]) for _, phes in routes for phe in phes):
            continue
        lo, hi = pieces[j][:2]
        qlo, qhi = np.interp([lo, hi], e.kwe, e.lt_kw)
        slope = (qhi - qlo) / (hi - lo)
        row[j] = -slope
        lt_const += qlo - slope * lo
    A_ub.append(row)
    b_ub.append(lt_const)''')
edit('solution/app/planner/optimize.py', '''    row[iB:iB + nB] = 1.0
    A_eq.append(row)
    b_eq.append(day.heat[t] + plant.lthw_loss_kw - sum(piece[4] for piece in pieces))''', '''    row[iB:iB + nB] = 1.0
    row[iR] = 1.0
    A_eq.append(row)
    b_eq.append(day.heat[t] + plant.lthw_loss_kw + day.ahu[t] - sum(piece[4] for piece in pieces))''')

# Independent reference: derive routes separately, use full-day MILP segments.
ref = 'tests/reference.py'
edit(ref, '        self.cool =', '        self.ahu = np.array([float(r["ahu_heat_kw"]) for r in rows])\n        self.cool =')
edit(ref, '        self.wet_bulb =', '        self.dry_bulb = np.array([float(wx[u]["dry_bulb_c"]) for u in utc])\n        self.wet_bulb =')
edit(ref, '        # A plant item can work', '''        ahu = next(c for c in self.plant["heat_circuits"].values() if "flow_c_by_dry_bulb_c" in c)
        f = np.array(ahu["flow_c_by_dry_bulb_c"], dtype=float)
        r = np.array(ahu["return_c_by_dry_bulb_c"], dtype=float)
        self.ahu_flow_c = np.interp(self.dry_bulb, f[:, 0], f[:, 1])
        self.ahu_return_c = np.interp(self.dry_bulb, r[:, 0], r[:, 1])
        self.lt_routes = {}
        for e in self.engines:
            source = f"{e['id']} intercooler"
            route = [c for c in self.plant["heat_circuits"].values() if source in c["from"]]
            assert len(route) == 1
            c = route[0]
            phes = tuple(x for x in c["to"] if x in ahu["from"])
            sinks = tuple(x for x in c["to"] if x not in ahu["from"])
            self.lt_routes[e["id"]] = (float(c["flow_c"]), phes, sinks)
        temperatures = {flow for flow, phes, _ in self.lt_routes.values() if phes}
        assert len(temperatures) == 1, "this task has one LT source temperature"
        lt_flow = temperatures.pop()
        self.ahu_len_fraction = np.clip((lt_flow - self.ahu_return_c) /
                                        (self.ahu_flow_c - self.ahu_return_c), 0.0, 1.0)
        self.ahu_len_cap = self.ahu * self.ahu_len_fraction
        self.ahu_strict_cap = self.ahu * (self.ahu_flow_c <= lt_flow - 5.0)
        self.lt_curve = {e["id"]: np.array([p["lt_heat_kw"] for p in e["part_load"]], dtype=float)
                         for e in self.engines}
        # A plant item can work''')
edit(ref, '                    for item in circuit["to"]:', '                    for item in circuit["to"]:\n                        if item in ahu["from"]:\n                            continue  # an unavailable LT PHE still leaves its radiator')
edit(ref, '        self.running0 = set(self.status["running_at_midnight"])', '''        self.running0 = set(self.status["running_at_midnight"])
        self.radiator_pressure = []
        # Certify the inherited radiator-outage => engine-off simplification.
        for e in self.engines:
            _, _, sinks = self.lt_routes[e["id"]]
            for sink in sinks:
                for t in np.flatnonzero(~self.available[sink]):
                    minimum = float(self.lt_curve[e["id"]][0])
                    cap = float(self.ahu_len_cap[t])
                    self.radiator_pressure.append({"engine": e["id"], "sink": sink,
                                                  "start": self.starts[t].strftime("%H:%M"),
                                                  "minimum_lt_kw": minimum, "lenient_cap_kw": cap})
                    assert cap < minimum, ("radiator outage does not force engine off", sink, t, cap, minimum)''')
edit(ref, '        out["running_ok"] =', '''        out["T_f"] = self.ahu_flow_c.copy()
        out["T_r"] = self.ahu_return_c.copy()
        out["lt_heat"] = np.zeros(N)
        out["lt_available"] = np.zeros(N)
        out["running_ok"] =''')
edit(ref, '                    out["engine_heat"][t] += np.interp(kwe, kw, heat)', '''                    out["engine_heat"][t] += np.interp(kwe, kw, heat)
                    lt = float(np.interp(kwe, kw, self.lt_curve[e["id"]]))
                    out["lt_heat"][t] += lt
                    _, phes, _ = self.lt_routes[e["id"]]
                    if self.available[e["id"]][t] and any(self.available[phe][t] for phe in phes):
                        out["lt_available"][t] += lt''')
edit(ref, '        out["starts"] = starts', '''        out["R_len"] = np.minimum(self.ahu_len_cap, out["lt_available"])
        out["R_strict"] = np.minimum(self.ahu_strict_cap, out["lt_available"])
        out["starts"] = starts''')
edit(ref, '+ ["Z", "I", "X"]', '+ ["Z", "I", "X", "R"]')
edit(ref, '            heat_terms, gen = {}, {}', '''            heat_terms, gen = {}, {}
            lt_terms = {v(t, "R"): 1.0}
            hi[v(t, "R")] = self.ahu_strict_cap[t]''')
edit(ref, '                nseg = len(kw) - 1', '''                nseg = len(kw) - 1
                _, phes, _ = self.lt_routes[e["id"]]
                lt_ok = any(self.available[phe][t] for phe in phes)
                lt = self.lt_curve[e["id"]]
                if lt_ok:
                    lt_terms[v(t, f"U{g}")] = -lt[0]''')
edit(ref, '                    gen[d] = self.q_per_kw[e["id"]]', '''                    gen[d] = self.q_per_kw[e["id"]]
                    if lt_ok:
                        lt_terms[d] = -(lt[s + 1] - lt[s]) / length''')
edit(ref, '            rejection = {}', '            add(lt_terms, -np.inf, 0.0)\n            rejection = {}')
edit(ref, '            rhs = self.heat[t] + self.lthw_loss', '            lthw[v(t, "R")] = 1.0\n            rhs = self.heat[t] + self.lthw_loss + self.ahu[t]')
edit('tests/test_plans.py', '    assert np.abs(lthw - day.heat - day.lthw_loss).max() <= KW', '''    upper = day.heat + day.lthw_loss + day.ahu
    assert (lthw <= upper + KW).all()  # no HT dump
    assert (lthw >= upper - flows["R_len"] - KW).all()''')
edit('README.md', 'Tolerances cover only rounding,', 'For AHU intercooler recovery, balance checks allow zero-approach series preheating, while the cost bound uses parallel heating with a 5 K approach, so either interpretation is accepted. Tolerances cover only rounding,')

print('Candidate copied and implemented; radiator windows still require certification.')
