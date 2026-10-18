An outage on a heat-circuit component stops the unit behind it, because the circuits give that unit no other route. instruction.md says plant.json lists every connection, so I assume there are no cross-ties or bypasses.

1. Effects
- B1, 06:00-08:00: B1 cannot run. Heat then comes only from B2 (2000 kW, efficiency 0.83 against B1's 0.905) and PHE1 (engine HT heat). AC1 is unaffected: it takes engine-circuit heat only, boilers make 80 C, and AC1 needs 85 C.
- LT radiator 1, 18:00-20:00: GE1 cannot run. Its intercooler circuit ge1_lt ends only at that radiator, and GE1 rejects 118-201 kW there at any permitted load. GE1's 600-1200 kWe and 835-1290 kW of HT heat are lost, so PHE1 and AC1 must share GE2's 590-900 kW alone (AC1 limited).
- EC1 condenser, 13:40-14:20: EC1 cannot run, because its condenser is its only route to CT1/CT2. That removes the larger (1400 kW) and more efficient chiller (higher COP at every condenser temperature). EC2 (1000 kW) and AC1 (800 kW, engine heat) remain, and the towers are unaffected.
- LT radiator 2, 02:10-02:20: GE2 cannot run, by the same reasoning via ge2_lt. GE1 is unaffected.

2. Unavailable units per half-hour (local start time; "to" treated as exclusive)
- 02:00: GE2 (LT radiator 2)
- 06:00, 06:30, 07:00, 07:30: B1
- 13:30, 14:00: EC1 (its condenser)
- 18:00, 18:30, 19:00, 19:30: GE1 (LT radiator 1)
That is 11 half-hours.

3. Open points
- Partial slots: 02:00 is hit for 10 of 30 minutes, and 13:30 and 14:00 for 20 of 30 each. No rule is given. The alternatives are to treat the whole slot as out, or to derate pro rata (EC1 about one-third available, GE2 two-thirds). Pro rata fails for an engine, because 10 minutes lost still means a stop and restart (GE2 27 GBP). I would take whole slots.
- Outage records give only a name and a window. Nothing says a radiator or condenser outage disables its engine or chiller, or by how much. I inferred total loss from the topology. Partial capacity and engine ride-through are the alternatives, but no buffer, bypass or radiator rating is given to support them.
- Engines: both run at midnight. Start costs are given, but minimum run and off times are not. So stopping early or restarting late is the planner's choice.
- Whether the remaining plant meets demand needs demand.csv and supply.json, which I was not given. PHE1 has no rating, and AC1's 800 kW is not stated as cooling or heat input. That decides whether GE2 alone can drive AC1.
