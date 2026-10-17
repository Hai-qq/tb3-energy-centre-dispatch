# Checks on v13 (v8.1 with four industry conventions added)

Run on 2026-10-16 on the task files in `archive/energy-centre-dispatch-v13/` (hash
`3475fcdd0057dea6`), against Terminal-Bench `1d49c52` and Harbor `0.23.1.dev202609170426`.

v13 goes back to the delivered v8.1 (the 1,220 kVA connection, EC2 at 1,000 kW, the shipped tool
of v8.1) and adds four conventions of the trade, each found by a search of practitioners' forums
and of the guidance and standards behind them (below). The tool must now know that:

1. **The exhaust heat can go up the stack.** Each engine's HT heat is split into its jacket water
   heat and its exhaust heat, and each exhaust heat exchanger has a modulating diverter to the
   stack. The jacket water heat still has nowhere to go but the absorption chiller and PHE1 (no
   dump radiator); the exhaust heat may be sent up the stack.
2. **An LT radiator limits its engine on hot afternoons.** Each LT radiator (a dry air cooler)
   has a duty point: the engine's full-load intercooler heat with water 40/35 °C and air on at
   27 °C. At full fan speed and the LT circuit's flow, the water it returns is warmer than the air
   by an amount in proportion to the heat it rejects, and the engine's intercooler takes it at
   40 °C at most (`intercooler_water_in_max_c`). Above 32 °C dry bulb the engines must run below
   rated output.
3. **The Capacity Market charge falls only in the period of high demand.** The supplier's
   Capacity Market charge (30.8 p/kWh, `capacity_market_charge_p_per_kwh`) is levied on what the
   site imports from 16:00 to 19:00 on working days from November to February, nothing else.
4. **Good Quality CHP fuel pays no Climate Change Levy.** Imports and boiler gas pay the levy
   (0.801 p/kWh); the gas of the engines listed as CHPQA certified does not.

The shipped tool counts all of the engines' heat (jacket water, exhaust and LT) and lets any of it
vanish (as in v8.1), ignores the radiators' duty points, adds the Capacity Market charge to every
kWh imported, and adds the levy to all gas. The likely half-fixes are the natural readings: all
of the HT heat must be used, the radiator is good for its duty whatever the weather (or its
approach is counted from the water entering it), the charge falls on every winter hour or every
weekday evening, the levy is left out of imports.

Two changes to v8.1's data keep the conventions unambiguous: GE2 is rated 795 kWe instead of 800
(its rated point moved along its last segment), so the CHP is under 2 MW and the Carbon Price
Support rates, which apply to CHP of 2 MW or above, cannot arise; and the winter day `h2` is
2026-12-09 instead of 2026-01-14 (both Wednesdays), so that all five days fall in one levy year
(from 1 April 2026) and the winter day in one Capacity Market delivery year (from 1 October 2026).

| file | what | command |
|---|---|---|
| `static-checks.log`, `static-checks-comment.md` | CI's static-check step (27 checks, all pass) | `scripts/run_static_checks.sh <terminal-bench-checkout>` |
| `oracle/`, `nop/` | the verifier's output: oracle reward 1 (55 passed), nop reward 0 (17 failed, 10 errors) | `harbor run -p <task> --agent oracle` (or `nop`) `--env docker` |
| `mutants.txt` | 46 planted bugs, half-fixes, reporting and execution faults (13, 28, 3 and 2), each applied alone to the solution: all caught | `python tools/energy_mutants.py` |
| `fresh-days.txt` | the solution on 16 days drawn at random: passes every day | `python tools/fresh_days.py --days 16 --seed 2026 <app>` |

