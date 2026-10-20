"""Controllers for the commissioning prototype: the one found on site, and generic PI."""

from __future__ import annotations

from plant import DT_CTRL


class PI:
    """Discrete PI on the supply sensor, output = valve command. anti_windup: stop integrating
    when the output is saturated in the direction the error pushes. deadband: no action on errors
    smaller than this (a common remedy for hunting)."""

    def __init__(self, kp, ti, bias=0.45, anti_windup=True, deadband=0.0, sp_filter_s=0.0, min_move=0.0):
        self.kp, self.ti, self.bias, self.aw, self.db, self.spf = kp, ti, bias, anti_windup, deadband, sp_filter_s
        self.min_move = min_move  # the command is resent only when it has moved this much (actuator wear)
        self.reset()

    def reset(self):
        self.i = 0.0
        self.sp = None
        self.out = self.bias

    def __call__(self, m):
        sp = m["setpoint_c"]
        if self.sp is None or self.spf <= 0:
            self.sp = sp
        else:
            self.sp += (sp - self.sp) * min(1.0, DT_CTRL / self.spf)
        e = self.sp - m["supply_c"]
        if abs(e) < self.db:
            e = 0.0
        u = self.bias + self.kp * (e + self.i)
        sat_hi, sat_lo = u > 1.0, u < 0.0
        if not self.aw or not ((sat_hi and e > 0) or (sat_lo and e < 0)):
            self.i += e * DT_CTRL / self.ti
        u = min(max(self.bias + self.kp * (e + self.i), 0.0), 1.0)
        if abs(u - self.out) >= self.min_move or u in (0.0, 1.0):
            self.out = u
        return self.out


def found_on_site():
    """The controller as found: tuned by hand, aggressive, no anti-windup."""
    return PI(kp=0.08, ti=60.0, anti_windup=False)
