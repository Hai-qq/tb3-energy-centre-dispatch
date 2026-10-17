"""Independent targeted checks of the single v18 reference revision."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TASK = ROOT / "tasks/energy-centre-dispatch"
spec = importlib.util.spec_from_file_location("v18_fairness_postfix_ref", TASK / "tests/reference.py")
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)


def fixture(name, outages):
    target = HERE / "postfix-fixtures" / name
    target.parent.mkdir(exist_ok=True)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(TASK / "tests/days/visible", target)
    status = json.loads((target / "status.json").read_text())
    status["outages"] = outages
    (target / "status.json").write_text(json.dumps(status, indent=2) + "\n")
    return R.Day(target)


result = {"reference_sha256": hashlib.sha256((TASK / "tests/reference.py").read_bytes()).hexdigest(),
          "components": [], "pv_unions": [], "hidden_coverage": {}, "heat_rejection": []}
for owner, component in [("GE1", "GE1 jacket water and exhaust"),
                         ("GE2", "GE2 jacket water and exhaust")]:
    d = fixture(owner + "_ht", [{"unit": component, "from": "10:10", "to": "10:20"},
                               {"unit": component, "from": "12:30", "to": "13:00"},
                               {"unit": component, "from": "14:20", "to": "14:40"}])
    off = [d.clock[t] for t in np.flatnonzero(~d.available[owner])]
    assert off == [600, 750, 840, 870]
    other = "GE2" if owner == "GE1" else "GE1"
    assert d.available[other].all()
    result["components"].append({"component": component, "owner": owner, "off_minutes": off,
                                 "other_engine_unaffected": True})

cases = [
    ("overlap", [("12:05", "12:15"), ("12:10", "12:20")], 15),
    ("reverse_order", [("12:10", "12:20"), ("12:05", "12:15")], 15),
    ("duplicate", [("12:05", "12:15"), ("12:05", "12:15")], 10),
    ("nested", [("12:05", "12:25"), ("12:10", "12:20")], 20),
    ("adjacent", [("12:05", "12:15"), ("12:15", "12:25")], 20),
    ("disjoint", [("12:00", "12:05"), ("12:20", "12:25")], 10),
    ("boundary", [("11:50", "12:00"), ("12:30", "12:40")], 0),
    ("full_cover", [("11:50", "12:20"), ("12:10", "12:40")], 30),
]
for label, intervals, unavailable in cases:
    d = fixture("pv_" + label, [{"unit": "PV1", "from": a, "to": b} for a, b in intervals])
    folder = HERE / "postfix-fixtures" / ("pv_" + label)
    wx = {datetime.fromisoformat(row["time_utc"].replace("Z", "+00:00")): float(row["pv_kw"])
          for row in csv.DictReader((folder / "weather.csv").open())}
    forecast = wx[d.starts[24].astimezone(timezone.utc)]
    expected = forecast * (30 - unavailable) / 30
    assert abs(d.pv_max[24] - expected) < 1e-10
    result["pv_unions"].append({"case": label, "unavailable_union_minutes": unavailable,
                                "expected_max_kw": expected, "actual_max_kw": float(d.pv_max[24])})

h2, h3, h4 = [R.Day(TASK / "tests/days" / name) for name in ["h2", "h3", "h4"]]
assert not h2.available["GE2"][36] and not h2.available["GE2"][37]
assert not h3.available["AC1"][25]
result["hidden_coverage"]["h2_GE2_HT_group"] = [h2.clock[t] for t in [36, 37]]
result["hidden_coverage"]["h3_AC1_generator"] = [h3.clock[25]]
# h4's added record is contained in the existing PV outage; the union must be
# invariant even in the first partial period where summing durations was wrong.
pv_outages = [o for o in h4.status["outages"] if o["unit"] == "PV1"]
assert len(pv_outages) == 2
wx = {datetime.fromisoformat(row["time_utc"].replace("Z", "+00:00")): float(row["pv_kw"])
      for row in csv.DictReader((TASK / "tests/days/h4/weather.csv").open())}
forecast = wx[h4.starts[32].astimezone(timezone.utc)]
assert abs(h4.pv_max[32] - forecast * 20 / 30) < 1e-10
result["hidden_coverage"]["h4_PV16_00"] = {"forecast_kw": forecast,
                                                   "union_available_minutes": 20,
                                                   "pv_max_kw": float(h4.pv_max[32])}

d = fixture("warm_rejection", [])
for temp, ec1, ec2, ac in [(26.0, 1000.0, 0.0, 0.0),
                           (27.3, 1000.0, 700.0, 0.0),
                           (22.0, 1000.0, 0.0, 0.4)]:
    input_kw = 0.0
    for ch, duty in zip(d.plant["electric_chillers"], [ec1, ec2]):
        pts = np.array(ch["cop_by_condenser_entering_c"])
        input_kw += duty / np.interp(temp, pts[:, 0], pts[:, 1])
    periods = []
    for t in range(48):
        # Only the first row carries the synthetic EC/AC inputs. All other rows
        # are neutral for these isolated flow calculations, not whole-day plans.
        periods.append({"start": f"{d.clock[t] // 60:02d}:{d.clock[t] % 60:02d}",
                        "engines_kwe": {"GE1": 0.0, "GE2": 0.0},
                        "boilers_kw": {"B1": 0.0, "B2": 0.0},
                        "chillers_kw": {"EC1": ec1 if t == 0 else 0.0,
                                        "EC2": ec2 if t == 0 else 0.0,
                                        "AC1": ac if t == 0 else 0.0},
                        "pv_kw": 0.0, "export_kw": 0.0,
                        "import_kw": float(d.elec[t]) + (input_kw + ac * .022 if t == 0 else 0.0)})
    # The visible day is naturally above22C at some times; use a cold first
    # period to isolate the minimum22C and variable-warmer reconstruction.
    for ch in d.plant["electric_chillers"]:
        pts = np.array(ch["cop_by_condenser_entering_c"])
        d.cop[ch["id"]][False][0] = np.interp(21.0, pts[:, 0], pts[:, 1])
        d.cop[ch["id"]][True][0] = np.interp(22.0, pts[:, 0], pts[:, 1])
    flows = d.true_flows({"periods": periods})
    expected = ec1 + ec2 + input_kw + ac * (1 + 1 / .71)
    assert abs(flows["rejected"][0] - expected) < 1e-9
    assert abs(flows["ec_elec"][0] - input_kw) < 1e-9
    result["heat_rejection"].append({"temperature_c": temp, "ec1_kw": ec1, "ec2_kw": ec2,
                                      "ac1_kw": ac, "expected_rejected_kw": expected,
                                      "actual_rejected_kw": float(flows["rejected"][0])})

result["all_assertions_passed"] = True
(HERE / "postfix_checks.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
