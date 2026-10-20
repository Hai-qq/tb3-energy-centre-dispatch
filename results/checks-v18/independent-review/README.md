# v18 独立复核事实记录

复核对象：`v18-gptpro`，起始提交 `cefe1e3`；起始工作区干净。只修改 AC1 运行判定阈值及相邻注释，所有其他新增文件均在本目录。未 commit、push、切分支，未运行 Harbor、Docker；未检查本机网络设施或设置。

**结果：指定检查完成。** 标准答案、fresh、变异及 E/F 分类与 GPT Pro 一致；E1/E2 仍未达到。阈值对照符合任务书，仓库已从 `> 1e-9` 改为 `> 0.01` kW，B/C/E/F 复测结论及变异失败矩阵未变。v17 旧 README 的成本精度说法不成立。

## 运行方式与证据边界

外部工作目录 `D=/private/tmp/claude-501/-Users-haiy-qq-Desktop----klavis/a70e7eab-ed43-4fbc-8c31-1d0858956a32/scratchpad/codex-v18-verify`。venv、任务副本、生成输入、计划和逐次 CLI 原始输出均保留在 D；本目录仅存命令、pytest 日志/XML、摘要和复核脚本。

使用 `/opt/miniconda3/bin/python3.13 -m venv "$D/venv"`，再 `PIP_CACHE_DIR="$D/pip-cache" "$D/venv/bin/python" -m pip install numpy==2.3.4 scipy==1.17.0 pytest==9.1.1`，安装成功；没有使用备选解释器环境，没有安装全局依赖。实测 Python **3.13.5**、NumPy **2.3.4**、SciPy **1.17.0**、pytest **9.1.1**。详见 [runtime.json](runtime.json)、[pip-install.log](pip-install.log)。

所有仓库工具均设 `PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1`，并设 `TMPDIR="$D"`。以下 `python` 均指 `$D/venv/bin/python`；命令在仓库根执行。每项实际完整参数和退出码见相应 `.command.json` / 日志首行；pytest 探针命令见 [probes/results.json](probes/results.json)。

独立驱动 `review_driver.py eval <label> <app> <task>` 用 `runpy` 进入**未修改的** `tools/eval_energy.py` 主入口，只在 subprocess 返回时复制即将删除的计划、pytest stdout/stderr、JUnit 并计时；不改输入、测试函数、MILP 或结果。每个应用五天各跑两次，由原 pytest 收集 55 项。另在仓库中直接执行原 CLI 做改前/最终验收。GPT Pro 的 `check_v18.py` 和 `verify_v18_evidence.py` 已读作对照，未以其输出代替本次检查，也未执行它们。

初版任务副本与仓库所有文件的 SHA-256 一致；关闭推断、改阈值两个副本均只改 `tests/reference.py`。见 [task-copy-provenance.json](task-copy-provenance.json)。C 及 2d 各用原 `tools/energy_mutants.py` 按字典顺序 `names[shard::4]` 分为四组运行，四组覆盖恰好 41 个变异，退出码均为 0；最多四个工具进程并发。最终 C 按无参数的原命令一次跑完 41 个，退出 0。所有变异仍使用工具自带 20 秒执行截止及原 pytest。

## A 与数据重建

命令：`python "$D/review_driver.py" prepare`（内含逐文件 SHA-256、实际字节比较及 `python tools/build_energy_days.py`）。instruction/environment 的路径集合与全部 13 个文件均与 v8.1 一致；五天的 plant/supply 共 10 对字节比较均相同。重建退出 0，前后 days 全文件哈希一致，紧接着 `git status --porcelain` 为空，无需恢复文件。与 GPT Pro 一致。证据：[A.json](A.json)、[逐字节补充比较](A-byte-compare.log)、[rebuild.json](rebuild.json)、[rebuild.log](rebuild.log)。v17→v18 全部指定代码差异保存在 [v18-source.diff](v18-source.diff)。

## B：标准答案及独立成本复算

