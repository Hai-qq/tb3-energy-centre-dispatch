"""Peer-review regressions for the proposed bounded EC-input acceptance fix.

Before the fix: records current discrepancies, exits zero (theory checks still
assert). After the fix: pass --require-fixed to require every current-reference
classification to agree. No repository files outside fairness/ are written.
"""
from __future__ import annotations
import argparse
import copy
import csv
import importlib.util
import json
import math
from pathlib import Path
import shutil
import sys

import numpy as np
from scipy.optimize import brentq

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

def import_reference(path):
    spec = importlib.util.spec_from_file_location("acceptance_peer_reference", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod

def fixture():
    target = HERE / "fixtures" / "acceptance_interval"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(ROOT / "archive/energy-centre-dispatch-v17/tests/days/visible", target)
    st = json.loads((target / "status.json").read_text())
    st["outages"], st["running_at_midnight"] = [], ["GE1"]
    (target / "status.json").write_text(json.dumps(st, indent=2)+"\n")
    for filename in ("demand.csv", "weather.csv"):
        p = target / filename
        rows = list(csv.DictReader(p.open()))
        for r in rows:
            if filename == "demand.csv":
                r.update(electricity_kw="1000", reactive_kvar="300", heat_kw="760", cooling_kw="1000")
            else:
                r.update(wet_bulb_c="12", dry_bulb_c="18", pv_kw="0")
        with p.open("w", newline="") as f:
            writer = csv.DictWriter(f, list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    return target

def ec_power(plant, row, temp):
    return sum(row["chillers_kw"][ch["id"]] / np.interp(temp,
                np.array(ch["cop_by_condenser_entering_c"])[:,0],
                np.array(ch["cop_by_condenser_entering_c"])[:,1])
               for ch in plant["electric_chillers"])

def set_grid(row, site_e, input_power, aux):
    net = site_e + aux + input_power - sum(row["engines_kwe"].values()) - row["pv_kw"]
    row["import_kw"], row["export_kw"] = max(net,0), max(-net,0)

def base_plan(day):
    periods = []
    for clock in day.clock:
        row = {"start": f"{clock//60:02d}:{clock%60:02d}",
               "engines_kwe": {"GE1":600.0,"GE2":0.0},
               "boilers_kw": {"B1":0.0,"B2":0.0},
               "chillers_kw": {"EC1":1000.0,"EC2":0.0,"AC1":0.0},
               "pv_kw":0.0,"import_kw":0.0,"export_kw":0.0}
        set_grid(row,1000,float(ec_power(day.plant,row,21)),32)
        periods.append(row)
    return {"date":day.date.isoformat(),"periods":periods}

def theoretical_interval(day, plan):
    residuals, endpoints = [], []
    for t,p in enumerate(plan["periods"]):
        aux = sum(e["auxiliary_kwe"] for e in day.engines if p["engines_kwe"][e["id"]] > .5)
        ac = p["chillers_kw"]["AC1"]
        aux += .022*ac
        inferred = sum(p["engines_kwe"].values())+p["pv_kw"]+p["import_kw"]-p["export_kw"]-day.elec[t]-aux
        low = max(float(day.wet_bulb[t])+4,21,22 if ac > 1e-9 else 21)
        high = max(low,34)
        power_lo, power_hi = float(ec_power(day.plant,p,low)), float(ec_power(day.plant,p,high))
        projected = min(max(inferred,power_lo),power_hi)
        residuals.append(float(inferred-projected))
        endpoints.append({"low_kw":power_lo,"high_kw":power_hi,"inferred_kw":float(inferred),"projected_kw":projected})
    return max(abs(x) for x in residuals), endpoints

def actual_balance(day, plan):
    f = day.true_flows(plan)
    errors = []
    for t,p in enumerate(plan["periods"]):
        supply = sum(p["engines_kwe"].values())+p["pv_kw"]+p["import_kw"]-p["export_kw"]
        errors.append(supply-day.elec[t]-f["aux"][t]-f["ec_elec"][t])
    return float(np.max(np.abs(errors)))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", type=Path, default=ROOT / "tasks/energy-centre-dispatch/tests/reference.py")
    ap.add_argument("--require-fixed", action="store_true")
    ap.add_argument("--label", default="current")
    args = ap.parse_args()
    args.reference = args.reference.resolve()
    mod = import_reference(args.reference)
    folder = fixture()
    day = mod.Day(folder)
    cases = []
    for name, q1, q2, ac, temp, offset, expected in (
        ("natural_header",1000,0,0,21,0,True),
        ("warmer_without_ac",1000,0,0,26,0,True),
        ("both_ec_common_27_3C",1000,700,0,27.3,0,True),
        ("small_positive_ac_0_4_at22",1000,0,.4,22,0,True),
        ("ac_needs22_not21",1000,0,.4,21,0,False),
        ("below_minimum_by5",1000,0,0,21,-5,False),
        ("above_maximum_by5",1000,0,0,34,5,False),
        ("zero_ec_cannot_absorb5",0,0,0,21,5,False),
        ("above_hot_endpoint_rounding_0_001",1000,0,0,34,.001,True),
        ("below_cold_endpoint_rounding_0_001",1000,0,0,21,-.001,True),
    ):
        p = base_plan(day)
        row = p["periods"][10]
        row["chillers_kw"] = {"EC1":q1,"EC2":q2,"AC1":ac}
        input_power = float(ec_power(day.plant,row,temp))+offset
        set_grid(row,1000,input_power,32+.022*ac)
        theory, bounds = theoretical_interval(day,p)
        actual = actual_balance(day,p)
        assert (theory <= 1) == expected, (name,theory,expected)
        cases.append({"case":name,"expected_electricity_acceptance":expected,
                      "theoretical_interval_residual_kw":theory,
                      "current_reference_balance_residual_kw":actual,
                      "current_reference_electricity_acceptance":actual<=1,
                      "interval_at_modified_period":bounds[10]})
    witness_dir = ROOT / "results/checks-v18/fuzz/water-probes/days/w1"
    wday = mod.Day(witness_dir)
    witness = json.loads((witness_dir / "v17_codex_parts.plan.json").read_text())
    theory,bounds = theoretical_interval(wday,witness)
    actual = actual_balance(wday,witness)
    assert theory < 1e-6
    cases.append({"case":"authentic_v17_codex_warm_witness_48_periods",
                  "expected_electricity_acceptance":True,
                  "theoretical_interval_residual_kw":theory,
                  "current_reference_balance_residual_kw":actual,
                  "current_reference_electricity_acceptance":actual<=1,
                  "interval_at_16_00":bounds[32]})
    bad = [c["case"] for c in cases if c["current_reference_electricity_acceptance"] != c["expected_electricity_acceptance"]]
    out = {"reference":str(args.reference.relative_to(ROOT)),"cases":cases,"classification_disagreements":bad,
           "note":"Isolated EC-envelope regressions; full-plan ratings, availability, heat, cooling, costs and least-cost tests must still run separately."}
    (HERE/f"acceptance_regressions_{args.label}.json").write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps(out,indent=2))
    if args.require_fixed:
        assert not bad, bad

if __name__ == "__main__":
    main()
