# v20: primary-source mechanism research

Research date: 2026-10-18. This note records engineering sources and candidate model implications. It does **not** report model trials, claim that a blind implementer failed, or estimate pass probabilities. Application replay and precheck evidence belongs in the parent experiment records.

The most supportable immediate candidates are **C1, C2 and C3** below. C4 is also physically straightforward. C5 is a useful topology experiment, but its NHS-specific equipment evidence is incomplete. C6 provides a fully sourced fifth independent mechanism if the candidate set must contain five with positive authenticity evidence.

## C1 — independently priced import and export contracts

### What the sources establish

- Drax's supplier page explicitly includes CHP in the technologies eligible for fixed, flexible and bespoke PPAs. Short excerpt: “fixed price, flex price, and bespoke PPAs”. [Drax: Sell power](https://energy.drax.com/sell-power/), section **Pick your PPA**; retrieval `turn9view0`, lines 80–82.
- Drax markets flexible electricity supply to large organisations. Its **Flex Balance** eligibility starts at 2 GWh/year with at least one half-hourly meter; **Flex Clarity** and **Flex Cashout** start at 5 GWh/year. [Drax: Flexible electricity plans](https://energy.drax.com/electricity-supply/flex-plans/), sections **Flex plans** and **Who's it for?**; `turn10view1`, lines 100–134. This is a commercial-scale source, not a domestic SEG analogy.
- The 2026 Drax brochure describes half-hourly residual volumes priced against system prices for Flex Cashout. [Drax Flex products 2026](https://assets.ctfassets.net/jl0e441lxc8n/26mJu8P1nLgJaqb7eGYASe/12b3bd443e4bcf27daf7351c143a86f5/DR2445.02_FLEX_DES_product_sheets_BF_V006.pdf), printed pp. 14–15 / PDF page index 7; `turn14view1`, lines 211–234.
- Octopus's **business** Shape Shifters: Agile prices are calculated as a fixed delivery/policy component plus the wholesale price times a loss multiplier. The supplier gives an off-peak example with a 3 p/kWh fixed component and a multiplier of 1. [Official business formula](https://octopus.energy/help-and-faqs/articles/how-calculate-prices-shape-shifters-agile/), sections **Your unit rate** and **Off-peak example**; `turn14view0` / `turn12search3`.

### Candidate and limits

A synthetic contract with an off-peak import price below a separately fixed export price is supported by the existence of these independently priced commercial products. The sources do **not** establish that a particular NHS hospital currently pays 7 p/kWh and receives 12 p/kWh, or that those prices apply on every night of the year. Describe numerical changes as a synthetic test contract calibrated to real commercial mechanisms.

No new device or data format is needed to test whether an implementation assumes import price always exceeds export price. However, simultaneous *steady-state* import/export at one algebraically netted connection is a modelling issue, not an assertion that both register totals can never grow during a real half-hour. A meter can record import during one portion of an interval and export during another. If the original instruction does not uniquely establish a steady operating point for each row, a narrowly scoped sentence defining that convention is preferable to claiming UK metering law supplies the missing assumption.

Potential errors to test: independent nonnegative import/export variables without direction exclusivity; objective minimisation using gross virtual exchanges while reporting only their net; a verifier reference with the same relaxation.

## C2 — common gas inlet capacity in standard volume

### Authenticity and numerical scale

1. The Scottish Government's NHS assets report describes the **Foresterhill Energy Centre** serving NHS Grampian, including a gas turbine CHP, biomass boiler, dual-fuel boilers, and a gas booster rated at 2,000 m³/h at 18 bar. Short excerpt: “a gas booster set providing 2000m³/hr at 18 bar pressure”. [Annual State of NHSScotland Assets and Facilities Report 2012, Annex A, case study 2](https://www.gov.scot/publications/annual-state-nhsscotland-assets-facilities-report-2012/pages/9/); `turn19view0`, lines 78–91. This establishes NHS use of a capacity-rated gas supply device. It is not evidence that the v20 reciprocating-engine site has this particular booster.
2. Honeywell's original RABO datasheet lists G400 meters with Qmax = 650 m³/h (DN100 and DN150). It expressly says the meters record volume **under operating conditions**, with electronic conversion available. Short excerpt: “They record the gas volume under operating conditions”. [Honeywell RABO datasheet](https://prod-edam.honeywell.com/content/dam/honeywell-edam/pmt/hps/products/pmc/gas/distribution/rotary-meters/rabo-g16-g250/hon-ia-rabo-datasheet.pdf?download=false), printed p. 1 and p. 5 / PDF indexes 0 and 4; `turn20view0` / `turn22view2`.
3. National Gas defines UK standard volume at **15 °C and 1.01325 bar**; EU normal volume instead uses 0 °C. [National Gas technical guidance](https://data.nationalgas.com/technical-guidance); search extract `turn17search2`. The page is client-rendered and its direct web open returned no body, so the retained evidence is the primary-domain search extract.
4. National Grid's *Gas Demand Forecasting Methodology 2020*, now hosted by National Gas, gives **39.6 MJ/m³** as the standard value used in demand forecasting when an actual CV is unavailable. [Original methodology](https://www.nationalgas.com/sites/default/files/documents/Gas%20Demand%20Forecasting%20Methodology%202020_v1.pdf), printed p. 54; `turn23search14`. This is a published modelling reference value, not a claim about every 2026 delivery.

### Minimum complete visible data

Use an explicitly commissioned **standard-volume service limit**, for example:

```json
{
  "max_standard_m3_per_h": 650,
  "reference_temperature_c": 15,
  "reference_pressure_bar_absolute": 1.01325,
  "gross_cv_mj_per_standard_m3": 39.6,
  "supplies": ["GE1", "GE2", "B1", "B2"]
}
```

The 650 value is a synthetic site's commissioned limit, with commercial meter scale supported by Honeywell. Do not present the meter's 650 **operating** m³/h rating as 650 **standard** m³/h without pressure/temperature conversion. Do not transplant the NHS example's 18-bar figure as a standard-volume quantity.

With the existing fuel-basis fields, the unique derived quantity is

\[
\dot V_s=\frac{3.6}{CV_g}\left[\sum_i f_{i,net}(P_i)\,r_{g/n}+\sum_j\frac{Q_{Bj}}{\eta_{Bj,gross}}\right].
\]

At 39.6 MJ/Sm³, a 650 Sm³/h limit equals 7,150 kW of gross gas input. Do not apply an additional residential meter correction factor: the new quantity is already at standard conditions.

Potential errors: summing net and gross fuel values directly; applying the limit separately to each unit; treating m³/h as kW or as half-hour volume; imposing the cap only on engines; double-correcting standard volume.

## C3 — dedicated chiller electrical feeder / transformer

### Primary authority

NHS HTM 06-01 (2017), section **10.45**, explicitly supports package substations for a dedicated large chiller station. Short excerpt: “Package substations may provide an effective solution for dedicated single loads such as large chiller stations.” Section **7.21** also describes separate transformer supplies with a normally open interconnection; subsection 10.47 discusses overload protection.

[NHS HTM 06-01 PDF](https://www.england.nhs.uk/wp-content/uploads/2021/05/Health_tech_memo_0601.pdf), printed p. 76 / PDF page index 86 for §10.45, printed p. 37 / index 47 for §7.21; `turn3view0`, `turn4view0`, `turn4view1`.

The 400 kVA rating is an actual manufacturer size. [Schneider Electric Trihal TRI040020003022](https://www.se.com/fr/fr/product/TRI040020003022/tfo-sec-400-kva-20kv-410v-ip31-mont%C3%A9-aaoak/) is a 400 kVA dry distribution transformer; `turn19view4`. It provides a rating scale, not proof that the synthetic NHS site uses that French-voltage SKU. The visible electrical network may specify the site's actual voltage independently.

### Minimum complete visible data

Declare the feeder's member loads, continuous apparent-power limit, and how to obtain the feeder's reactive load from the existing whole-site forecast. A forecast reactive-power allocation is a **partition** of that existing quantity. It must not be added to the site's reactive total again.

\[
P_F=P_{EC1}+P_{EC2}+a_{AC1}Q_{AC1}+\text{other explicitly assigned auxiliaries},\qquad
P_F^2+Q_F^2\le S_F^2.
\]

For an example 400 kVA feeder with 240 kvar allocated to it, active headroom is 320 kW. A site-wide limit can remain satisfied while this branch is overloaded. The existing dispatch output already allows its active load to be reconstructed, so no extra plan field is necessarily required.

Potential errors: applying only the 1,220 kVA grid limit; counting kVA as kW; summing apparent powers instead of summing P and Q then taking their magnitude; double-counting allocated reactive power; using PV or remote CHP to offset power on a feeder to which it is not connected.

Fairness conditions: label a hard continuous limit, not merely a nominal design example; identify all branch members; avoid unstated transformer losses, switch controls or overload allowances; maintain consistency with the instruction's whole-site reactive forecast definition.

## C4 — PHE1 water-side flow limit

[AEL Heat Exchangers UK](https://aelheatexchangers.co.uk/central-heating-system-break-heat-exchangers/) explicitly discusses hospital LTHW hydraulic separation and asks for primary/secondary flow rates and entering/leaving temperatures; `turn19view5`, lines 284–327. The existing PHE1 is already part of the task's visible topology, so this need not introduce a new class of hospital plant.

[Alfa Laval, *The theory behind heat transfer*](https://www.alfalaval.com/globalassets/documents/microsites/heating-and-cooling-hub/alfa_laval_heating_and_cooling_hub_the_theory_behind_heat_transfer.pdf), printed pp. 5–6 / PDF indexes 4–5, gives mass-flow ranges, definitions and the equation P = m cp ΔT; `turn22view0`.

An explicit `max_primary_mass_flow_kg_per_s` plus a specified model heat capacity gives a uniquely computable cap at the existing 90/70 °C primary conditions. Example: 15 kg/s × 4.18 kJ/(kg K) × 20 K = 1,254 kW. This exact mass-flow value is an illustrative plant selection, not an extracted NHS nameplate.

Potential errors: limiting all CHP HT heat including heat sent directly to AC1; ignoring the PHE bottleneck; applying secondary ΔT or ambient temperature; treating a design flow as an unconditional maximum.

Fairness conditions: the field must say **maximum permitted** flow. If return temperatures are adjustable, the cap is no longer uniquely 1,254 kW; either the task fixes the operating temperatures or more operating-envelope data is required. State a constant cp in visible data if that simplification is used.

## C5 — parallel LT heat-rejection capacity survives one outage

Engineering proposal: provide individually isolatable parallel LT heat-rejection branches with individual capacity curves. A branch outage removes that branch's capacity, rather than necessarily stopping the engine. The remaining summed capacity limits engine load via the existing LT part-load table.

This directly attacks an all-downstream-sinks-required heuristic. For example, with a surviving 200 kW sink and GE1's existing 158 kW LT point at 900 kWe and 201 kW point at 1,200 kWe, the surviving sink would permit approximately 1,193.02 kWe under the linear interpolation convention. It does not imply GE1 must stop.

**Source gap:** this research located NHS N+1 electrical supplies, steam-plant redundancy, and a heat-pump project with redundant boreholes, but did not verify a primary NHS source for this exact parallel LT radiator arrangement. Those adjacent examples must not be described as evidence for N+1 CHP LT radiators. This candidate should stay at an initial experimental stage or be dropped under the requested authenticity gate until a suitable source is found.

**Data gap:** a list of multiple `to` entries alone does not establish parallel hydraulics or independent isolation. The visible topology must identify those facts. Otherwise an implementation that regards an outage as common-loop isolation is a reasonable competing reading.

## C6 — thermal storage separates present heat production from present demand

This is a well-sourced independent alternative to C5. Veolia, the project developer and operator, describes the University Hospital of Hartlepool project with a **70,000-litre thermal store** and **1,400 kW ground-source heat pump**, integrated with CHP, hot-water boilers and PV. It explicitly describes charging the store at higher heat-pump loading and drawing it down over several hours.

[Veolia UK project announcement](https://www.veolia.co.uk/press-releases/veolia-deliver-innovative-project-decarbonise-energy-university-hospital-hartlepool), paragraphs describing the new scheme and smart controls; `turn22view1`, lines 227–235.

Candidate consequence: a row-by-row heat balance must include stored-energy change, which defeats a solver that only couples rows through engine starts. A return-side connection or a temperature-limited heat exchanger can additionally make only part of the nominal stored heat usable for a particular service.

Minimum data: active volume or usable energy, temperature levels/heat capacity where capacity is inferred, initial state, flow or power limits, losses, allowed connections, and a specified terminal target/value. Merely stating a tank volume does not define useful capacity; “least cost” does not specify an end-of-day state. Introducing the necessary state/output fields is materially more work and much more visible than C1–C4, so it is a fallback design direction rather than the preferred v20 change.

## Findings that should not be overclaimed

- The published sources establish authenticity and parameter scales. They do not themselves define the synthetic task's scoring model.
- Reading old implementations can identify assumptions to challenge. It cannot measure a new strong model's chance of noticing the new fields.
- New explicit objects may be easy for a careful blind implementer. The required prompt precheck, rather than this research note, decides that issue.
- No need was found to invent an NHS operational reserve constraint from an N+1 design recommendation. Design redundancy alone does not uniquely prescribe real-time online reserve.
- Commercial export remuneration is not evidence that physically fictitious same-point simultaneous flows should receive payment.

