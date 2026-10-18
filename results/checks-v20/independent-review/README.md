# PR #2（v20-gptpro）独立复核事实记录

本次按任务书完成第 1–4 节。结论：三候选都击破 A16/A19，分别只补对应新规则后，两强恢复五日全过；去掉具名部件检修后，三份冻结盲替身和标准答案均通过全部原判分。新增规则有实际受限时段，支持这三项提示预检应淘汰、正式题目保留 v19 的结论。完整结论仅限本次列明的输入和程序。

初始分支 `v20-gptpro`、提交 `e903a50`，初始 `git status --porcelain` 为空。没有运行 Harbor、Docker、正式模型试跑、提交或推送，也没有更改原任务、原工具、已有结果或网络设施。只新增本目录，任务副本、计划和生成日放在指定 `<D>`。

## 命令和记录约定

全部计算使用任务书给定 venv；通用命令前缀如下（以下 `$P` 是 Python 路径）：

```sh
P=/private/tmp/claude-501/-Users-haiy-qq-Desktop----klavis/a70e7eab-ed43-4fbc-8c31-1d0858956a32/scratchpad/codex-v18-verify/venv/bin/python
D=/private/tmp/claude-501/-Users-haiy-qq-Desktop----klavis/a70e7eab-ed43-4fbc-8c31-1d0858956a32/scratchpad/codex-v20-review
O=results/checks-v20/independent-review
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
```

每条外部命令对应 `*.command.json`，含完整 argv、`ECD_TASK`、独立 `TMPDIR`、退出码、耗时和日志路径；同名 `.log` 保存 stdout/stderr。三个变异组和第四个顺序验证组并行，最多四组评测；各变异组有独立 `TMPDIR`。本目录脚本是本次独立复核代码，未改仓库原脚本。命令为本次执行记录；重新执行时应另选新的输出目录，避免覆盖现有证据。

[run_review.py](run_review.py) 记录命令并运行原入口；[candidate_review.py](candidate_review.py) 做逐候选检查、独立因果补丁和成本/绑定统计；[remaining_review.py](remaining_review.py) 做第 1、3、4 节。判分采用原 `tools/eval_energy.py` / `evaluate()`，由它调用原 pytest；只在抽样副本中把 `DAYS` 换成预选 25 日，未改变断言。GPT Pro 的 `check_v20.extras()` 仅提供原有新增变异文本，未用其判分结果作本次结论。

## 1. 正式题目及 fresh 默认行为

实际命令：

```sh
git diff 9db5808 HEAD -- tasks/
git diff 9db5808 HEAD -- tools/fresh_days.py
# 不设置 ECD_TASK

"$P" tools/fresh_days.py --days 4 --seed 2026 --output "$D/formal-fresh-4" tasks/energy-centre-dispatch/solution/app
```

结果：tasks diff 为空；fresh diff 仅增加 `os`、`ECD_TASK` 路径选择，以及从所选任务加载 `B.PLANT/B.SUPPLY`。正式任务这两个对象与旧生成器常量逐项相等，见 [formal/default-constants.json](formal/default-constants.json)；未指定 `ECD_TASK` 时仍选原正式任务。实跑 4 日，失败 0/4，退出码 0。与 GPT Pro 一致。证据：[formal/tasks-diff.log](formal/tasks-diff.log)、[formal/fresh-diff.log](formal/fresh-diff.log)、[formal/fresh-4.log](formal/fresh-4.log)、[formal/fresh-manifest.json](formal/fresh-manifest.json)。

## 2. C1

本组完整执行命令：`"$P" "$O/candidate_review.py" c1`；变量 `T=results/checks-v20/candidates/c1/task`，`B=results/checks-v20/blind/c1/app`。

### 2a. 可见文件

命令/方法：脚本逐字节比较 `T/environment/` 与正式 `environment/`，再递归比较变化 JSON 的字段，并直接比较两份 `instruction.md`。结果：instruction 相同；变化仅为 `data/supply.json` 中 weekday/weekend 第一档 13.8→7.0、出口 5.9→12.0，共三个数值。 与 `VISIBLE_CHANGES.md` 一致。完整差异：[c1/environment.diff](c1/environment.diff)；字段摘要：[c1/visible-summary.json](c1/visible-summary.json)。

### 2b. 标准答案与独立费用

命令：`ECD_TASK="$T" "$P" tools/eval_energy.py "$T/solution/app"`；随后脚本逐日实际 CLI 输出计划，调用该候选自己的 `Day.least_cost()` 和 `Day.true_flows(plan)`。
结果：原判分 60/60 通过。五日成本差（真实成本减同口径 MILP）最大绝对值 £0.000181119，全部小于 £0.001；与 GPT Pro 一致。[c1/oracle-eval.log](c1/oracle-eval.log)、[c1/oracle-cost-binding.json](c1/oracle-cost-binding.json)。

