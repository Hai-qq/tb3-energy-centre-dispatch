# 固定五日与差分矩阵

本文件由 `tools/report_v20.py` 从原始结果生成。PASS 表示该日全部检查通过，不是只过成本；固定日均有两次真实 CLI 运行。

费用参考沿用 v19 的口径：MILP 优化最低许可水温及较严格 AC 辅助排热，而物理检查接受更宽的合理运行解释。因此 MILP 数值是同口径最优及宽模型的可行费用上界；oracle 的 £0.001 检查不构成所有被接受解释的全局最优证明。正成本差可与较便宜可行方案比较以证明失优，负差不能当作错误或遗憾。

## C1

[原始历史工具矩阵](candidates/c1/gates-r1/apps.json) · [全部变异](candidates/c1/gates-r1/mutants.json)

| 应用 | visible | h1 | h2 | h3 | h4 | 全部通过 |
|---|---|---|---|---|---|---|
| oracle | PASS | PASS | PASS | PASS | PASS | 是 |
| strong-v16-claude | FAIL | FAIL | FAIL | PASS | FAIL | 否 |
| strong-v19-claude | FAIL | FAIL | FAIL | FAIL | FAIL | 否 |
| v18-run1-claude | FAIL | FAIL | FAIL | FAIL | FAIL | 否 |
| v18-run1-codex | FAIL | FAIL | FAIL | FAIL | FAIL | 否 |
| v18-run2-claude | FAIL | FAIL | FAIL | FAIL | FAIL | 否 |
| v18-run2-codex | FAIL | FAIL | FAIL | FAIL | FAIL | 否 |
| v18-run3-claude | FAIL | FAIL | FAIL | FAIL | FAIL | 否 |
| v18-run3-codex | FAIL | FAIL | FAIL | FAIL | FAIL | 否 |
| v19-run1-claude | FAIL | FAIL | FAIL | FAIL | FAIL | 否 |
| blind | PASS | FAIL | FAIL | FAIL | FAIL | 否 |

### 失败断言

