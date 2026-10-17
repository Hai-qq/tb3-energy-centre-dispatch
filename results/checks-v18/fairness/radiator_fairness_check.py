"""Check the missing air-on-temperature assumption in the hot-radiator proposal.

The alternative's 80% precooler effectiveness is an explicitly hypothetical
parameter, not a property inferred or added to this task. Positive temperature
head demonstrates why dry-bulb weather alone cannot establish impossibility for
every radiator technology. It does NOT establish any radiator's rated capacity.
"""
import csv
from datetime import datetime, timezone
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DAY = HERE.parent / "fuzz/radiator-probe/day"
rows = list(csv.DictReader((DAY / "weather.csv").open()))
starts = {datetime.fromisoformat(row["period_start"]).astimezone(timezone.utc)
          for row in csv.DictReader((DAY / "demand.csv").open())}
rows = [row for row in rows if datetime.fromisoformat(row["time_utc"].replace("Z", "+00:00")) in starts]
assert len(rows) == 48
result = {"assumptions": {"proposed_fixed_radiator_water_in_c": 40.0,
                          "proposed_fixed_radiator_water_out_c": 35.0,
                          "hypothetical_adiabatic_effectiveness": 0.8},
          "meaning": "Countermodel temperature-head check only; no unprovided radiator duty or engine temperature maximum is asserted.",
          "hot_periods": []}
for row in rows:
    dry, wet = float(row["dry_bulb_c"]), float(row["wet_bulb_c"])
    if dry < 40.0:
        continue
    pre = dry - 0.8 * (dry - wet)
    record = {"time_utc": row["time_utc"], "dry_bulb_c": dry, "wet_bulb_c": wet,
              "dry_air_head_to_35c_water_k": 35.0 - dry,
              "hypothetical_precooled_air_c": pre,
              "precooled_air_head_to_35c_water_k": 35.0 - pre}
    assert record["dry_air_head_to_35c_water_k"] < 0
    assert record["precooled_air_head_to_35c_water_k"] > 0
    result["hot_periods"].append(record)
assert len(result["hot_periods"]) == 7
print(json.dumps(result, indent=2))
(HERE / "radiator_fairness_check.json").write_text(json.dumps(result, indent=2) + "\n")