| 日子 | MILP (£) | true_flows (£) | 差 (£) |
|---|---:|---:|---:|
| visible | 5959.003279125 | 5959.003250190 | -0.000028935 |
| h1 | 6120.657620078 | 6120.657801197 | +0.000181119 |
| h2 | 8630.929864418 | 8630.929843864 | -0.000020553 |
| h3 | 5242.028050077 | 5242.027896042 | -0.000154035 |
| h4 | 6933.978477561 | 6933.978453059 | -0.000024502 |

### 2c. 变异

命令：`"$P" "$O/run_review.py" mutants c1`，内部先执行 `ECD_TASK="$T" "$P" tools/energy_mutants.py`，再把候选新增变异分别应用到 `<D>` 的标准答案副本，用原 `eval_energy.py` 判分。
结果：原入口 42/42 被抓，额外 1/1 被抓，合计 **43/43**；MISSED=0。原入口正常退出 0，逐个补丁都执行 `source.count(old)==1` 断言，没有找不到原文的跳过项。与 GPT Pro 的 43 一致。原入口单独运行只涵盖 42 个，43/44 是加上候选新增变异的总数。[c1/mutants-base.log](c1/mutants-base.log)、[c1/mutants-extra-summary.json](c1/mutants-extra-summary.json)。

### 2d. 16 个随机日

命令：`ECD_TASK="$T" "$P" tools/fresh_days.py --days 16 --seed 2026 --output "$D/c1-fresh-16" "$T/solution/app"`。
结果：16 个已通过输入检查及独立可行性筛选的日期，双次 CLI + 原 pytest 全过，失败 0/16，退出 0；输入在判分前后散列不变。与 GPT Pro 对 seed 2026 的声明一致。本次没有重跑另外两个 seed。[c1/fresh-16.log](c1/fresh-16.log)、[c1/fresh-manifest.json](c1/fresh-manifest.json)。

### 2e. 两强原样与仅新规则的因果对照

实际每份命令：`ECD_TASK="$T" "$P" tools/eval_energy.py <原app>`，以及 `ECD_TASK="$T" "$P" tools/eval_energy.py "$D/<候选>-<A16或A19>-rule-only"`。A16 原 app 为 `results/v16-trials/ecd16-run2-claude/app`，A19 为 `results/v19-trials/ecd19-run2-claude/app`。

| 工具 | 原样失败的测试与日子 | 仅补新规则后 | 补丁 |
|---|---|---|---|
| A16 | `test_least_cost`：visible, h1, h2, h4 | 全部通过（exit 0） | [c1/A16-rule-only.patch](c1/A16-rule-only.patch) |
| A19 | `test_least_cost`：h2；`test_reported_gas_and_cost`：visible, h1, h2, h3, h4；`test_single_connection_direction`：visible, h1, h2, h3, h4 | 全部通过（exit 0） | [c1/A19-rule-only.patch](c1/A19-rule-only.patch) |

补丁范围：只在购价低于售价的时段分别求仅进口、仅出口两种 LP，保留原有费用、检修、设备、连接约束及选优方法。原样两强都失败，补丁副本各 60/60 全过，因果结果与 GPT Pro 一致；原目录没有适配。完整失败日志和命令在本候选子目录。

### 2f. 冻结盲替身及去部件检修的隔离检查

命令/方法：逐项读取 `blind/c1/FREEZE.json` 的 files 清单并重新 SHA-256；然后 `ECD_TASK="$T" "$P" tools/eval_energy.py "$B"`。
结果：323 个冻结文件全部匹配，mismatch=0。原五日 visible 全过；h1–h4 因原有具名部件的 unknown outage 报错退出，无法建立 case，因此不是已经执行并通过了新规则断言。与 GPT Pro 一致。[c1/freeze.json](c1/freeze.json)、[c1/blind-original.log](c1/blind-original.log)。

隔离命令：复制任务到 `$D/c1-whole-unit-outages-task`，仅对 h1–h4 的 `status.json.outages` 删除 `unit` 名称含空格的条目，再分别执行：

```sh
ECD_TASK="$D/c1-whole-unit-outages-task" "$P" tools/eval_energy.py "$B"
ECD_TASK="$D/c1-whole-unit-outages-task" "$P" tools/eval_energy.py "$D/c1-whole-unit-outages-task/solution/app"
```