| 应用 | 失败日：断言 |
|---|---|
| strong-v16-claude | h1: test_least_cost; h2: test_least_cost; h4: test_least_cost; visible: test_least_cost |
| strong-v19-claude | h1: test_reported_gas_and_cost, test_single_connection_direction; h2: test_least_cost, test_reported_gas_and_cost, test_single_connection_direction; h3: test_reported_gas_and_cost, test_single_connection_direction; h4: test_reported_gas_and_cost, test_single_connection_direction; visible: test_reported_gas_and_cost, test_single_connection_direction |
| v18-run1-claude | h1: test_reported_gas_and_cost, test_single_connection_direction, test_units_within_ratings_and_availability; h2: test_reported_gas_and_cost, test_single_connection_direction, test_units_within_ratings_and_availability; h3: test_least_cost, test_reported_gas_and_cost, test_single_connection_direction; h4: test_reported_gas_and_cost, test_single_connection_direction; visible: test_least_cost, test_reported_gas_and_cost, test_single_connection_direction |
| v18-run1-codex | h1: test_reported_gas_and_cost, test_single_connection_direction, test_units_within_ratings_and_availability; h2: test_reported_gas_and_cost, test_single_connection_direction, test_units_within_ratings_and_availability; h3: test_reported_gas_and_cost, test_single_connection_direction, test_units_within_ratings_and_availability; h4: test_reported_gas_and_cost, test_single_connection_direction; visible: test_least_cost, test_reported_gas_and_cost, test_single_connection_direction |
| v18-run2-claude | h1: execution_0, execution_1, test_same_plan_every_time; h2: execution_0, execution_1, test_same_plan_every_time; h3: execution_0, execution_1, test_same_plan_every_time; h4: execution_0, execution_1, test_same_plan_every_time; visible: execution_0, execution_1, test_same_plan_every_time |
| v18-run2-codex | h1: execution_0, execution_1, test_same_plan_every_time; h2: execution_0, execution_1, test_same_plan_every_time; h3: execution_0, execution_1, test_same_plan_every_time; h4: execution_0, execution_1, test_same_plan_every_time; visible: test_connection_limits, test_least_cost, test_reported_gas_and_cost, test_reported_import_export_and_grid_flags, test_single_connection_direction |
| v18-run3-claude | h1: test_connection_limits, test_reported_gas_and_cost, test_reported_import_export_and_grid_flags, test_single_connection_direction, test_units_within_ratings_and_availability; h2: test_connection_limits, test_reported_gas_and_cost, test_reported_import_export_and_grid_flags, test_single_connection_direction, test_units_within_ratings_and_availability; h3: test_reported_gas_and_cost, test_single_connection_direction, test_units_within_ratings_and_availability; h4: test_connection_limits, test_reported_gas_and_cost, test_reported_import_export_and_grid_flags, test_single_connection_direction; visible: test_connection_limits, test_reported_gas_and_cost, test_reported_import_export_and_grid_flags, test_single_connection_direction |
| v18-run3-codex | h1: test_connection_limits, test_reported_gas_and_cost, test_reported_import_export_and_grid_flags, test_single_connection_direction, test_units_within_ratings_and_availability; h2: test_connection_limits, test_reported_gas_and_cost, test_reported_import_export_and_grid_flags, test_single_connection_direction, test_units_within_ratings_and_availability; h3: test_reported_gas_and_cost, test_single_connection_direction, test_units_within_ratings_and_availability; h4: test_connection_limits, test_least_cost, test_reported_gas_and_cost, test_reported_import_export_and_grid_flags, test_single_connection_direction; visible: test_connection_limits, test_least_cost, test_reported_gas_and_cost, test_reported_import_export_and_grid_flags, test_single_connection_direction |
| v19-run1-claude | h1: test_connection_limits, test_least_cost, test_reported_gas_and_cost, test_single_connection_direction, test_units_within_ratings_and_availability; h2: test_connection_limits, test_reported_gas_and_cost, test_reported_import_export_and_grid_flags, test_single_connection_direction, test_units_within_ratings_and_availability; h3: execution_0, execution_1, test_same_plan_every_time; h4: test_connection_limits, test_least_cost, test_reported_gas_and_cost, test_single_connection_direction; visible: test_connection_limits, test_reported_gas_and_cost, test_reported_import_export_and_grid_flags, test_single_connection_direction |
| blind | h1: execution_0, execution_1, test_same_plan_every_time; h2: execution_0, execution_1, test_same_plan_every_time; h3: execution_0, execution_1, test_same_plan_every_time; h4: execution_0, execution_1, test_same_plan_every_time |

变异抓住 **43/43**。

## C2

[原始历史工具矩阵](candidates/c2/gates-r1/apps.json) · [全部变异](candidates/c2/gates-r1/mutants.json)

| 应用 | visible | h1 | h2 | h3 | h4 | 全部通过 |
|---|---|---|---|---|---|---|
| oracle | PASS | PASS | PASS | PASS | PASS | 是 |
| strong-v16-claude | PASS | PASS | FAIL | PASS | PASS | 否 |
| strong-v19-claude | PASS | PASS | FAIL | PASS | PASS | 否 |
| v18-run1-claude | PASS | FAIL | FAIL | FAIL | FAIL | 否 |
| v18-run1-codex | PASS | FAIL | FAIL | FAIL | FAIL | 否 |
| v18-run2-claude | FAIL | FAIL | FAIL | FAIL | FAIL | 否 |
| v18-run2-codex | PASS | FAIL | FAIL | FAIL | FAIL | 否 |
| v18-run3-claude | PASS | FAIL | FAIL | FAIL | FAIL | 否 |
| v18-run3-codex | PASS | FAIL | FAIL | FAIL | FAIL | 否 |
| v19-run1-claude | PASS | FAIL | FAIL | FAIL | FAIL | 否 |
| blind | PASS | FAIL | FAIL | FAIL | FAIL | 否 |

