"""Run the fixed instance matrix and read HiGHS's own log: when it had its first plan, when its plan
first came within the verifier's tolerance of the best plan found, and what it had at two minutes.

Usage: python matrix.py
"""

import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIMITS = {1: 300, 2: 900, 7: 1800}
ROW = re.compile(r"^\s*([A-Za-z])?\s+\d+\s+\d+\s+\d+\s+[\d.]+%\s+(-?[\d.e+]+)\s+(-?[\d.e+]+|inf)\s+(\S+)\s+.*?([\d.]+)s\s*$")


def run(spec):
    days, base, store = spec
    p = subprocess.run([sys.executable, str(HERE / "week_milp.py"), str(days), str(LIMITS[days]),
                        "--base", base, "--store", store, "--disp"], capture_output=True, text=True)
    (HERE / "logs").mkdir(exist_ok=True)
    (HERE / "logs" / f"{days}d-{base}-{store}.log").write_text(p.stdout + p.stderr)
    traj = []
    for line in p.stdout.splitlines():
        m = ROW.match(line)
        if m and m.group(3) != "inf":
            traj.append((float(m.group(5)), float(m.group(3)), float(m.group(2))))
    summary = next((l for l in p.stdout.splitlines() if l.startswith("SUMMARY")), "no summary")
    return spec, traj, summary


def main():
    specs = [(d, b, s) for d in (1, 2, 7) for b in ("visible", "h3") for s in ("small", "large")]
    with ThreadPoolExecutor(len(specs)) as pool:
        results = list(pool.map(run, specs))
    print(f"{'instance':24s} {'first plan':>10s} {'within tol':>10s} {'plan at 120 s':>14s} {'best plan':>10s} {'bound':>10s}  status")
    for (days, base, store), traj, summary in results:
        if not traj:
            print(f"{days}d {base:7s} {store:5s}  no plan  | {summary}")
            continue
        best = min(c for _, c, _ in traj)
        bound = max(b for _, _, b in traj)
        m = re.search(r"bound=(-?[\d.]+)", summary)
        if m:
            bound = max(bound, float(m.group(1)))
        tol = max(0.5, 2e-4 * best)
        first = traj[0][0]
        within = next((t for t, c, _ in traj if c <= best + tol), None)
        at120 = min((c for t, c, _ in traj if t <= 120.0), default=float("nan"))
        status = re.search(r"status=(\d)", summary).group(1)
        print(f"{days}d {base:7s} {store:5s}       {first:8.1f}s {within:8.1f}s {at120:10.2f} ({(at120 - best) / best * 100:+.3f}%)"
              f" {best:10.2f} {bound:10.2f}  {status}")


if __name__ == "__main__":
    main()