四天分别删 1、3、3、2 条，共 9 条；包括按任务书要求删除的 LT radiator 名称，visible 不动，所有其他文件逐字节保留。删除清单：[c1/removed-outages.json](c1/removed-outages.json)。独立 MILP 以副本输入重算，未使用原日子的费用缓存。

结果：盲替身和标准答案均 **60/60 全过**（h1–h4 各 12/12，加 visible 12/12）；新规则断言 `test_single_connection_direction` 与 `test_least_cost` 在 h1–h4 全部通过；其他 10 项也全过。[c1/blind-whole-unit.log](c1/blind-whole-unit.log)、[c1/oracle-whole-unit.log](c1/oracle-whole-unit.log)。这是本次新增隔离证据，GPT Pro 未自称跑过完全相同的去检修副本；结果支持其“新规则已被解决”的判断。

| 日子 | 标准答案新规则绑定情况 | 盲替身新规则绑定情况 | 盲替身成本−副本MILP (£) |
|---|---|---|---:|
| h1 | 方向边界 48/48；可套利松弛 14 段 | 双向 0 段 | -6.394127908 |
| h2 | 方向边界 48/48；可套利松弛 3 段 | 双向 0 段 | +0.004264012 |
| h3 | 方向边界 48/48；可套利松弛 14 段 | 双向 0 段 | +0.000000000 |
| h4 | 方向边界 48/48；可套利松弛 14 段 | 双向 0 段 | -14.879030783 |

方向限制无独立的容量数字：“顶格”指 `min(import,export)=0`。为避免把这个形式事实当成有效压力，另在保持设备出力和净交换不动时计算放宽方向可添加的共同买卖量；h1–h4 分别有 14、3、14、14 个反向价格时段可增加超过 1 kW 的共同交易并降低费用，故这四天方向规则实际起作用。该松弛计算是压力诊断，不作为物理合法计划；盲替身没有进行共同交易。

逐日完整数值：[c1/oracle-whole-unit-cost-binding.json](c1/oracle-whole-unit-cost-binding.json)、[c1/blind-whole-unit-cost-binding.json](c1/blind-whole-unit-cost-binding.json)。盲替身按原成本容差判分；负差额不声称突破全物理模型最优，正差额也没有套用标准答案专属 £0.001 门槛。

## 2. C2

本组完整执行命令：`"$P" "$O/candidate_review.py" c2`；变量 `T=results/checks-v20/candidates/c2/task`，`B=results/checks-v20/blind/c2/app`。

### 2a. 可见文件

命令/方法：脚本逐字节比较 `T/environment/` 与正式 `environment/`，再递归比较变化 JSON 的字段，并直接比较两份 `instruction.md`。结果：instruction 相同；变化仅为 `data/supply.json` 新增完整 `gas.entry` 对象（550 Sm³/h、39.6 MJ/Sm³、四个供气对象及标准状态）。 与 `VISIBLE_CHANGES.md` 一致。完整差异：[c2/environment.diff](c2/environment.diff)；字段摘要：[c2/visible-summary.json](c2/visible-summary.json)。

### 2b. 标准答案与独立费用

命令：`ECD_TASK="$T" "$P" tools/eval_energy.py "$T/solution/app"`；随后脚本逐日实际 CLI 输出计划，调用该候选自己的 `Day.least_cost()` 和 `Day.true_flows(plan)`。
结果：原判分 60/60 通过。五日成本差（真实成本减同口径 MILP）最大绝对值 £0.000276852，全部小于 £0.001；与 GPT Pro 一致。[c2/oracle-eval.log](c2/oracle-eval.log)、[c2/oracle-cost-binding.json](c2/oracle-cost-binding.json)。

| 日子 | MILP (£) | true_flows (£) | 差 (£) |
|---|---:|---:|---:|
| visible | 6303.560319427 | 6303.560409190 | +0.000089763 |
| h1 | 6426.647467103 | 6426.647743955 | +0.000276852 |
| h2 | 8973.720100812 | 8973.720054129 | -0.000046684 |
| h3 | 5375.538040469 | 5375.538030470 | -0.000009999 |
| h4 | 7310.971840533 | 7310.971820541 | -0.000019992 |

### 2c. 变异

命令：`"$P" "$O/run_review.py" mutants c2`，内部先执行 `ECD_TASK="$T" "$P" tools/energy_mutants.py`，再把候选新增变异分别应用到 `<D>` 的标准答案副本，用原 `eval_energy.py` 判分。
结果：原入口 42/42 被抓，额外 2/2 被抓，合计 **44/44**；MISSED=0。原入口正常退出 0，逐个补丁都执行 `source.count(old)==1` 断言，没有找不到原文的跳过项。与 GPT Pro 的 44 一致。原入口单独运行只涵盖 42 个，43/44 是加上候选新增变异的总数。[c2/mutants-base.log](c2/mutants-base.log)、[c2/mutants-extra-summary.json](c2/mutants-extra-summary.json)。

