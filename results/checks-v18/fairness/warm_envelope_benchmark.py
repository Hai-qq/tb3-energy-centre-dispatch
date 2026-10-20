"""Independent reference extension used only to audit the CW policy ambiguity.

One nonnegative EC compressor excess-power variable per period is bounded by
the 34C COP endpoint minus the minimum allowed shared-header input. The sum
of reciprocals of the actual linearly interpolated COPs is continuous monotone,
so this interval is exactly attainable by one common header temperature.
This script never modifies the task or its frozen reference.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time
import types

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = ROOT / "archive/energy-centre-dispatch-v17"
parser = argparse.ArgumentParser()
parser.add_argument("--reference", type=Path, default=BASE / "tests/reference.py")
parser.add_argument("--days-root", type=Path, default=BASE / "tests/days")
parser.add_argument("--label", default="")
args = parser.parse_args()
source = args.reference.read_text()
output_name = "warm_envelope_benchmark" + ("_" + args.label if args.label else "")


def module(text, name):
    result = types.ModuleType(name)
    exec(compile(text, str(args.reference), "exec"), result.__dict__)
    return result


cold = module(source, "cold_v17_fairness")
needle = '+ ["Z", "I", "X"]'
assert source.count(needle) == 1
warm_source = source.replace(needle, '+ ["Z", "I", "X", "EXCESS"]')
needle = '            for a, ac in enumerate(acs):\n                cap = ac["max_kw"]'
assert warm_source.count(needle) == 1
insert = '''            # Independent fairness experiment: full continuous shared-header envelope.
            excess = v(t, "EXCESS")
            hi[excess] = sum(ch["max_kw"] / ch["cop_by_condenser_entering_c"][-1][1] for ch in ecs)
            el[excess] = -1.0
            rejection[excess] = 1.0
            envelope = {excess: 1.0}
            for i, ch in enumerate(ecs):
                hot_cop = float(ch["cop_by_condenser_entering_c"][-1][1])
                for name, mode in ((f"E{i}", False), (f"H{i}", True)):
                    envelope[v(t, name)] = -(1.0 / hot_cop - 1.0 / self.cop[ch["id"]][mode][t])
            add(envelope, -np.inf, 0.0)
'''
warm_source = warm_source.replace(needle, insert + needle)
warm = module(warm_source, "warm_v17_fairness")

results = {"reference": str(args.reference), "reference_sha256": hashlib.sha256(source.encode()).hexdigest(),
           "extension": "one exact continuous common-CW aggregate compressor-input envelope per period; strict AC auxiliary heat; v17 constant-output PV convention",
           "days": []}
cases = [(name, args.days_root / name) for name in ["visible", "h1", "h2", "h3", "h4"]]
cases.append(("warm_witness_w1", ROOT / "results/checks-v18/fuzz/water-probes/days/w1"))
for name, folder in cases:
    start = time.monotonic()
    dc, dw = cold.Day(folder), warm.Day(folder)
    pc, pw = dc.least_cost(), dw.least_cost()
    actual = dw.true_flows(pw)
    changed = []
    for t, row in enumerate(pw["periods"]):
        implied = sum(row["engines_kwe"].values()) + row["pv_kw"] + row["import_kw"] - row["export_kw"] - dw.elec[t] - actual["aux"][t]
        absorbing = any(row["chillers_kw"][a["id"]] > 1e-9 for a in dw.plant["absorption_chillers"])
        minimum_ec = sum(row["chillers_kw"][ch["id"]] / dw.cop[ch["id"]][absorbing][t]
                         for ch in dw.plant["electric_chillers"])
        if implied - minimum_ec > 1e-6:
            changed.append({"start": row["start"], "extra_ec_kw": implied - float(minimum_ec)})
    entry = {"name": name, "cold_cost_gbp": pc["cost"], "continuous_cost_gbp": pw["cost"],
             "cold_minus_continuous_gbp": pc["cost"] - pw["cost"],
             "elapsed_s": time.monotonic() - start, "warmer_periods": changed}
    print(json.dumps(entry), flush=True)
    results["days"].append(entry)
    (HERE / (output_name + ".json")).write_text(json.dumps(results, indent=2) + "\n")
