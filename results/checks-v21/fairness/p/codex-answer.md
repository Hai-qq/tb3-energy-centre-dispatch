1. LT pump 1, 10:00–12:00

GE1 must be off: plant.json connects its intercooler through the dedicated ge1_lt circuit to LT radiator 1 using LT pump 1. Every permitted running load produces LT heat, and no alternative cooling connection is listed.

GE2 can run using its separate LT pump 2 and radiator 2. B1, B2, EC1, EC2, AC1, CT1, CT2 and PV1 are not directly disabled by this pump outage. Their normal constraints still apply; AC1 needs sufficient engine HT heat and suitable cooling water. Boilers cannot supply its generator through the listed connections.

If the example outage is added to the supplied status.json, B2 remains unavailable all day, and GE1’s existing outage also applies until 11:00.

2. LT pump 2, 02:10–02:20

The same reasoning disables GE2 during the outage; GE1 and the other plant remain independently available.

dispatch.py specifies that outputs are held for the whole half-hour. Therefore GE2 must be off throughout 02:00–02:30: positive output for that interval would require operation during the outage. It may resume at 02:30, subject to other constraints.

3. What is open or incorrect

The hydraulic connections are explicit, but the files do not formally specify pump-failure interlocks, thermal ride-through or restart delays. The defensible dispatch assumption is that the affected engine cannot run without its LT circulation. Standby circulation or temporary operation using thermal inertia would require additional evidence; neither is documented.

The existing code implements neither pump dependency: optimize.py checks outages only against engine IDs, so both pump outages are ignored. Its start-time-only check would also miss 02:10–02:20 even if translated to GE2.

Sub-half-hour dispatch could preserve operation outside those ten minutes, but would require changing the stated whole-half-hour operating contract.