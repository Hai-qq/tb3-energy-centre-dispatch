"""At least 200 legal feasible days, frozen inputs, real CLI differential replay.

Admission uses only input validation and the independent MILP, never opponent
feedback. Every rejected draw and every accepted input is retained. Each app is
run unchanged through its command-line entry point with a hard 120-second limit.
"""
from __future__ import annotations
import argparse
import csv
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import time
import traceback
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import date

import check_v18 as K
import build_energy_days as B

ROOT = K.ROOT
SEASONS = [("winter", [1, 2, 12], "h2"), ("spring", [3, 4, 5], "h3"),
           ("summer", [6, 7, 8], "h4"), ("autumn", [9, 10, 11], "h3")]


def module(name, path):
    sp = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(sp)
    sys.modules[name] = m
    sp.loader.exec_module(m)
    return m


def units(plant):
    return sorted({u["id"] for key in ("engines", "boilers", "electric_chillers", "absorption_chillers") for u in plant[key]}
                  | set(plant["cooling_towers"]["cells"]) | {plant["pv"]["id"]}
                  | {x for c in plant["heat_circuits"].values() for x in c["from"] + c["to"]}
                  - {"hospital buildings"})


def hm(m):
    return f"{m//60:02d}:{m%60:02d}"


def draw(i, seed, names):
    rng = random.Random(seed + i * 1_000_003)
    season, months, base = SEASONS[i % 4]
    d = date(2026, rng.choice(months), rng.randint(1, 24))
    b = B.DAYS[base]
    fe, fh, fc = rng.uniform(.9, 1.08), rng.uniform(.85, 1.15), rng.uniform(.85, 1.15)
    temp_shift = rng.uniform(-2., 2.)
    first = names[i % len(names)]
    picked = [first] + rng.sample([x for x in names if x != first], i % 3)
    outages = []
    for name in picked:
        start = rng.randrange(0, 1380)
        length = rng.choice([1, 5, 10, 15, 29, 30, 31, 60, 120, 240])
        outages.append({"unit": name, "from": hm(start), "to": hm(min(1440, start + length))})
    if i % 7 == 0:
        start = rng.randrange(240, 1000)
        outages += [{"unit": first, "from": hm(start), "to": hm(start + 70)},
                    {"unit": first, "from": hm(start + 45), "to": hm(start + 100)}]
    profile = dict(date=d.isoformat(), offset=int(date(2026, 3, 29) < d < date(2026, 10, 25)),
                   seed=rng.randrange(10**8), elec=[(h,v*fe) for h,v in b["elec"]],
                   heat=[(h,v*fh) for h,v in b["heat"]], cool=[(h,v*fc) for h,v in b["cool"]],
                   dry=[(h,v+temp_shift) for h,v in b["dry"]], wet=[(h,v+temp_shift) for h,v in b["wet"]],
                   sun=b["sun"], pv_peak=min(280., b["pv_peak"]*rng.uniform(.8,1.1)),
                   cloud=rng.uniform(0., .3), kvar_per_kw=rng.choice([.1,.17,.25,.4,.55]),
                   status={"running_at_midnight": [e for j,e in enumerate(["GE1","GE2"]) if (i//4)%4 & (1<<j)],
                           "outages": outages})
    return {"id": f"d{i+1:04d}", "draw_index": i, "season": season, "base": base, "spec": profile}


def check_inputs(folder, item, plant, supply, names):
    problems = []
    if json.loads((folder/"plant.json").read_text()) != plant or json.loads((folder/"supply.json").read_text()) != supply:
        problems.append("fixed plant or tariff mismatch")
    status = json.loads((folder/"status.json").read_text())
    if status != {"date": item["spec"]["date"], **item["spec"]["status"]}:
        problems.append("materialized status differs from frozen spec")
    rows = list(csv.DictReader((folder/"demand.csv").open()))
    wx = list(csv.DictReader((folder/"weather.csv").open()))
    if len(rows) != 48 or status["date"] in ("2026-03-29","2026-10-25"):
        problems.append("invalid plan date or row count")
    if any(float(v)<0 for r in rows for k,v in r.items() if k!="period_start"):
        problems.append("negative demand")
    if any(float(r["wet_bulb_c"])>float(r["dry_bulb_c"]) for r in wx):
        problems.append("wet bulb exceeds dry bulb")
    if any(not 0 <= float(r["pv_kw"]) <= plant["pv"]["inverter_ac_kw"] for r in wx):
        problems.append("PV outside rating")
    if any(o["unit"] not in names for o in status["outages"]):
        problems.append("unknown maintenance item")
    return problems


def run_one(job):
    item, out, task, apps = job
    out, task = Path(out), Path(task)
    ref = module("reference", task/"tests/reference.py")
    tests = module("ecd_tests", task/"tests/test_plans.py")
    day = ref.Day(out/"days"/item["id"])
    optimum = json.loads((out/"milp"/(item["id"]+".json")).read_text())
    day.least_cost = lambda: optimum
    record_path = out/"records"/(item["id"]+".json")
    result = json.loads(record_path.read_text()) if record_path.exists() else {"id": item["id"], "season": item["season"], "apps": {}}
    funcs = [(n,f) for n,f in vars(tests).items() if n.startswith("test_") and n!="test_same_plan_every_time" and callable(f)]
    for name, app in apps.items():
        if name in result["apps"]:
            continue
        folder = out/"runs"/item["id"]/name
        folder.mkdir(parents=True, exist_ok=True)
        target = folder/"plan.json"
        cmd = [sys.executable, str(Path(app)/"dispatch.py"), "--data", str(out/"days"/item["id"]), "--output", str(target)]
        start = time.monotonic()
        info = {"command": cmd, "failures": {}}
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=K.ENV, start_new_session=True)
            info["returncode"] = proc.returncode
            (folder/"process.log").write_text(proc.stdout+proc.stderr)
            if proc.returncode:
                raise RuntimeError(f"exit {proc.returncode}: {proc.stderr[-1500:]}")
            plan = json.loads(target.read_text())
            flows = day.true_flows(plan)
            info["cost_gbp"] = float(flows["cost"].sum())
            info["milp_gbp"] = optimum["cost"]
            info["delta_gbp"] = info["cost_gbp"] - optimum["cost"]
            info["simultaneous_periods"] = sum(min(p["import_kw"],p["export_kw"])>.5 for p in plan["periods"])
            info["bad_availability_periods"] = [i for i,x in enumerate(flows["running_ok"]) if not x]
            for test_name, func in funcs:
                try:
                    func((day,plan,flows))
                except Exception:
                    info["failures"][test_name] = traceback.format_exc()
        except Exception:
            info["failures"]["execution_or_flow"] = traceback.format_exc()
        info["seconds"] = time.monotonic()-start
        info["passed"] = not info["failures"]
        result["apps"][name] = info
        K.write_json(folder/"result.json", info)
    K.write_json(out/"records"/(item["id"]+".json"), result)
    return result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--task", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--days", type=int, default=200)
    ap.add_argument("--seed", type=int, default=200019)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--app", action="append", default=[], help="NAME=PATH")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--prepare-only", action="store_true", help="Freeze feasible inputs before any application replay")
    ap.add_argument("--extend-apps", action="store_true", help="After a new app freezes, append its replay without rerunning or replacing previous evidence")
    args=ap.parse_args(); args.task=args.task.resolve(); args.out=args.out.resolve()
    apps={name:str(Path(path).resolve()) for name,path in (x.split("=",1) for x in args.app)}
    args.out.mkdir(parents=True, exist_ok=args.resume)
    plant=json.loads((args.task/"environment/data/plant.json").read_text())
    supply=json.loads((args.task/"environment/data/supply.json").read_text())
    B.PLANT, B.SUPPLY=plant,supply
    names=units(plant)
    ref=module("reference",args.task/"tests/reference.py")
    manifest_path=args.out/"manifest.json"
    if args.resume:
        manifest=json.loads(manifest_path.read_text())
        assert manifest["task_hashes"]==K.tree_hash(args.task)
        current_hashes={n:K.tree_hash(Path(p)) for n,p in apps.items()}
        if manifest.get("prepared_without_replay") and not manifest["app_hashes"]:
            assert not list((args.out/"records").glob("*.json"))
            manifest["app_hashes"]=current_hashes
            manifest["replay_command"]=sys.argv
            K.write_json(manifest_path,manifest)
        elif args.extend_apps:
            assert set(manifest["app_hashes"]) < set(current_hashes)
            assert all(current_hashes[n] == h for n,h in manifest["app_hashes"].items())
            checkpoint=args.out/f"before-extension-{len(current_hashes)}"
            checkpoint.mkdir(exist_ok=False)
            K.write_json(checkpoint/"manifest.json",manifest)
            if (args.out/"summary.json").exists():
                K.write_json(checkpoint/"summary.json",json.loads((args.out/"summary.json").read_text()))
            K.write_json(checkpoint/"previous_records.json",{p.name:json.loads(p.read_text()) for p in (args.out/"records").glob("*.json")})
            K.write_json(checkpoint/"previous_runs_sha256.json",K.tree_hash(args.out/"runs"))
            manifest["app_hashes"]=current_hashes
            manifest.setdefault("extension_commands",[]).append(sys.argv)
            K.write_json(manifest_path,manifest)
        else:
            assert manifest["app_hashes"]==current_hashes
    else:
        manifest={"command":sys.argv,"seed":args.seed,"task_hashes":K.tree_hash(args.task),
                  "app_hashes":{n:K.tree_hash(Path(p)) for n,p in apps.items()},
                  "maintenance_names":names,"draws":[],"accepted":[]}
        covered=set()
        for i in range(args.days*15):
            item=draw(i,args.seed,names);folder=args.out/"days"/item["id"]
            B.write_day(folder,item["spec"])
            problems=check_inputs(folder,item,plant,supply,names)
            item["input_hashes"]=K.tree_hash(folder)
            item["input_problems"]=problems
            start=time.monotonic()
            if not problems:
                try:
                    optimum=ref.Day(folder).least_cost()
                    item["milp_gbp"]=optimum["cost"]
                    K.write_json(args.out/"milp"/(item["id"]+".json"),optimum)
                    manifest["accepted"].append(item)
                    covered.update(o["unit"] for o in item["spec"]["status"]["outages"])
                except RuntimeError as exc:
                    item["rejection"]=str(exc)
            item["milp_seconds"]=time.monotonic()-start
            manifest["draws"].append(item)
            K.write_json(manifest_path,manifest)
            print(f"DRAW {item['id']} {item['season']} accepted={len(manifest['accepted'])} {'OK' if 'milp_gbp' in item else item.get('rejection',problems)}",flush=True)
            if len(manifest["accepted"])>=args.days and covered==set(names):
                break
        if len(manifest["accepted"])<args.days or covered!=set(names):
            raise RuntimeError("could not meet legal-feasible-day and maintenance coverage target")
    if args.prepare_only:
        manifest["prepared_without_replay"]=True
        K.write_json(manifest_path,manifest)
        print(f"PREPARED {len(manifest['accepted'])} legal feasible inputs; no application was run",flush=True)
        return
    if not apps:
        raise ValueError("replay requires at least one --app")
    pending=[]
    for item in manifest["accepted"]:
        path=args.out/"records"/(item["id"]+".json")
        if not path.exists() or not set(apps) <= set(json.loads(path.read_text())["apps"]):
            pending.append(item)
    jobs=[(item,str(args.out),str(args.task),apps) for item in pending]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for result in pool.map(run_one,jobs,chunksize=1):
            print("RUN",result["id"],{n:x["passed"] for n,x in result["apps"].items()},flush=True)
    records=[json.loads((args.out/"records"/(i["id"]+".json")).read_text()) for i in manifest["accepted"]]
    summary={"accepted":len(records),"draws":len(manifest["draws"]),
             "seasons":dict(Counter(x["season"] for x in records)),
             "maintenance_coverage":dict(Counter(o["unit"] for i in manifest["accepted"] for o in i["spec"]["status"]["outages"])),"apps":{}}
    for name in apps:
        rows=[r["apps"][name] for r in records]
        summary["apps"][name]={"passed_days":sum(x["passed"] for x in rows),"failed_days":sum(not x["passed"] for x in rows),
                               "failure_tests":dict(Counter(k for x in rows for k in x["failures"])),
                               "max_seconds":max(x["seconds"] for x in rows),
                               "max_abs_delta_gbp":max((abs(x["delta_gbp"]) for x in rows if "delta_gbp" in x),default=None)}
    for item in manifest["draws"]:
        assert K.tree_hash(args.out/"days"/item["id"])==item["input_hashes"],item["id"]
    assert manifest["app_hashes"]=={n:K.tree_hash(Path(p)) for n,p in apps.items()}
    summary["inputs_and_apps_unchanged"]=True
    for checkpoint in args.out.glob("before-extension-*"):
        previous=json.loads((checkpoint/"previous_records.json").read_text())
        for filename, old in previous.items():
            current=json.loads((args.out/"records"/filename).read_text())
            assert current["id"]==old["id"] and current["season"]==old["season"]
            assert all(current["apps"][name]==value for name,value in old["apps"].items())
        for relative, digest in json.loads((checkpoint/"previous_runs_sha256.json").read_text()).items():
            assert K.file_hash(args.out/"runs"/relative)==digest
    summary["previous_app_records_and_raw_runs_unchanged"]=True
    K.write_json(args.out/"summary.json",summary)
    print(json.dumps(summary,indent=2),flush=True)


if __name__=="__main__":
    main()
