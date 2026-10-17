# Prototype: commissioning a heating circuit by experiment (falsification test)

The outside review's first-ranked direction: a task whose physics is not all written down, so
that the model must find it out by experimenting on the plant and then deliver a controller that
works on days it has not seen. Before building a task, the review's falsification test: does a
generic pipeline (excite, fit a low-order model, tune) already pass, or does the simplest
conservative controller? Run on 2026-10-15/16.

## The plant (`plant.py`)

A boiler charges a stratified 2 m³ tank (8 nodes); a heating circuit with a constant-speed pump
draws from the tank's top through a 3-port mixing valve that blends in the circuit's return; a
20 s supply pipe takes the water to the radiators (lumped, 100 kW class) and a 20 s return pipe
brings it back. The controller sets the valve actuator's target every 5 s. The BMS sees the supply
sensor (in a thermowell), the tank top, the return at the valve (0.1 K resolution, a little
noise) and the actuator's own position feedback; the plant is judged on the water's **true**
supply temperature, which no sensor shows.

Two instances, the same plant otherwise:

| | linkage play | thermowell lag | valve characteristic |
|---|---|---|---|
| A | 5% of stroke | 15 s | f = x^0.85 |
| B | 1% of stroke | 75 s | f = x^0.85 |

The specification, fixed before any controller was tried (`plant.score`), on 8 validation
scenarios of 6 h (seeds 100-107: a weather-compensated setpoint with three steps of 3 to 7 K,
radiator zones opening and closing, rooms drifting, the tank partly discharged at the start, the
boiler cycling on its own thermostat): the true supply temperature within 1 K of the setpoint
for at least 95% of the time outside the 10 minutes after each setpoint change; no overshoot
beyond the new setpoint of more than 1.5 K; at most 20 actuator reversals per hour.

The controller found on site (an aggressive PI with no anti-windup) fails every scenario on both.

## The generic pipeline (`generic.py`)

A test run in quiet conditions (settle, steps of 0.05 to 0.15 both ways, a PRBS), a
first-order-plus-dead-time model from the command (and the tank top and return as measured
inputs) to the supply sensor by bounded least squares from 12 starts, and PI controllers by the
SIMC rules with anti-windup: 40 settings (closed-loop time constant 1 to 4 times the dead time,
with or without a 0.2 K deadband, a minimum command move of 0.005 or 0.01, with or without a 120 s
setpoint filter).

- **No setting passes both instances.** On A the play makes the PI overshoot 1.55 to 1.9 K
  (only one setting of 40 passes A, at 1.48 K); on B aggressive settings overshoot by up to
  9.7 K in the water while the sensor shows a clean response.
- Choosing the setting the way an engineer can, by what the BMS log shows on six trial days,
  picks a setting that passes A 8/8 and fails B 0/8 (true overshoot up to 7.6 K). Twelve of the
  40 settings would pass B, but the BMS log ranks a failing one first.

## The expert's commissioning (`expert.py`)

Experiments chosen to separate the parts: a staircase up then down, each level held until the
circuit settles, gives the plug's characteristic and the play (the up and down curves are one
curve shifted by the play); steps that never reverse the actuator, with the mixed temperature
computed from the mixing equation, give the pipe delay and the thermowell lag separately. The
controller sets the plug where the mixing equation puts the setpoint (from the tank top and
return readings), reaches it through the play from the side it must move, and trims slowly on
the estimated true temperature.

| | found play | found thermowell | validation (true temperature) |
|---|---|---|---|
| A | 0.050 (true 0.05) | 13.9 s (15) | 8/8; mean error 0.067 K, overshoot ≤ 0.81 K, ≤ 6.3 reversals/h |
| B | 0.014 (0.01) | 70.1 s (75) | 8/8; mean error 0.075 K, overshoot ≤ 0.68 K, ≤ 7.3 reversals/h |

Ablations (same experiments, one piece removed):

