# v19 build 验收

结果：A′、B、C、F 全部通过；四份指定对照均已实际运行。未运行 Harbor、Docker。
分支 `v19`，基线 `f02497a`；未提交、推送、切分支或修改历史。

## 命令与产物

所有仓库工具均使用以下 Python 和三个环境变量：

```sh
PY=/private/tmp/claude-501/-Users-haiy-qq-Desktop----klavis/a70e7eab-ed43-4fbc-8c31-1d0858956a32/scratchpad/codex-v18-verify/venv/bin/python
D=/private/tmp/claude-501/-Users-haiy-qq-Desktop----klavis/a70e7eab-ed43-4fbc-8c31-1d0858956a32/scratchpad/codex-v19-build
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
"$PY" results/checks-v19/build/verify.py snapshot
"$PY" tools/build_energy_days.py
"$PY" results/checks-v19/build/verify.py static
"$PY" results/checks-v19/build/verify.py canonical
"$PY" results/checks-v19/build/verify.py matrix
"$PY" results/checks-v19/build/verify.py deliveries
"$PY" results/checks-v19/build/verify.py mutants
for S in 2026 2403 87123; do
  "$PY" tools/fresh_days.py --days 16 --seed "$S" --output "$D/fresh-$S" tasks/energy-centre-dispatch/solution/app
done
"$PY" results/checks-v19/build/verify.py fresh-summary
PLANS_DIR="$D/matrix/oracle" "$PY" -m pytest -q -p no:cacheprovider --junitxml="$D/oracle-junit.xml" tasks/energy-centre-dispatch/tests/test_plans.py
"$PY" results/checks-v19/build/report.py
git diff --check
git status --porcelain --untracked-files=all
git diff -- tasks/energy-centre-dispatch/instruction.md tasks/energy-centre-dispatch/environment/planner tasks/energy-centre-dispatch/environment/dispatch.py
"$PY" results/checks-v19/build/verify.py integrity
```

`canonical` 与 `mutants` 分别调用未改动的原 CLI；实际子命令、退出码、耗时及环境变量见对应 `*.command.json`。
`matrix` 用现有 `check_v18.check_app` 保存每份计划、两次执行日志、物理重算及逐项断言；`deliveries` 再经原 `eval_energy.evaluate` 对全部旧交付物跑完整 pytest。
fresh 的完整命令见三个 `fresh-*.command.json`；上面列出等价循环。输出目录须为新目录，复现时另选 `<D>`，或先保留原证据再调整 `verify.py` 的 `LARGE`。
完整计划、随机日输入、原始 JUnit、v18 基线快照在 `<D>`；仓库保留摘要、manifest、日志和可复现脚本。

## A′ 与数据生成

通过：除 `environment/data/plant.json` 外，可见文件与 v8.1 逐字节相同；文件集合也相同。
plant 唯一差异是两处名称，见 [plant-v8.1.diff](plant-v8.1.diff)。五天 plant 完全相同，visible 与 environment/data 逐字节相同。
各天相对 `f02497a` 的输入仅做任务书要求的名称替换，时间和其他数据未变。证据：[A-prime.json](A-prime.json)、[baseline-snapshot.json](baseline-snapshot.json)。

## B 标准答案和参考模型

原 CLI 退出 0；实际 pytest **55/55**，见 [canonical-eval.log](canonical-eval.log)、[oracle-pytest.log](oracle-pytest.log)。

| Day | MILP £ | true_flows £ | 差额 £ |
|---|---:|---:|---:|
| visible | 6303.560319426553 | 6303.560409190050 | +0.000089763496 |
| h1 | 6426.647467103042 | 6426.647743955096 | +0.000276852054 |
| h2 | 8879.731991258708 | 8879.731915146565 | -0.000076112143 |
| h3 | 5375.538040469284 | 5375.538030470144 | -0.000009999140 |
| h4 | 7310.971840533033 | 7310.971820541148 | -0.000019991885 |

五天最大绝对差额均 < £0.001，见 [oracle-costs.json](oracle-costs.json)。
v18/v19 五天所有原有设备可用性、其他模型属性、MILP 完整结果、标准答案完整计划、true_flows 全部相同；新增接受的热路名称仅 `hospital buildings`。
证据：[v18-invariance.json](v18-invariance.json)。定向探针还把热路键改名、出口改成两个无机组前缀的任意名字，分别检修两个出口；参考和答案都只停 GE1，见 [topology-probe.json](topology-probe.json)。

| Seed | 接受/抽取 | radiator 1 检修数 | radiator 2 检修数 | 结果 |
|---|---:|---:|---:|---|
| 2026 | 16/34 | 3 | 2 | 16/16 通过，原 CLI 退出 0 |
| 2403 | 16/43 | 2 | 2 | 16/16 通过，原 CLI 退出 0 |
| 87123 | 16/30 | 0 | 4 | 16/16 通过，原 CLI 退出 0 |

