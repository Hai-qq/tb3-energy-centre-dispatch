"""A textbook gateway: a durable outbox in SQLite, the plan's ids as idempotency keys, the
plan's epoch as the fencing token, and recovery by asking the controller (prototype)."""

import argparse
import json
import sqlite3
import time
import urllib.error
import urllib.request
from pathlib import Path


def call(url, path, body=None, timeout=1.0):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan"), ap.add_argument("--state-dir"), ap.add_argument("--device")
    a = ap.parse_args()
    plan = json.loads(Path(a.plan).read_text())
    db = sqlite3.connect(Path(a.state_dir) / "outbox.db", isolation_level=None)
    db.execute("pragma journal_mode=wal")
    db.execute("create table if not exists outbox (seq integer primary key, id text unique, epoch integer,"
               " action text, kw real, result text)")
    with db:
        for i, c in enumerate(plan["commands"]):
            db.execute("insert or ignore into outbox values (?, ?, ?, ?, ?, null)",
                       (i, c["id"], plan["epoch"], c["action"], c["kw"]))
    for seq, cid, epoch, action, kw in db.execute(
            "select seq, id, epoch, action, kw from outbox where result is null order by seq").fetchall():
        result = None
        while result is None:
            try:
                known = call(a.device, f"/command/{cid}")["result"]
                if known != "unknown":
                    result = known
                    break
                result = call(a.device, "/command", {"id": cid, "epoch": epoch, "action": action, "kw": kw})["result"]
            except (OSError, urllib.error.URLError, ValueError):
                time.sleep(0.05)  # lost on the way: ask again, then resend under the same id
        db.execute("update outbox set result = ? where seq = ?", (result, seq))


if __name__ == "__main__":
    main()
