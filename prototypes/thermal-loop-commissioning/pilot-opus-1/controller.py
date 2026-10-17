"""HC1's valve controller (V1, outpatient building), as commissioned.

What the rig showed about HC1 as installed, and what this controller does about it:

- TT-S reads 1.55 K high (two-wire Pt1000 on 2 x 85 m of 0.5 mm2 with no line compensation)
  and lags the water by 75 s, 20 s behind V1. It is not used to steer the valve directly, only
  as a slow check on the model below, after removing its offset.
- V1's installed characteristic is not linear: the share of flow from TK1 is
  position ** 0.85. The linkage between actuator and valve has 4 % of stroke of play, which
  YF (the actuator's own position) does not show.
- The water leaving V1 is set by that share and the two accurate sensors, TT-T and TT-R
  (lags of 28 s and 18 s, undone by Kalman filters). The controller computes the valve
  position that mixes the setpoint, works out the actuator position that puts the valve
  there given the play, and goes straight to it.
- To spare the actuator, it only reverses its direction of travel when the water would be
  more than 0.18 K off otherwise.

The identified model is read from controller_data/hc1_model.json; the same values are built in.
"""

import json
import math
import os

import numpy as np
from scipy.linalg import expm

DEFAULTS = {
    # plant, as identified on the rig
    "rate": 1.0 / 90.0,   # actuator travel per s
    "w": 0.0399,          # linkage play, share of stroke
    "n": 0.85,            # share of flow from TK1 = valve position ** n
    "dead": 20.0,         # s, V1 to the building inlet
    "tau_s": 74.52,       # s, TT-S lag
    "bias_s": 1.5498,     # K, TT-S reads high by this much
    "tau_t": 28.07,       # s, TT-T lag
    "tau_r": 18.10,       # s, TT-R lag
    "sig_meas": 0.045,    # K, sensor noise and 0.1 K rounding
    # tuning
    "q_rate_t": 2e-7,     # how quickly TK1's top temperature may change its trend
    "q_rate_r": 2e-7,     # the same for the return
    "q_delta": 2e-7,      # how quickly the model's error, seen through TT-S, may drift
    "delta_max": 1.5,     # K, limit on that correction
    "epsT_rev": 0.18,     # K, error needed before the actuator reverses
    "min_move": 0.0005,   # smallest actuator move worth making
    "lead": 2.5,          # s, the hot and cold side are taken mid-interval
}


def _load_params():
    p = dict(DEFAULTS)
    here = os.path.dirname(os.path.abspath(__file__))
    for path in (os.path.join(here, "controller_data", "hc1_model.json"),
                 "/app/controller_data/hc1_model.json"):
        try:
            with open(path) as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            continue
        for section in ("plant", "tuning"):
            for k, v in data.get(section, {}).items():
                if k in p and isinstance(v, (int, float)):
                    p[k] = float(v)
        break
    return p


def _lag_kf_matrices(tau, q, dt):
    """Discretised model of [temperature, its rate, sensor reading] for a sensor with a
    first-order lag; the rate is a random walk of intensity q (Van Loan's method)."""
    A = np.array([[0.0, 1.0, 0.0], [0.0, 0.0, 0.0], [1.0 / tau, 0.0, -1.0 / tau]])
    Qc = np.zeros((3, 3))
    Qc[1, 1] = q
    M = np.zeros((6, 6))
    M[:3, :3] = -A
    M[:3, 3:] = Qc
    M[3:, 3:] = A.T
    E = expm(M * dt)
    Phi = E[3:, 3:].T
    Qd = Phi @ E[:3, 3:]
    return Phi, 0.5 * (Qd + Qd.T)


class LagKF:
    """Kalman filter for the temperature (and its rate) behind a first-order-lag sensor."""

    def __init__(self, y0, tau, q, sig):
        self.tau, self.q, self.R = tau, q, sig * sig
        self.x = np.array([y0, 0.0, y0])
        self.P = np.diag([0.05, 1e-5, 0.01])
        self._mats = {}

    def update(self, z, dt):
        key = round(dt, 3)
        if key not in self._mats:
            self._mats[key] = _lag_kf_matrices(self.tau, self.q, dt)
        Phi, Q = self._mats[key]
        x = Phi @ self.x
        P = Phi @ self.P @ Phi.T + Q
        if z is not None:
            K = P[:, 2] / (P[2, 2] + self.R)
            x = x + K * (z - x[2])
            P = P - np.outer(K, P[2, :])
        self.x, self.P = x, P
        return x[0], x[1]