命令：`python tools/eval_energy.py tasks/energy-centre-dispatch/solution/app`；保留计划的同一入口重放为 `python "$D/review_driver.py" eval before/eval-oracle tasks/energy-centre-dispatch/solution/app tasks/energy-centre-dispatch`。成本命令：`python "$D/probes.py" costs before`；改后将 label / costs 参数改为 `after`。每次成本都重新调用对应 reference 的 `Day.least_cost()` 和 `Day.true_flows(plan)`，未复用 GPT Pro 的成本缓存。改前改后均 55/55，通过退出 0；各天绝对成本差均 < £0.001，与 GPT Pro 一致。

| 日 | MILP (£) | 标准答案−MILP (£) | 改前最长 CLI (s) | 改后最长 CLI (s) |
|---|---:|---:|---:|---:|
| visible | 6303.560319426553 | +0.000089763496 | 7.678222 | 0.820326 |
| h1 | 6426.647467103042 | +0.000276852054 | 0.698139 | 0.721981 |
| h2 | 8879.731991258708 | -0.000076112143 | 0.618205 | 0.666415 |
| h3 | 5375.538040469284 | -0.000009999140 | 0.777723 | 0.803082 |
| h4 | 7310.971840533033 | -0.000019991885 | 0.721666 | 0.951368 |

计时为本机实测墙钟时间，包含当时并行负载；不要求与 GPT Pro 的秒数完全一致。改前最大值高于其 6.010606 秒，仍远小于 150 秒上限。成本数值与其逐天声明一致。证据：[改前成本](before/costs.json)、[改后成本](after/costs.json)、[改前直接运行](before/direct-eval-oracle.log)、[最终直接运行](acceptance/eval-oracle.log)。

## fresh：三个种子，各 16 天

命令分别为 `python tools/fresh_days.py --days 16 --seed S --output "$D/fresh-S" tasks/energy-centre-dispatch/solution/app`，S=2026、2403、87123。三次均退出 0，各 16 天 / 176 项全部通过，共 48 天 / 528 项；每个生成日 CLI 跑两次，manifest 中输入哈希前后不变。改后按任务书未重跑 fresh。与 GPT Pro 一致。

| seed | 结果 | 证据 |
|---|---|---|
| 2026 | 16/16 天通过，退出 0 | [日志](fresh-2026.log)、[manifest](fresh-2026.manifest.json) |
| 2403 | 16/16 天通过，退出 0 | [日志](fresh-2403.log)、[manifest](fresh-2403.manifest.json) |
| 87123 | 16/16 天通过，退出 0 | [日志](fresh-87123.log)、[manifest](fresh-87123.manifest.json) |

## C、2d：全部变异与推断开关

命令：`ECD_TASK="$D/original" python tools/energy_mutants.py <分组变异名>`，关闭推断时换成 `ECD_TASK="$D/no-inference"`。副本唯一差异为 `ec_used = ec_min`。阈值修改后：`python tools/energy_mutants.py`（无分组、原入口）。三组均 41/41 被抓。每个变异在每种配置下的测试/日/执行错误、原始行和来源日志均见 [mutants-summary.json](mutants-summary.json)，改前/改后失败测试×日矩阵完全一致。

2d 是本次新增的开关隔离实验，GPT Pro 未提供该对照的自称结果。推断打开后，抓到它的测试或天数变少的变异：
**无。** 41 个变异的失败测试×日矩阵在推断打开/关闭时完全一致。

GPT Pro 声明的 41/41 及逐变异失败测试×日集合与独立结果一致。其 `plan_varies_between_runs` 历史记录额外有 `h1.rerun:timed out`，本次没有复现该额外超时，但五天的确定性测试仍均将其抓到。挂起与写出后非零退出两个变异均按原入口判失败，未将它们当成物理错误。

## E/F：三份强程序、六份原件

对下表每个 app 分别调用 `python tools/eval_energy.py <app>`（带原入口取证驱动）；v17 强程序基线设置 `ECD_TASK=archive/energy-centre-dispatch-v17`。完整命令见 `before/eval-*.command.json`、`after/eval-*.command.json`、`v17/eval-*.command.json`；完整异常和失败断言见各自 pytest.log / report.xml。

