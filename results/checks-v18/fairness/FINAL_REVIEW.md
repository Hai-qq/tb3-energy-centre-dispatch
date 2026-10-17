# Independent review of the single v18 task revision

## Finding

No concrete defect was found in the reviewed fairness repairs. The post-fix
reference SHA-256 is
`9a76ed87d2ef7ab13f9734ddfffec29ba8715a61ada2745851e63efe480970b4`.
The changes preserve independent bounds on equipment, balances, grid limits,
reported fuel/cost and runtime. This is a code-and-experiment review, not a TB3
CI approval or a fresh model trial.

The added hidden cases expand coverage of existing mechanisms. They do not
establish a new uniquely implied failure in the three strong opponents. The
root agent must report E's actual failures or passes from its complete replay;
this review supplies no permission to relabel a physically consistent program
as a failed solution.

## Personally executed post-fix checks

All commands below use Python3.13.16 with the pinned dependencies and
`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1`.

```sh
/workspace/scratch/3a594630faca/ecd-venv/bin/python \
  results/checks-v18/fairness/acceptance_regressions.py --require-fixed --label v18

/workspace/scratch/3a594630faca/ecd-venv/bin/python \
  results/checks-v18/fairness/postfix_checks.py

/workspace/scratch/3a594630faca/ecd-venv/bin/python \
  results/checks-v18/fairness/warm_envelope_benchmark.py \
  --reference tasks/energy-centre-dispatch/tests/reference.py \
  --days-root tasks/energy-centre-dispatch/tests/days --label v18
```

All three commands exit0. Machine-readable evidence and captured stdout share
their script names, with `_v18` for the first and third commands.

### Common-header reconstruction:11/11 classifications agree

The regression compares independently calculated feasible compressor-input
intervals to the reference's resulting electricity balance. It accepts the
natural header, a26°C header without AC, one common27.3°C header serving both
electric chillers, and AC0.4kW with22°C water. It also accepts the authentic
48-period patched-Codex warmer-header witness. The frozenv17 reference disagreed
on six cases; the revised reference disagrees on none.

The following invalid proposals are rejected: AC0.4kW with electricity still
computed at21°C (5.147269kW shortage), compressor input5kW below the cold endpoint,
input5kW above the hot endpoint, and a5kW fictitious sink when both EC outputs
are zero. A0.001kW endpoint rounding residual remains accepted under the existing
1kW balance tolerance. This confirms interval projection has no discontinuous
fallback to the cold endpoint.

The separate direct checks confirm heat rejection is updated exactly once.
For EC1/EC2 duties1000/700kW at27.3°C, compressor input347.3229528171805kW gives
tower rejection2047.3229528171805kW. The26°C single-EC and0.4kW-AC cases also
match direct conservation-of-energy arithmetic. Those cases are isolated flow
tests; they are not represented as complete feasible hospital schedules.

### Component names and outage union

Both literal HT source names now disable their owning engine for outages
10:10–10:20,12:30–13:00 and14:20–14:40, and leave the other engine unaffected.
The exact disabled starts are10:00,12:30,14:00 and14:30. The new hidden h2
`GE2 jacket water and exhaust` record disables18:00 and18:30. The hidden h3
`AC1 generator` record disables12:30.

The named HT group includes jacket water. Treating its whole maintenance event
as merely an exhaust-only bypass would omit an explicitly named essential
part. This is the existing component-dependency consequence applied to another
literal endpoint, without inventing an unlisted bypass.

Eight PV interval cases pass: overlapping, reverse-ordered, duplicated, nested,
adjacent, disjoint, touching-boundary and fully covering intervals. The known
12:05–12:15 plus12:10–12:20 case now has exactly15 unavailable minutes and
128.9kW maximum average PV from a257.8kW forecast. In final hidden h4 at16:00,
the nested records remove10 distinct minutes, leaving123.4kW from185.1kW. An
all-off PV schedule remains permitted by the conservative benchmark.

## Is the conservative cost bound weakened on the scored days?

An independent experiment extends the frozen/current reference MILP with one
nonnegative aggregate extra compressor-input variable per period. The upper
bound is the difference between power at the flat34°C COP endpoint and power
at the active coldest header. That difference is linear in each chiller's
cooling duty. Electricity consumes the extra input and the towers reject it.

For any fixed pair of nonnegative chiller duties, total input is a continuous
monotone function of one shared water temperature. Every input in the bounded
interval has some common temperature. The added scalar interval therefore
represents the full continuous-header alternative exactly for this fixed
plant; it does not discretize temperatures or grant each chiller its own water.

| Final v18 day | Coldest-header strict-auxiliary MILP (£) | Continuous-header MILP (£) | Difference (£) |
|---|---:|---:|---:|
| visible | 6303.560319426553 | 6303.560319426553 | 0 |
| h1 | 6426.647467103042 | 6426.647467103042 | 0 |
| h2 | 8879.731991258708 | 8879.731991258708 | 0 |
| h3 | 5375.538040469284 | 5375.538040469284 | 0 |
| h4 | 7310.971840533033 | 7310.971840533033 | 0 |

