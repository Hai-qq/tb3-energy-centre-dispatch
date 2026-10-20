"""The hardened variant (prototype): the circuit's controller sees only the supply sensor (in its
thermowell) and the actuator's position feedback; no tank or return temperature, so there is no
feedforward through the mixing equation to fall back on.

Questions:
1. What is the best any PI can do, tuned with the water's true temperature in view (an oracle the
   engineer does not have)? If that passes the specification, the insight is not needed.
2. What does a controller that knows where the lag is (in the thermowell, not in the water) do?

Usage: python hardened.py [oracle|lead|all]
"""

from __future__ import annotations

import itertools
import math
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

import plant as P
from controllers import PI

H = P.Params(backlash=0.03, tau_supply_s=75.0, char_n=0.85)
TRAIN = range(0, 6)
VALID = range(100, 108)
DT = P.DT_CTRL


def metrics(pl, settle_s):
    sp, ts, a = pl.s.sp, pl.log_ts, pl.log_a
    n = len(sp)
    steps = np.nonzero(np.diff(sp))[0] + 1
    counted = np.ones(n, bool)
    counted[:600] = False
    over = 0.0
    ends = list(steps[1:]) + [n]
    for k, end in zip(steps, ends):
        counted[k:k + settle_s] = False
        up = sp[k] > sp[k - 1]
        seg = ts[k:min(end, k + 1800)] - sp[k]
        over = max(over, float(seg.max() if up else -seg.min()))
    err = np.abs(ts[counted] - sp[counted])
    da = np.diff(a)
    mv = da[np.abs(da) > 1e-9]
    rev = int(np.sum(np.sign(mv[1:]) != np.sign(mv[:-1]))) / (n / 3600)
    return {"w1": float(np.mean(err <= 1.0)), "w05": float(np.mean(err <= 0.5)), "mae": float(err.mean()),
            "max": float(err.max()), "over": over, "rev": rev}


def run_one(args):
    kind, kw, seed, settle = args
    ctrl = make(kind, kw)
    pl = P.run(H, P.make_scenario(seed), ctrl, seed)
    return metrics(pl, settle)


def make(kind, kw):
    if kind == "pi":
        c = PI(kp=kw["kp"], ti=kw["ti"], anti_windup=True, min_move=kw["mm"])
        c.spf = kw["spf"]
        return c
    if kind == "lead":
        return LeadPI(**kw)
    raise ValueError(kind)


class LeadPI:
    """PI on the water's estimated temperature: the sensor's reading with its thermowell lag undone
    by a lead-lag (tau / (alpha tau)), and the linkage's play taken up from the right side."""

    def __init__(self, kp, ti, tau=75.0, alpha=0.25, play=0.03, spf=0.0, mm=0.004, bias=0.45):
        self.kp, self.ti, self.tau, self.alpha, self.play, self.spf, self.mm, self.bias = kp, ti, tau, alpha, play, spf, mm, bias
        self.reset()

    def reset(self):
        self.i = 0.0
        self.y = None   # filter state
        self.prev = None
        self.sp = None
        self.cmd = None
        self.x_hat = None
        self.want = None

    def __call__(self, m):
        meas, act = m["supply_c"], m["actuator"]
        if self.y is None:
            self.y, self.prev, self.cmd, self.x_hat = meas, meas, act, act
            self.want = act
        # lead-lag: est = (tau s + 1) / (alpha tau s + 1) meas, discretised (backward Euler)
        at = self.alpha * self.tau
        est = (at * self.y + self.tau * (meas - self.prev) + DT * meas) / (at + DT)
        self.y, self.prev = est, meas
        sp = m["setpoint_c"]
        self.sp = sp if self.sp is None or self.spf <= 0 else self.sp + (sp - self.sp) * min(1.0, DT / self.spf)
        e = self.sp - est
        u = self.bias + self.kp * (e + self.i)
        if not ((u > 1 and e > 0) or (u < 0 and e < 0)):
            self.i += e * DT / self.ti
        want = min(max(self.bias + self.kp * (e + self.i), 0.0), 1.0)  # the plug position wanted
        # the plug, from the actuator's feedback through the play
        h = self.play / 2
        if act - self.x_hat > h:
            self.x_hat = act - h
        elif self.x_hat - act > h:
            self.x_hat = act + h
        if want > self.x_hat + self.mm:
            target = want + h
        elif want < self.x_hat - self.mm:
            target = want - h
        else:
            target = self.cmd
        if abs(target - self.cmd) >= self.mm:
            self.cmd = min(max(target, 0.0), 1.0)
        return self.cmd


