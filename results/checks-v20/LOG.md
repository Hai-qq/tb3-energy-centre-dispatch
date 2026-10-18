# v20 实验日志

基线：`v19` / `9db580817b1dc46ac6c500f8c472faaafce0a997`。工作分支：`v20-gptpro`。
开始实际工作：2026-10-18 **04:40:50 UTC**。所有下述项目均为本轮实际执行；没有运行正式 Opus/GPT、Harbor、Docker、28 项静态检查或 CI 轨迹审查。

最终候选资格：C1/C2/C4完成三道预检，但全部被盲修正确解决新要求；没有合格晋级候选。正式任务保持v19；完整负结果交付于本分支。各阶段的“进行中”记录保留其历史时态，后续完成情况见追加段落。

## 环境和执行边界

- Python 3.13.16、NumPy 2.3.4、SciPy 1.17.0、pytest 9.1.1，独立虚拟环境。
- 应用使用真实 `dispatch.py --data ... --output ...` 子进程；固定五日每应用每日至少两次，120 秒截止，记录计划、源码 SHA256、退出码和耗时。
- 原始交付物、archive、旧结果均只读。所有实验输入和失败记录位于本目录；任务目录在候选预检完成之前没有改动。
- 独立参考是整天 MILP；标准答案是枚举半小时 LP 加启停动态规划。共享原始数据，分别建立约束；没有用标准答案输出填充参考最优值。
- 本日志中的阶段顺序不是为每个子进程补造精确时刻。各命令和实际结果见对应 JSON / log。

## R0：冻结和重现 v19

`baseline/task/` 保存原任务逐字节快照，`baseline/task-sha256.json` 保存散列。
运行原 oracle、v16-run2-Claude 和 v19-run2-Claude 的固定五日矩阵；另经 `eval_energy.py` 真正执行 pytest。

结果：三份均通过 55/55。原 oracle 对 MILP 最大绝对成本差 £0.000276853。
证据：`baseline/matrix/`、`baseline/oracle.log`。

对旧记录和强工具的源码审计独立完成，见 `audit/STRONG_IMPLEMENTATIONS.md`。
审计纠正了两点：v16 原始 reward 曾因辅助排热口径被判 0，公平修复后才属于通过工具；两强对 LT 多出口的 all/any 规则并不相同。

## S1：五个候选的可见包与参数筛选

命令：`python tools/build_v20_candidates.py`。
各包只有 `instruction.md` 和原始可见 app，`VISIBLE_SHA256.json` 冻结实际读者输入。
完整可见差异见 `VISIBLE_CHANGES.md`、各候选 `visible.diff`。

| 候选 | 初始实验与修改 | 决策依据 |
|---|---|---|
| C1 购售价差 | night 7p/kWh、export 12p/kWh；只改原供应数据的三个数值 | `audit/arbitrage/` 的五个实跑机制隔离日；没有新增字段 |
| C2 共享燃气入口 | 初始 650 Sm³/h、39.5 MJ/Sm³；读者开始前改为 550、39.6 | `limit-probes/` 对 550/575/600 做五日独立 MILP；仅用可行性和容量是否起作用选值，不用盲修反馈 |
| C3 冷机馈线 | 三台冷机共用 400 kVA、固定 lagging PF 0.9；另探 315/350/375 | 小额定使 h1 无解，较大额定不绑定；保留全部结果 |
| C4 PHE 流量 | 初始 15 kg/s；读者开始前改为 20 kg/s；另探 24 | 15 使 h2 无解，不能用作困难；20 五日可行并真正限制 h2 |
| C5 并联 LT | GE1 增加第三散热器、明确并联独立隔离、每只 250 kW | 实测只击破 v16；v19 全过；精确 NHS 设备出处缺口未弥补 |

C2/C4 的初始可见散列和 `parameter-selection.json` 留存，未覆盖成“最初就是最终值”的记录。
容量扫描共 45 个 MILP，见 `limit-probes/results.json`；不是完整验收，出现无解的参数立即淘汰，未把无解交付物失败算作 E。
追加 C3 单 EC1 馈线 200/250/315/400 kVA 的 20 个 MILP，和 C5 两工具五日各两次回放，见 `remaining-screens/`。C3 仅为数值初筛，未完成三道预检。

## R1：C1 / C2 / C4 的独立模型和第一轮矩阵

命令：`python tools/build_v20_models.py c1 c2 c4`；随后各自执行 `tools/check_v20.py`。
每个模型都附至少一个新要求的合理错读变异。旧对手没有任何改动；空适配补丁和解释见 `adapters/`。

