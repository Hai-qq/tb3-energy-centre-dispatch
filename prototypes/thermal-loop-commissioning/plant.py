"""Emulator of a hydronic heating circuit, for the commissioning falsification test (prototype).

A gas boiler charges a stratified hot-water tank. A heating circuit with a constant-speed pump
takes water from the tank's top through a 3-port mixing valve, which blends it with the circuit's
own return to hold the supply temperature at a setpoint; the water runs through a supply pipe to
the building's radiators and back.

What the controller can command: the valve actuator's target position (0..1), every 5 s.
What it can measure (BMS sensors, 0.1 K resolution, a little noise): the supply temperature at
the building inlet (an immersion sensor in a thermowell), the tank's top temperature, the circuit
return temperature at the valve, and the actuator's own position feedback (the motor, not the
plug). What the plant is judged on: the water's true temperature at the building inlet.

Simulated each second. Everything is deterministic given the scenario and the seed.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field, replace

import numpy as np

CP = 4.19  # kJ/(kg K)
DT_CTRL = 5  # s between controller calls


@dataclass(frozen=True)
class Params:
    # the valve: an electromechanical actuator at constant speed, linkage play, plug characteristic
    stroke_s: float = 90.0        # full stroke, s
    backlash: float = 0.0         # play between actuator and plug, fraction of stroke
    char_n: float = 1.0           # share of tank water f = x ** char_n at plug position x
    # pipes (plug flow at constant pump speed)
    supply_delay_s: int = 20      # mixing point to building inlet
    return_delay_s: int = 20      # building outlet to the valve
    # sensors (first-order lags)
    tau_supply_s: float = 60.0    # thermowell at the building inlet
    tau_tank_s: float = 30.0
    tau_return_s: float = 20.0
    noise_k: float = 0.03
    resolution_k: float = 0.1
    # hydraulics
    m_load: float = 1.2           # kg/s, heating circuit
    m_boiler: float = 1.0         # kg/s, boiler loop when the boiler runs
    # tank
    nodes: int = 8
    tank_kg: float = 2000.0
    mix_kw_per_k: float = 0.05    # conduction and mixing between neighbouring nodes
    # boiler, with its own thermostat on the tank (not the commissioning engineer's business)
    boiler_out_c: float = 80.0
    boiler_max_kw: float = 140.0
    boiler_on_below_c: float = 70.0   # second node from the top
    boiler_off_above_c: float = 74.0  # second node from the bottom
    # radiators, lumped
    rad_kj_per_k: float = 3500.0
    rad_k: float = 1.2            # kW per K**1.3 with every zone open


INSTANCES = {
    # A: a worn linkage and a quick sensor; B: a tight linkage and a slow, deep thermowell
    "A": Params(backlash=0.05, tau_supply_s=15.0, char_n=0.85),
    "B": Params(backlash=0.01, tau_supply_s=75.0, char_n=0.85),
}


@dataclass
class Scenario:
    """Per-second exogenous inputs: the supply setpoint, the share of radiator zones open, the
    rooms' temperature; and the initial state."""
    sp: np.ndarray
    zones: np.ndarray
    room: np.ndarray
    tank0: tuple = (78.0,) * 8
    valve0: float = 0.45
    name: str = ""

    @property
    def seconds(self):
        return len(self.sp)