| 应用 | v18 改前通过项 | v18 改后通过项 | v17 基线 |
|---|---:|---:|---|
| oracle | 55/55 | 55/55 | 55/55 |
| patched-v17-claude | 55/55 | 55/55 | 55/55 |
| patched-v17-codex | 55/55 | 55/55 | 55/55 |
| strong-v16-claude | 55/55 | 55/55 | 55/55 |
| v17-run1-claude | 11/55 | 11/55 | 本项未要求 |
| v17-run1-codex | 11/55 | 11/55 | 本项未要求 |
| v17-run2-claude | 51/55 | 51/55 | 本项未要求 |
| v17-run2-codex | 51/55 | 51/55 | 本项未要求 |
| v17-run3-claude | 37/55 | 37/55 | 本项未要求 |
| v17-run3-codex | 11/55 | 11/55 | 本项未要求 |

三份强程序全过，E1/E2 未达到；六份原件全部失败，F 达到。与 GPT Pro 的逐日主要失败类型一致。下列列出每份原件**所有**失败测试与日期；无计划的日期使该日全部 11 项失败，具体执行错误保留在 JSON/XML 中。改后集合完全相同。

### v17-run1-claude

| 测试 | 失败日 |
|---|---|
| `test_connection_limits` | h1, h2, h3, h4 |
| `test_cooling_balance` | h1, h2, h3, h4 |
| `test_cooling_towers` | h1, h2, h3, h4 |
| `test_electricity_balance` | h1, h2, h3, h4 |
| `test_heat_balance` | h1, h2, h3, h4 |
| `test_least_cost` | h1, h2, h3, h4 |
| `test_plan_covers_the_day` | h1, h2, h3, h4 |
| `test_reported_gas_and_cost` | h1, h2, h3, h4 |
| `test_reported_import_export_and_grid_flags` | h1, h2, h3, h4 |
| `test_same_plan_every_time` | h1, h2, h3, h4 |
| `test_units_within_ratings_and_availability` | h1, h2, h3, h4 |

### v17-run1-codex

| 测试 | 失败日 |
|---|---|
| `test_connection_limits` | h1, h2, h3, h4 |
| `test_cooling_balance` | h1, h2, h3, h4 |
| `test_cooling_towers` | h1, h2, h3, h4 |
| `test_electricity_balance` | h1, h2, h3, h4 |
| `test_heat_balance` | h1, h2, h3, h4 |
| `test_least_cost` | h1, h2, h3, h4 |
| `test_plan_covers_the_day` | h1, h2, h3, h4 |
| `test_reported_gas_and_cost` | h1, h2, h3, h4 |
| `test_reported_import_export_and_grid_flags` | h1, h2, h3, h4 |
| `test_same_plan_every_time` | h1, h2, h3, h4 |
| `test_units_within_ratings_and_availability` | h1, h2, h3, h4 |

### v17-run2-claude

| 测试 | 失败日 |
|---|---|
| `test_units_within_ratings_and_availability` | h1, h2, h3, h4 |

### v17-run2-codex

| 测试 | 失败日 |
|---|---|
| `test_units_within_ratings_and_availability` | h1, h2, h3, h4 |

### v17-run3-claude

| 测试 | 失败日 |
|---|---|
| `test_connection_limits` | h1, h2, h3, h4 |
| `test_cooling_balance` | h3 |
| `test_cooling_towers` | h3 |
| `test_electricity_balance` | h3 |
| `test_heat_balance` | h3 |
| `test_least_cost` | h1, h3, h4 |
| `test_plan_covers_the_day` | h3 |
| `test_reported_gas_and_cost` | h3 |
| `test_reported_import_export_and_grid_flags` | h3 |
| `test_same_plan_every_time` | h3 |
| `test_units_within_ratings_and_availability` | h1, h2, h3 |

### v17-run3-codex

