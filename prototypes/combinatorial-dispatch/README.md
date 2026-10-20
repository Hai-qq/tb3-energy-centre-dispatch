# Prototype: the optimisation itself made hard (third falsification test: dropped)

Can the dispatch optimisation be made hard to solve to the verifier's tolerance (the larger of
GBP 0.5 and 0.02% of the least cost) within two minutes, in a way a careful use of SciPy's MILP
solver does not already handle? `week_milp.py` plans the current task's plant (v12) over several
days at once with a hot-water thermal store on the LTHW circuit (one net flow, 0.5%/h standing
loss, back to its starting level at the end) and minimum up and down times
for the engines (3 h and 2 h), as one MILP built the careful generic way (the standard tight
minimum up/down constraints, the task reference's part-load segments and header modes).

```
python week_milp.py DAYS [time_limit_s]            # whole MILP with HiGHS
ECD_NO=store python week_milp.py 3 600             # the same without a part (store, minupdown, header, segbin)
```

The store first had a round-trip efficiency, which let a plan charge and discharge at once and
turn the losses into a hidden heat dump, round the rule that the engines' HT heat must go
somewhere; the plans used it (an hour of HiGHS found a large-store summer week at GBP 38,886.47
with it, GBP 446 below the least cost without it; those runs are in `logs/round-trip-store/`). It
now has one net flow and a standing loss only.

## The instance matrix (store with one net flow)

`python matrix.py` runs 12 instances (1, 2 and 7 days; a small store, 1,500 kWh / 750 kW, and a
large one, 3,000 kWh / 1,500 kW; the summer weekday of the task's visible day and the spring
Monday of its day h3, each perturbed day by day) with HiGHS's own log on, and reads from it when
HiGHS had its first plan, when its plan first came within the verifier's tolerance of the best
plan it found, and what it had at two minutes. Logs: `logs/`.

| instance | first plan | within tolerance of its best | plan at 120 s | best plan | bound | end |
|---|---|---|---|---|---|---|
| 1 day, summer, small | 0.0 s | 0.6 s | 6,255.62 | 6,255.62 | 6,255.00 | optimal |
| 1 day, summer, large | 0.0 s | 3.5 s | 6,081.11 | 6,081.11 | 6,080.82 | optimal |
| 1 day, spring, small / large | 0.0 s | 0.3 s | 5,421.81 / 5,419.30 | same | | optimal |
| 2 days, summer, small | 0.0 s | 17.5 s | 12,187.84 | 12,187.84 | 12,186.64 | optimal in 30 s |
| 2 days, summer, large | 0.1 s | 18.6 s | 11,897.69 | 11,897.69 | 11,896.56 | optimal in 22 s |
| 2 days, spring, small / large | 0.1 s | 0.7 s | 10,614.63 / 10,607.29 | same | | optimal |
| 7 days, summer, small | 0.6 s | 1,292.6 s | 40,187.25 (+0.35%) | 40,045.79 | 39,907.58 | 30 min limit, gap 0.35% |
| 7 days, summer, large | 0.7 s | 1,713.7 s | 39,395.14 (+0.14%) | 39,339.33 | 39,253.88 | 30 min limit, gap 0.22% |
| 7 days, spring, small / large | 0.2 s | 3.6 s | 35,648.94 / 35,615.71 | same | | optimal in 11 s |

`fix_optimize.py` is the careful generic heuristic: 20 s of HiGHS on the whole week, then
two-day windows whose binaries are re-solved with every other binary fixed, for two minutes in all.
On the spring weeks it ends where HiGHS ends (35,615.14 and 35,648.81). On the summer weeks it ends
worse than HiGHS alone at two minutes: 39,459.85 (large store, +0.31% above the best plan) and
40,314.31 (small, +0.67%).

## The exact DP (`exact_dp.py`)

```
python exact_dp.py DAYS [--base visible|h3] [--store small|large]
```

The state before a half-hour is each engine's on/off state with its minimum up or down counter
(10 per engine, 100 joint) and the store's level, kept continuous. For every half-hour and
engines' on/off pattern, the half-hour's least cost is an exact piecewise-linear function of the
store's net flow: one parametric LP per part-load segment and header mode (each convex in the flow,
found exactly by the sandwich method from HiGHS's duals), and their lower envelope. The value
function of the store's level is kept exactly as a list of convex runs (the pieces between its
concave kinks and jumps) and carried backwards by min-plus convolution of convex runs (merging
slopes) and lower envelopes; the plan comes from a forward pass over the breakpoints. The only
approximation is rounding: a fall in slope smaller than 1e-8 GBP per kWh (or worth less than
1e-9 GBP over its pieces) is not taken for a concave kink, and points within 1e-9 GBP of their
neighbours' chord are dropped. Without that, rounding noise split the value functions into
thousands of runs; with it the largest has about 100 runs.