def make_scenario(seed: int, hours: float = 6.0) -> Scenario:
    """A heating day's piece: a weather-compensated setpoint with a few steps (boost, setback),
    zone valves opening and closing in groups, rooms drifting by a degree."""
    rng = np.random.default_rng(seed)
    n = int(hours * 3600)
    t = np.arange(n)
    base = rng.uniform(55.0, 62.0)
    sp = np.full(n, base)
    for at in sorted(rng.choice(np.arange(1800, n - 1800, 60), size=3, replace=False)):
        sp[at:] += rng.choice([-1, 1]) * rng.uniform(3.0, 7.0)
    sp = np.clip(sp, 48.0, 68.0)
    zones = np.full(n, rng.uniform(0.7, 1.0))
    for at in sorted(rng.choice(np.arange(600, n - 600, 30), size=6, replace=False)):
        zones[at:] = np.clip(zones[at] + rng.uniform(-0.25, 0.25), 0.45, 1.0)
    room = 20.0 + 0.5 * np.sin(2 * np.pi * t / (6 * 3600) + rng.uniform(0, 6.28)) + rng.uniform(-0.5, 0.5)
    top = rng.uniform(74.0, 79.0)
    tank0 = tuple(np.linspace(top, top - rng.uniform(2.0, 20.0), 8))
    return Scenario(sp=sp, zones=zones, room=room, tank0=tank0, valve0=rng.uniform(0.3, 0.6), name=f"s{seed}")


class Plant:
    """One plant instance running one scenario. step(command) advances DT_CTRL seconds."""

    def __init__(self, p: Params, scen: Scenario, seed: int = 0):
        self.p, self.s = p, scen
        self.rng = np.random.default_rng(10_000 + seed)
        self.t = 0
        n = p.nodes
        self.tank = list(scen.tank0)[:n] + [scen.tank0[-1]] * max(0, n - len(scen.tank0))
        self.a = self.x = scen.valve0
        self.boiler_on = False
        # the circuit in a steady state for the initial valve position and tank top
        f = self.x ** p.char_n
        top, room, z = self.tank[0], scen.room[0], scen.zones[0]
        lo, hi = room, top  # steady radiators: m cp f (top - Trad) = K z (Trad - room)^1.3
        for _ in range(60):
            trad = 0.5 * (lo + hi)
            if p.m_load * CP * f * (top - trad) > p.rad_k * z * max(trad - room, 0.0) ** 1.3:
                lo = trad
            else:
                hi = trad
        ts = f * top + (1 - f) * trad
        self.trad = trad
        self.sline = deque([ts] * p.supply_delay_s)
        self.rline = deque([trad] * p.return_delay_s)
        self.tr_valve = trad
        self.ts_true = ts
        self.m_ts, self.m_top, self.m_tr = ts, top, trad
        self.log_ts = np.zeros(scen.seconds)
        self.log_a = np.zeros(scen.seconds)

    def _tick(self, command: float):
        p, s, t = self.p, self.s, self.t
        # valve: actuator at constant speed, then the linkage's play, then the plug's characteristic
        rate = 1.0 / p.stroke_s
        self.a += min(max(command - self.a, -rate), rate)
        half = 0.5 * p.backlash
        if self.a - self.x > half:
            self.x = self.a - half
        elif self.x - self.a > half:
            self.x = self.a + half
        self.x = min(max(self.x, 0.0), 1.0)
        f = self.x ** p.char_n
        top = self.tank[0]
        tmix = f * top + (1 - f) * self.tr_valve
        self.sline.append(tmix)
        ts = self.sline.popleft()
        self.ts_true = ts
        # radiators
        q = p.rad_k * s.zones[t] * max(self.trad - s.room[t], 0.0) ** 1.3
        self.trad += (p.m_load * CP * (ts - self.trad) - q) / p.rad_kj_per_k
        self.rline.append(self.trad)
        tr = self.rline.popleft()
        # tank: the circuit draws f * m_load from the top and returns it to the bottom at tr;
        # the boiler, when on, draws from the bottom and returns to the top
        T = self.tank
        n = p.nodes
        if self.boiler_on and T[n - 2] > p.boiler_off_above_c:
            self.boiler_on = False
        elif not self.boiler_on and T[1] < p.boiler_on_below_c:
            self.boiler_on = True
        mh = f * p.m_load
        mb = p.m_boiler if self.boiler_on else 0.0
        tb = min(p.boiler_out_c, T[-1] + p.boiler_max_kw / (p.m_boiler * CP)) if self.boiler_on else T[0]
        down = mb - mh  # net flow from each node to the one below, kg/s
        mass = p.tank_kg / n
        dT = [0.0] * n
        dT[0] += mb * (tb - T[0])
        dT[-1] += mh * (self.tr_valve - T[-1])
        for i in range(n - 1):
            if down > 0:
                dT[i + 1] += down * (T[i] - T[i + 1])
            else:
                dT[i] += -down * (T[i + 1] - T[i])
            k = p.mix_kw_per_k / CP
            dT[i] += k * (T[i + 1] - T[i])
            dT[i + 1] += k * (T[i] - T[i + 1])
        for i in range(n):
            T[i] += dT[i] / mass
        self.tr_valve = tr
        # sensors
        self.m_ts += (ts - self.m_ts) / p.tau_supply_s
        self.m_top += (T[0] - self.m_top) / p.tau_tank_s
        self.m_tr += (tr - self.m_tr) / p.tau_return_s
        self.log_ts[t] = ts
        self.log_a[t] = self.a
        self.t += 1

    def measure(self) -> dict:
        p = self.p
        def q(v):
            v = v + p.noise_k * self.rng.standard_normal()
            return round(v / p.resolution_k) * p.resolution_k
        return {"t": self.t, "supply_c": q(self.m_ts), "tank_top_c": q(self.m_top), "return_c": q(self.m_tr),
                "actuator": round(self.a, 3), "setpoint_c": float(self.s.sp[min(self.t, self.s.seconds - 1)])}

    def step(self, command: float) -> dict:
        command = min(max(float(command), 0.0), 1.0)
        for _ in range(DT_CTRL):
            if self.t >= self.s.seconds:
                break
            self._tick(command)
        return self.measure()

    @property
    def done(self):
        return self.t >= self.s.seconds