| 测试 | 失败日 |
|---|---|
| `test_connection_limits` | h1, h2, h3, h4 |
| `test_cooling_balance` | h1, h2, h3, h4 |
| `test_cooling_towers` | h1, h2, h3, h4 |
| `test_electricity_balance` | h1, h2, h3, h4 |
| `test_heat_balance` | h1, h2, h3, h4 |
| `test_least_cost` | h1, h2, h3, h4 |
| `test_plan_covers_the_day` | h1, h2, h3, h4 |
| `test_reported_gas_and_cost` | h1, h2, h3, h4 |
| `test_reported_import_export_and_grid_flags` | h1, h2, h3, h4 |
| `test_same_plan_every_time` | h1, h2, h3, h4 |
| `test_units_within_ratings_and_availability` | h1, h2, h3, h4 |

机器可读完整表：[evaluation-matrix.json](evaluation-matrix.json)。三份强程序的 app 分别为任务书指定的 v16 run2 Claude、v17 run2 Claude parts、v17 run2 Codex parts；六份原件均来自 `results/v17-trials/ecd17-run{1,2,3}-{claude,codex}/app`。

## v17 成本口径争议

命令：`ECD_TASK=archive/energy-centre-dispatch-v17 python tools/eval_energy.py archive/energy-centre-dispatch-v17/solution/app`（取证驱动），然后 `python "$D/probes.py" costs v17`。标准答案依然通过 55/55，但成本不等于严格 MILP：

| 日 | v17 标准答案−v17 MILP (£) |
|---|---:|
| visible | +0.000089763496 |
| h1 | -5.812224697746 |
| h2 | -0.000096366199 |
| h3 | +0.000047362757 |
| h4 | -14.878995913985 |

**GPT Pro 的 −£5.812 / −£14.879 正确；`results/checks-v17/README.md` 的“五天在 £0.001 内”不正确。** 额外控制实验只在 D 中复制 v17 solution，把塔负荷的 `a.rejected(1.0)` 改为 `a.rejected(1.0) + a.aux_per_kw`，其余不变，运行原评测入口并复算五天。h1/h4 的差额分别变为 +£0.000276852054 / −£0.000019991885，另三天不变；原计划若计入辅机热量，h1/h4 峰值分别超塔负荷 13.4144 / 13.6971 kW。这支持 AC 辅机排热口径差异的解释。没有修改归档或旧 README。证据：[costs.json](v17/costs.json)、[tower-convention.json](v17/tower-convention.json)、[严格口径原入口日志](v17/eval-strict-aux.log)。

## 2a–2c、3e–3f：构造例

命令：`python "$D/probes.py" probes`。均基于本次独立生成的标准答案计划或实际日子副本，所有修改仅存 D。a/b 保持制冷出力不变；c 使用本来无 EC 运行的时段，制冷平衡也不变。修改后按独立 reference 重写成本/气耗汇报并同步汇总，防止旧汇报数值混入目标电平衡对照。a/b/c 各自用原 pytest 运行对应日全部 11 项（包含汇报、制冷及费用测试）。

| 例 | 修改 | 实测 |
|---|---|---|
| 2a | h3 06:30：EC 359.1 kW；最冷耗电 53.397769517 kW，上限 92.076923077 kW；增加 5 kW 电源交换 | 11/11 通过；实际耗电被接受为 58.397769517 kW |
| 2b | 同时段低于最冷耗电 5 kW | 只有 `test_electricity_balance[h3]` 失败 |
| 2c | h1 00:00：EC1=EC2=0，AC1=523.5 kW；多进口 5 kW | 只有 `test_electricity_balance[h1]` 失败 |
| 3e | PV1 12:05–12:15 与 12:10–12:20 | 12:00 段预测 236.6 kW，pv_max=118.3 kW，等于预测×(1−15/30) |
| 3f | GE1 jacket water and exhaust 12:05–12:20 | Day 加载成功，无 KeyError；GE1 在 12:00 半小时不可用 |

