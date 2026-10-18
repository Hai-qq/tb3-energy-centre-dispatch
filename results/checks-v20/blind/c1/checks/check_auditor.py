"""Confirm that the independent auditor rejects deliberately corrupted plans."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from audit import check_plan

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/auditor-sensitivity"


def main():
    OUT.mkdir(exist_ok=True)
    results = []

    def reject(name, case, mutation, message):
        source = ROOT / "experiments" / case
        plan = deepcopy(json.loads((source / "plan.json").read_text()))
        mutation(plan)
        path = OUT / (name + ".json")
        path.write_text(json.dumps(plan, indent=1) + "\n")
        data = ROOT / "app/data" if case == "visible" else source / "data"
        try:
            check_plan(data, path)
        except AssertionError as error:
            assert message in str(error), (name, str(error))
            results.append({"mutation": name, "correctly_rejected": True, "required_diagnostic": message,
                            "diagnostics": str(error).splitlines()})
        else:
            raise AssertionError(f"auditor incorrectly accepted {name}")

    reject("understated_gas", "visible", lambda p: p["periods"][0].__setitem__("gas_kwh", p["periods"][0]["gas_kwh"] * .9),
           "reconstructed billed gas")
    reject("missing_start_charge", "visible", lambda p: p["periods"][0].__setitem__("cost_gbp", p["periods"][0]["cost_gbp"] - 27.),
           "reconstructed bill")
    reject("unrouted_ht_surplus", "visible", lambda p: p["periods"][0]["engines_kwe"].__setitem__("GE1", 600.),
           "HT/LTHW equality")

    def simultaneous(plan):
        plan["periods"][0]["import_kw"] += 10.
        plan["periods"][0]["export_kw"] += 10.

    reject("simultaneous_meter_flows", "visible", simultaneous, "simultaneous import and export")
    reject("outage_running", "visible", lambda p: p["periods"][14]["engines_kwe"].__setitem__("GE1", 600.), "GE1 outage")
    reject("apparent_power_overload", "visible", lambda p: p["periods"][0].__setitem__("import_kw", 2000.), "import kVA overload")

    def pv_limit(plan):
        plan["periods"][12]["pv_kw"] += 1.
        plan["periods"][12]["import_kw"] -= 1.

    reject("pv_above_inverter", "pv_inverter_cap", pv_limit, "PV forecast, inverter and outage")

    def tower_limit(plan):
        plan["periods"][14]["chillers_kw"]["AC1"] += 10.
        plan["periods"][14]["chillers_kw"]["EC1"] -= 10.

    reject("tower_overload", "tower_binding", tower_limit, "tower rejection overload")
    reject("wrong_start_total", "visible", lambda p: p["summary"].__setitem__("engine_starts", p["summary"]["engine_starts"] + 1),
           "summary starts including midnight")
    reject("endpoint_chord_fuel", "ge1_segments", lambda p: p["periods"][2].__setitem__("gas_kwh", p["periods"][2]["gas_kwh"] + 6.925),
           "reconstructed billed gas")

    def round_tree(value):
        if isinstance(value, float):
            return round(value, 3)
        if isinstance(value, dict):
            return {key: round_tree(item) for key, item in value.items()}
        if isinstance(value, list):
            return [round_tree(item) for item in value]
        return value

    reject("premature_three_decimal_rounding", "visible", lambda p: p.update(round_tree(p)), "HT/LTHW equality")
    report = {"passed": True, "mutations_rejected": len(results), "results": results}
    (OUT / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, indent=2))


if __name__ == "__main__":
    main()
