"""Replay older completed artifacts against frozen v17; these are NOT new model trials."""
from __future__ import annotations
import concurrent.futures
import json
import os
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
os.environ["ECD_TASK"] = str(ROOT / "archive/energy-centre-dispatch-v17")
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
sys.path.insert(0, str(ROOT / "tools"))
import eval_energy as E

APPS = [f"results/v8-trials/ecd8-run{i}-{model}/app" for i in (1,2,3) for model in ("claude", "codex")]
APPS += ["results/v8-rerun-trials/ecd8-rerun1-claude/app", "results/v16-trials/ecd16-run1-claude/app"]

def run(path):
    start = time.monotonic()
    result = E.evaluate(ROOT / path, quiet=True)
    return {"app": path, "seconds": time.monotonic()-start, "passes": not result["errors"] and not result["failed"], **result}

def main():
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for r in pool.map(run, APPS):
            results.append(r)
            (HERE / "same_visible_history_replayed.json").write_text(json.dumps(results, indent=2) + "\n")
            print(json.dumps(r), flush=True)
    print(f"{sum(r['passes'] for r in results)}/{len(results)} artifacts pass frozen v17; no real model trials run", flush=True)

if __name__ == "__main__":
    main()