C1 第一份整天方向 MILP 与标准答案在 h4 不一致：默认 presolve 返回 £6964.624246，标准答案存在约 £6933.978453 的可行计划。
诊断关闭 presolve 后，整天 MILP 返回 **£6933.978477561302**；把 gap 改成 0 并未消除原差异。
未把这个错误参考值用作 B 的通过证据。初次失败矩阵、初始模型散列、诊断脚本和计划均保存于 `candidates/c1/matrix/`、`INITIAL_MODELS_SHA256.json`、`milp-diagnostic/`。
本轮采用 `presolve=False` 后重建模型，**完整重跑 B/C/E/F**，输出 `gates-r1/`。这项修订只影响参考求解设置，未改变读者的可见文件或物理约束。
诊断中曾试传 `threads=1`，该运行在当前 HiGHS 全局线程环境报 NotSet；它没有用于任何最终参考值，也没有当作不可行证据。

截至 05:16:52 UTC：

- 三个 oracle 均过固定五日；对同口径 MILP 最大绝对差分别为 C1 £0.000181120、C2/C4 £0.000276853，均小于 £0.001。
- 两历史通过工具在 C1、C2、C4 上均失败；七历史失败工具仍全部失败。具体每一天每项断言见各 `gates-r1/apps.json`。
- C1 的 3×16 fresh_days 全部通过，seed 为 2026、2403、87123；输入散列复核通过。
- 变异矩阵仍在跑，未提前称全部抓住。

复现模板（将 C 替换为 c1/c2/c4，使用新的 OUT 目录）：

```sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python tools/check_v20.py --candidate C --task results/checks-v20/candidates/C/task --out OUT
ECD_TASK="$PWD/results/checks-v20/candidates/c1/task" \
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python tools/fresh_days.py --days 16 --seed 2026 --output OUT \
results/checks-v20/candidates/c1/task/solution/app
```

`fresh_days.py` 的唯一行为扩展是允许 `ECD_TASK` 选择隔离任务，并从该任务读取固定 plant/supply；默认使用当前正式任务，避免为并行候选改写共享生成器。

## 独立预检与差分输入冻结

所有读者、盲修均以 `fork_turns=none` 启动。只授权读取相应候选可见包和其自身输出；不给机制名、隐藏输入、判分器、标准答案或前人意见。隔离是工具可审计的上下文与阅读范围隔离，并非操作系统级文件访问隔离；不得声称物理沙箱。

公平性读者的完整原始回答位于 `prechecks/reader_c*_*.md`。盲修获得完整实现目标、足够时间、NumPy/SciPy 和自行写独立检查/测试日的许可，冻结前不反馈外部评分。

C1 的至少 200 日差分先以 `--prepare-only` 冻结输入：仅由原始输入合法性和独立 MILP 可行性决定取舍，不查看对手或盲修输出来选日。所有被拒抽样也保留原数据、理由和散列。待盲修完成 FREEZE 后，才封存应用散列并实际回放全部日。

```sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python tools/fuzz_v20.py --task results/checks-v20/candidates/c1/task \
  --out results/checks-v20/candidates/c1/fuzz-200 --days 200 --seed 200019 --prepare-only
```

后续完成结果追加于下方，不覆盖以上失败和筛选记录。

### R1 完成更新（05:24:48 UTC 检查）

三个完整 B/C/E/F 矩阵均结束，退出码 0。C1 为 43/43 个变异抓住，C2/C4 各为 44/44；三套五日 oracle、两强回归、七旧失败回归均满足相应门槛。
新变异不是以执行错误代替规则检验：C1 的不分方向造成虚假交易/次优；C2 两种错读造成共享入口超量；C4 忽略流量造成实体超限，误限所有 HT 则造成真实成本增加。

`tools/explain_v20.py` 从原始 h2 计划复算容量峰值，并对两强 C1 做仅改报表的因果控制。两者都仅剩 least_cost 失败，设备出力逐字保持不变；结果见 `causal-details/`。
对旧强代码的独立方向修复诊断，两份均五日通过，见 `candidates/c1/causal-direction-fix/matrix.json`。这仍不是对手适配，也不是新模型试跑。

200 日输入冻结完成：277 次抽样，200 个接受、77 个拒绝；冬 53、春 66、夏 17、秋 64；21 个全部检修名称均出现，四个午夜发动机状态计数为 55/48/49/48。季节不等量是只按独立可行性取舍的结果，未按对手失败挑选。

