"""Independently verify the common-header feasibility of an adversary's warm-water witness.

Does not assert that the site contract authorizes every setpoint. It establishes
that the alternative plan is thermodynamically/arithmetic consistent under a
continuous-temperature interpretation, so rejecting it is not a capability result.
"""
from __future__ import annotations
import csv
from datetime import datetime, timezone, date
import json
import math
from pathlib import Path
import sys

import numpy as np
from scipy.optimize import brentq

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FOLDER = ROOT / "results/checks-v18/fuzz/water-probes/days/w1"

def main():
    plant = json.loads((FOLDER / "plant.json").read_text())
    supply = json.loads((FOLDER / "supply.json").read_text())
    status = json.loads((FOLDER / "status.json").read_text())
    codex = json.loads((FOLDER / "v17_codex_parts.plan.json").read_text())
    old = json.loads((FOLDER / "v16_claude.plan.json").read_text())
    demand = list(csv.DictReader((FOLDER / "demand.csv").open()))
    weather = {datetime.fromisoformat(x["time_utc"].replace("Z", "+00:00")): x
               for x in csv.DictReader((FOLDER / "weather.csv").open())}
    errors, details = [], []
    running = set(status["running_at_midnight"])
    starts = 0
    total = 0.0
    assert status["outages"] == []
    for t, (p, d) in enumerate(zip(codex["periods"], demand)):
        w = weather[datetime.fromisoformat(d["period_start"]).astimezone(timezone.utc)]
        g = p["engines_kwe"]
        ac = p["chillers_kw"]["AC1"]
        gas = ht = qgen = aux = maintenance = startup = 0.0
        for engine in plant["engines"]:
            output = g[engine["id"]]
            if output > 0:
                pts = engine["part_load"]
                x = [k["kwe"] for k in pts]
                assert x[0] - .01 <= output <= x[-1] + .01
                gas += float(np.interp(output, x, [k["fuel_kw"] for k in pts])) * 1.108
                ht += float(np.interp(output, x, [k["ht_heat_kw"] for k in pts]))
                pf = engine["generator"]["power_factor"]
                qgen += output * math.sqrt(1 - pf**2) / pf
                aux += engine["auxiliary_kwe"]
                maintenance += output * engine["maintenance_gbp_per_mwhe"] / 1000
                if engine["id"] not in running:
                    startup += engine["start_cost_gbp"]
                    starts += 1
        running = {k for k,v in g.items() if v > 0}
        boiler = 0.0
        for b in plant["boilers"]:
            output = p["boilers_kw"][b["id"]]
            assert -.01 <= output <= b["max_kw"] + .01
            boiler += output
            gas += output / b["efficiency"]
        aux += ac * .022
        ac_heat = ac / .71
        expected_ec = sum(g.values()) + p["pv_kw"] + p["import_kw"] - p["export_kw"] - float(d["electricity_kw"]) - aux
        low = max(float(w["wet_bulb_c"]) + 4, 21, 22 if ac > 1e-6 else 21)
        high = max(low, 34)

        def electric(temp):
            ans = 0.0
            for ch in plant["electric_chillers"]:
                pts = np.array(ch["cop_by_condenser_entering_c"])
                ans += p["chillers_kw"][ch["id"]] / float(np.interp(temp, pts[:, 0], pts[:, 1]))
            return ans

        lo_power, hi_power = electric(low), electric(high)
        assert lo_power - .01 <= expected_ec <= hi_power + .01, (t, expected_ec, lo_power, hi_power)
        if expected_ec <= lo_power + .01:
            chosen = low
        elif expected_ec >= hi_power - .01:
            chosen = high
        else:
            chosen = brentq(lambda temp: electric(temp) - expected_ec, low, high)
        rej_table = np.array(plant["cooling_towers"]["heat_rejection_kw_per_cell_by_wet_bulb_c"])
        tower_cap = 2 * float(np.interp(float(w["wet_bulb_c"]), rej_table[:,0], rej_table[:,1]))
        rejection = sum(p["chillers_kw"].values()) + expected_ec + ac_heat
        grid_kva = math.hypot(p["import_kw"]-p["export_kw"], float(d["reactive_kvar"]) - qgen)
        assert abs(ht - ac_heat + boiler - float(d["heat_kw"]) - 75) <= .02
        assert ht - ac_heat >= -.01
        assert abs(sum(p["chillers_kw"].values()) - float(d["cooling_kw"])) <= .01
        assert rejection <= tower_cap + .01
        assert grid_kva <= 1220 + .01 and p["export_kw"] <= 250 + .01
        assert -.01 <= p["pv_kw"] <= min(float(w["pv_kw"]), 280) + .01
        clock = p["start"]
        bands = supply["electricity"]["import_rates_p_per_kwh"]["weekend" if date.fromisoformat(status["date"]).weekday()>=5 else "weekday"]
        rate = next(x["rate"]/100 for x in bands if x["from"] <= clock < x["to"])
        cost = .5 * (gas*.0435 + maintenance + p["import_kw"]*rate - p["export_kw"]*.059) + startup
        assert abs(p["gas_kwh"] - .5*gas) < .1
        assert abs(p["cost_gbp"] - cost) < .1
        total += cost
        if chosen > low + .02:
            details.append({"start": clock, "engines_kwe": g, "chillers_kw": p["chillers_kw"],
                            "site_electricity_kw": float(d["electricity_kw"]),
                            "site_reactive_kvar": float(d["reactive_kvar"]),
                            "import_kw": p["import_kw"], "export_kw": p["export_kw"],
                            "coldest_header_c": low, "inferred_common_header_c": chosen,
                            "ec_input_kw": expected_ec, "coldest_ec_input_kw": lo_power,
                            "coldest_recompute_error_kw": expected_ec-lo_power,
                            "tower_rejection_kw": rejection, "tower_capacity_kw": tower_cap,
                            "signed_connection_kva": grid_kva})
    assert starts == codex["summary"]["engine_starts"]
    assert abs(total - codex["summary"]["cost_gbp"]) < .1
    out = {"status": "PASS: 48 periods physically consistent under continuous-header interpretation",
           "plan_source": str((FOLDER / "v17_codex_parts.plan.json").relative_to(ROOT)),
           "warmer_periods": details, "recomputed_cost_gbp": total,
           "reported_cost_gbp": codex["summary"]["cost_gbp"], "engine_starts": starts,
           "v16_discrete_header_plan_cost_gbp": old["summary"]["cost_gbp"],
           "cost_saving_vs_v16_plan_gbp": old["summary"]["cost_gbp"]-codex["summary"]["cost_gbp"],
           "qualification": "A feasibility and arithmetic witness, not proof of site control authorization or an independent optimality certificate."}
    (HERE / "water_witness_checked.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