### 失败断言

| 应用 | 失败日：断言 |
|---|---|
| strong-v16-claude | h2: test_shared_gas_entry |
| strong-v19-claude | h2: test_shared_gas_entry |
| v18-run1-claude | h1: test_units_within_ratings_and_availability; h2: test_shared_gas_entry, test_units_within_ratings_and_availability; h3: test_least_cost; h4: test_units_within_ratings_and_availability |
| v18-run1-codex | h1: test_units_within_ratings_and_availability; h2: test_shared_gas_entry, test_units_within_ratings_and_availability; h3: test_units_within_ratings_and_availability; h4: test_units_within_ratings_and_availability |
| v18-run2-claude | h1: execution_0, execution_1, test_same_plan_every_time; h2: execution_0, execution_1, test_same_plan_every_time; h3: execution_0, execution_1, test_same_plan_every_time; h4: execution_0, execution_1, test_same_plan_every_time; visible: execution_0, execution_1, test_same_plan_every_time |
| v18-run2-codex | h1: execution_0, execution_1, test_same_plan_every_time; h2: execution_0, execution_1, test_same_plan_every_time; h3: execution_0, execution_1, test_same_plan_every_time; h4: execution_0, execution_1, test_same_plan_every_time |
| v18-run3-claude | h1: test_units_within_ratings_and_availability; h2: test_shared_gas_entry, test_units_within_ratings_and_availability; h3: test_units_within_ratings_and_availability; h4: test_units_within_ratings_and_availability |
| v18-run3-codex | h1: test_units_within_ratings_and_availability; h2: test_shared_gas_entry, test_units_within_ratings_and_availability; h3: test_units_within_ratings_and_availability; h4: test_units_within_ratings_and_availability |
| v19-run1-claude | h1: test_connection_limits, test_least_cost, test_units_within_ratings_and_availability; h2: test_connection_limits, test_shared_gas_entry, test_units_within_ratings_and_availability; h3: execution_0, execution_1, test_same_plan_every_time; h4: test_connection_limits, test_least_cost |
| blind | h1: execution_0, execution_1, test_same_plan_every_time; h2: execution_0, execution_1, test_same_plan_every_time; h3: execution_0, execution_1, test_same_plan_every_time; h4: execution_0, execution_1, test_same_plan_every_time |

变异抓住 **44/44**。

## C4

[原始历史工具矩阵](candidates/c4/gates-r1/apps.json) · [全部变异](candidates/c4/gates-r1/mutants.json)

| 应用 | visible | h1 | h2 | h3 | h4 | 全部通过 |
|---|---|---|---|---|---|---|
| oracle | PASS | PASS | PASS | PASS | PASS | 是 |
| strong-v16-claude | PASS | PASS | FAIL | PASS | PASS | 否 |
| strong-v19-claude | PASS | PASS | FAIL | PASS | PASS | 否 |
| v18-run1-claude | PASS | FAIL | FAIL | FAIL | FAIL | 否 |
| v18-run1-codex | PASS | FAIL | FAIL | FAIL | FAIL | 否 |
| v18-run2-claude | FAIL | FAIL | FAIL | FAIL | FAIL | 否 |
| v18-run2-codex | PASS | FAIL | FAIL | FAIL | FAIL | 否 |
| v18-run3-claude | PASS | FAIL | FAIL | FAIL | FAIL | 否 |
| v18-run3-codex | PASS | FAIL | FAIL | FAIL | FAIL | 否 |
| v19-run1-claude | PASS | FAIL | FAIL | FAIL | FAIL | 否 |
| blind | PASS | FAIL | FAIL | FAIL | FAIL | 否 |

### 失败断言