为并行推进，历史对手与 oracle 的 200 日回放先开始；**盲修仍未读取或评测**。`fuzz_v20.py --extend-apps` 在新应用冻结后只追加它缺失的运行，先保存旧 manifest、完整旧 records 和旧 summary 的快照；不重跑或替换既有原始计划。每轮前后继续核对原始输入、模型和应用散列。

```sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python tools/fuzz_v20.py --task results/checks-v20/candidates/c1/task \
  --out results/checks-v20/candidates/c1/fuzz-200 --days 200 --seed 200019 \
  --resume --workers 3 \
  --app oracle=results/checks-v20/candidates/c1/task/solution/app \
  --app strong-v16=results/v16-trials/ecd16-run2-claude/app \
  --app strong-v19=results/v19-trials/ecd19-run2-claude/app
```

### 200 日第一阶段回放与根因控制完成

标准答案 200/200 通过，最大绝对成本差 £0.000489197；A16 为 117 通过 / 83 失败，83 次均有真实净结算成本失优；A19 为 0 通过 / 200 失败，200 次均同时申报两个方向并导致报告费用不实，其中 113 次还存在真实净结算成本失优。三份应用均成功执行，最长单日回放加核验分别约 5.684 / 4.557 / 3.429 秒。这项计时含子进程后的物理重算和断言，是 CLI 时间上界而非精确 CLI 耗时。原输入和源码的散列在回放后再次吻合。

`tools/explain_v20_fuzz.py` 在上述结果冻结后选择每个旧强工具真实成本损失最大的日。A16 的 d0229 多付 £57.586464，A19 的 d0217 多付 £57.642491。把两份旧强的诊断副本仅改成分进口/出口方向求解后，各自对两个日均通过全部检查。该控制每应用每日至少两次，保留全部计划；既有最差日结果没有覆盖。诊断副本在 d0229 相对整天 MILP 尚差 £0.002524 / £0.003397，低于原交付物的既定判分容差，但**不满足 oracle 专用的 £0.001 门槛**，因此没有冒充新的标准答案。

原始证据：`candidates/c1/fuzz-200/summary.json`、`candidates/c1/fuzz-causal-controls/results.json`。此时三个盲修仍未冻结，故此处仅记三份应用，不把未执行的第四份算入差分。

C2/C4 初始参数的文件后来按初始值重建，逐文件 SHA256 与早先保留的 `INITIAL_VISIBLE_SHA256.json` 完全一致。`INITIAL_RECONSTRUCTION.json` 标明重建而非原文件一直留存；当前读者所用可见包未变化。

### 固定五日真实 pytest 交叉核对（05:58:10 UTC 观察到完成）

对 C1/C2/C4 分别执行以下命令，三个进程均退出 0，输出 `all tests pass`。它们是固定五日的真实 pytest 流程，补充已有的逐断言开发矩阵；没有运行 Harbor、Docker 或正式 CI。

```sh
ECD_TASK="$PWD/results/checks-v20/candidates/C/task" ECD_RUN_TIMEOUT=120 \
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python tools/eval_energy.py results/checks-v20/candidates/C/task/solution/app
```

其中 C 分别为 c1/c2/c4，日志为各自 `oracle-pytest-r1.log`。与原脚本一致，pytest 此次临时计划在结束后删除；完整固定日原计划、两次执行日志和源码散列已由 `gates-r1/` 保留。没有虚称 pytest 临时输出也被留存。

## C1 冻结盲修与完整 200 日（06:06:47 UTC 已全部完成）

盲修明确声明完成后，先检查其 `FREEZE.json` 的声明摘要 `1220262247d9bf395943035000aedbf24f5b49a7d7faa77fc1cf9d3069a5e39d`，323 个文件全部匹配且无未声明文件。`prechecks/c1-freeze-before-eval.json` 的时钟读数在校验之后、外部评分之前取得。随后实际运行固定五日：

```sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python tools/check_v18.py --task results/checks-v20/candidates/c1/task \
  --out results/checks-v20/candidates/c1/blind-eval --apps blind \
  --app blind=results/checks-v20/blind/c1/app
```

可见日通过，费用 £5959.003279125；h1/h2/h3/h4 分别因 `EC1 condenser`、`GE2 jacket water and exhaust`、`AC1 absorber and condenser`、`GE1 intercooler` 不被识别而退出。它**正确处理新增购售电方向**：优化时显式枚举两方向，独立检查器与独立全天 MILP 同样检查，不是最后修改报表。故虽然整题失败，C1 仍按提示预检规则淘汰。冻结后没有反馈或修复。

