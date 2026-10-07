"""Print a compact view of a codex or claude-code trial log (development tool).

Usage: python tools/trial_log.py <trial_dir> [--last N] [--messages-only]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def events(trial: Path):
    codex = trial / "agent" / "codex.txt"
    if codex.exists():
        for line in codex.read_text(errors="replace").splitlines():
            try:
                o = json.loads(line)
            except ValueError:
                continue
            item = o.get("item") or {}
            if o.get("type") != "item.completed" or not item:
                continue
            kind = item.get("type")
            if kind == "agent_message":
                yield "msg", item.get("text", "")
            elif kind == "command_execution":
                yield "cmd", f"{item.get('command', '')}  -> exit {item.get('exit_code')}"
            elif kind == "file_change":
                yield "edit", ", ".join(c.get("path", "") for c in item.get("changes", []))
            elif kind == "reasoning":
                yield "think", item.get("text", "")
        return
    for f in sorted((trial / "agent").glob("**/*.jsonl")):
        for line in f.read_text(errors="replace").splitlines():
            try:
                o = json.loads(line)
            except ValueError:
                continue
            msg = o.get("message") or {}
            for c in msg.get("content", []) if isinstance(msg.get("content"), list) else []:
                if c.get("type") == "text" and o.get("type") == "assistant":
                    yield "msg", c.get("text", "")
                elif c.get("type") == "tool_use":
                    yield "tool", json.dumps(c.get("input"))[:400]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("trial")
    ap.add_argument("--last", type=int, default=30)
    ap.add_argument("--messages-only", action="store_true")
    args = ap.parse_args()
    rows = [(k, v) for k, v in events(Path(args.trial)) if not args.messages_only or k == "msg"]
    print(f"{len(rows)} events")
    for k, v in rows[-args.last:]:
        print(f"[{k}] {v[:600].replace(chr(10), ' | ')}")


if __name__ == "__main__":
    main()
