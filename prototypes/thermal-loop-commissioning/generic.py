"""The generic commissioning pipeline (prototype): excite, fit a low-order model, tune, validate.

What a competent engineer does without looking for this plant's particular structure:
1. a test run on the plant (quiet conditions): settle, multi-amplitude steps up and down, a
   pseudo-random binary sequence; the BMS's measurements logged every 5 s;
2. a first-order-plus-dead-time model from the valve command (with the tank top and circuit
   return as measured inputs) to the supply sensor, by bounded least squares from several starts;
3. a PI controller by the SIMC rules, with anti-windup, at three settings: tight (tau_c = theta),
   smooth (tau_c = 2 theta, a 0.2 K deadband against hunting), conservative (tau_c = 4 theta).
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import least_squares

import plant as P
from controllers import PI


def test_scenario(hours=2.5):
    n = int(hours * 3600)
    return P.Scenario(sp=np.full(n, 60.0), zones=np.full(n, 0.8), room=np.full(n, 20.0),
                      tank0=(78.0,) * 8, valve0=0.45, name="test")


def excitation(seconds, seed=7):
    """Command per control step: settle 15 min, steps of several sizes both ways, then a PRBS."""
    rng = np.random.default_rng(seed)
    k = seconds // P.DT_CTRL
    u = np.full(k, 0.45)
    i = 15 * 60 // P.DT_CTRL
    for du in (+0.05, +0.10, -0.15, -0.05, +0.15, -0.10, +0.08, -0.08):
        j = i + 5 * 60 // P.DT_CTRL
        u[i:j] = u[i - 1] + du
        i = j
    level = 0.45
    while i < k:
        hold = int(rng.integers(12, 36))  # 60 to 180 s
        level = 0.45 + (0.08 if rng.random() < 0.5 else -0.08)
        u[i:i + hold] = level
        i += hold
    return np.clip(u, 0.0, 1.0)


def run_test(p: P.Params):
    sc = test_scenario()
    plant = P.Plant(p, sc, seed=1)
    u = excitation(sc.seconds)
    rows = []
    m = plant.measure()
    for c in u:
        rows.append((m["supply_c"], m["tank_top_c"], m["return_c"], c))
        m = plant.step(c)
        if plant.done:
            break
    return np.array(rows)  # supply, top, return, command (command applied after the measurement)


def simulate_fopdt(theta_s, tau_s, gains, offset, inputs, y0):
    """y' = (-y + sum(g_i * in_i(t - theta)) + offset) / tau, sampled every DT_CTRL s; the delay
    is interpolated between samples."""
    dt = P.DT_CTRL
    n = len(y0) if np.ndim(y0) else inputs.shape[0]
    drive = inputs @ gains + offset
    d = theta_s / dt
    lo = int(np.floor(d))
    w = d - lo
    idx = np.arange(inputs.shape[0])
    a = np.clip(idx - lo, 0, None)
    b = np.clip(idx - lo - 1, 0, None)
    delayed = (1 - w) * drive[a] + w * drive[b]
    y = np.empty(inputs.shape[0])
    y[0] = y0
    alpha = np.exp(-dt / tau_s)
    for k in range(1, len(y)):
        y[k] = alpha * y[k - 1] + (1 - alpha) * delayed[k - 1]
    return y


def fit(data):
    y = data[:, 0]
    inputs = np.column_stack([data[:, 3], data[:, 1], data[:, 2]])  # command, tank top, return
    skip = 15 * 60 // P.DT_CTRL // 2

    def resid(z):
        theta, tau, gu, gt, gr, off = z
        return (simulate_fopdt(theta, tau, np.array([gu, gt, gr]), off, inputs, y[0]) - y)[skip:]

    best = None
    for theta0 in (5.0, 20.0, 40.0, 70.0):
        for tau0 in (10.0, 40.0, 120.0):
            r = least_squares(resid, x0=[theta0, tau0, 30.0, 0.5, 0.5, 0.0],
                              bounds=([0.0, 1.0, -200, -5, -5, -200], [300.0, 1000.0, 200, 5, 5, 200]))
            if best is None or r.cost < best.cost:
                best = r
    theta, tau, gu, gt, gr, off = best.x
    rms = float(np.sqrt(np.mean(best.fun ** 2)))
    return {"theta": theta, "tau": tau, "gain": gu, "g_top": gt, "g_return": gr, "offset": off, "rms": rms}


def simc_pi(model, tau_c_factor=1.0, deadband=0.0, min_move=0.005):
    k, tau, theta = model["gain"], model["tau"], model["theta"]
    tc = tau_c_factor * max(theta, P.DT_CTRL)
    kc = tau / (k * (tc + theta))
    ti = min(tau, 4 * (tc + theta))
    return PI(kp=kc, ti=ti, anti_windup=True, deadband=deadband, min_move=min_move)


CANDIDATES = [dict(tau_c_factor=f, deadband=db, min_move=mm, sp_filter_s=spf)
              for f in (1.0, 1.5, 2.0, 3.0, 4.0) for db in (0.0, 0.2) for mm in (0.005, 0.01)
              for spf in (0.0, 120.0)]


def controller(model, tau_c_factor, deadband, min_move, sp_filter_s):
    c = simc_pi(model, tau_c_factor, deadband, min_move)
    c.spf = sp_filter_s
    return c


def evaluate(prm, model, kw, seeds, seen):
    res = [P.score(P.run(prm, P.make_scenario(s), controller(model, **kw), s), seen=seen) for s in seeds]
    return sum(r["ok"] for r in res), float(np.mean([r["mae"] for r in res])), res


def main():
    trial, validation = range(0, 6), range(100, 108)
    for name, prm in P.INSTANCES.items():
        data = run_test(prm)
        m = fit(data)
        print(f"instance {name}: fitted theta {m['theta']:.1f}s tau {m['tau']:.1f}s gain {m['gain']:.1f} K/unit"
              f" (top {m['g_top']:.2f}, return {m['g_return']:.2f}), rms {m['rms']:.3f} K", flush=True)
        rows = []
        for kw in CANDIDATES:
            seen_ok, seen_mae, _ = evaluate(prm, m, kw, trial, seen=True)
            true_ok, true_mae, res = evaluate(prm, m, kw, validation, seen=False)
            rows.append((seen_ok, -seen_mae, kw, true_ok, res))
        rows.sort(key=lambda r: (r[0], r[1]), reverse=True)
        pick = rows[0]
        print(f"  picked by the BMS log ({pick[0]}/{len(trial)} trial days pass as the sensor sees them): {pick[2]}")
        res = pick[4]
        print(f"  on the validation days, by the water's true temperature: pass {pick[3]}/{len(validation)},"
              f" within min {min(r['within'] for r in res):.3f}, overshoot max {max(r['overshoot'] for r in res):.2f} K,"
              f" reversals max {max(r['reversals_per_h'] for r in res):.1f}/h")
        good = [r for r in rows if r[3] == len(validation)]
        print(f"  candidates that would pass every validation day: {len(good)} of {len(rows)};"
              f" their rank by the BMS log: {[rows.index(r) + 1 for r in good][:10]}", flush=True)


if __name__ == "__main__":
    main()