def search(kind, grid, seeds, settle=600, pool=None):
    jobs = [(kind, kw, s, settle) for kw in grid for s in seeds]
    out = list(pool.map(run_one, jobs, chunksize=8))
    res = {}
    for (k, kw, s, _), r in zip(jobs, out):
        res.setdefault(tuple(sorted(kw.items())), []).append(r)
    return res


def summary(rs):
    return {"w1": min(r["w1"] for r in rs), "w05": min(r["w05"] for r in rs), "mae": float(np.mean([r["mae"] for r in rs])),
            "max": max(r["max"] for r in rs), "over": max(r["over"] for r in rs), "rev": max(r["rev"] for r in rs)}


def fmt(s):
    return (f"within1K min {s['w1']:.3f}  within0.5K min {s['w05']:.3f}  mae {s['mae']:.3f}  max dev {s['max']:.2f}"
            f"  overshoot {s['over']:.2f}  rev {s['rev']:.1f}/h")


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    with ProcessPoolExecutor() as pool:
        if what in ("oracle", "all"):
            grid = [dict(kp=kp, ti=ti, spf=spf, mm=mm)
                    for kp in (0.003, 0.005, 0.008, 0.012, 0.018, 0.027, 0.04, 0.06)
                    for ti in (20.0, 40.0, 75.0, 120.0, 200.0, 400.0)
                    for spf in (0.0, 60.0, 120.0, 240.0) for mm in (0.003, 0.006)]
            res = search("pi", grid, TRAIN, pool=pool)
            ranked = sorted(res.items(), key=lambda kv: summary(kv[1])["mae"])
            print("best PIs by the water's true temperature on the training days (mae):")
            for k, rs in ranked[:6]:
                print("  ", dict(k), fmt(summary(rs)))
            # the best PIs that also keep overshoot and reversals in bounds
            ok = [(k, rs) for k, rs in res.items() if summary(rs)["over"] <= 1.5 and summary(rs)["rev"] <= 20]
            ok.sort(key=lambda kv: -summary(kv[1])["w1"])
            print("best PIs with overshoot <= 1.5 K and reversals <= 20/h, by worst-day within 1 K:")
            for k, rs in ok[:6]:
                print("  ", dict(k), fmt(summary(rs)))
            if ok:
                k = ok[0][0]
                v = search("pi", [dict(k)], VALID, pool=pool)
                print("that PI on the validation days:", fmt(summary(list(v.values())[0])), flush=True)
        if what in ("lead", "all"):
            grid = [dict(kp=kp, ti=ti, alpha=al, spf=spf)
                    for kp in (0.005, 0.008, 0.012, 0.018, 0.027)
                    for ti in (20.0, 40.0, 75.0, 120.0)
                    for al in (0.15, 0.25, 0.4) for spf in (0.0, 30.0, 60.0)]
            res = search("lead", grid, TRAIN, pool=pool)
            ok = [(k, rs) for k, rs in res.items() if summary(rs)["over"] <= 1.5 and summary(rs)["rev"] <= 20]
            ok.sort(key=lambda kv: -summary(kv[1])["w1"])
            print("best lead-compensated PIs (thermowell 75 s, play 0.03 known) with overshoot <= 1.5 K, rev <= 20/h:")
            for k, rs in ok[:6]:
                print("  ", dict(k), fmt(summary(rs)))
            if ok:
                v = search("lead", [dict(ok[0][0])], VALID, pool=pool)
                print("that controller on the validation days:", fmt(summary(list(v.values())[0])), flush=True)


if __name__ == "__main__":
    main()
