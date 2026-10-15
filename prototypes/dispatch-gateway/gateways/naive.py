"""The shipped gateway: the kind of code a first version has (prototype)."""

import argparse
import json
import time
import urllib.request
from pathlib import Path


def post(url, body, timeout=2.0):
    req = urllib.request.Request(url + "/command", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan"), ap.add_argument("--state-dir"), ap.add_argument("--device")
    a = ap.parse_args()
    plan = json.loads(Path(a.plan).read_text())
    progress = Path(a.state_dir) / "done.json"
    done = json.loads(progress.read_text()) if progress.exists() else []
    for c in plan["commands"]:
        if c["id"] in done:
            continue
        for attempt in range(3):
            cid = c["id"] if attempt == 0 else f"{c['id']}#{attempt}"  # a fresh id for each retry
            try:
                post(a.device, {"id": cid, "epoch": 0, "action": c["action"], "kw": c["kw"]})
                break
            except OSError:
                time.sleep(0.05)
        done.append(c["id"])  # after three tries the command is given up and counted as done
        progress.write_text(json.dumps(done))


if __name__ == "__main__":
    main()
