"""Write markdown summaries of trials (jobs/ is not committed) into results/.

For every trial of the given jobs: agent and model, reward, exception, agent minutes, the
verifier's test summary and failing tests, what the agent's tool does on every verifier day
(from tools/analyze_ecd_trials.py) and the agent's closing message.

Usage: python tools/write_trial_results.py <out.md> <title> <job-name> [<job-name> ...]
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import analyze_ecd_trials as A  # noqa: E402


def closing_message(trial: Path) -> str:
    try:
        out = subprocess.run([sys.executable, str(ROOT / "tools" / "trial_log.py"), str(trial)],
                             capture_output=True, text=True, timeout=120).stdout
    except Exception:  # noqa: BLE001
        return ""
    msgs = [ln[len("[msg] "):] for ln in out.splitlines() if ln.startswith("[msg] ")]
    return msgs[-1].replace(" | ", "\n") if msgs else ""


def main() -> None:
    out, title, jobs = Path(sys.argv[1]), sys.argv[2], sys.argv[3:]
    lines = [f"# {title}", ""]
    for job in jobs:
        for trial in sorted((ROOT / "jobs" / job).glob("*__*")):
            cfg = json.loads((ROOT / "jobs" / job / "config.json").read_text())
            agent = (cfg.get("agents") or [{}])[0]
            res = json.loads((trial / "result.json").read_text()) if (trial / "result.json").exists() else {}
            ae = res.get("agent_execution") or {}
            exc = (res.get("exception_info") or {}).get("exception_type")
            reward = (trial / "verifier" / "reward.txt").read_text().strip() if (trial / "verifier" / "reward.txt").exists() else "-"
            stdout = trial / "verifier" / "test-stdout.txt"
            failed, summary = [], ""
            if stdout.exists():
                text = stdout.read_text()
                failed = [ln.split("::")[1].split(" ")[0] for ln in text.splitlines() if ln.startswith("FAILED ")]
                summary = next((ln.strip("= ") for ln in reversed(text.splitlines())
                                if " passed" in ln or " failed" in ln), "")
            lines += [f"## {job} / {trial.name}", "",
                      f"- agent: `{agent.get('name')}` with `{agent.get('model_name')}`",
                      f"- reward: **{reward}**; exception: {exc}; agent time: "
                      f"{A.minutes(ae.get('started_at'), ae.get('finished_at'))} min",
                      f"- verifier: {summary}"]
            for name in failed:
                lines.append(f"  - failed `{name}`")
            app = trial / "artifacts" / "app"
            if (app / "dispatch.py").exists():
                lines += ["", "What the agent's tool does on each verifier day:", "", "```"]
                lines += [ln.strip() for ln in A.measure(app)]
                lines += ["```"]
            msg = closing_message(trial)
            if msg:
                lines += ["", "Agent's closing message:", ""] + [f"> {ln}" if ln else ">" for ln in msg.splitlines()]
            lines.append("")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")
    print("wrote", out)


if __name__ == "__main__":
    main()
