# Prototype: batch scenarios against the clock (option A)

A falsification test, run on 2026-10-15: does exploiting the problem's structure give a large,
stable speed-up over a well-optimised generic approach, when one plant model (the current task,
v12) is planned for a batch of forecast scenarios of one day? Scenarios: the visible day with
electricity, heat and cooling demand and PV perturbed each half-hour. Per scenario the solution
plans the day with 768 small LPs and a DP over the day.

```
python experiment.py 200 40   # 200 scenarios; the naive method and the exactness check on 40
```

Every method gives the same least cost as the solution's own `plan_day` on every checked scenario.
Times on this Mac (one core):

| method | per scenario | notes |
|---|---|---|
| naive: the solution's `plan_day`, scenario by scenario | 452 ms | 768 LPs, each built in Python and passed to HiGHS |
| building the LPs with the solution's code | 94 ms | |
| generic, done carefully: the kVA tangents left out (the connection never binds), every LP made elastic, 50 scenarios' LPs stacked into one sparse LP | 47 ms stacking + 57 ms HiGHS | |
| structured: an LP's matrix and costs are the same in every scenario, so each LP slot keeps a library of optimal bases and tries them on all scenarios at once (one square solve per basis), HiGHS only where none fits | 15.7 ms, all included | 1,281 HiGHS solves for 153,600 LPs |

What the numbers say:

- The structure is real: 63% of the LPs are infeasible (an engine whose heat has nowhere to
  go), and across 40 scenarios a feasible LP slot has a median of one optimal basis (at most
  three). Basis reuse on elastic LPs turns almost every LP into a small linear solve, and its
  fixed cost (about 1,300 HiGHS solves) is spread over the batch.
- A careful generic code closes much of the gap: it can drop most infeasible LPs with a cheap
  physical check (the engines' minimum HT heat against what can take it) and use both CPUs, which
  puts it at an estimated 12 to 20 ms per scenario, against perhaps 2 to 4 ms for the structured
  code on batches of thousands.
- For a careful generic code to clearly miss a two-minute budget while the structured one
  finishes in a quarter of it, the batch would have to be about 6,000 to 10,000 scenarios. That
  is difficulty from the amount of computation, which TB3's implementation rubric fails
  ("difficulty stems primarily from computational intensity rather than intellectual challenge");
  the margin would depend on the verifier's hardware; and reusing an optimal basis across
  right-hand sides is textbook LP sensitivity analysis.

**Result: not worth building.** The structured advantage exists but separates from careful
generic code only at batch sizes chosen to make the clock decide.