### 2d. 16 个随机日

命令：`ECD_TASK="$T" "$P" tools/fresh_days.py --days 16 --seed 2026 --output "$D/c2-fresh-16" "$T/solution/app"`。
结果：16 个已通过输入检查及独立可行性筛选的日期，双次 CLI + 原 pytest 全过，失败 0/16，退出 0；输入在判分前后散列不变。与 GPT Pro 对 seed 2026 的声明一致。本次没有重跑另外两个 seed。[c2/fresh-16.log](c2/fresh-16.log)、[c2/fresh-manifest.json](c2/fresh-manifest.json)。

### 2e. 两强原样与仅新规则的因果对照

实际每份命令：`ECD_TASK="$T" "$P" tools/eval_energy.py <原app>`，以及 `ECD_TASK="$T" "$P" tools/eval_energy.py "$D/<候选>-<A16或A19>-rule-only"`。A16 原 app 为 `results/v16-trials/ecd16-run2-claude/app`，A19 为 `results/v19-trials/ecd19-run2-claude/app`。

| 工具 | 原样失败的测试与日子 | 仅补新规则后 | 补丁 |
|---|---|---|---|
| A16 | `test_shared_gas_entry`：h2 | 全部通过（exit 0） | [c2/A16-rule-only.patch](c2/A16-rule-only.patch) |
| A19 | `test_shared_gas_entry`：h2 | 全部通过（exit 0） | [c2/A19-rule-only.patch](c2/A19-rule-only.patch) |

补丁范围：只读取入口对象，并在原 LP 中添加四设备合计 gross 燃气功率上限，包含发动机仿射燃料截距与锅炉效率。原样两强都失败，补丁副本各 60/60 全过，因果结果与 GPT Pro 一致；原目录没有适配。完整失败日志和命令在本候选子目录。

### 2f. 冻结盲替身及去部件检修的隔离检查

命令/方法：逐项读取 `blind/c2/FREEZE.json` 的 files 清单并重新 SHA-256；然后 `ECD_TASK="$T" "$P" tools/eval_energy.py "$B"`。
结果：198 个冻结文件全部匹配，mismatch=0。原五日 visible 全过；h1–h4 因原有具名部件的 unknown outage 报错退出，无法建立 case，因此不是已经执行并通过了新规则断言。与 GPT Pro 一致。[c2/freeze.json](c2/freeze.json)、[c2/blind-original.log](c2/blind-original.log)。

隔离命令：复制任务到 `$D/c2-whole-unit-outages-task`，仅对 h1–h4 的 `status.json.outages` 删除 `unit` 名称含空格的条目，再分别执行：

```sh
ECD_TASK="$D/c2-whole-unit-outages-task" "$P" tools/eval_energy.py "$B"
ECD_TASK="$D/c2-whole-unit-outages-task" "$P" tools/eval_energy.py "$D/c2-whole-unit-outages-task/solution/app"
```

四天分别删 1、3、3、2 条，共 9 条；包括按任务书要求删除的 LT radiator 名称，visible 不动，所有其他文件逐字节保留。删除清单：[c2/removed-outages.json](c2/removed-outages.json)。独立 MILP 以副本输入重算，未使用原日子的费用缓存。

结果：盲替身和标准答案均 **60/60 全过**（h1–h4 各 12/12，加 visible 12/12）；新规则断言 `test_shared_gas_entry` 与 `test_least_cost` 在 h1–h4 全部通过；其他 10 项也全过。[c2/blind-whole-unit.log](c2/blind-whole-unit.log)、[c2/oracle-whole-unit.log](c2/oracle-whole-unit.log)。这是本次新增隔离证据，GPT Pro 未自称跑过完全相同的去检修副本；结果支持其“新规则已被解决”的判断。

| 日子 | 标准答案新规则绑定情况 | 盲替身新规则绑定情况 | 盲替身成本−副本MILP (£) |
|---|---|---|---:|
| h1 | 0/48 顶格；峰值 289.087273 Sm³/h | 0/48 顶格；峰值 289.087273 | +0.003249244 |
| h2 | 14/48 顶格；峰值 550.000091 Sm³/h | 14/48 顶格；峰值 550.000000 | +0.003457164 |
| h3 | 0/48 顶格；峰值 439.249847 Sm³/h | 0/48 顶格；峰值 439.249792 | -0.000000000 |
| h4 | 0/48 顶格；峰值 291.379984 Sm³/h | 0/48 顶格；峰值 291.380038 | -0.000000000 |