def run(p: Params, scen: Scenario, controller, seed: int = 0):
    """Run a controller (callable: measurements -> command, with a reset() method) through a
    scenario; return the plant (its logs hold the true supply temperature and actuator)."""
    plant = Plant(p, scen, seed)
    controller.reset()
    m = plant.measure()
    seen = [m]
    while not plant.done:
        m = plant.step(controller(m))
        seen.append(m)
    plant.seen = seen  # what the BMS logged, every DT_CTRL s
    return plant


def score(plant: Plant, limit_k=1.0, settle_s=600, overshoot_limit_k=1.5, reversals_per_h=20.0, seen=False):
    """The specification, on the water's true temperature at the building inlet (seen=True: the
    same figures from the BMS log, the supply sensor's readings, which is all an engineer sees)."""
    sp, ts, a = plant.s.sp, plant.log_ts, plant.log_a
    if seen:
        t = np.array([m["t"] for m in plant.seen])
        keep = t < len(sp)
        t = t[keep]
        sp = sp[t]
        ts = np.array([m["supply_c"] for m in plant.seen])[keep]
        a = np.array([m["actuator"] for m in plant.seen])[keep]
        settle_s //= DT_CTRL
    n = len(sp)
    steps = np.nonzero(np.diff(sp))[0] + 1
    counted = np.ones(n, bool)
    counted[:settle_s] = False
    overshoot = 0.0
    ends = list(steps[1:]) + [n]
    for k, end in zip(steps, ends):
        counted[k:k + settle_s] = False
        up = sp[k] > sp[k - 1]
        seg = ts[k:min(end, k + (1800 // DT_CTRL if seen else 1800))] - sp[k]  # until the next change
        overshoot = max(overshoot, float(seg.max() if up else -seg.min()))
    within = float(np.mean(np.abs(ts[counted] - sp[counted]) <= limit_k))
    da = np.diff(a)
    moving = da[np.abs(da) > 1e-9]
    rev = int(np.sum(np.sign(moving[1:]) != np.sign(moving[:-1])))
    per_h = rev / (n * (DT_CTRL if seen else 1) / 3600)
    ok = within >= 0.95 and overshoot <= overshoot_limit_k and per_h <= reversals_per_h
    return {"within": within, "overshoot": overshoot, "reversals_per_h": per_h, "ok": ok,
            "mae": float(np.mean(np.abs(ts[counted] - sp[counted])))}