| controller | A | B |
|---|---|---|
| full | 8/8 | 8/8 |
| no play compensation | **0/8** (within 89%, overshoot 2.1 K) | 8/8 |
| linear valve assumed | 8/8 | 8/8 |
| thermowell ignored | 8/8 | 8/8 (overshoot 1.40 K) |
| feedforward only, no trim | 8/8 | 8/8 |
| naive feedforward (no play, linear valve) | **0/8** | 5/8 |

## What it shows

- By the review's criteria the direction survives this test: the generic pipeline fails for a
  reason of model structure (the play, and a lag that hides the water's real overshoot from the
  sensor), not of tuning luck alone, and a few targeted experiments let a short controller pass
  with a wide margin.
- But the pieces that decide it are standard commissioning practice: a feedforward through the
  mixing equation, and a stroke test both ways for the play. The thermowell trap, the one a
  model's own checks cannot see, is sidestepped by any controller that works by feedforward.
  A model that writes down the physics of what the documents describe, as Opus did in every
  run of the dispatch task, is likely to pass this version.

## The hardened variant (`hardened.py`): no tank or return sensor

The circuit's controller sees only the supply sensor (thermowell 75 s) and the actuator's
feedback; play 3%, the rest as before. With no feedforward to fall back on, does knowing that
the lag is in the thermowell and not in the water become necessary?

| controller | validation days, the water's true temperature |
|---|---|
| the best PI of 384, tuned with the true temperature in view (an oracle) | within 1 K 99.1%, mean error 0.150 K, overshoot 1.54 K, 16 reversals/h |
| PI on the thermowell's lag undone by a lead-lag, play compensated (the expert) | within 1 K 99.3%, mean error 0.110 K, overshoot 1.23 K, 14 reversals/h |
| the generic pipeline, its setting picked by the BMS log (`tau_c = 2 theta`, 120 s setpoint filter) | **8/8 pass**, overshoot 1.47 K, within 98.7% |
| the same pipeline's settings without a setpoint filter | 0/8, the water overshooting by 6.9 to 8.4 K while the sensor looks clean |

**Result: falsified.** With one lagged sensor at 0.1 K resolution the information itself limits
any controller, so knowing where the lag is buys little (the oracle PI is nearly as good), and
the generic pipeline passes as soon as it uses a setpoint filter, a standard remedy that its own
BMS-log ranking happened to put first. What is left is a judgment (do not trust a clean sensor
trace; ramp the setpoint), not a structure the model must find.

## The pilot (2026-10-16): the task built around the supply sensor's error

The task (built in `staging/`, not in this repository): the circuit as above with TT-T and
TT-R back, play 4%, thermowell 75 s, and TT-S a two-wire Pt1000 on 85 m of 0.5 mm² cable with
no line compensation, reading 1.55 K high (stated in the installation documents); the rig in a
sidecar container, the verifier judging the water's true temperature on five hidden days. The
reference solution passes (mean error 0.07 to 0.08 K); a PI trusting TT-S, at the best of 60
settings, and the reference controller without the correction pass none.

**Opus 5.5 (Claude Code, max) passed, reward 1, in 68 minutes** (`pilot-opus-1/`). Its first
experiment was "end-position tests to calibrate TT-S against the accurate sensors"; with the
valve fully open it measured the 1.5 to 1.7 K error and attributed it at once to the
uncompensated line resistance. It then found every hidden parameter almost exactly (play 0.0399,
characteristic exponent 0.85, transport delay 20.0 s, thermowell 74.5 s, TT-S error 1.550 K),
built a Kalman-filter reconstruction of the water's temperature with feedforward through the
mixing equation and play compensation, and checked it on 865 random rig days. On the hidden days
its controller is better than the reference: mean error 0.036 to 0.048 K, overshoot at most
0.35 K, 2.0 to 2.7 reversals per hour. **Result: the direction does not stop Opus.**