标准答案中有实际顶格的日子为 h2；其他未顶格的日子单独不能证明容量约束被正确处理。顶格判定数值容差为 0.01 Sm³/h，与正式判分的越界容差分别记录，不混同。

逐日完整数值：[c2/oracle-whole-unit-cost-binding.json](c2/oracle-whole-unit-cost-binding.json)、[c2/blind-whole-unit-cost-binding.json](c2/blind-whole-unit-cost-binding.json)。盲替身按原成本容差判分；负差额不声称突破全物理模型最优，正差额也没有套用标准答案专属 £0.001 门槛。

## 2. C4

本组完整执行命令：`"$P" "$O/candidate_review.py" c4`；变量 `T=results/checks-v20/candidates/c4/task`，`B=results/checks-v20/blind/c4/app`。

### 2a. 可见文件

命令/方法：脚本逐字节比较 `T/environment/` 与正式 `environment/`，再递归比较变化 JSON 的字段，并直接比较两份 `instruction.md`。结果：instruction 相同；变化仅为 `data/plant.json` 新增 `heat_exchangers` 的 PHE1 对象（一次/二次回路、20 kg/s、4.18 kJ/(kg K)）。 与 `VISIBLE_CHANGES.md` 一致。完整差异：[c4/environment.diff](c4/environment.diff)；字段摘要：[c4/visible-summary.json](c4/visible-summary.json)。

### 2b. 标准答案与独立费用

命令：`ECD_TASK="$T" "$P" tools/eval_energy.py "$T/solution/app"`；随后脚本逐日实际 CLI 输出计划，调用该候选自己的 `Day.least_cost()` 和 `Day.true_flows(plan)`。
结果：原判分 60/60 通过。五日成本差（真实成本减同口径 MILP）最大绝对值 £0.000276852，全部小于 £0.001；与 GPT Pro 一致。[c4/oracle-eval.log](c4/oracle-eval.log)、[c4/oracle-cost-binding.json](c4/oracle-cost-binding.json)。

| 日子 | MILP (£) | true_flows (£) | 差 (£) |
|---|---:|---:|---:|
| visible | 6303.560319427 | 6303.560409190 | +0.000089763 |
| h1 | 6426.647467103 | 6426.647743955 | +0.000276852 |
| h2 | 9107.675896200 | 9107.675997181 | +0.000100980 |
| h3 | 5375.538040469 | 5375.538030470 | -0.000009999 |
| h4 | 7310.971840533 | 7310.971820541 | -0.000019992 |

### 2c. 变异

命令：`"$P" "$O/run_review.py" mutants c4`，内部先执行 `ECD_TASK="$T" "$P" tools/energy_mutants.py`，再把候选新增变异分别应用到 `<D>` 的标准答案副本，用原 `eval_energy.py` 判分。
结果：原入口 42/42 被抓，额外 2/2 被抓，合计 **44/44**；MISSED=0。原入口正常退出 0，逐个补丁都执行 `source.count(old)==1` 断言，没有找不到原文的跳过项。与 GPT Pro 的 44 一致。原入口单独运行只涵盖 42 个，43/44 是加上候选新增变异的总数。[c4/mutants-base.log](c4/mutants-base.log)、[c4/mutants-extra-summary.json](c4/mutants-extra-summary.json)。

### 2d. 16 个随机日

命令：`ECD_TASK="$T" "$P" tools/fresh_days.py --days 16 --seed 2026 --output "$D/c4-fresh-16" "$T/solution/app"`。
结果：16 个已通过输入检查及独立可行性筛选的日期，双次 CLI + 原 pytest 全过，失败 0/16，退出 0；输入在判分前后散列不变。与 GPT Pro 对 seed 2026 的声明一致。本次没有重跑另外两个 seed。[c4/fresh-16.log](c4/fresh-16.log)、[c4/fresh-manifest.json](c4/fresh-manifest.json)。

### 2e. 两强原样与仅新规则的因果对照

实际每份命令：`ECD_TASK="$T" "$P" tools/eval_energy.py <原app>`，以及 `ECD_TASK="$T" "$P" tools/eval_energy.py "$D/<候选>-<A16或A19>-rule-only"`。A16 原 app 为 `results/v16-trials/ecd16-run2-claude/app`，A19 为 `results/v19-trials/ecd19-run2-claude/app`。

