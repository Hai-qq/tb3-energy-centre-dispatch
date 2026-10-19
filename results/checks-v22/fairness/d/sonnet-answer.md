1. GE1 can still run (600-1200 kWe, same fuel and power): the exchanger's bypass, a modulating diverter to the stack, takes its exhaust. Only jacket heat (565-840 kW) reaches the HT circuit, so heat for buildings and AC1 falls by 270-450 kW. Boilers make up building heat but cannot fire AC1 (80 °C LTHW against its 85 °C minimum), so cooling shifts to electric chillers.

2. GE2 cannot run. Its jacket heat (390-570 kW) has no other path: no jacket bypass is listed and the HT circuit has no dump, only AC1 and PHE1. The plant loses 400-800 kWe (GE1 and import cover it) and 590-900 kW of HT heat (boilers and chillers cover it).

3. Both engines can run, but LT rejection halves from 440 to 220 kW, and intercooler heat (up to 201 kW GE1, 139 kW GE2) is too cold for any other use. One engine alone fits; the pair must stay under 220 kW, which caps them at about 1.14 MWe together (e.g. GE1 740, GE2 400 kWe). Engine output tops out at 1.2 MWe (GE1 alone), not 2.0; import and boilers cover the rest.

4. Either engine's jacket and exhaust heat enter the shared 90/70 °C HT circuit, then go to AC1's generator or to PHE1 and the buildings. Only exhaust can go to the stack instead, so jacket heat must always be absorbed. Intercooler heat goes through its own loop to the shared 37/32 °C loop and either radiator (220 kW each).

5. Open:
(a) Outages begin and end mid-half-hour, but outputs are held per half-hour. Counting any overlapped half-hour as out (09:00-15:00, 18:30-22:00, 10:30-14:30) is safe. Alternatives: the code's period-start test (misses the partial first half-hour) or pro-rating (fine for recovered-heat energy, not for availability or capacity).
(b) No file defines a sub-component outage; I inferred this from the circuit lists. The code matches only engine IDs, so it ignores all three.
(c) "GE2 off" and "jacket heat must be absorbed" rest on instruction.md saying every connection is listed; an unlisted emergency cooler would allow derated running or venting.
(d) Radiators are pooled (one circuit lists both); if paired with engines, radiator 2 out would stop only GE2. No dry-bulb derating is given for their 220 kW.
(e) Diverter range, exchanger capacities and efficiency penalties are unstated; I assumed full bypass, no limits.