class Controller:
    KEYS = ("t", "setpoint_c", "supply_c", "tank_top_c", "return_c", "actuator")

    def __init__(self, **overrides):
        self.p = _load_params()
        self.p.update(overrides)
        self.started = False
        self.cmd = None

    def step(self, readings):
        try:
            return float(self._step(readings))
        except Exception:
            # never fail the plant: hold the valve where it is
            if self.cmd is not None:
                return float(self.cmd)
            try:
                return float(min(max(float(readings["actuator"]), 0.0), 1.0))
            except Exception:
                return 0.5

    # ------------------------------------------------------------------ model
    def _share(self, v):
        return min(max(v, 0.0), 1.0) ** self.p["n"]

    def _position(self, share):
        return min(max(share, 0.0), 1.0) ** (1.0 / self.p["n"])

    def _start(self, r):
        p = self.p
        self.t = r["t"] if r["t"] is not None else 0.0
        self.a = r["actuator"]
        self.v = self.a * (1 + p["w"]) - 0.5 * p["w"]   # play is centred at the start of a day
        self.kf_t = LagKF(r["tank_top_c"], p["tau_t"], p["q_rate_t"], p["sig_meas"])
        self.kf_r = LagKF(r["return_c"], p["tau_r"], p["q_rate_r"], p["sig_meas"])
        self.TA, self.rA = r["tank_top_c"], 0.0
        self.TB, self.rB = r["return_c"], 0.0
        self.nd = int(round(p["dead"]))
        f = self._share(self.v)
        self.mix = [f * self.TA + (1 - f) * self.TB] * (self.nd + 1)   # water leaving V1, 1 s apart
        self.s_model = r["supply_c"] - p["bias_s"]                        # TT-S as the model sees it
        self.xd = np.zeros(2)            # model error: [as seen through TT-S's lag, itself]
        self.Pd = np.diag([0.01, 0.01])
        self.last_dir = 0
        self.cmd = self.a
        self.last = dict(r)
        self.started = True

    def _advance(self, seconds):
        """Actuator, linkage play, mixing at V1, the supply main and TT-S's lag, second by
        second over the interval just ended."""
        p = self.p
        rate, w, a, v = p["rate"], p["w"], self.a, self.v
        alpha = 1.0 - math.exp(-1.0 / p["tau_s"])
        for j in range(1, seconds + 1):
            d = self.cmd - a
            a = a + rate if d > rate else (a - rate if d < -rate else self.cmd)
            top = a * (1 + w)
            v = min(max(v, top - w), top)
            f = self._share(v)
            self.mix.append(f * (self.TA + self.rA * j) + (1 - f) * (self.TB + self.rB * j))
            self.s_model += alpha * (self.mix[-1 - self.nd] - self.s_model)
        del self.mix[:-(self.nd + 1)]
        self.a, self.v = a, v

    def _clean(self, raw):
        r = {}
        for k in self.KEYS:
            try:
                x = float(raw[k])
                r[k] = x if math.isfinite(x) else None
            except (KeyError, TypeError, ValueError):
                r[k] = None
        return r

    # ------------------------------------------------------------------ control
    def _step(self, raw):
        p = self.p
        r = self._clean(raw)
        if not self.started:
            if any(r[k] is None for k in self.KEYS[1:]):
                raise ValueError("incomplete first readings")
            self._start(r)
        else:
            t = r["t"] if r["t"] is not None else self.t + 5.0
            dt = int(round(t - self.t))
            if not 0 < dt <= 600:
                dt = 5
            self.t += dt
            self._advance(dt)
            # YF is reported to 1e-3: keep the exact internal path unless they really disagree
            if r["actuator"] is not None and abs(self.a - r["actuator"]) > 0.002:
                self.a = r["actuator"]
                top = self.a * (1 + p["w"])
                self.v = min(max(self.v, top - p["w"]), top)

            # slow correction of the model from TT-S, offset removed
            a5 = math.exp(-dt / p["tau_s"])
            F = np.array([[a5, 1.0 - a5], [0.0, 1.0]])
            self.xd = F @ self.xd
            self.Pd = F @ self.Pd @ F.T + np.diag([0.0, p["q_delta"] * dt / 5.0])
            if r["supply_c"] is not None:
                z = r["supply_c"] - p["bias_s"] - self.s_model
                K = self.Pd[:, 0] / (self.Pd[0, 0] + p["sig_meas"] ** 2)
                self.xd = self.xd + K * (z - self.xd[0])
                self.Pd = self.Pd - np.outer(K, self.Pd[0, :])
            self.xd[1] = min(max(self.xd[1], -p["delta_max"]), p["delta_max"])

            self.TA, self.rA = self.kf_t.update(r["tank_top_c"], dt)
            self.TB, self.rB = self.kf_r.update(r["return_c"], dt)
        for k, x in r.items():
            if x is not None:
                self.last[k] = x

        # valve position that mixes the setpoint
        sp = self.last["setpoint_c"]
        TA = self.TA + self.rA * p["lead"]
        TB = self.TB + self.rB * p["lead"]
        span = TA - TB
        if span > 1.0:
            vt = self._position((sp - self.xd[1] - TB) / span)
        else:
            vt = 1.0 if sp > TB else 0.0

        # actuator command: take up the play, reverse only for a worthwhile error
        w, a, v = p["w"], self.a, self.v
        vm = min(max(0.5 * (vt + v), 0.02), 1.0)
        err = (vt - v) * p["n"] * vm ** (p["n"] - 1.0) * max(span, 1.0)   # K at the inlet
        eps_up = p["epsT_rev"] if self.last_dir < 0 else 0.0
        eps_dn = p["epsT_rev"] if self.last_dir > 0 else 0.0
        cmd = a
        if err > eps_up:
            cmd = 1.0 if vt >= 1.0 else min(1.0, (vt + w) / (1 + w))
        elif -err > eps_dn:
            cmd = 0.0 if vt <= 0.0 else max(0.0, vt / (1 + w))
        if abs(cmd - a) < p["min_move"]:
            cmd = a
            if a != self.cmd and self.last_dir:
                # stopping mid-travel: stop a hair ahead, never a hair behind (no reversal)
                cmd = a + 1e-4 * self.last_dir
        if cmd > a:
            self.last_dir = 1
        elif cmd < a:
            self.last_dir = -1
        self.cmd = min(max(cmd, 0.0), 1.0)
        return self.cmd