| 工具 | 原样失败的测试与日子 | 仅补新规则后 | 补丁 |
|---|---|---|---|
| A16 | `test_phe_primary_water_flow`：h2 | 全部通过（exit 0） | [c4/A16-rule-only.patch](c4/A16-rule-only.patch) |
| A19 | `test_phe_primary_water_flow`：h2 | 全部通过（exit 0） | [c4/A19-rule-only.patch](c4/A19-rule-only.patch) |

补丁范围：只从一次侧流量、比热和给定 90/70°C 温差计算 1672 kW，并限制原有 PHE 传热变量；没有限制全部 HT。原样两强都失败，补丁副本各 60/60 全过，因果结果与 GPT Pro 一致；原目录没有适配。完整失败日志和命令在本候选子目录。

### 2f. 冻结盲替身及去部件检修的隔离检查

命令/方法：逐项读取 `blind/c4/FREEZE.json` 的 files 清单并重新 SHA-256；然后 `ECD_TASK="$T" "$P" tools/eval_energy.py "$B"`。
结果：307 个冻结文件全部匹配，mismatch=0。原五日 visible 全过；h1–h4 仅 `test_units_within_ratings_and_availability` 失败。与 GPT Pro 一致。[c4/freeze.json](c4/freeze.json)、[c4/blind-original.log](c4/blind-original.log)。

隔离命令：复制任务到 `$D/c4-whole-unit-outages-task`，仅对 h1–h4 的 `status.json.outages` 删除 `unit` 名称含空格的条目，再分别执行：

```sh
ECD_TASK="$D/c4-whole-unit-outages-task" "$P" tools/eval_energy.py "$B"
ECD_TASK="$D/c4-whole-unit-outages-task" "$P" tools/eval_energy.py "$D/c4-whole-unit-outages-task/solution/app"
```

四天分别删 1、3、3、2 条，共 9 条；包括按任务书要求删除的 LT radiator 名称，visible 不动，所有其他文件逐字节保留。删除清单：[c4/removed-outages.json](c4/removed-outages.json)。独立 MILP 以副本输入重算，未使用原日子的费用缓存。

结果：盲替身和标准答案均 **60/60 全过**（h1–h4 各 12/12，加 visible 12/12）；新规则断言 `test_phe_primary_water_flow` 与 `test_least_cost` 在 h1–h4 全部通过；其他 10 项也全过。[c4/blind-whole-unit.log](c4/blind-whole-unit.log)、[c4/oracle-whole-unit.log](c4/oracle-whole-unit.log)。这是本次新增隔离证据，GPT Pro 未自称跑过完全相同的去检修副本；结果支持其“新规则已被解决”的判断。

| 日子 | 标准答案新规则绑定情况 | 盲替身新规则绑定情况 | 盲替身成本−副本MILP (£) |
|---|---|---|---:|
| h1 | 0/48 顶格；峰值 501.900000 kW | 0/48 顶格；峰值 501.900000 | -6.394127908 |
| h2 | 31/48 顶格；峰值 1672.000506 kW | 31/48 顶格；峰值 1672.000000 | +0.003457164 |
| h3 | 0/48 顶格；峰值 1610.599744 kW | 0/48 顶格；峰值 1610.600000 | +0.000000000 |
| h4 | 0/48 顶格；峰值 487.400000 kW | 0/48 顶格；峰值 487.400000 | -14.879030783 |

标准答案中有实际顶格的日子为 h2；其他未顶格的日子单独不能证明容量约束被正确处理。顶格判定数值容差为 0.01 kW，与正式判分的越界容差分别记录，不混同。

逐日完整数值：[c4/oracle-whole-unit-cost-binding.json](c4/oracle-whole-unit-cost-binding.json)、[c4/blind-whole-unit-cost-binding.json](c4/blind-whole-unit-cost-binding.json)。盲替身按原成本容差判分；负差额不声称突破全物理模型最优，正差额也没有套用标准答案专属 £0.001 门槛。

## 3. C1 200 日均匀抽 25 日重放

方法：把原目录的 200 个已接受日按零填充编号排序，在位置 `round(i × 199 / 24)`（i=0…24，零起始）取 25 日，含首尾，不使用应用成绩选日。具体编号：`d0001, d0014, d0026, d0035, d0045, d0057, d0070, d0083, d0093, d0105, d0115, d0128, d0138, d0150, d0159, d0168, d0180, d0192, d0203, d0216, d0227, d0238, d0252, d0265, d0277`。[sample/selection.json](sample/selection.json)

执行记录：首次抽样脚本把 `days/` 当作只有200个已接受日，在调用任何应用前触发计数断言；实际目录保留277个抽样（含77个拒绝日）。修正为仅使用冻结 `manifest.accepted` 的200项，先逐文件核对原manifest散列，再按上述固定规则取25日，没有按成绩换日。首次日志保留在 [sample-driver.log](sample-driver.log)，成功重跑记录为 [sample-retry-driver.command.json](sample-retry-driver.command.json)。

