I've replaced `/app/controller.py` with a new HC1 controller, and it reads the plant model I measured from `/app/controller_data/hc1_model.json`. One limit on all the results below: the rig never shows the actual water temperature, which is what acceptance judges. I scored every day on a reconstruction of it from my fitted model, not on the rig's own truth. Checked that way, the controller passes all three acceptance criteria with wide margins on every random day I ran (over 850).

**Why the supply temperature never settled.** The installation description hides several problems, all confirmed on the rig and identical on every day:

| Finding | Measured |
|---|---|
| TT-S reads too high. It is a two-wire Pt1000 on 2 × 85 m of 0.5 mm² cable with no line compensation (about 5.9 Ω). | +1.55 K, constant. A second check with the valve held fully open gave 1.57 K. |
| TT-S is slow, and sits downstream of a pipe delay | 75 s lag behind a 20 s transport delay from V1 |
| V1's real mixing behaviour is not linear, despite the data sheet | share of flow from the tank = position^0.85 |
| The linkage between actuator and valve has play, which the actuator's position feedback (YF) can't show | 4 % of stroke; the valve starts each day in the middle of it |

The old controller therefore held the water about 1.55 K too cold, and its loop cycled through the play. It reversed the actuator about 220 times an hour and kept the water within ±1 K only 1.5–9 % of the time.

**What the new controller does:**
- It sets the valve mainly from the two accurate sensors (tank top and return), calculating the position that mixes exactly the setpoint.
- It takes up the linkage play before each move, then goes straight to that position.
- It uses TT-S, with the 1.55 K removed, only as a slow check on its model.
- To limit actuator wear, it only reverses direction when the water would otherwise be more than 0.18 K off.

**Results** on 865 random rig days (5 of them run the way the BMS will call it) and 9 extreme days I built:

| Criterion | Limit | Worst day |
|---|---|---|
| Within 1 K of setpoint | ≥ 95 % of the time | 100 % on every random day |
| Overshoot after a setpoint step | ≤ 1.5 K | 0.74 K |
| Actuator reversals | ≤ 20 per hour | 4.2 per hour (2.3 on average) |

- **Reconstruction check:** the reconstructed temperature, passed through the TT-S model, matches the real TT-S readings to 0.045 K (the sensor's noise level) on every day.
- **Accuracy limit:** the absolute accuracy can't be better than the handover check on the tank-top and return sensors (within 0.15 K).
- **Model errors:** with deliberately wrong values (play ±25 %, offset ±0.2 K, delay ±5 s), tracking stayed at 100 %.
- **Timing:** each call takes under 0.5 ms, about 0.13 s per day.

**One limit the controller can't overcome.** On one extreme day I built (valve starting at 0.6 with a 48 °C setpoint), the water stayed above setpoint for 84 s after the first 10 minutes. The valve was fully closed, and the loop can only cool as fast as the building cools it. That day still scored 99.6 %, and no random day came close to this.

If the model ever needs re-tuning, my scratch tools are in `/root/hc1`: `evalrig.py` rebuilds the true inlet temperature and scores a day. Run the rig with no more than 14 parallel sessions, because it drops connections at about 28.
