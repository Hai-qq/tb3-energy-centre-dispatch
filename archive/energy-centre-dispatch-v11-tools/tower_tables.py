"""Cooling-tower tables for plant.json, from a physical model of a cell (development tool).

The cell is a counterflow tower modelled with Braun's effectiveness method (Braun, Klein and
Mitchell, ASHRAE Transactions 95(2), 1989): constant water flow, air flow set by the fan,
NTU = c (m_w / m_a)^(1 + n), saturated-air enthalpy from the Buck vapour pressure. The fan's
power is cubic in its air flow. Prints:

- the heat a cell rejects with its fan at full speed, by wet bulb and approach (water leaving
  the cell minus the wet bulb), which goes into plant.json as a table;
- the fan's power against the fraction of that full-speed heat the cell rejects, for a range of
  wet bulbs and approaches, and the single curve plant.json uses (their mean).

Usage: python tools/tower_tables.py
"""

from __future__ import annotations

import math

import numpy as np
from scipy.optimize import brentq

CPW = 4.186                       # kJ/kg K
DESIGN_KW, DESIGN_RANGE = 2400.0, 5.5
DESIGN_WB, DESIGN_APPROACH = 21.0, 4.5
MW = DESIGN_KW / (CPW * DESIGN_RANGE)  # water per cell, kg/s
MA = MW / 1.2                     # air per cell at full fan speed, kg/s
N_EXP = -0.6
FAN_KW = 37.0                     # fan motor input per cell at full speed

WET_BULBS = [0, 4, 8, 12, 16, 20, 22]
APPROACHES = [0, 1, 2, 3, 4, 5, 6, 7]
CAP_KW = 30000.0                  # the scan stops here


def h_sat(t: float) -> float:
    """Enthalpy of saturated air at t (deg C), kJ per kg of dry air, at 101.325 kPa."""
    p = 611.21 * math.exp((18.678 - t / 234.5) * (t / (257.14 + t)))
    w = 0.62198 * p / (101325.0 - p)
    return 1.006 * t + w * (2501.0 + 1.86 * t)


def _eps(ntu: float, mstar: float) -> float:
    if abs(1.0 - mstar) < 1e-9:
        return ntu / (1.0 + ntu)
    x = -ntu * (1.0 - mstar)
    if x > 50.0:  # air side much the larger: the limit of the expression below
        return 1.0 / mstar
    e = math.exp(x)
    return (1.0 - e) / (1.0 - mstar * e)


def rejected(ma: float, leaving: float, wb: float, c: float) -> float:
    """Heat a cell rejects with air flow ma when its water leaves at `leaving`; CAP_KW if more."""
    if ma <= 0.0 or leaving <= wb:
        return 0.0
    ha = h_sat(wb)

    def g(q: float) -> float:
        tin = leaving + q / (MW * CPW)
        if q > 1e-9:
            cs = (h_sat(tin) - h_sat(leaving)) / (tin - leaving)
        else:
            cs = (h_sat(leaving + 1e-3) - h_sat(leaving)) / 1e-3
        ntu = c * (MW / ma) ** (1.0 + N_EXP)
        return q - _eps(ntu, ma * cs / (MW * CPW)) * ma * (h_sat(tin) - ha)

    # the physical root is the first sign change above zero
    step, q = 50.0, 0.0
    while q < CAP_KW:
        if g(q + step) > 0.0:
            return brentq(g, q, q + step, xtol=1e-6)
        q += step
    return CAP_KW


C_NTU = brentq(lambda c: rejected(MA, DESIGN_WB + DESIGN_APPROACH, DESIGN_WB, c) - DESIGN_KW, 0.3, 3.0)


def full_fan(wb: float, approach: float) -> float:
    return min(rejected(MA, wb + approach, wb, C_NTU), CAP_KW)


def fan_fraction(wb: float, approach: float, fraction: float) -> float:
    """Fan power, as a fraction of full power, to reject `fraction` of the full-speed heat."""
    q = fraction * full_fan(wb, approach)
    ma = brentq(lambda m: rejected(m, wb + approach, wb, C_NTU) - q, 1e-6, MA)
    return (ma / MA) ** 3


def main() -> None:
    print(f"cell: water {MW:.1f} kg/s, air {MA:.1f} kg/s at full speed, c = {C_NTU:.4f}, n = {N_EXP}")
    print("\nheat rejected per cell at full fan speed, kW (rows: wet bulb; columns: approach)")
    table = [[round(full_fan(wb, a) / 10.0) * 10.0 for a in APPROACHES] for wb in WET_BULBS]
    print("approach_k:", APPROACHES)
    for wb, row in zip(WET_BULBS, table):
        print(f"wb {wb:>2}: {[int(v) for v in row]}")
    fractions = [0.1 * i for i in range(1, 11)]
    curves = []
    print("\nfan power / full power at each fraction of the full-speed heat")
    for wb in (8, 12, 16, 20, 22):
        for a in (2, 3, 4, 5, 6, 7):
            if full_fan(wb, a) >= CAP_KW:
                continue
            curve = [fan_fraction(wb, a, f) for f in fractions]
            curves.append(curve)
            print(f"wb {wb:>2} approach {a}: " + " ".join(f"{v:.3f}" for v in curve))
    mean = np.mean(np.array(curves), axis=0)
    spread = np.max(np.array(curves), axis=0) - np.min(np.array(curves), axis=0)
    print("mean:                " + " ".join(f"{v:.3f}" for v in mean))
    print("max - min:           " + " ".join(f"{v:.3f}" for v in spread))
    print("\nfan kWe per cell by fraction (for plant.json):",
          [[0.0, 0.0]] + [[round(f, 1), round(float(FAN_KW * v), 1)] for f, v in zip(fractions, mean)])


if __name__ == "__main__":
    main()