命令：`"$P" "$O/remaining_review.py" sample`。它复制原 C1 `reference.py/test_plans.py`，只替换后者的 DAYS 列表，以原 `eval_energy.evaluate()` 对 oracle/A16/A19/冻结 C1 盲替身各跑每一天两次并执行原 pytest。具体四条 adapter 命令、环境和失败日志见 `sample/*.command.json` 和 `.log`；eval入口按原行为删除临时CLI计划；本次保留了逐测试失败、CLI错误与命令，未把未保存的抽样计划声称为已归档。固定日成本复算计划则保存在<D>。

`summary.json` 只有汇总，没有逐日成绩；本次先与同目录 `runs/<day>/<app>/result.json` 逐天比较，再汇总。未把 25 日结果冒充重新运行全部 200 日。

| 工具 | 本次25日通过/失败 | 与原逐日成绩一致 | GPT Pro原200日通过/失败 |
|---|---:|---:|---:|
| oracle | 25/0 | 25/25 | 200/0 |
| strong-v16 | 10/15 | 25/25 | 117/83 |
| strong-v19 | 0/25 | 25/25 | 0/200 |
| blind | 11/14 | 25/25 | 91/109 |

| 日子 | oracle | A16 | A19 | C1盲替身 |
|---|---|---|---|---|
| d0001 | PASS/同 | FAIL/同 | FAIL/同 | PASS/同 |
| d0014 | PASS/同 | PASS/同 | FAIL/同 | FAIL/同 |
| d0026 | PASS/同 | PASS/同 | FAIL/同 | FAIL/同 |
| d0035 | PASS/同 | FAIL/同 | FAIL/同 | FAIL/同 |
| d0045 | PASS/同 | FAIL/同 | FAIL/同 | FAIL/同 |
| d0057 | PASS/同 | FAIL/同 | FAIL/同 | FAIL/同 |
| d0070 | PASS/同 | PASS/同 | FAIL/同 | PASS/同 |
| d0083 | PASS/同 | FAIL/同 | FAIL/同 | PASS/同 |
| d0093 | PASS/同 | FAIL/同 | FAIL/同 | FAIL/同 |
| d0105 | PASS/同 | FAIL/同 | FAIL/同 | FAIL/同 |
| d0115 | PASS/同 | FAIL/同 | FAIL/同 | PASS/同 |
| d0128 | PASS/同 | PASS/同 | FAIL/同 | FAIL/同 |
| d0138 | PASS/同 | FAIL/同 | FAIL/同 | PASS/同 |
| d0150 | PASS/同 | PASS/同 | FAIL/同 | FAIL/同 |
| d0159 | PASS/同 | FAIL/同 | FAIL/同 | PASS/同 |
| d0168 | PASS/同 | PASS/同 | FAIL/同 | PASS/同 |
| d0180 | PASS/同 | PASS/同 | FAIL/同 | PASS/同 |
| d0192 | PASS/同 | PASS/同 | FAIL/同 | FAIL/同 |
| d0203 | PASS/同 | FAIL/同 | FAIL/同 | FAIL/同 |
| d0216 | PASS/同 | PASS/同 | FAIL/同 | FAIL/同 |
| d0227 | PASS/同 | FAIL/同 | FAIL/同 | FAIL/同 |
| d0238 | PASS/同 | PASS/同 | FAIL/同 | PASS/同 |
| d0252 | PASS/同 | FAIL/同 | FAIL/同 | PASS/同 |
| d0265 | PASS/同 | FAIL/同 | FAIL/同 | FAIL/同 |
| d0277 | PASS/同 | FAIL/同 | FAIL/同 | PASS/同 |

结果：100 个“工具×日子”通过/失败均与 GPT Pro 一致。CLI 报错会使原 pytest 的整个 case 建立失败，测试名数量与 GPT Pro 的 `execution_or_flow` 分类不同；逐日通过/失败口径一致。证据：[sample/day-comparison.json](sample/day-comparison.json)、[sample/summary.json](sample/summary.json)。

## 4. 共享 LT 散热器内存探针与可行见证

命令：`"$P" "$O/remaining_review.py" probe`。本次按描述重建内存图，直接调用两份未修改应用的 `load_day`、`Plant`、`Tariff`、`plan_day`：一条 engine_lt，两个中冷器连两只并联独立隔离散热器，每只 220 kW；负荷 1250 kW / 450 kvar / 热2000 kW / 冷500 kW，PV=0，湿球18°C、干球24°C，共48段；唯一检修 radiator 1 的12:00–14:00。没有生成新的正式候选。

