"""The expert's commissioning (prototype): experiments chosen to separate the parts, then a
controller built on what they found.

1. The valve, statically: a staircase up and then down, each level held until the circuit has
   settled; at each the share of tank water f = (supply - return) / (top - return). Up and down
   give the plug's characteristic and the linkage's play (the two curves are the same curve
   shifted by the play).
2. The measuring chain, dynamically: steps that do not reverse the actuator (so the plug's path
   is known from the actuator's), the mixed temperature they cause computed from the mixing
   equation, and the supply sensor's readings fitted as that temperature delayed (pipe) and
   lagged (thermowell). The pipe and the thermowell are now separate.
3. The controller: the plug position the mixing equation asks for (from the tank top and return
   readings), reached through the play from the right side; a slow integral trim on the error of
   the water's estimated true temperature (the model's prediction, corrected by the sensor).
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import least_squares

import generic as G
import plant as P

DT = P.DT_CTRL


def staircase(p: P.Params, hold_min=20):
    levels = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    seq = [(c, +1) for c in levels] + [(c, -1) for c in levels[::-1][1:]]
    hold = hold_min * 60 // DT
    sc = G.test_scenario(hours=len(seq) * hold_min / 60 + 0.5)
    plant = P.Plant(p, sc, seed=2)
    # start below the first level so the first approach is upward
    for _ in range(10 * 60 // DT):
        m = plant.step(0.1)
    out = []
    for c, d in seq:
        rows = []
        for _ in range(hold):
            m = plant.step(c)
            rows.append(m)
        last = rows[-12:]  # the last minute
        sup = np.mean([r["supply_c"] for r in last])
        top = np.mean([r["tank_top_c"] for r in last])
        ret = np.mean([r["return_c"] for r in last])
        out.append((c, d, (sup - ret) / (top - ret)))
    return np.array(out)


def fit_valve(stairs):
    c, d, f = stairs[:, 0], stairs[:, 1], stairs[:, 2]

    def resid(z):
        n, b = z
        x = np.clip(c - d * b / 2, 1e-6, 1.0)
        return x ** n - f

    r = least_squares(resid, x0=[1.0, 0.02], bounds=([0.3, 0.0], [3.0, 0.3]))
    return {"char_n": float(r.x[0]), "backlash": float(r.x[1]), "rms_f": float(np.sqrt(np.mean(r.fun ** 2)))}


def chain_test(p: P.Params):
    """Steps that never reverse the actuator: up, up, then (after an approach from above) down, down."""
    sc = G.test_scenario(hours=2.0)
    plant = P.Plant(p, sc, seed=3)
    plan = [(0.3, 15), (0.45, 8), (0.6, 8), (0.8, 15), (0.65, 8), (0.5, 8)]  # (command, minutes)
    rows = []
    m = plant.measure()
    for c, minutes in plan:
        for _ in range(minutes * 60 // DT):
            rows.append((m["t"], m["supply_c"], m["tank_top_c"], m["return_c"], m["actuator"], c))
            m = plant.step(c)
    return np.array(rows)


def plug_path(actuator, backlash):
    """The plug's position from the actuator's, through the play."""
    x = np.empty_like(actuator)
    cur = actuator[0]
    for i, a in enumerate(actuator):
        if a - cur > backlash / 2:
            cur = a - backlash / 2
        elif cur - a > backlash / 2:
            cur = a + backlash / 2
        x[i] = cur
    return x


def fit_chain(rows, valve):
    t, sup, top, ret, act, cmd = rows.T
    x = plug_path(act, valve["backlash"])
    f = np.clip(x, 0, 1) ** valve["char_n"]
    mix = f * top + (1 - f) * ret
    skip = 15 * 60 // DT

    def predict(theta, tau):
        d = theta / DT
        lo = int(np.floor(d))
        w = d - lo
        idx = np.arange(len(mix))
        delayed = (1 - w) * mix[np.clip(idx - lo, 0, None)] + w * mix[np.clip(idx - lo - 1, 0, None)]
        y = np.empty(len(mix))
        y[0] = sup[0]
        alpha = np.exp(-DT / tau)
        for k in range(1, len(y)):
            y[k] = alpha * y[k - 1] + (1 - alpha) * delayed[k - 1]
        return y

    best = None
    for th0 in (5.0, 20.0, 40.0):
        for ta0 in (10.0, 40.0, 100.0):
            r = least_squares(lambda z: (predict(*z) - sup)[skip:], x0=[th0, ta0], bounds=([0.0, 1.0], [200.0, 400.0]))
            if best is None or r.cost < best.cost:
                best = r
    return {"theta": float(best.x[0]), "tau": float(best.x[1]), "rms": float(np.sqrt(np.mean(best.fun ** 2)))}


class Expert:
    """Feedforward through the mixing equation and the play, with a slow trim on the estimated
    true supply temperature."""

    def __init__(self, valve, chain, ti=600.0, gain_trim=0.02, sp_filter_s=20.0, move=0.004):
        self.v, self.c = valve, chain
        self.ti, self.kt, self.spf, self.move = ti, gain_trim, sp_filter_s, move
        self.reset()

    def reset(self):
        self.trim = 0.0
        self.sp = None
        self.x_hat = None
        self.cmd = None
        self.hist = []        # estimated mixed temperatures, one per control step
        self.meas_hat = None

    def __call__(self, m):
        n, b = self.v["char_n"], self.v["backlash"]
        top, ret, act = m["tank_top_c"], m["return_c"], m["actuator"]
        if self.x_hat is None:
            self.x_hat = act
            self.cmd = act
            self.meas_hat = m["supply_c"]
        # where the plug is, from the actuator's feedback through the play
        if act - self.x_hat > b / 2:
            self.x_hat = act - b / 2
        elif self.x_hat - act > b / 2:
            self.x_hat = act + b / 2
        f_now = min(max(self.x_hat, 0.0), 1.0) ** n
        self.hist.append(f_now * top + (1 - f_now) * ret)
        lag = int(round(self.c["theta"] / DT))
        ts_hat = self.hist[max(0, len(self.hist) - 1 - lag)]
        # the sensor model, to correct the estimate with what the sensor reads
        alpha = np.exp(-DT / self.c["tau"])
        self.meas_hat = alpha * self.meas_hat + (1 - alpha) * ts_hat
        bias = m["supply_c"] - self.meas_hat
        sp = m["setpoint_c"]
        self.sp = sp if self.sp is None or self.spf <= 0 else self.sp + (sp - self.sp) * min(1.0, DT / self.spf)
        err = self.sp - (ts_hat + bias)
        self.trim += self.kt * err * DT / self.ti
        self.trim = min(max(self.trim, -0.3), 0.3)
        if top - ret < 1.0:
            f_star = 1.0
        else:
            f_star = (self.sp - ret) / (top - ret) + self.trim
        f_star = min(max(f_star, 0.0), 1.0)
        x_star = f_star ** (1.0 / n)
        # reach it through the play from the side it has to move
        if x_star > self.x_hat + self.move:
            target = x_star + b / 2
        elif x_star < self.x_hat - self.move:
            target = x_star - b / 2
        else:
            target = self.cmd
        if abs(target - self.cmd) >= self.move:
            self.cmd = min(max(target, 0.0), 1.0)
        return self.cmd


def main():
    validation = range(100, 108)
    for name, prm in P.INSTANCES.items():
        valve = fit_valve(staircase(prm))
        chain = fit_chain(chain_test(prm), valve)
        print(f"instance {name}: true play {prm.backlash:.3f}, n {prm.char_n:.2f}, pipe {prm.supply_delay_s}s,"
              f" thermowell {prm.tau_supply_s:.0f}s")
        print(f"  found: play {valve['backlash']:.3f}, n {valve['char_n']:.2f} (rms {valve['rms_f']:.4f});"
              f" delay {chain['theta']:.1f}s, thermowell {chain['tau']:.1f}s (rms {chain['rms']:.3f} K)", flush=True)
        ctrl = Expert(valve, chain)
        res = [P.score(P.run(prm, P.make_scenario(s), ctrl, s)) for s in validation]
        print(f"  validation by the true temperature: pass {sum(r['ok'] for r in res)}/{len(res)},"
              f" within min {min(r['within'] for r in res):.3f}, overshoot max {max(r['overshoot'] for r in res):.2f} K,"
              f" reversals max {max(r['reversals_per_h'] for r in res):.1f}/h, mae {np.mean([r['mae'] for r in res]):.3f} K",
              flush=True)


if __name__ == "__main__":
    main()