在完全相同的 200 日上追加盲修回放：

```sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python tools/fuzz_v20.py --task results/checks-v20/candidates/c1/task \
  --out results/checks-v20/candidates/c1/fuzz-200 --days 200 --seed 200019 \
  --resume --extend-apps --workers 3 \
  --app oracle=results/checks-v20/candidates/c1/task/solution/app \
  --app strong-v16=results/v16-trials/ecd16-run2-claude/app \
  --app strong-v19=results/v19-trials/ecd19-run2-claude/app \
  --app blind=results/checks-v20/blind/c1/app
```

追加程序退出 0；四份共 800 次真实 CLI 回放已完成。盲修 91 通过 / 109 失败。逐日核对证明，109 个失败与输入包含它未识别的八种原有部件端口名称完全对应；91 个输出计划全部通过原判分和新方向要求。最长单日回放加核验 6.237893 秒，故 CLI 本身也低于两分钟。已生成计划相对参考成本界的有符号差为 −£20.577533 至 +£0.002639，不能把其最大绝对差当作失优，也不声称其全部达到 oracle 的 £0.001 要求。

`fuzz-200/before-extension-4/` 保存追加前的全部记录、manifest、summary 与既有原始文件摘要。追加结束后：277 次抽样全部输入、四份应用源码、原先 600 次回放的所有结果和原文件均逐项未变。盲修自身 323 个文件也再次全部匹配，见 `prechecks/c1-freeze-after-eval.json`。

根因与独立复核：`candidates/c1/fuzz-blind-classification.json`、`prechecks/BLIND_C1_REVIEW.md`。该审查者没有参与盲修实现，没有向其作者反馈结果。

## C4 冻结盲修外部预检完成

收到作者明确声明后，于 06:22:37 UTC 核验其 307 文件及声明的 manifest SHA256，随后运行与 C1 完全相同的 `check_v18.py --apps blind` 流程，将 candidate 与 app 路径换成 c4。输出 `candidates/c4/blind-eval/`。完成后再次核对全部冻结文件，见 `prechecks/c4-freeze-before-eval.json`、`c4-freeze-after-eval.json`。

可见日通过；四隐藏日只失败在旧部件检修可用性，全部新 PHE 流量检查通过。h2 有 27 个时段达到 20 kg/s 的一次侧流量上限，最大值 20.000000000000004 kg/s；不是新限制未绑定的偶然通过。生产、独立检查器、独立 MILP 均将上限施加于 `HT−AC驱动热`，没有错限全部 HT。最慢单次 CLI 2.310197 秒。

结论：C4 虽然整题失败，但做对了新要求，按提示预检淘汰；同时保留两位公平读者对固定 90/70°C 运行工况的限定。源码审查与原始物理峰值输出分别位于 `prechecks/BLIND_C4_REVIEW.md`、`candidates/c4/blind-new-rule.json`。隐藏成本不能当成节约，因为其运行违反旧检修条件。

作者保留的 `blind/c4/experiments/revisions/revision_history.json` 明示初轮自测汇总曾被后续自测覆盖；本交付不虚称这些中间汇总也完整留存。最终冻结后的应用、自检、测试数据和计划均未改动，未向作者反馈外部得分。

## C2 冻结盲修外部预检完成

06:33:05 UTC记录评分前核验时刻。作者声明 `FREEZE.json` SHA256为`866d197a59cd0ef7380deb3e0bfa74d3c720240971be406a756cd70f78e33724`；198个文件的摘要与字节数全部匹配。然后运行：

```sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python tools/check_v18.py --task results/checks-v20/candidates/c2/task \
  --out results/checks-v20/candidates/c2/blind-eval --apps blind \
  --app blind=results/checks-v20/blind/c2/app
```

visible全部通过，成本差−£1.2369×10⁻¹⁰；h1–h4都因原有具名热路部件不在已知名称集合而退出1。其新燃气断言未执行，不能记为隐藏四日新规则通过。

冻结源码与独立检查器/全天MILP已正确建模6050 gross kW共同入口，包含发动机net/gross转换、燃料曲线截距与锅炉用气。作者自建且已冻结的`gas_binding`日48时段全部绑定，锅炉确实参与；另有随机日12绑定时段。为独立核对这项关键证据，父任务又从原冻结输入执行两次真实CLI并运行全部外部断言：

```sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python tools/audit_v20_blind_gas.py \
  --out results/checks-v20/candidates/c2/frozen-binding-audit-r1
```