It agrees with every optimum HiGHS proves (relative gap 1e-9):

| instance | exact DP | HiGHS, proven |
|---|---|---|
| summer, 8 / 12 / 16 half-hours, large store | 712.5300 / 1,086.0108 / 1,536.7330 | the same (to 1e-13) |
| 1 day, summer, large / small | 6,081.0693 / 6,255.2889 | 6,081.0693 / 6,255.2889 |
| 2 days, summer, large / small | 11,897.6892 / 12,187.8138 | 11,897.6892 / 12,187.8138 (92 s) |
| 2 days, spring, large | 10,607.2885 | 10,607.29 (gap 1e-4) |

On the summer weeks, which HiGHS cannot close in half an hour:

| 7 days, summer | exact DP | time | HiGHS at 2 min | HiGHS best in 30 min | HiGHS bound |
|---|---|---|---|---|---|
| small store | 40,026.2284 | 100 s | 40,187.25 (+161.0) | 40,045.79 (+19.6) | 39,907.58 |
| large store | 39,332.8469 | 228 s | 39,395.14 (+62.3) | 39,339.33 (+6.5) | 39,253.88 |

The verifier's tolerance there is GBP 8.0 and 7.9. The times are this unoptimised code on one core
(the half-hour LPs through `linprog`, 27 to 39 s of each; the rest Python-level PWL operations).

## The careful approximate method (`grid_dp.py`)

```
python grid_dp.py DAYS [--store small|large] --step 10 5 2
python grid_dp.py DAYS --step 10 --refine 30 1 --rounds 2
```

What an expert would try once the whole-week MILP stalls: the same DP over the engines' states,
but with the store's level on a grid (the half-hour costs between grid levels exact), then HiGHS
on the whole week with the engines' on/off fixed to the DP's schedule ("polish"; the part-load
segments, header modes and all flows stay free). Times exclude the half-hour cost functions.

| 7 days, summer | grid step | DP | polish | polished plan | above the optimum |
|---|---|---|---|---|---|
| small store | 50 kWh | 0.3 s | 60 s (limit) | 40,061.54 | +35.3 |
| | 25 kWh | 0.4 s | 60 s (limit) | 40,048.40 | +22.2 |
| | 10 kWh | 1.3 s | 12.9 s | 40,029.59 | **+3.4, within tolerance** |
| | 5 kWh | 3.2 s | 35.8 s | 40,027.44 | +1.2 |
| | 2 kWh | 44.1 s | 17.8 s | 40,026.2284 | **0: the optimum** |
| large store | 50 kWh | 0.4 s | 60 s (limit) | 39,385.88 | +53.0 |
| | 25 kWh | 0.7 s | 27.8 s | 39,353.55 | +20.7 |
| | 10 kWh | 3.3 s | 6.0 s | 39,340.63 | **+7.8, within tolerance (7.9)** |
| | 5 kWh | 26.8 s | 5.7 s | 39,334.79 | +1.9 |
| | 10 kWh, then twice a 1 kWh grid within 30 kWh of the polished levels | 1.0 s | 12.9 s | 39,340.63 | +7.8 (stuck) |
| | 2 kWh | 149.7 s | 5.1 s | 39,333.28 | +0.43, inside GBP 0.5 |

## What it shows

- Only the summer week is hard for HiGHS: half an hour leaves a 0.22 to 0.35% gap, and its
  two-minute plan is 0.16 to 0.40% above the optimum, 8 to 20 times the verifier's tolerance.
  Fix-and-optimise windows do no better. In spring the heating load takes the engines' heat, the
  store matters little and HiGHS proves the week optimal in 11 s.
- An exact reference exists: the DP above, checked against every optimum HiGHS can prove. It is
  not yet fast enough to be the solution of a two-minute task (100 to 230 s).
- But the test fails on its other side: a careful approximate method, the commitment DP with the
  store on a 10 kWh grid and a polish by HiGHS, reaches the verifier's tolerance on both summer
  weeks in well under two minutes, and a 2 kWh grid finds the exact optimum of the small-store
  week in about a minute. The difficulty is "replace the whole-week MILP by a DP over the engines'
  states", a standard decomposition, not one the review asked for.
- Demanding the exact optimum (GBP 0.5) does not save it: the 2 kWh grid comes within GBP 0.5 on
  both weeks (62 s and 155 s in this plain implementation). What is left is a race between grid
  resolution and the clock, the computational kind of difficulty TB3's rubric fails, with a margin
  a better-vectorised grid DP would erase, and an exact reference that would itself have to get
  several times faster.
- By the rule set before the test (a careful approach that is not the insight already meets the
  bar), the direction is dropped.
