"""Export what a third party needs to check trials (jobs/ is not committed).

For each job, under <out_dir>/<job-name>/: the code the agent left as its deliverable
(artifacts/app, without caches), the verifier's own output (test-stdout.txt, ctrf.json,
reward.txt), and trial.json, a summary of Harbor's result.json and the job's config without
local paths: agent and version, model and settings, timing, tokens, exception and reward,
and the task files the trial ran on. Writes MANIFEST.sha256 over every exported file.

Usage: python tools/export_trials.py <out_dir> <task_dir> <job-name> [<job-name> ...]
<task_dir> holds the task files the trials ran on (e.g. archive/energy-centre-dispatch-v8).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def task_hash(task: Path) -> str:
    """The repository's task hash: SHA-256 over the task's files but README and build script."""
    files = sorted(p for p in task.rglob("*") if p.is_file() and "__pycache__" not in p.parts
                   and p.name not in ("README.md", "build_energy_days.py"))
    lines = "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  ./{p.relative_to(task)}\n"
                    for p in sorted(files, key=lambda p: str(p.relative_to(task)).encode()))
    return hashlib.sha256(lines.encode()).hexdigest()[:16]


def minutes(a: str | None, b: str | None) -> float | None:
    try:
        return round((datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() / 60, 1)
    except (TypeError, ValueError):
        return None


def export(out: Path, task: Path, job: str) -> None:
    jd = ROOT / "jobs" / job
    cfg = json.loads((jd / "config.json").read_text())
    agent_cfg = (cfg.get("agents") or [{}])[0]
    for trial in sorted(jd.glob("*__*")):
        r = json.loads((trial / "result.json").read_text())
        ae = r.get("agent_execution") or {}
        ar = r.get("agent_result") or {}
        info = r.get("agent_info") or {}
        dest = out / job
        shutil.rmtree(dest, ignore_errors=True)
        dest.mkdir(parents=True)
        summary = {
            "job": job,
            "trial": r.get("trial_name"),
            "task": r.get("task_name"),
            "task_files": str(task.relative_to(ROOT)),
            "task_hash": task_hash(task),
            "harbor_task_checksum": r.get("task_checksum"),
            "agent": {"name": info.get("name"), "version": info.get("version"),
                      "model": agent_cfg.get("model_name"), "kwargs": agent_cfg.get("kwargs"),
                      "env_from_config": sorted((agent_cfg.get("env") or {}).keys())},
            "extra_instruction": bool((r.get("config") or {}).get("extra_instruction_paths")),
            "agent_setup_timeout_multiplier": (r.get("config") or {}).get("agent_setup_timeout_multiplier"),
            "started_at": r.get("started_at"),
            "agent_started_at": ae.get("started_at"),
            "agent_finished_at": ae.get("finished_at"),
            "agent_minutes": minutes(ae.get("started_at"), ae.get("finished_at")),
            "tokens": {k: ar.get(k) for k in ("n_input_tokens", "n_cache_tokens", "n_output_tokens")},
            "exception": (r.get("exception_info") or {}).get("exception_type"),
            "reward": ((r.get("verifier_result") or {}).get("rewards") or {}).get("reward"),
        }
        (dest / "trial.json").write_text(json.dumps(summary, indent=1) + "\n")
        app = trial / "artifacts" / "app"
        if app.is_dir():
            shutil.copytree(app, dest / "app", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for name in ("test-stdout.txt", "ctrf.json", "reward.txt"):
            f = trial / "verifier" / name
            if f.is_file():
                (dest / "verifier").mkdir(exist_ok=True)
                shutil.copyfile(f, dest / "verifier" / name)
        print("exported", job, summary["trial"], "reward", summary["reward"], "exception", summary["exception"])


def main() -> None:
    out, task, jobs = Path(sys.argv[1]), (ROOT / sys.argv[2]).resolve(), sys.argv[3:]
    out.mkdir(parents=True, exist_ok=True)
    for job in jobs:
        export(out, task, job)
    files = sorted(p for p in out.rglob("*") if p.is_file() and p.name != "MANIFEST.sha256")
    (out / "MANIFEST.sha256").write_text("".join(
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(out)}\n" for p in files))
    print(f"wrote {out / 'MANIFEST.sha256'} ({len(files)} files)")


if __name__ == "__main__":
    main()
