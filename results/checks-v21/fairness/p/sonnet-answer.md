1. LT pump 1 out 10:00–12:00 (the half-hours starting 10:00 to 11:30): GE1 cannot run.
- GE1's intercooler heat (118–201 kW) has one path in plant.json: ge1_lt, LT pump 1 to LT radiator 1. With the pump out the heat cannot be rejected.
- instruction.md says plant.json lists every connection, so there is no alternative route via LT radiator 2.
- GE2 has its own ge2_lt and LT pump 2, so it can run, provided PHE1 or AC1 can absorb its high-temperature (HT) heat.
- The boilers, chillers and towers are unaffected.
- AC1 burns only engine HT heat, because the LTHW circuit is at 80°C and AC1 needs 85°C. It can therefore run only while GE2 is on.

2. LT pump 2 out 02:10–02:20: the mirror image. GE2 cannot run, and GE1 and the rest can (AC1 only on GE1's heat). The plan holds each unit's output constant for the whole half-hour, and the outage sits inside 02:00–02:30. So GE2 must be off for that whole half-hour and can restart from 02:30.

3. The files leave two points open.
(a) What a pump outage does. status.json names the pump, and plant.json only attaches pumps to the LT circuits. Nothing says "pump out means engine out", so that is my inference. The alternatives are to ignore the outage, to run the engine derated (there is no derating data), or to cool via the other circuit (no connection exists). The current code ignores it: it never reads the pump field, and `_available` matches only engine ids. B2's all-day outage in the sample status.json is ignored too.
(b) An outage that does not line up with the half-hours. The alternatives are:
- Any overlap blocks the whole half-hour. This is my choice.
- Test only the half-hour's start time, as the current code does. 02:10–02:20 never matches, so the outage is ignored.
- Block only when the outage covers the whole half-hour, which also misses it.
- Run the engine for the other 20 minutes. The plan format cannot express that, and it needs an extra stop and start.

I read only the files in that folder and changed nothing.
