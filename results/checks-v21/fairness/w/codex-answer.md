1. The applicable prices in app/data/supply.json, using its explicit “local time” basis, are:

Saturday 8 August 2026, 03:00–03:30: import 5.0 p/kWh; export 5.9 p/kWh.
Tuesday 21 July 2026, 03:00–03:30: import 13.8 p/kWh; export 5.9 p/kWh.

There is a separate implementation error: app/planner/tariff.py determines the weekday from UTC epoch days. With the +01:00 midnight offset shown in demand.csv, Saturday midnight falls on Friday UTC, so the code would incorrectly select Saturday’s weekday import rate, 13.8 p/kWh.

2. In the current optimizer, both import_kw and export_kw are nonnegative, independently bounded variables. Only their difference enters the electricity balance. There is no constraint requiring either to be zero, so both can be positive in one half-hour.

With the correct Saturday prices, increasing both equally preserves the balance and earns 0.9 p/kWh on the matched quantities, until a limit binds. On Tuesday, matched import/export costs 7.9 p/kWh, so reducing both by their minimum preserves feasibility and lowers cost; a least-cost solution therefore would not retain both positive.

3. The files leave the intended metering interpretation open. instruction.md requires physically workable operation and metered/billed costs, but neither it nor supply.json explicitly defines net versus separately metered exchange or prohibits simultaneous import/export.

For one constant net exchange at the connection, require import_kw × export_kw = 0; either may also be zero.

If separate flows are permitted and separately billed, both could be positive, but the metering arrangement and applicable limits need defining. Half-hour directional averages could also both be positive if flow reverses within the interval; that requires an explicit interpretation consistent with the stated fixed plant outputs.