| 应用 | 失败日：断言 |
|---|---|
| strong-v16-claude | h2: test_phe_primary_water_flow |
| strong-v19-claude | h2: test_phe_primary_water_flow |
| v18-run1-claude | h1: test_units_within_ratings_and_availability; h2: test_phe_primary_water_flow, test_units_within_ratings_and_availability; h3: test_least_cost; h4: test_units_within_ratings_and_availability |
| v18-run1-codex | h1: test_units_within_ratings_and_availability; h2: test_phe_primary_water_flow, test_units_within_ratings_and_availability; h3: test_units_within_ratings_and_availability; h4: test_units_within_ratings_and_availability |
| v18-run2-claude | h1: execution_0, execution_1, test_same_plan_every_time; h2: execution_0, execution_1, test_same_plan_every_time; h3: execution_0, execution_1, test_same_plan_every_time; h4: execution_0, execution_1, test_same_plan_every_time; visible: execution_0, execution_1, test_same_plan_every_time |
| v18-run2-codex | h1: execution_0, execution_1, test_same_plan_every_time; h2: execution_0, execution_1, test_same_plan_every_time; h3: execution_0, execution_1, test_same_plan_every_time; h4: execution_0, execution_1, test_same_plan_every_time |
| v18-run3-claude | h1: test_units_within_ratings_and_availability; h2: test_phe_primary_water_flow, test_units_within_ratings_and_availability; h3: test_units_within_ratings_and_availability; h4: test_units_within_ratings_and_availability |
| v18-run3-codex | h1: test_units_within_ratings_and_availability; h2: test_phe_primary_water_flow, test_units_within_ratings_and_availability; h3: test_units_within_ratings_and_availability; h4: test_units_within_ratings_and_availability |
| v19-run1-claude | h1: test_connection_limits, test_least_cost, test_units_within_ratings_and_availability; h2: test_connection_limits, test_phe_primary_water_flow, test_units_within_ratings_and_availability; h3: execution_0, execution_1, test_same_plan_every_time; h4: test_connection_limits, test_least_cost |
| blind | h1: test_units_within_ratings_and_availability; h2: test_units_within_ratings_and_availability; h3: test_units_within_ratings_and_availability; h4: test_units_within_ratings_and_availability |

变异抓住 **44/44**。

## C1：200 日差分

[完整摘要](candidates/c1/fuzz-200/summary.json) · [全部输入及接受/拒绝记录](candidates/c1/fuzz-200/manifest.json)

| 应用 | 通过日 | 失败日 | 最大单日回放及核验秒数 | 最大绝对成本差 £ |
|---|---:|---:|---:|---:|
| blind | 91 | 109 | 6.238 | 20.577533 |
| oracle | 200 | 0 | 5.684 | 0.000489 |
| strong-v16 | 117 | 83 | 4.557 | 57.586464 |
| strong-v19 | 0 | 200 | 3.429 | 57.642491 |

本表计时包含 CLI 执行及其后的流量重算/断言，因而是 CLI 时间的上界，不是单独 CLI 的精确耗时。失败工具的成本差不能代替可行性检查；表中的最大绝对差也不等于每份工具的最大有效可行计划遗憾。具体失败原因见每一天 `runs/` 内的原始计划与 `result.json`。

## 三组候选的 fresh 日

每个候选独立生成并评测三个 seed，各16个接受日。下表只在该次 manifest 的评测完成标志存在时记作完成。

| 候选 | seed | 接受日 | 评测完成 | 所有测试通过 | 输入未变 |
|---|---:|---:|---|---|---|
| c1 | 2026 | 16 | 是 | 是 | 是 |
| c1 | 2403 | 16 | 是 | 是 | 是 |
| c1 | 87123 | 16 | 是 | 是 | 是 |
| c2 | 2026 | 16 | 是 | 是 | 是 |
| c2 | 2403 | 16 | 是 | 是 | 是 |
| c2 | 87123 | 16 | 是 | 是 | 是 |
| c4 | 2026 | 16 | 是 | 是 | 是 |
| c4 | 2403 | 16 | 是 | 是 | 是 |
| c4 | 87123 | 16 | 是 | 是 | 是 |