The two models likewise gave exactly equal minima on all five frozenv17 days.
This supports the narrow statement that broadening header-flow acceptance adds
no extra optimality gap on the actual scoreddays, holding the other conventions
fixed. It does not make the auxiliary-heat and partial-PV interpretations unique.

The unpromoted witness `fuzz/water-probes/days/w1` has coldest-header minimum
£6034.446098971162 versus continuous-header minimum£6014.361415011951. The
£20.08468395921136 difference is real. Its16:00 half-hour uses13.158878504674277kW
extra EC input while avoiding a later generator start. Consequently the task's
documentation correctly calls the general coldest-policy value a conservative
acceptance bound; it must not claim exact global optimality over the union of
all accepted controls. The witness is evidence against using that boundary as
an unambiguous new trap.

## Remaining qualifications

- The warmer-header model's site-control permission is not uniquely specified;
  acceptance broadening avoids rejecting the demonstrated physical reading.
  No hidden day was promoted to force that policy choice.
- The pre-existing AC auxiliary-heat and partial-PV ambiguities remain accepted
  alternatives. The oracle's stricter auxiliary-heat convention addresses B's
  absolute agreement with the selected reference MILP, not those semantics.
- Minor negative unit outputs already allowed by the0.5kW rating tolerance can
  leave a small negative lower compressor bound. They cannot create a large
  electrical sink: the upper endpoint clips individual negative cooling tozero,
  and separate unit/cooling constraints remain active. This is existing numeric
  tolerance, not material new physics or a difficulty mechanism.
- Full B/C/E/F runs, three16-day seeds, all mutations, Docker/Harbor behavior and
  actual fresh model pass rates are outside this independent diff review.
  The root agent's results must be used for those claims.
- The hot-radiator direction is rejected for specification uncertainty; the
  primary-source and experimental rationale is in `REJECTED_RADIATOR.md`.

## Final read-only recheck of the current files

At the root agent's final-review request, both task sources were read again.
Their current SHA-256 values are:

```text
reference.py  9a76ed87d2ef7ab13f9734ddfffec29ba8715a61ada2745851e63efe480970b4
test_plans.py 0ab4df77dcd23c4a1f74444ae620f7bc1304d77da16738faba5f96d841621355
```

The reference hash exactly matches this report, `postfix_checks.json`, and
`warm_envelope_benchmark_v18.json`. The 11 envelope regressions and the complete
five-day cold/continuous MILP comparison were personally rerun against these
current files. Evidence is `acceptance_regressions_final_recheck.json` and
`warm_envelope_benchmark_final_recheck.json`, with matching captured stdout.
All 11 classifications still agree; all five MILP differences remain exactly
zero at the costs in the table above. The unpromoted witness still differs by
£20.08468395921136.

No additional undisclosed relaxation was found. When both EC outputs are zero,
the compressor interval is exactly `[0, 0]`; the projection cannot absorb an
extra load. Its original electrical residual remains subject to the existing
1 kW balance allowance, so the precise claim is that this change adds no new
zero-EC sink, not that all sub-kW residuals are rejected. The same existing
allowance applies to inputs just outside either endpoint. Both 5 kW endpoint
violations and the 5 kW zero-EC sink are rejected in the rerun. The overall
conservative cost bound and the remaining auxiliary/PV/policy interpretations
are explicitly disclosed in both task test modules and this report.

### Minimal visible authority for the added component coverage

The current, unchanged `instruction.md` states:

> It lists all of the plant and every connection of its heat circuits.

Its description of `status.json` states:

> the plan date, the engines running at midnight and planned outages of plant (local time)

The literal visible `environment/data/plant.json` entries are:

```json
"engine_ht": {
  "flow_c": 90,
  "return_c": 70,
  "from": ["GE1 jacket water and exhaust", "GE2 jacket water and exhaust"],
  "to": ["AC1 generator", "PHE1"]
}
```

The GE2 source is a whole named jacket-water/exhaust group; removing it cannot
be read as merely bypassing an exhaust exchanger while retaining jacket-water
operation. AC1's generator is a named part of the absorption machine's driving
heat path. These are the already established component-dependency consequences
applied to literal endpoints, without adding a new heat connection.

Finally, the unchanged visible `environment/dispatch.py` docstring states:

> Writes, for each half-hour of the plan date (local time), the output of every unit,
> held for the whole half-hour, the grid exchange, the gas burned (kWh, as billed) and the
> cost (GBP, including the starts of engines started in that half-hour), with day totals
> in `summary`.

The instruction additionally requires preserving the plan's format and keeping
every reported figure consistent with operation. Thus the constant-output
reading is supported by a visible format contract, not by an unseen reference
comment or by trusting the broken optimizer's algorithm.
