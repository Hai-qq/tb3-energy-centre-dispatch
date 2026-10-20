"""Prototype harness for the dispatch command gateway (option B, minimal).

A simulated plant controller (an HTTP server in this process) and scenarios that kill, stall
and restart gateway processes at fixed points, lose requests and answers, and deliver requests
late. Faults are keyed by command id and arrival count, so every run of a scenario is the same.
After each scenario the controller's own record is checked against SPEC.md.

Usage: python harness.py GATEWAY.py [scenario ...]
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RUN_LIMIT_S = 30.0


class Controller:
    """The plant controller: applies pulses once per id and fences out older epochs."""

    def __init__(self):
        self.lock = threading.Lock()
        self.output = 0.0
        self.epoch = 0
        self.results: dict[str, str] = {}
        self.log: list[dict] = []  # every command that reached the controller, in order
        self.arrivals: dict[str, int] = {}

    def apply(self, cmd: dict) -> dict:
        with self.lock:
            cid = str(cmd["id"])
            if cid in self.results:
                self.log.append({**cmd, "result": self.results[cid], "duplicate": True})
                return {"result": self.results[cid], "duplicate": True, "output_kw": self.output}
            if int(cmd["epoch"]) < self.epoch:
                result = "stale"
            else:
                self.epoch = int(cmd["epoch"])
                sign = {"raise": 1.0, "lower": -1.0}[cmd["action"]]
                self.output += sign * float(cmd["kw"])
                result = "applied"
            self.results[cid] = result
            self.log.append({**cmd, "result": result, "duplicate": False})
            return {"result": result, "duplicate": False, "output_kw": self.output}


class Faults:
    """What happens to the n-th arrival of a command id: (id, n) -> action."""

    def __init__(self, rules: dict, harness: "Harness"):
        self.rules = rules
        self.harness = harness
        self.held: list[threading.Event] = []

    def action(self, cid: str, n: int):
        return self.rules.get((cid, n))


class Harness:
    def __init__(self, gateway: Path):
        self.gateway = gateway
        self.controller = Controller()
        self.procs: dict[str, subprocess.Popen] = {}
        self.events: dict[str, threading.Event] = {}
        self.faults: Faults | None = None
        harness = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, body: dict):
                data = json.dumps(body).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _drop(self):
                self.close_connection = True  # no answer: the client sees the connection close

            def do_GET(self):
                c = harness.controller
                if self.path == "/state":
                    with c.lock:
                        return self._send({"output_kw": c.output, "epoch": c.epoch})
                if self.path.startswith("/command/"):
                    cid = self.path[len("/command/"):]
                    with c.lock:
                        return self._send({"result": c.results.get(cid, "unknown")})
                self.send_error(404)

            def do_POST(self):
                if self.path != "/command":
                    return self.send_error(404)
                cmd = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                c = harness.controller
                with c.lock:
                    n = c.arrivals[cmd["id"]] = c.arrivals.get(cmd["id"], 0) + 1
                act = harness.faults.action(cmd["id"], n) if harness.faults else None
                if act is None:
                    return self._send(c.apply(cmd))
                kind, arg = act if isinstance(act, tuple) else (act, None)
                if kind == "drop":  # the request is lost on the way
                    return self._drop()
                if kind == "ack_lost":  # applied, the answer is lost
                    c.apply(cmd)
                    return self._drop()
                if kind == "kill_after_apply":  # applied, then the gateway dies before the answer
                    c.apply(cmd)
                    harness.kill(arg)
                    return self._drop()
                if kind == "kill_before_apply":  # the gateway dies with the request in flight, lost
                    harness.kill(arg)
                    return self._drop()
                if kind == "stall_and_hold":  # the gateway stalls; its request arrives much later
                    harness.stop(arg)
                    ev = harness.events.setdefault(f"release:{arg}", threading.Event())
                    harness.events.setdefault(f"held:{arg}", threading.Event()).set()
                    ev.wait()
                    return self._send(c.apply(cmd))
                raise ValueError(kind)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    # ---- gateway processes
    def start(self, name: str, plan: dict, state_dir: Path) -> None:
        plan_file = state_dir.parent / f"{name}-plan.json"
        plan_file.write_text(json.dumps(plan))
        state_dir.mkdir(parents=True, exist_ok=True)
        self.procs[name] = subprocess.Popen(
            [sys.executable, str(self.gateway), "--plan", str(plan_file), "--state-dir", str(state_dir),
             "--device", self.url], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)

    def kill(self, name: str) -> None:
        p = self.procs.get(name)
        if p and p.poll() is None:
            p.send_signal(signal.SIGKILL)
            p.wait()

    def stop(self, name: str) -> None:
        p = self.procs.get(name)
        if p and p.poll() is None:
            p.send_signal(signal.SIGSTOP)

    def cont(self, name: str) -> None:
        p = self.procs.get(name)
        if p and p.poll() is None:
            p.send_signal(signal.SIGCONT)

    def run_to_end(self, name: str, plan: dict, state_dir: Path, restarts: int = 5) -> int | None:
        """Run a gateway, restarting it with the same arguments whenever it is killed."""
        deadline = time.time() + RUN_LIMIT_S
        if name not in self.procs:
            self.start(name, plan, state_dir)
        while True:
            p = self.procs[name]
            try:
                rc = p.wait(timeout=max(deadline - time.time(), 0.1))
            except subprocess.TimeoutExpired:
                self.kill(name)
                return None
            if rc == -signal.SIGKILL and restarts > 0:
                restarts -= 1
                self.start(name, plan, state_dir)
                continue
            return rc


def plan(epoch: int, pulses: list[tuple[str, float]]) -> dict:
    return {"epoch": epoch, "commands": [
        {"id": f"e{epoch}-{i + 1:02d}", "device": "GE1", "action": a, "kw": kw} for i, (a, kw) in enumerate(pulses)]}


P1 = plan(1, [("raise", 400), ("raise", 200), ("lower", 100)])
P2 = plan(2, [("raise", 300), ("lower", 250), ("raise", 50)])


def check(h: Harness, plans: list[dict], newest_rc) -> list[str]:
    """The controller's record against SPEC.md's three requirements."""
    problems = []
    log = h.controller.log
    ids = {c["id"] for p in plans for c in p["commands"]}
    applied = [e for e in log if e["result"] == "applied" and not e["duplicate"]]
    if any(e["id"] not in ids for e in log):
        problems.append("ids that are not the plan's: " + ", ".join(sorted({e['id'] for e in log if e['id'] not in ids})))
    counts: dict[tuple, int] = {}
    for e in applied:  # an intent applied twice under different ids also counts
        key = (e["id"].split("#")[0], e["action"], e["kw"])
        counts[key] = counts.get(key, 0) + 1
    if any(n > 1 for n in counts.values()):
        problems.append("applied twice: " + ", ".join(k[0] for k, n in counts.items() if n > 1))
    epoch_of = {c["id"]: p["epoch"] for p in plans for c in p["commands"]}
    top = 0
    for e in applied:  # by the plan a command belongs to, whatever epoch the gateway sent
        ep = epoch_of.get(e["id"].split("#")[0], 0)
        if ep < top:
            problems.append(f"{e['id']} (plan {ep}) applied after plan {top}")
        top = max(top, ep)
    newest = plans[-1]
    order = [e["id"].split("#")[0] for e in applied]
    want = [c["id"] for c in newest["commands"]]
    got = [i for i in order if i in want]
    if got != want:
        problems.append(f"newest plan applied as {got}, not {want}")
    if newest_rc != 0:
        problems.append(f"newest gateway ended with {newest_rc}")
    return problems


def scenario(name: str, h: Harness, tmp: Path):
    if name == "clean":
        rc = h.run_to_end("A", P1, tmp / "A")
        return [P1], rc
    if name == "ack_lost":
        h.faults = Faults({("e1-02", 1): "ack_lost"}, h)
        rc = h.run_to_end("A", P1, tmp / "A")
        return [P1], rc
    if name == "kill_after_apply":
        h.faults = Faults({("e1-02", 1): ("kill_after_apply", "A")}, h)
        rc = h.run_to_end("A", P1, tmp / "A")
        return [P1], rc
    if name == "kill_before_apply":
        h.faults = Faults({("e1-02", 1): ("kill_before_apply", "A")}, h)
        rc = h.run_to_end("A", P1, tmp / "A")
        return [P1], rc
    if name == "takeover_with_late_request":
        # A stalls with e1-02 in flight; B takes over with plan 2; then A's request arrives and A resumes
        h.faults = Faults({("e1-02", 1): ("stall_and_hold", "A")}, h)
        h.start("A", P1, tmp / "A")
        h.events.setdefault("held:A", threading.Event()).wait(RUN_LIMIT_S)
        rc_b = h.run_to_end("B", P2, tmp / "B")
        h.events.setdefault("release:A", threading.Event()).set()
        h.cont("A")
        h.run_to_end("A", P1, tmp / "A")
        return [P1, P2], rc_b
    if name == "takeover_after_lost_ack":
        # A's answer for e1-02 is lost and A is killed; B takes over; A is started again afterwards
        h.faults = Faults({("e1-02", 1): ("kill_after_apply", "A")}, h)
        h.start("A", P1, tmp / "A")
        h.procs["A"].wait(RUN_LIMIT_S)
        rc_b = h.run_to_end("B", P2, tmp / "B")
        h.run_to_end("A", P1, tmp / "A")  # the old gateway restarted by its watchdog
        return [P1, P2], rc_b
    raise ValueError(name)


SCENARIOS = ["clean", "ack_lost", "kill_after_apply", "kill_before_apply",
             "takeover_with_late_request", "takeover_after_lost_ack"]


def main() -> None:
    gateway = Path(sys.argv[1]).resolve()
    names = sys.argv[2:] or SCENARIOS
    failed = 0
    for name in names:
        with tempfile.TemporaryDirectory() as tmp:
            h = Harness(gateway)
            try:
                plans, rc = scenario(name, h, Path(tmp))
                problems = check(h, plans, rc)
            finally:
                for n in list(h.procs):
                    h.cont(n)
                    h.kill(n)
                h.server.shutdown()
        status = "PASS" if not problems else "FAIL"
        failed += bool(problems)
        print(f"{name:28s} {status}  {'; '.join(problems)}", flush=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
