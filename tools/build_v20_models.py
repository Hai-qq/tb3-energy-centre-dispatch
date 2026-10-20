"""Build candidate-only solution/reference extensions for prespecified prechecks.

The reference is a whole-day MILP; the oracle enumerates interval LPs and uses
dynamic programming. Historical adversaries are never modified by this script.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil

from build_v20_candidates import BASE, OUT, hashes
from probe_v20_limits import extended_source


def replace_once(src, old, new):
    assert src.count(old) == 1, old
    return src.replace(old, new)


def oracle_source(cid):
    src = (BASE / "solution/app/planner/optimize.py").read_text()
    if cid == "c1":
        src = replace_once(src, 't: int, seg: tuple, absorbing: bool):',
                           't: int, seg: tuple, absorbing: bool, importing=None):')
        marker = '    bounds[iX] = (0.0, tariff.export_limit_kw)'
        src = replace_once(src, marker, marker + '''
    # A single point of connection has one signed active-power flow.
    if importing is True:
        bounds[iX] = (0.0, 0.0)
    elif importing is False:
        bounds[iI] = (0.0, 0.0)
''')
        src = replace_once(src, '''                    c, out = _period(day, plant, tariff, t, seg, absorbing)
                    if c < cost[t, k]:
                        cost[t, k], loading[t][k] = c, out''', '''                    directions = (True, False) if tariff.import_rate(day.starts[t]) < tariff.export_rate else (None,)
                    for importing in directions:
                        c, out = _period(day, plant, tariff, t, seg, absorbing, importing)
                        if c < cost[t, k]:
                            cost[t, k], loading[t][k] = c, out''')
    elif cid == "c2":
        marker = '    res = linprog(c, A_ub=np.array(A_ub), b_ub=b_ub, A_eq=np.array(A_eq), b_eq=b_eq,'
        src = replace_once(src, marker, '''    if tariff.gas_entry is not None:
        entry = tariff.gas_entry
        row = np.zeros(n)
        offset = 0.0
        for j, (e, piece) in enumerate(zip(engines, pieces)):
            row[j] = tariff.billed_gas(piece[3], e.fuel_basis)
            offset += tariff.billed_gas(piece[2], e.fuel_basis)
        for j, b in enumerate(boilers):
            row[iB + j] = tariff.billed_gas(1.0 / b.efficiency, b.fuel_basis)
        maximum_kw = entry["maximum_standard_m3_per_hour"] * entry["gross_calorific_value_mj_per_standard_m3"] / 3.6
        A_ub.append(row)
        b_ub.append(maximum_kw - offset)

''' + marker)
    elif cid == "c4":
        marker = '    # cooling\n'
        src = replace_once(src, marker, '''    for hx in plant.heat_exchangers:
        if hx["id"] == "PHE1":
            row = np.zeros(n)
            for j, piece in enumerate(pieces):
                row[j] = piece[5]
            for j, a in enumerate(absorbers):
                row[iA + j] = -1.0 / a.cop
            circ = plant.circuits[hx["primary_circuit"]]
            cap_kw = hx["primary_maximum_water_flow_kg_per_s"] * hx["water_specific_heat_kj_per_kg_k"] * (circ["flow_c"] - circ["return_c"])
            A_ub.append(row)
            b_ub.append(cap_kw - sum(piece[4] for piece in pieces))
    # cooling
''')
    else:
        raise ValueError(cid)
    return src


def reference_source(cid):
    src = (BASE / "tests/reference.py").read_text() if cid == "c1" else extended_source()
    if cid == "c1":
        src = replace_once(src, 'options={"mip_rel_gap": 1e-9}',
                           'options={"mip_rel_gap": 1e-9, "presolve": False}')
        src = replace_once(src, '["Z", "I", "X"]', '["Z", "I", "X", "DIR"]')
        marker = '            hi[v(t, "I")], hi[v(t, "X")] = self.import_kva, self.export_max'
        src = replace_once(src, marker, marker + '''
            hi[v(t, "DIR")], integ[v(t, "DIR")] = 1.0, 1
            add({v(t, "I"): 1.0, v(t, "DIR"): -self.import_kva}, -np.inf, 0.0)
            add({v(t, "X"): 1.0, v(t, "DIR"): self.export_max}, -np.inf, self.export_max)
''')
        src = replace_once(src, '''            cost += DT_H * (float(p["import_kw"]) * self.import_rate[t] - float(p["export_kw"]) * self.export_rate)''', '''            net_grid = float(p["import_kw"]) - float(p["export_kw"])
            cost += DT_H * (max(net_grid, 0.0) * self.import_rate[t] - max(-net_grid, 0.0) * self.export_rate)''')
    return src


EXTRA_TESTS = {
    "c1": '''

def test_single_connection_direction(case):
    _, plan, _ = case
    imp, exp = series(plan, "import_kw"), series(plan, "export_kw")
    assert (np.minimum(imp, exp) <= 0.5).all(), "one steady operating point cannot import and export simultaneously"
''',
    "c2": '''

def test_shared_gas_entry(case):
    day, _, flows = case
    entry = day.supply["gas"]["entry"]
    volume_per_hour = flows["gas_kwh"] * 2.0 * 3.6 / entry["gross_calorific_value_mj_per_standard_m3"]
    assert (volume_per_hour <= entry["maximum_standard_m3_per_hour"] + 0.1).all()
''',
    "c4": '''

def test_phe_primary_water_flow(case):
    day, _, flows = case
    hx = next(h for h in day.plant["heat_exchangers"] if h["id"] == "PHE1")
    circ = day.plant["heat_circuits"][hx["primary_circuit"]]
    capacity = hx["primary_maximum_water_flow_kg_per_s"] * hx["water_specific_heat_kj_per_kg_k"] * (circ["flow_c"] - circ["return_c"])
    assert (flows["engine_heat"] - flows["ac_heat"] <= capacity + KW).all()
'''
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("candidates", nargs="*", default=["c1", "c2", "c4"])
    args = ap.parse_args()
    for cid in args.candidates:
        dest = OUT / "candidates" / cid
        task = dest / "task"
        if (dest / "MODELS_SHA256.json").exists():
            raise FileExistsError(f"Models already frozen: {cid}")
        (task / "solution/app/planner/optimize.py").write_text(oracle_source(cid))
        if cid == "c2":
            path = task / "solution/app/planner/tariff.py"
            src = path.read_text()
            src = replace_once(src, '        gas = supply["gas"]', '        gas = supply["gas"]\n        self.gas_entry = gas.get("entry")')
            path.write_text(src)
        if cid == "c4":
            path = task / "solution/app/planner/plant.py"
            src = path.read_text()
            marker = '        self.engines = [Engine(x) for x in d["engines"]]'
            src = replace_once(src, marker, '        self.heat_exchangers = d.get("heat_exchangers", [])\n        self.circuits = d["heat_circuits"]\n' + marker)
            path.write_text(src)
        (task / "tests/reference.py").write_text(reference_source(cid))
        tests = (BASE / "tests/test_plans.py").read_text()
        (task / "tests/test_plans.py").write_text(tests + EXTRA_TESTS[cid])
        (dest / "MODELS_SHA256.json").write_text(json.dumps(hashes(task), indent=2) + "\n")
        print(f"Built {cid}")


if __name__ == "__main__":
    main()
