Basis: each engine's intercooler heat goes through its own LT PHE (1 for GE1, 2 for GE2) to the two LT radiators, 220 kW each. plant.json lists every connection, and nothing else can take this 40/35 C heat (too cool for LTHW or AC1; the towers serve only the condenser circuit). LT heat runs 118 to 201 kW for GE1 (600 to 1200 kWe) and 83 to 139 kW for GE2 (400 to 800).

1. Radiator 1 out (periods 12:00 to 13:30): capacity 220 kW. Either engine alone runs its full range. Both run only while combined LT heat is at most 220 kW; the minima already use 201, so together they reach about 1,140 kWe at most (GE1 ~742 with GE2 at 400, or GE2 ~541 with GE1 at 600), less than GE1 alone at 1,200. Nothing else is affected.

2. LT PHE 2 out: GE2 has no outlet for its intercooler heat, so it cannot run; GE1 is unaffected. Outputs are held for a whole half-hour, so GE2 is off for all of 02:00-02:30 and available again at 02:30. (The tool's start-time test would miss this.)

3. No. Both radiators give 440 kW against at most 340 kW (201 + 139), and one radiator alone covers either engine. They matter only in an outage.

4. Open:
- Outages are to the minute but plans half-hourly; nothing says how to treat a part-period outage. Alternatives: block the whole half-hour (my choice); block only periods starting inside the window (current code; GE2 would run through it); pro-rate (not representable).
- Radiator capacity is a flat 220 kW with no ambient derating, though the circuit returns at 32 C and dry-bulb reaches 28.8 C. Below 170 kW each, a normal day would bind.
- LT PHE capacities are missing (I assume each passes its engine's full heat). Both PHEs feed both radiators, so I pool them; paired routing would make a radiator outage shut one engine. No bypass or derating is listed, so an engine losing its outlet is off.