| 工具 | 12:00 GE1/GE2 (kWe) | 4段LT热量(kW) | grid flag失败段数 | 日费用(£，非法计划不可比较节省) |
|---|---:|---|---:|---:|
| A16 | 0.000000/0.000000 | 0.000000, 0.000000, 0.000000, 0.000000 | 4 | 5390.732890686 |
| A19 | 900.000000/482.923077 | 252.194615, 252.194615, 252.194615, 252.194615 | 0 | 4934.822204469 |

与 `research/shared-lt-root-replay.json` 逐字段比较（排除运行耗时、描述文字），差异 0 项，所有数值在 1e-7 内一致。A16 错把可旁路检修传播到两台发动机而超接入容量；A19 保留两机运行，但 LT=252.194615 kW > 剩余220 kW。[lt/replay.json](lt/replay.json)、[lt/A16-periods.json](lt/A16-periods.json)、[lt/A19-periods.json](lt/A19-periods.json)。

可行见证不是照抄摘要常数：从正式原始 `plant.json/supply.json` 重新插值和计算，固定 GE1=1200、GE2=0、B1=785、B2=0、EC1=500、EC2=AC1=PV=0。48 段输入相同，检查额定范围、发电机kVA、电热冷平衡、塔能力、PCC容量、LT剩余能力、午夜状态及并联绕过检修。

| 项目 | 重算结果 |
|---|---:|
| LT热量 (kW，限220) | 201.000000000 |
| 发动机HT (kW) | 1290.000000000 |
| 建筑得热 (kW，需2000) | 2000.000000000 |
| 自然冷凝水 (°C) | 22.000000000 |
| EC1 COP | 6.500000000 |
| 有功进口 (kW) | 158.923076923 |
| 净无功 (kvar) | 55.579073785 |
| PCC (kVA，限1220) | 168.361449927 |
| 塔排热 (kW) | 576.923076923 |
| 塔能力 (kW) | 3500.000000000 |

14 项见证检查全部成立，覆盖48段；与 GPT Pro 记录一致。[lt/witness.json](lt/witness.json)。此结论仅证明描述中的抽象图和固定输入可行；本次不核实 NHS 工程真实性，也未求该图的全天最优成本。

## 不一致、口径差别与未验证范围

- 没有发现本次要求复现的关键结果与 GPT Pro 的通过/失败声明不一致。
- 原 `energy_mutants.py` 单独只有 42 个；43/44 包括 `check_v20.extras` 的候选新增变异。本次全部以原 eval/pytest 重验，未跳过补丁匹配断言。
- GPT Pro 没有自称运行本次去掉部件检修后的同一组任务副本；本次为新隔离证据，不能标成其原运行的逐字复现。C1/C2 原 h1–h4 在读入时退出，原日的新规则断言确实没有执行。
- C1 盲替身在隔离 h2 的成本与同口径 MILP 有约 £0.004264 正差，仍通过正式成本容差；没有声称盲替身也达到 oracle 的 £0.001 标准。负差额保留 v19 对辅助排热、PV及公共水温解释的原有宽验收边界。
- 初次自验收把全仓库已有缓存也列为失败，日志保留于 [self-validation.log](self-validation.log)。清点发现 `jobs/` 下10处缓存共50个文件，创建/修改时间均早于本次复核，见 [preexisting-cache-inventory.json](preexisting-cache-inventory.json)。按任务书不能动其他目录的约束保留；最终检查改为严格核实没有新缓存、这10处历史缓存时间未变。不能声称整个仓库从来没有缓存。
- 第3节只重跑25/200天，不重新认证完整200天统计；未运行其余两个fresh seed、C3/C5完整候选、NHS来源检索或正式模型试跑。任务书未要求这些。
- C4 的1672 kW上界沿用给定90/70°C运行温度口径；没有通过本次计算消除原审计已注明的温度解释问题。共享LT仍是抽象机制探针，不能据此晋级正式题目。


## 自验收

收尾运行 `"$P" "$O/final_validate.py"`，将验证记录写入 [validation.json](validation.json)，并重新保存 [git-status.log](git-status.log)。检查本目录覆盖1、各候选2a–2f、3、4；检查所有预期日志/JSON存在、最终各项的返回码符合预期，且首次抽样脚本失败记录已保留、变异数与匹配断言、冻结散列、隔离副本仅改指定status、100项抽样成绩、LT见证与原证据一致，以及 Git 只新增本目录。没有为了收尾改写已有文档或其他项目文件。

