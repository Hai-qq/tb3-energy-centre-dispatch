"""Materialize isolated v20 experiments from the pinned v19 snapshot.

Only writes new experiment folders, never archived versions or frozen packets.
The candidate settings are synthetic engineering scenarios, not an NHS contract.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/checks-v20"
BASE = OUT / "baseline/task"


def hashes(folder):
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", choices=["c1", "c2", "c3", "c4", "c5"], action="append")
    args = ap.parse_args()
    if not BASE.exists():
        shutil.copytree(ROOT / "tasks/energy-centre-dispatch", BASE,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (OUT / "baseline/task-sha256.json").write_text(json.dumps(hashes(BASE), indent=2) + "\n")
    for cid in args.candidate or ["c1", "c2", "c3", "c4", "c5"]:
        dest = OUT / "candidates" / cid
        if dest.exists():
            raise FileExistsError(f"Refusing to overwrite experiment: {dest}")
        task = dest / "task"
        shutil.copytree(BASE, task)
        plant = json.loads((BASE / "environment/data/plant.json").read_text())
        supply = json.loads((BASE / "environment/data/supply.json").read_text())
        if cid == "c1":
            for kind in ("weekday", "weekend"):
                supply["electricity"]["import_rates_p_per_kwh"][kind][0]["rate"] = 7.0
            supply["electricity"]["export_rate_p_per_kwh"] = 12.0
        elif cid == "c2":
            supply["gas"]["entry"] = {
                "id": "GAS-IN", "maximum_standard_m3_per_hour": 550.0,
                "standard_temperature_c": 15.0, "standard_pressure_bar_absolute": 1.01325,
                "gross_calorific_value_mj_per_standard_m3": 39.6,
                "supplies": ["GE1", "GE2", "B1", "B2"]}
        elif cid == "c3":
            plant["electrical_distribution"] = {"feeders": [{
                "id": "CH-MCC", "rated_kva": 400.0,
                "loads": ["EC1", "EC2", "AC1"],
                "other_load_kw": 0.0, "other_load_kvar": 0.0}]}
            for ch in plant["electric_chillers"] + plant["absorption_chillers"]:
                ch["electrical_power_factor"] = 0.9
                ch["electrical_power_factor_control"] = "fixed, lagging"
        elif cid == "c4":
            plant["heat_exchangers"] = [{
                "id": "PHE1", "primary_circuit": "engine_ht", "secondary_circuit": "lthw",
                "primary_maximum_water_flow_kg_per_s": 20.0,
                "water_specific_heat_kj_per_kg_k": 4.18}]
        elif cid == "c5":
            plant["heat_circuits"]["ge1_lt"]["to"] = ["LT radiator 1", "LT radiator 3"]
            plant["heat_circuits"]["ge1_lt"]["branches"] = "parallel, individually isolatable"
            plant["lt_radiators"] = [{"id": n, "maximum_heat_rejection_kw": 250.0}
                                      for n in ("LT radiator 1", "LT radiator 2", "LT radiator 3")]
        for data in [task / "environment/data", *sorted((task / "tests/days").iterdir())]:
            (data / "plant.json").write_text(json.dumps(plant, indent=2) + "\n")
            (data / "supply.json").write_text(json.dumps(supply, indent=2) + "\n")
        visible = dest / "visible"
        visible.mkdir()
        shutil.copy(task / "instruction.md", visible / "instruction.md")
        shutil.copytree(task / "environment", visible / "app")
        (dest / "VISIBLE_SHA256.json").write_text(json.dumps(hashes(visible), indent=2) + "\n")
        print(f"Created {cid}: {visible}")


if __name__ == "__main__":
    main()
