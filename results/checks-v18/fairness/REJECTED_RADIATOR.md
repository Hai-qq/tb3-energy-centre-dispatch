# Why the hot-radiator candidate was not promoted

## Decision

The candidate is physically persuasive **conditional on two additional design
facts**: the LT radiator exchanges heat only with unconditioned outdoor dry air,
and the circuit's listed40/35°C temperatures are absolute operating limits.
Neither design fact is uniquely established by the immutable visible files.
Do not use it to claim criterion E success.

This decision is not a claim that a dry radiator can cool water against a
temperature gradient. If the radiator's warmest water is40°C and all entering
air is at least40°C, positive cooling is impossible. The uncertainty concerns
whether those are the actual temperatures and equipment assumptions specified
by the task.

## Visible evidence and missing data

The instruction calls `plant.json` the description of ratings, part-load
performance, efficiencies, auxiliary loads, running costs and heat circuits.
It says the complete plant and every heat-circuit connection are listed.
For each LT circuit the file supplies:

```json
{"flow_c": 40, "return_c": 35,
 "from": ["GE1 intercooler"], "to": ["GE1 LT radiator"]}
```

There is no radiator type, air-on temperature, ambient design point, heat-transfer
coefficient, fan/precooling specification, or maximum admissible intercooler
inlet temperature. A radiator assembly with integral air precooling still serves
the same LT circuit; the generic component name does not identify its internal
technology. A40/35 design point also does not uniquely say whether hotter
operation is forbidden or merely different from the nominal condition.

The v13 archive explicitly added `type: dry air cooler`, a full-load duty point
at27°C air-on, and `intercooler_water_in_max_c:40`. Its40/35 circuit fields remained
unchanged. `results/checks-v13/README.md` then described a quantitative derate
above32°C. This is historical evidence of what extra information that earlier
model used, not a primary technical authority establishing the present plant's
design. Those extra fields were removed before v16/v17.

## Primary technical evidence personally retrieved

All sources below are manufacturers' own publications, read on2026-10-17.

1. [Cummins T-035 Gas Power Plant Application Manual](https://www.cummins.com/sites/default/files/2024-08/t035-Gas-Power-Plant-application-manual.pdf),
   engine heat-rejection discussion, PDF pages22–23. Radiator selection depends
   on engine heat load, coolant temperatures/flow, site maximum ambient and
   installation. Maximum engine-inlet temperature comes from the engine's
   applicable specification. This supports asking for the missing operating
   limits; it does not supply limits for this unnamed NHS plant.
2. [Güntner High Density Adiabatic Dry Cooler](https://guntner.com/en-us/products/dry-coolers/high-density-dc).
   The manufacturer offers power-generation cooling equipment that combines a
   dry heat exchanger with humidification pads. Evaporation cools the air before
   it crosses the exchanger when ambient conditions require it. Thus outdoor
   dry bulb alone does not determine air-on temperature for every closed-circuit
   radiator/cooler assembly.
3. [Güntner Energy & Process Cooling](https://guntner.com/en-us/applications/energy-process-cooling)
   identifies engine/biogas and power-generation applications for its dry and
   adiabatic cooling product range. This establishes that the alternative is a
   real relevant technology, without claiming it is installed at this hospital.

These sources cannot add adiabatic equipment to the task any more than they can
add a dry-only restriction. Their purpose is to show why the supplied generic
name does not select a unique physical boundary condition.

## Experiments and attribution

The adversary-fuzz agent personally ran all three strong opponents on its
heatwave probe. Its output is `../fuzz/radiator-probe/results.json`, and its
code is `../fuzz/probe_hot_radiator.py`. It found seven half-hours at dry bulb
at least40°C in which every opponent ran engines. An explicitly **conditional**
engine-off extension remained feasible and gave a MILP cost of£4261.517429657426;
the unextended programs cost about£3524.4878. Those runs are the other agent's
experiments, not this audit's independent executions. They prove that an added
rule would fail the opponents, not that the rule is present in the visible task.

This audit personally ran `radiator_fairness_check.py` on the same weather data,
matching its UTC rows to all48 local demand intervals. It checks the temperature
gradient under two explicitly identified boundary assumptions. During all seven
hot periods, an illustrative80%-effective integral air-precooling stage would
give26.10–26.90°C air-on despite40.1–41.9°C dry bulb. At41.9°C dry bulb and22.9°C
wet bulb, the example air-on is26.7°C:35°C return water still has8.3K positive
temperature head. Results are `radiator_fairness_check.json` and `.stdout.txt`.

The80% parameter is a hypothetical countermodel, not a number inferred for this
site. This arithmetic establishes no radiator duty or engine capacity. It only
demonstrates that the claimed thermodynamic impossibility is not entailed by
the weather file alone. An initial draft incorrectly counted the full96-row
forecast window; the final executed check joins the48 demanded instants before
evaluating the seven relevant periods.

## Minimum experiment if visible changes become permissible

State that the radiators use unconditioned outdoor dry air and give the maximum
allowed intercooler inlet temperature. Add a radiator duty relation only if
quantitative derating is to be tested. Then compare a hot feasible day against
implementations written from the revised visible data. A pure impossibility
test needs less added data than a derating law, but the actual thermal boundary
conditions must still be stated. No fresh model probability estimate follows
from the conditional programs' failures; the visible changes themselves may
prompt the careful review observed in v13.