结果：全部通过，成本差+£5.3478×10⁻¹⁰；原冻结计划的最大标准体积流量550.0000000000202 Sm³/h，48绑定、0超量。此为额外诊断，不是隐藏日通过，也没有改输入、改盲修或反馈作者。

根程序首次附加诊断在真实回放已经PASS后，因汇总阶段把`maximum_standard_m3_per_hour`误写成长字段名发生KeyError；初次输出与错误保留于`frozen-binding-audit/`及`.log`。只修正父任务诊断脚本的字段名并增加新输出目录参数，再完整重跑到`-r1`。未改候选模型或盲修；没有把这次汇总脚本错误归因于对手。

06:38:19 UTC记录的评分后校验再次证明198文件完全未变。独立审查详见`prechecks/BLIND_C2_REVIEW.md`。C2与C1/C4一样：新要求被完整盲修解决，提示预检不通过，淘汰。

## 补齐 C2 / C4 的三个 seed 各16天

在冻结盲修全部完成后，对C2与C4分别使用seed2026、2403、87123，各自生成并通过16个随机可行日，共新增96个完整pytest日期。六次进程全部退出0，`0/16 days failed`；06:42:54 UTC时已全部观察到完成。固定候选模型、读者可见包及盲修均未变化。

```sh
ECD_TASK="$PWD/results/checks-v20/candidates/C/task" ECD_RUN_TIMEOUT=120 \
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python tools/fresh_days.py --days 16 --seed SEED \
  --output results/checks-v20/candidates/C/fresh-SEED \
  results/checks-v20/candidates/C/task/solution/app
```

C分别为c2/c4，SEED为上述三个数。各自日志与manifest完整保存，所有输入散列在评测后匹配。加上C1早先48日，三个候选各自满足3×16 fresh数值门槛；仍不能挽救失败的提示预检。原fresh工具删除临时执行计划、拒绝抽样的原始文件的行为没有改动；生成规范和拒绝理由保留于manifest，不能把这点与200日工具完整保留277份原始输入混同。

## 合并结论与发布前检查

`prechecks/DECISIONS.json`与`BLIND_RESULTS.md`固定三道预检的去留语义。`tools/report_v20.py`从原始JSON生成矩阵，并逐候选检查九次fresh的完成/通过状态。概率章节给出有明确假设的敏感性计算，未把一次替身或200次固定代码回放换算为目标模型独立样本。

正式任务仍是v19；没有因为需要交付v20而绕过用户的“盲修解决新要求就淘汰”门槛。本轮交付候选实验及反证，不声称达成稳定3+3全挂。对进一步共享LT拓扑的有限审计另存研究说明，不能据此断言整个题目结构到顶。

发布前的普通网络环境首次`git ls-remote`连接browser-proxy失败；经过自动批准的网络权限后同一只读命令成功，远端当时尚无`v20-gptpro`。没有查看或输出凭据。

06:46:06 UTC所记录阶段运行`tools/verify_v20_evidence.py`，输出`FINAL_INTEGRITY.json`：正式任务与基线快照逐字节相同，六读者、828个盲修文件、三候选评测模型与全部历史应用未变；九组fresh共144日的输入散列与全部通过结果一致。

06:47:14 UTC观察到父任务已亲自重放追加LT内存图探针。命令完整保留于`research/ADDITIONAL_DESIGN_AUDIT.md`第6节；执行原始输出和结构化结果为`shared-lt-root-replay.log/json`。A16有4段超连接，A19在仅剩220kW的4段各排252.194615kW；恒定可行证人LT201kW、PCC168.361450kVA。它尚缺精确NHS拓扑出处与三道预检，未建成候选；没有把内存函数调用包装成完整CLI验收。

06:52:01 UTC已收到并阅读最终独立一致性审查`prechecks/FINAL_REVIEW.md`。审查复核131/131变异、九份fresh通过manifest/144日/720个输入文件摘要、216项历史应用源码摘要、828冻结文件及三个manifest声明，以及C1的800条差分应用/日记录；未发现实质不一致，明确不建议扩大数值测试。候选模型冻结后仅新增诊断、报告与发布检查，没有改变被评测的可见包或参考约束。

从04:40:50 UTC到06:52:01 UTC，实际实验、独立盲修与审查阶段已持续**2小时11分11秒**；后续发布耗时另行追加。时长不能替代候选资格。

暂存范围检查：首次暂存11008文件，其中10995个在`results/checks-v20/`、13个在`tools/`；正式任务无变更。工具代码的`git diff --cached --check -- tools`退出0。随后加入最终审查及发布说明时将再次确认范围；未对冻结原始材料进行格式整理。