The Harbor runs used a frozen copy of the task (`staging/`). The solution is within GBP 0.0003 of
the whole-day optimum on all five days. On the winter day the least-cost plan exports 683 kWh;
fuel used for exported electricity is exempt too (HMRC Excise Notice CCL1/2, para 3.1: all fuel
used to produce a certified station's outputs).

What each new convention's likeliest wrong reading does to the tool's plan (GBP per day above the
least cost, the error in the reported cost, or the limit broken; a scratch script ran each mutant
and priced its plans with the reference model):

| mutant | visible | h1 | h2 | h3 | h4 |
|---|---|---|---|---|---|
| `exhaust_heat_must_be_used` (all HT heat used) | +1033.20 | +527.89 | 0 | +16.71 | +1198.97 |
| `radiator_ignored` | 0 | 0 | 0 | 0 | an engine 108 kWe over its limit |
| `radiator_approach_from_water_in` | +72.64 | no plan | 0 | 0 | no plan |
| `capacity_market_on_all_import` (shipped) | reported +1264.62 | reported +2679.27 | reported +1548.75 | reported +668.45 | reported +1801.59 |
| `capacity_market_ignored` | 0 | 0 | +9.03, reported -328.55 | 0 | 0 |
| `levy_on_chp_gas` (shipped) | reported +725.04 | reported +635.34 | reported +792.51 | reported +744.04 | reported +757.58 |
| `levy_not_on_import` | reported -35.98 | reported -75.57 | reported -48.09 | reported -22.11 | reported -54.21 |

None of these errors shows in a tool's own checks: every plan is workable by the tool's own
model, and the visible day (28.8 °C at most) never reaches the radiators' limit.

## Where the conventions come from

The search ran on 2026-10-16 in four parts (gas-engine CHP; chillers and cooling towers; boilers,
LTHW and NHS guidance; UK metering and billing), forums first and then the documents they rely on.
Reddit was not reachable from the search tool and Eng-Tips refused direct fetches, so forum
material is from search summaries or read through a browser, and counts as practice, not fact.

- **Exhaust bypass.** Jenbacher offers the exhaust heat exchanger with or without a bypass
  (https://www.jenbacher.com/en/?p=19959); CHP exhaust heat exchangers carry an integrated or
  external bypass box (baulinks.de, 15 Aug 2014, https://www.baulinks.de/webplugin/2014/1394.php4);
  about a third of a spark-ignition engine's recovered heat is exhaust heat, and the return must
  stay under the supplier's maximum or a dump radiator must take the surplus (CIBSE CHP Group
  Datasheet 02, Jan 2012, https://www.cibse.org/media/zcsofqea/datasheet-2-spark-ignition-engines.pdf).
  A Jenbacher J416 technical description (1,202 kWe, 5 Mar 2024, in an EPA Ireland licence file,
  https://epawebapp.epa.ie/licences/lic_eDMS/090151b2808ea723.pdf) puts 403 kW of a full-load
  1,155 kW in the exhaust (35%), the share used for GE1.
- **LT radiator in hot weather.** Dry coolers are selected at a duty point (water in and out, air
  on) and rated per kelvin of entering temperature difference (Heatcraft selection guide,
  https://www.heatcraftrpd.com/dA/ae284e6a1a/BN-TB-FC-DIRECTDRIVE.pdf; ICS Cool Energy DAC 250,
  250 kW at 40/35 °C water and 25 °C air, https://www.icscoolenergy.com/?p=82446). Gas engines
  limit the water entering the second-stage intercooler (40 °C on the J416), and high ambient
  temperature is the main cause of unplanned gas-engine derates (Chevron, 21 Sep 2023,
  https://www.chevronlubricants.com/en_us/home/learning/from-chevron/industrial-machinery/the-importance-of-natural-gas-engine-nge-coolant.html).
- **Capacity Market charge.** Suppliers are charged on their customers' demand in the period of
  high demand, 16:00 to 19:00 on working days from November to February (EMRS guidance G12,
  https://www.emrsettlement.co.uk/document/guidance/g12-supplier-capacity-market-demand-forecast/;
  working day: https://www.emrsettlement.co.uk/glossary/working-day/); half-hourly invoices follow
  the site's own 16:00-19:00 consumption (https://energy.drax.com/support/electricity-market-reform/).
  The rate is the 2026/27 settlement figures' payments over demand (GBP 3,474.5m over 11.29 TWh,
  https://www.emrsettlement.co.uk/document/settlement-data/key-figures-for-payment-2026-27/).
- **Climate Change Levy and CHPQA.** Main rate 0.801 p/kWh from 1 April 2026
  (https://www.gov.uk/guidance/climate-change-levy-rates); all fuel used to produce a certified
  CHP station's outputs is exempt when its power efficiency is 20% or more (HMRC Excise Notice
  CCL1/2, paras 3.1-3.2, https://www.gov.uk/government/publications/excise-notice-ccl12-combined-heat-and-power-schemes/excise-notice-ccl12-combined-heat-and-power-schemes).
  The engines' electrical efficiency is 31 to 38% on gross CV.

Considered and not used: the absorption chiller's hot-water temperature drop in series with PHE1
(its share limit would make v8.1's summer days infeasible on the 1,220 kVA connection), the
electric chillers' minimum load rising with condenser water temperature, a fixed-flow HT circuit
whose supply temperature droops, the LTHW return temperature limiting the engines, hot-standby
boiler gas, boiler minimum firing, DUoS excess reactive power, line loss factors and bank-holiday
day types (each either small, explicit once stated, or not determined by data an engineer would
have).
