"""Evaluate physical capacity hypotheses with an isolated whole-day model."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/checks-v20"


def extended_source():
    src = (OUT / "baseline/task/tests/reference.py").read_text()
    def sub(old, new):
        nonlocal src
        assert src.count(old) == 1, old
        src = src.replace(old, new)
    sub('            heat_terms, gen = {}, {}', '            heat_terms, gen, gas_terms = {}, {}, {}')
    sub('                el[v(t, f"U{g}")] = kw[0] - e["auxiliary_kwe"]',
        '                gas_terms[v(t, f"U{g}")] = fuel[0] * self.gross_net\n'
        '                el[v(t, f"U{g}")] = kw[0] - e["auxiliary_kwe"]')
    sub('                    el[d] = 1.0',
        '                    gas_terms[d] = (fuel[s + 1] - fuel[s]) / length * self.gross_net\n'
        '                    el[d] = 1.0')
    sub('                c[v(t, f"B{b}")] = DT_H * self.gas_rate / bl["efficiency"]',
        '                c[v(t, f"B{b}")] = DT_H * self.gas_rate / bl["efficiency"]\n'
        '                gas_terms[v(t, f"B{b}")] = 1.0 / bl["efficiency"]')
    marker = '            add(rejection, -np.inf, self.tower_max[t])'
    sub(marker, marker + '''
            entry = self.supply["gas"].get("entry")
            if entry:
                fuel_cap = entry["maximum_standard_m3_per_hour"] * entry["gross_calorific_value_mj_per_standard_m3"] / 3.6
                add(gas_terms, -np.inf, fuel_cap)
            for feeder in self.plant.get("electrical_distribution", {}).get("feeders", []):
                active, reactive = {}, {}
                for i, ch in enumerate(ecs):
                    if ch["id"] in feeder["loads"]:
                        pf = ch["electrical_power_factor"]
                        tan = math.sqrt(1.0 - pf * pf) / pf
                        for mode in ("E", "H"):
                            j = v(t, f"{mode}{i}")
                            active[j], reactive[j] = -el[j], -el[j] * tan
                for a, ac in enumerate(acs):
                    if ac["id"] in feeder["loads"]:
                        pf = ac["electrical_power_factor"]
                        j = v(t, f"A{a}")
                        active[j] = -el[j]
                        reactive[j] = -el[j] * math.sqrt(1.0 - pf * pf) / pf
                # Equal fixed PF gives an exact linear feeder bound here, independently
                # derived from its complete active/reactive load components.
                for th in np.linspace(0.0, np.pi / 2, 91):
                    row = {j: active.get(j, 0.0) * math.cos(th) + reactive.get(j, 0.0) * math.sin(th)
                           for j in active.keys() | reactive.keys()}
                    cap = feeder["rated_kva"] - feeder["other_load_kw"] * math.cos(th) - feeder["other_load_kvar"] * math.sin(th)
                    add(row, -np.inf, cap)
            for hx in self.plant.get("heat_exchangers", []):
                if hx["id"] == "PHE1":
                    circ = self.plant["heat_circuits"][hx["primary_circuit"]]
                    cap = hx["primary_maximum_water_flow_kg_per_s"] * hx["water_specific_heat_kj_per_kg_k"] * (circ["flow_c"] - circ["return_c"])
                    add(absorb, -np.inf, cap)
''')
    return src


def main():
    out = OUT / "limit-probes"
    out.mkdir(exist_ok=True)
    ref = out / "reference_limits.py"
    ref.write_text(extended_source())
    spec = importlib.util.spec_from_file_location("reference_limits", ref)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    settings = [("c2", n) for n in (550., 575., 600.)] + [("c3", n) for n in (315., 350., 375.)] + [("c4", n) for n in (15., 20., 24.)]
    result = {}
    for cid, value in settings:
        case = f"{cid}-{value:g}"
        result[case] = {}
        for name in ("visible", "h1", "h2", "h3", "h4"):
            folder = out / case / name
            if folder.exists():
                raise FileExistsError(folder)
            shutil.copytree(OUT / "candidates" / cid / "task/tests/days" / name, folder)
            p = json.loads((folder / "plant.json").read_text())
            s = json.loads((folder / "supply.json").read_text())
            if cid == "c2":
                s["gas"]["entry"]["maximum_standard_m3_per_hour"] = value
                s["gas"]["entry"]["gross_calorific_value_mj_per_standard_m3"] = 39.6
            elif cid == "c3":
                p["electrical_distribution"]["feeders"][0]["rated_kva"] = value
            else:
                p["heat_exchangers"][0]["primary_maximum_water_flow_kg_per_s"] = value
            (folder / "plant.json").write_text(json.dumps(p, indent=2) + "\n")
            (folder / "supply.json").write_text(json.dumps(s, indent=2) + "\n")
            start = time.monotonic()
            try:
                plan = mod.Day(folder).least_cost()
                (folder.parent / f"{name}-milp-plan.json").write_text(json.dumps(plan, indent=2) + "\n")
                r = {"feasible": True, "cost": plan["cost"]}
            except RuntimeError as exc:
                r = {"feasible": False, "error": str(exc)}
            r["seconds"] = time.monotonic() - start
            result[case][name] = r
            (out / "results.json").write_text(json.dumps(result, indent=2) + "\n")
            print(case, name, json.dumps(r), flush=True)


if __name__ == "__main__":
    main()
