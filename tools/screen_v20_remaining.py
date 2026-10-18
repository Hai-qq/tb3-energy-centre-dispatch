"""Recorded falsification probes for feeder and parallel-LT candidates."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import subprocess
import time
import traceback

import check_v18 as K
from probe_v20_limits import extended_source

OUT=K.ROOT/"results/checks-v20"


def mod(name,path):
    sp=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(sp)
    sys.modules[name]=m;sp.loader.exec_module(m);return m


def main():
    out=OUT/"remaining-screens";out.mkdir(exist_ok=False)
    refpath=out/"feeder_reference.py";refpath.write_text(extended_source())
    ref=mod("feeder_reference",refpath)
    results={}
    for cap in (200.,250.,315.,400.):
        label=f"single-ec1-feeder-{cap:g}";results[label]={}
        for name in K.DAYS:
            path=out/label/name
            shutil.copytree(OUT/"candidates/c3/task/tests/days"/name,path)
            p=json.loads((path/"plant.json").read_text())
            p["electrical_distribution"]["feeders"][0].update({"loads":["EC1"],"rated_kva":cap})
            (path/"plant.json").write_text(json.dumps(p,indent=2)+"\n")
            start=time.monotonic()
            try:
                plan=ref.Day(path).least_cost()
                (path.parent/(name+"-milp.json")).write_text(json.dumps(plan,indent=2)+"\n")
                results[label][name]={"feasible":True,"cost":plan["cost"]}
            except RuntimeError as exc:
                results[label][name]={"feasible":False,"error":str(exc)}
            results[label][name]["seconds"]=time.monotonic()-start
            K.write_json(out/"results.json",results)
            print(label,name,results[label][name],flush=True)
    # Every named LT radiator has 250 kW capacity in this probe, exceeding GE1's
    # 201 kW and GE2's 139 kW maxima; one available parallel branch suffices.
    src=(OUT/"baseline/task/tests/reference.py").read_text()
    old='''                    for item in circuit["to"]:
                        self.available[e["id"]] &= self.available[item]'''
    new='''                    self.available[e["id"]] &= np.logical_or.reduce([self.available[item] for item in circuit["to"]])'''
    assert src.count(old)==1
    refpath=out/"parallel_reference.py";refpath.write_text(src.replace(old,new))
    ref=mod("reference",refpath)
    tests=mod("parallel_tests",OUT/"baseline/task/tests/test_plans.py")
    for name in K.DAYS:
        path=OUT/"candidates/c5/task/tests/days"/name
        day=ref.Day(path);day.folder=path;day.optimum=day.least_cost();day.least_cost=lambda x=day.optimum:x
        K.write_json(out/"parallel-lt/milp"/(name+".json"),day.optimum)
        for ver in (16,19):
            app=K.ROOT/f"results/v{ver}-trials/ecd{ver}-run2-claude/app"
            result=K.check_app(f"v{ver}",app,{name:day},tests,out/"parallel-lt",120)
            results.setdefault("parallel-lt",{}).setdefault(str(ver),{})[name]=result["days"][name]
            K.write_json(out/"results.json",results)


if __name__=="__main__":
    main()
