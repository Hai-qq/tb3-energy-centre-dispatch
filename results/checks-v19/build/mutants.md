# v19 mutation failures

Each entry comes from the actual `tools/energy_mutants.py` run.

| Mutant | Failed tests and days |
|---|---|
| `weather_by_utc_date` | `test_connection_limits`: h1; `test_cooling_balance`: h1; `test_cooling_towers`: h1, h4; `test_electricity_balance`: visible, h1, h3, h4; `test_heat_balance`: h1; `test_least_cost`: visible, h1; `test_plan_covers_the_day`: h1; `test_reported_gas_and_cost`: h1; `test_reported_import_export_and_grid_flags`: h1; `test_same_plan_every_time`: h1; `test_units_within_ratings_and_availability`: h1 |
| `two_point_curve` | `test_heat_balance`: visible, h1, h2, h3, h4; `test_least_cost`: h2; `test_reported_gas_and_cost`: visible, h1, h2, h3, h4 |
| `gas_net_to_gross_divided` | `test_least_cost`: h2, h3; `test_reported_gas_and_cost`: visible, h1, h2, h3, h4 |
| `starts_not_in_decision` | `test_least_cost`: visible, h1, h3 |
| `heat_can_be_dumped` | `test_heat_balance`: visible, h1, h3, h4 |
| `lt_heat_counted` | `test_connection_limits`: h1, h4; `test_cooling_balance`: h1, h4; `test_cooling_towers`: h1, h4; `test_electricity_balance`: h1, h4; `test_heat_balance`: visible, h1, h2, h3, h4; `test_least_cost`: h1, h3, h4; `test_plan_covers_the_day`: h1, h4; `test_reported_gas_and_cost`: h1, h4; `test_reported_import_export_and_grid_flags`: h1, h4; `test_same_plan_every_time`: h1, h4; `test_units_within_ratings_and_availability`: h1, h4 |
| `towers_take_cooling_only` | `test_cooling_towers`: h1, h4 |
| `kva_ignores_engines` | `test_connection_limits`: h1, h2; `test_cooling_balance`: h1, h2; `test_cooling_towers`: h1, h2; `test_electricity_balance`: h1, h2; `test_heat_balance`: h1, h2; `test_least_cost`: h1, h2; `test_plan_covers_the_day`: h1, h2; `test_reported_gas_and_cost`: h1, h2; `test_reported_import_export_and_grid_flags`: h1, h2; `test_same_plan_every_time`: h1, h2; `test_units_within_ratings_and_availability`: h1, h2 |
| `absorber_needs_cold_weather` | `test_connection_limits`: h1, h2, h3, h4; `test_cooling_balance`: h1, h2, h3, h4; `test_cooling_towers`: h1, h2, h3, h4; `test_electricity_balance`: h1, h2, h3, h4; `test_heat_balance`: h1, h2, h3, h4; `test_least_cost`: h1, h2, h3, h4; `test_plan_covers_the_day`: h1, h2, h3, h4; `test_reported_gas_and_cost`: h1, h2, h3, h4; `test_reported_import_export_and_grid_flags`: h1, h2, h3, h4; `test_same_plan_every_time`: h1, h2, h3, h4; `test_units_within_ratings_and_availability`: h1, h2, h3, h4 |
| `weekend_from_utc_start` | `test_least_cost`: h1; `test_reported_gas_and_cost`: h1 |
| `kva_as_kw` | `test_connection_limits`: h1, h2 |
| `kva_engines_absorb_kvar` | `test_connection_limits`: h1, h2, h4; `test_cooling_balance`: h1, h2, h4; `test_cooling_towers`: h1, h2, h4; `test_electricity_balance`: h1, h2, h4; `test_heat_balance`: h1, h2, h4; `test_least_cost`: h1, h2, h4; `test_plan_covers_the_day`: h1, h2, h4; `test_reported_gas_and_cost`: h1, h2, h4; `test_reported_import_export_and_grid_flags`: h1, h2, h4; `test_same_plan_every_time`: h1, h2, h4; `test_units_within_ratings_and_availability`: h1, h2, h4 |
| `towers_absorber_only` | `test_cooling_towers`: h1, h4 |
| `cop_at_dry_bulb` | `test_connection_limits`: h1, h4; `test_cooling_balance`: h1, h4; `test_cooling_towers`: h1, h4; `test_electricity_balance`: visible, h1, h2, h3, h4; `test_heat_balance`: h1, h4; `test_least_cost`: visible, h1, h4; `test_plan_covers_the_day`: h1, h4; `test_reported_gas_and_cost`: h1, h4; `test_reported_import_export_and_grid_flags`: h1, h4; `test_same_plan_every_time`: h1, h4; `test_units_within_ratings_and_availability`: h1, h4 |
| `cewt_without_minimum` | `test_electricity_balance`: h2, h3 |
| `no_engine_aux` | `test_electricity_balance`: visible, h1, h2, h3, h4 |
| `no_lthw_loss` | `test_connection_limits`: h1, h4; `test_cooling_balance`: h1, h4; `test_cooling_towers`: h1, h4; `test_electricity_balance`: h1, h4; `test_heat_balance`: visible, h1, h2, h3, h4; `test_least_cost`: h1, h4; `test_plan_covers_the_day`: h1, h4; `test_reported_gas_and_cost`: h1, h4; `test_reported_import_export_and_grid_flags`: h1, h4; `test_same_plan_every_time`: h1, h4; `test_units_within_ratings_and_availability`: h1, h4 |
| `outages_ignored` | `test_units_within_ratings_and_availability`: visible, h1, h2, h3, h4 |
| `outage_by_period_start` | `test_electricity_balance`: h4; `test_heat_balance`: h4; `test_units_within_ratings_and_availability`: h1, h2, h3, h4 |
| `phe1_outage_ignored` | `test_heat_balance`: h4 |
| `lt_radiator_outage_ignored` | `test_units_within_ratings_and_availability`: h2, h3, h4 |
| `intercooler_outage_ignored` | `test_units_within_ratings_and_availability`: h2, h4 |
| `ht_source_outage_ignored` | `test_units_within_ratings_and_availability`: h2 |
| `parts_by_name_prefix` | `test_units_within_ratings_and_availability`: h2, h3, h4 |
| `ac_generator_outage_ignored` | `test_units_within_ratings_and_availability`: h3 |
| `condenser_outage_ignored` | `test_units_within_ratings_and_availability`: h1 |
| `absorption_chiller_parts_ignored` | `test_units_within_ratings_and_availability`: h3 |
| `outages_engines_only` | `test_units_within_ratings_and_availability`: h1, h2, h3, h4 |
| `tower_cell_outage_ignored` | `test_cooling_towers`: h1 |
| `pv_outage_ignored` | `test_electricity_balance`: h4 |
| `kva_positive_reactive_only` | `test_connection_limits`: h2 |
| `outages_one_per_unit` | `test_electricity_balance`: h4; `test_units_within_ratings_and_availability`: h2 |
| `outage_capacity_prorated` | `test_units_within_ratings_and_availability`: h1, h2, h3, h4 |
| `absorber_cooling_water_ignored` | `test_electricity_balance`: h1, h3, h4 |
| `header_not_shared` | `test_electricity_balance`: h1, h3, h4 |
| `midnight_state_ignored` | `test_reported_gas_and_cost`: h1, h2 |
| `saturday_is_weekday` | `test_least_cost`: h1; `test_reported_gas_and_cost`: h1 |
| `import_total_in_kw` | `test_reported_import_export_and_grid_flags`: visible, h1, h2, h3, h4 |
| `grid_flag_without_generators` | `test_reported_import_export_and_grid_flags`: h1, h2 |
| `plan_varies_between_runs` | `test_same_plan_every_time`: visible, h1, h2, h3, h4 |
| `exits_with_error_after_writing` | `test_connection_limits`: visible, h1, h2, h3, h4; `test_cooling_balance`: visible, h1, h2, h3, h4; `test_cooling_towers`: visible, h1, h2, h3, h4; `test_electricity_balance`: visible, h1, h2, h3, h4; `test_heat_balance`: visible, h1, h2, h3, h4; `test_least_cost`: visible, h1, h2, h3, h4; `test_plan_covers_the_day`: visible, h1, h2, h3, h4; `test_reported_gas_and_cost`: visible, h1, h2, h3, h4; `test_reported_import_export_and_grid_flags`: visible, h1, h2, h3, h4; `test_same_plan_every_time`: visible, h1, h2, h3, h4; `test_units_within_ratings_and_availability`: visible, h1, h2, h3, h4 |
| `hangs_after_writing` | `test_connection_limits`: visible, h1, h2, h3, h4; `test_cooling_balance`: visible, h1, h2, h3, h4; `test_cooling_towers`: visible, h1, h2, h3, h4; `test_electricity_balance`: visible, h1, h2, h3, h4; `test_heat_balance`: visible, h1, h2, h3, h4; `test_least_cost`: visible, h1, h2, h3, h4; `test_plan_covers_the_day`: visible, h1, h2, h3, h4; `test_reported_gas_and_cost`: visible, h1, h2, h3, h4; `test_reported_import_export_and_grid_flags`: visible, h1, h2, h3, h4; `test_same_plan_every_time`: visible, h1, h2, h3, h4; `test_units_within_ratings_and_availability`: visible, h1, h2, h3, h4 |