证据：[fresh-summary.json](fresh-summary.json)、三个 `fresh-*.log`、`fresh-*.manifest.json` 与 `fresh-*.command.json`。
汇总脚本最初额外断言每个 seed 都覆盖两个名字，在 87123 上失败（两种检修数为 0/4）；当时三条 fresh 原命令均已退出 0。已将汇总断言改为三组总体覆盖，不改采样、不重新抽取或重跑；原失败保留于 `fresh-runner.log`，最终汇总退出 0，见 `fresh-summary-runner.log`。

## C 变异

**42/42 被抓，原 CLI 退出 0**，包含原 41 个和 `parts_by_name_prefix`。
新增变异只凭机组名前缀归属部件，实际在 **h2、h3、h4 的 `test_units_within_ratings_and_availability`** 失败。
全部变异各自失败的测试和日期列于 [mutants.md](mutants.md)；结构化结果见 [mutants.json](mutants.json)，原始运行见 [canonical-mutants.log](canonical-mutants.log)、[canonical-mutants.command.json](canonical-mutants.command.json)。
执行错误、超时变异按原工具规则判无有效计划；未把它们描述成物理约束失败。

## F 六份 v18 交付物

全部失败；下表为原 pytest 结果。`availability` 指 `test_units_within_ratings_and_availability`。

| 交付物 | v19 通过项 | 失败情况 |
|---|---:|---|
| ecd18-run1-claude | 51/55 | availability: h1/h2/h4；least_cost: h3，实际成本超过 MILP £1231.611769 |
| ecd18-run1-codex | 51/55 | availability: h1/h2/h3/h4 |
| ecd18-run2-claude | 0/55 | 五天两次均 exit 1；硬编码要求 `GE1 LT radiator`，实际得到 `LT radiator 1`，全部 55 项失败 |
| ecd18-run2-codex | 11/55 | 四个隐藏日两次均 exit 1：h1/h2/h4 在 00:00、h3 在 13:30 报 `no feasible loading`，隐藏日全部测试失败 |
| ecd18-run3-claude | 51/55 | availability: h1/h2/h3/h4 |
| ecd18-run3-codex | 51/55 | availability: h1/h2/h3/h4 |

原 CLI 的逐测试/逐日失败和错误：[canonical-deliveries.json](canonical-deliveries.json)、[deliveries-runner.log](deliveries-runner.log)。
计划逐时段检修冲突：[availability-violations.json](availability-violations.json)。完整回溯、计划、两次运行耗时见 [matrix.json](matrix.json) 和 `<D>/matrix/`。

## 四份对照（仅记录）

| 交付物 | v19 结果 | 原因 |
|---|---|---|
| ecd16-run2-claude | 55/55 | 从热路处理散热器及其可用性，未出现失败 |
| ecd17-run2-claude-parts | 55/55 | 从热路处理散热器及其可用性，未出现失败 |
| ecd17-run2-codex-parts | 55/55 | 从热路处理散热器及其可用性，未出现失败 |
| ecd18-run2-claude | 0/55 | 在建模前强制校验旧散热器名，五天均报 ValueError；这次失败发生在名称校验阶段 |

三个较早的强对照仍全部通过；不能把改名说成已击败这三份程序。证据同 `canonical-deliveries.json`、`matrix.json` 及归档源码。

## 与 v18 不一致的结果

- 可见 plant 的两个名称改变，因此 A 改为任务书定义的 A′；其余可见文件保持相同。
- C 从 41/41 增至 42/42；原 41 个的失败测试/日期集合变化见下项。
- 原变异失败集合变化：`{}`。对照来源为已有 `results/checks-v18/final-mutants.log`，未在本轮重跑旧变异。
- 六份 v18 交付物的通过数变化：`{"ecd18-run2-claude": {"v18": 53, "v19": 0}}`；其余五份通过数与已有 v18 CTRF 记录一致。
- 三个较早的强对照仍为 55/55，与已有 `results/checks-v18/canonical_eval.json` 一致。
- B 五天成本和参考/答案计划未变。fresh 接受的抽样编号和规格（名称归一后）与 v18 完全相同；MILP 成本最大浮点差见 `v18-comparison.json`，均 < £1e-8，48 天通过结论相同。
- v18 旧日志的执行超时等原始错误文本未要求一致，也未当成本轮 v18 重跑结果。

## 修改范围与遗留

仅修改生成器、参考模型、标准答案、变异和 fresh 工具、生成数据及本目录；`test_plans.py` 未改。
参考和标准答案均由包含 `<engine> intercooler` 的热路 `to` 列表推出散热器依赖，不硬编码新名字。其他中冷器、HT 源、冷凝器和 AC1 部件处理保持原样。
未运行 Harbor/Docker；按任务书留给 Claude。未删除用户文件，未安装依赖，未更改全局或网络设置。
`tools/`、当前 task 和本验收目录没有 `__pycache__`。历史 `jobs/` 中已有 45 个 pyc，mtime 均早于本次 v18 快照；遵守不删用户文件的限制予以保留，见 `existing-caches.json`，不能宣称整个仓库原本没有缓存。
验收汇总见 [gates.json](gates.json)；最终 Git 范围、禁止修改项和无缓存检查见 `final-integrity.json`、`final-checks.log`。