2a–2c 的区间接受/拒绝、3e–3f 的修复结果均与 GPT Pro 的说明一致。2a 的单时段升温增加成本后仍在原 `test_least_cost` 容差内，因此费用测试也通过；这不表示取消费用判分。该例核对的是接受区间，不要求费用必然失败。证据：[完整构造与命令](probes/results.json)、[PV/HT 原始值](probes/reference-fixes.json)、各探针 XML/日志。

## 第 4 节：阈值对照及最终修改

选择 h3 06:30：自然母管 21°C，标准答案 EC1=359.1 kW、EC2=AC1=0。给 AC1 增加指定微小出力，同时等量减少 EC1，保持制冷负荷 359.1 kW，并按给定温度的 COP 计算电源交换。计划使用完整浮点精度写出。改前/改后副本分别运行原 `test_electricity_balance[h3]`：

| AC1 (kW) | 电制冷 COP 温度 | 改前 | 改后 | 改前/改后电残差 (kW) |
|---:|---:|---|---|---:|
| 0.4 | 21°C | 失败 | 失败 | -1.846325421790 / -1.846325421790 |
| 3e-08 | 21°C | 失败 | 通过 | -1.848384329271 / -0.000000000000 |
| 0.005 | 22°C | 通过 | 通过 | -0.000000000000 / 0.000000000000 |

三种结果均与任务书预期一致后才修改仓库 `tests/reference.py`。0.01 kW 注释说明高于求解器数值噪声、远小于任何有意义 AC 出力。随后对仓库重跑 B、C、E/F；55/55、41/41、三强全过与六原件全失败均不变。此项为任务书新增检查，GPT Pro 的报告未声明 0.01 阈值对照，不能称其“原先已通过”。

AC1 输出扫描：标准答案、三强、六原件共尝试 100 次 CLI；74 份成功输出计划（3,552 个半小时值）均无 AC1∈(0,0.5) kW。26 次未写计划的运行不纳入值统计，不声称其 AC1 为零。完整缺失清单见 [ac1-small-values.json](ac1-small-values.json)；改前改后的 74 份输出逐字节相同，见 [before-after-plan-identity.json](before-after-plan-identity.json)。

## 与既有声明的差异与限制

- v17 旧 README 的成本精度声明被实测推翻；GPT Pro 对其差额及原因的说明得到本次复现与控制实验支持。旧文件按授权边界未改。
- Python 微版本为 3.13.5，GPT Pro 声明为 3.13.16；指定解释器实际创建的 venv 如实记录，依赖版本完全匹配。独立运行时间与其报告不同，成本及分类结论一致。
- GPT Pro 的随机汇报变异历史记录有一次额外超时，本次没有该额外超时；41 个变异的失败测试×日集合仍一致。
- 本复核未重跑 GPT Pro 全量 fuzz、blind、外部模型试跑、TB3 CI、Harbor 或 Docker，不对这些声明追加独立认证；这不影响本任务列明的检查均已完成。
- E1/E2 仍未达到，不能把候选版称为能击败这三份强程序；本次没有另起方案或改变题意。

## 最终验收与可复现入口

最终直接运行 `python tools/eval_energy.py tasks/energy-centre-dispatch/solution/app` 退出 0；`python tools/energy_mutants.py` 无参数一次执行退出 0，41/41 被抓。后者即改后 C 的原始运行，不为收尾重复同一长检查。`git status --porcelain` 只列阈值文件和本目录；`git diff tasks/` 只有那一处阈值及相邻注释，days 哈希仍等于起始值，任务及新增结果目录中没有 `__pycache__`。证据：[final-validation.json](final-validation.json)、[task.diff](task.diff)、[git-status.txt](git-status.txt)、[最终变异日志](after/mutants-all.log)。

本目录脚本是 D 中实际驱动的副本；`review_driver.py` 支持 `ECD_REVIEW_WORK` 指定外部工作目录。重放应使用新的 D、干净的原版 checkout 和新输出目录；`prepare` 故意要求起始 Git 干净及结果目录不存在，避免覆盖已有证据。D 里的计划、输入、venv 均保留，没有删除用户文件。

按 neat-freak 仅收尾本次授权的 README/摘要，未修改受保护的项目 README、旧结果或工具。
