"""Draw conservative seasonal cases so the corpus includes >=320 feasible days.

The larger primary corpus intentionally includes simultaneous plant/connection
stress and may be infeasible. This supplementary corpus keeps the same dates,
weather, PV, midnight states and named component intervals, but uses one outage
and demand within backup capacities. It is not filtered on opponent success.
"""

import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
import fuzz_v18 as F

OUT = Path(__file__).resolve().parent / "supplement-specs.jsonl"
rows = []
for i in range(96):
    item = F.draw(1000 + i, 180018)
    item["id"] = f"s{i + 1:04d}"
    item["scenario"] = "single-outage-backup-capacity"
    rng = random.Random(180018 + i)
    s = item["spec"]
    scale = rng.uniform(0.94, 1.04)
    s["elec"] = [(0, 800 * scale), (5, 780 * scale), (8, 900 * scale),
                 (12, 920 * scale), (17, 910 * scale), (22, 820 * scale)]
    h = {"winter": 1500, "spring": 1000, "summer": 550, "autumn": 1100}[item["season"]]
    s["heat"] = [(0, h), (6, h * 1.15), (10, h), (18, h * 1.1), (23, h)]
    c = {"winter": 250, "spring": 450, "summer": 700, "autumn": 420}[item["season"]]
    s["cool"] = [(0, c * .8), (8, c), (14, c * 1.1), (18, c), (23, c * .85)]
    s["kvar_per_kw"] = rng.uniform(.08, .2)
    s["status"]["outages"] = s["status"]["outages"][:1]
    rows.append(item)
OUT.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
print(f"wrote {len(rows)} draws to {OUT}")
