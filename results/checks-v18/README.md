# v18：公平修复与对手压力测试候选，E 未达标

**这个分支不能被称为“稳定六场全挂”的成功 v18。** E1 与 E2 没有达到：
最强 v16 Claude、仅补部件检修的两份 v17 第二场程序，在最终 v18 上仍各
通过 55/55 项。F 达到：原 v17 六份交付物在 v18 上全部失败。新增隐藏数据
只扩展了已有机制的覆盖；没有把歧义、误判、数值容差或超时当作 E 成功。

实际开发以 `hardening-v9-v12` 的 `12a1116` 为基线，工作分支为
`v18-gptpro`。所有 task 变更只有一个正式修订 r1。运行环境为 Python
3.13.16、NumPy 2.3.4、SciPy 1.17.0、pytest 9.1.1。未运行新模型订阅
试跑、Harbor、Docker、TB3 轨迹审查或远端 CI；本报告的通过/失败都是实际
执行保存程序、冻结替身、参考模型和变异程序得到的。

## 验收状态

| 判据 | 实测状态 | 主要证据 |
|---|---|---|
| A 可见文件不变 | 13 个文件与 v8.1 逐字节一致；固定 plant/supply 不变 | `evidence-verification/report.json` |
| B 标准答案 | 五天 55/55；最大绝对成本差 £0.000276853；三种 seed 各 16 天全过 | `final-matrix/oracle/result.json`、`final-fresh-verified/` |
| C 变异 | **41/41 被抓，退出 0**；原 39 + 新 2 个均使用原评测入口运行 | `final-mutants.log` |
| D 新要求公平性 | 仅加入字面拓扑部件覆盖；原文与针对性正反例已审查；有歧义的候选未加入 | `fairness/FAIRNESS.md`、`fairness/FINAL_REVIEW.md` |
| E1 最强 v16 失败 | **未达到，5 天全过，55/55** | `canonical_eval.json` |
| E2 补丁两份 v17 失败 | **未达到，两份各 5 天全过，55/55**；补丁版 v17 基线亦各 55/55 | `opponents/v17-baseline.json`、`canonical_eval.json` |
| E3 独立替身 | 完成；v17/v18 都是可见过、4 隐藏日部件检修失败 | `blind/`、`baseline-blind/`、`final-matrix/blind/` |
| F 原六份仍失败 | **完成，6/6 失败** | `final-matrix/matrix.json` |

`tools/check_v18.py --gate-v18` 实际退出 **1**，因为 E1/E2 为 false。
这是测试揭示目标未达；不是基础运行失败，也没有将它改成成功退出。
`RELEASE_STATUS.json` 明确给出 `promotable_as_stable_six_failures: false`。

## 第一阶段结论及搜索强度

[ANALYSIS.md](ANALYSIS.md) 逐一回答五个问题；
[LOG.md](LOG.md) 记录实际命令、修改时点、第一次 fresh 异常及最终结果。

独立公平审计发现并验证了旧参考的部件名称漏项、PV 重叠扣时、AC 小正出力
母管模式边界、可行暖母管计划被拒等问题。另发现旧标准答案与严格 MILP
相差 £5.81/£14.88，原因是已有两种 AC 辅机排热口径，而不是整数优化。
修复这些问题有价值，但不能作为降低模型通过率的证据。

差分测试共 **480 次尝试、479 个有效输入、375 个有效且有解的日子**。
其中 **317 天使用未修改的归档 v17 参考模型**；58 天显式扩展其遗漏的
两个 HT 源部件名。三份强程序共 1,125 次可行日运行，10,125 次独立物理/
汇报检查，**零有效失败**。130 个不同的可行日又与整天 MILP 比成本，全过。
104 个独立 MILP 无解组合与一个英国换钟日都排除，没有拿来凑失败。

| 可行样本 | 冬 | 春 | 夏 | 秋 | 总数 |
|---|---:|---:|---:|---:|---:|
| 物理与汇报检查 | 98 | 109 | 57 | 111 | 375 |
| 去重 MILP 成本检查 | 42 | 33 | 23 | 32 | 130 |

所有 21 个设备/部件名及四种午夜机组状态均覆盖；检修覆盖单段、多段、重叠、
相接、1–240 分钟及半小时/电价边界。完整生成规格、代码、根因分类、运行
时间和证据局限见 [fuzz/README.md](fuzz/README.md)。

v17 新一次单场通过率不能从固定程序回放直接推断。结合历史试跑和本次补丁
验证，主观规划中心取 Opus 20%、GPT 10%（约 10–30%、3–15% 的定性范围，
非置信区间），对应独立假设下 3+3 全挂仅 37.3248%。v18 没有证据支持把
这些概率下调。统计及样本选择限定详见 [fairness/PASS_RATE.md](fairness/PASS_RATE.md)。

## 正式写入的变化

### 1. h2：HT 源部件检修和更平滑的负无功检验

日期仍为 2026-01-14。新增 `GE2 jacket water and exhaust` 检修
18:20–18:40，因此 GE2 在 18:00、18:30 两个恒定出力半小时必须停机。
可见 `heat_circuits.engine_ht.from` 原文列出这一组件；它包含发动机必须的
jacket water，不能将整个命名组件的检修解释为仅绕过排烟换热。

可见原工具还明说输出 `held for the whole half-hour`。因此将 20 分钟检修
折算为部分额定容量也不合法。新增变异只忽略 HT 源组件依赖，实际输出：

```text
ht_source_outage_ignored h2: FAIL delta=-259.3857246204316 test_units_within_ratings_and_availability
```

替换原 h2 单行 2350 kW / 50 kvar 极端覆盖点，采用 0–1 时 2380 kW、
2 时 1750 kW、3 时 1300 kW 的需求控制点和全日 Q/P=0.10；取消单行
覆盖。实际生成的 00:00/00:30 分别为 2362.8/2357.6 kW、242.9/230.6
kvar；GE2 凌晨检修到 03:00，GE1 LT radiator 深夜检修止于 23:00。
这是可行合成曲线，并非医院实测负荷。

净无功可因固定 PF、过励磁的发电机而成为负值，仍须用 `sqrt(P²+Q²)` 检查
1220 kVA 接入容量。只限制正 Q 的旧变异，在上述两段超限 9.373251、
8.232199 kVA，实际输出：

```text
kva_positive_reactive_only h2: FAIL delta=-3.57524917291812 test_connection_limits
```

三份强程序在 h2 **全部通过**。部件名称和无功符号均为它们已经正确处理的
旧机制，新增数据不能估出一个新的模型漏掉概率。对于这三个固定程序，
本次漏掉频率是 0/3；对新的 Opus/GPT 运行没有直接测量。

### 2. h3：AC1 发生器短检修

日期仍为 2026-04-20。新增 `AC1 generator` 12:40–12:50，令 AC1 在
12:30 这一整段停机。可见 `heat_circuits.engine_ht.to` 字面列出
`AC1 generator`。这里的 generator 是吸收制冷热力循环的发生器，失去它
不能完成该循环；不是一个可绕过的额外发电机。不存在只认冷凝器检修而
忽略发生器检修的合理物理读法。

```text
ac_generator_outage_ignored h3: FAIL delta=-30.346996204940297 test_units_within_ratings_and_availability
```

三份强程序在 h3 **全部通过**。冻结替身及原第二场两份在 h1–h4 都有
`test_units_within_ratings_and_availability` 失败，但不能将它们旧有失败
全部归因于新增发生器事件。该事件扩大已有部件依赖覆盖，不是新推理路径。
新的 Opus/GPT 对此的漏掉概率未测；固定三个强程序为 0/3。

### 3. h4：PV 重叠检修公平性回归

2026-07-29，保留原 PV1 16:20–18:40，增加嵌套的 16:25–17:10。
两个检修记录必须按时间并集处理，不能把同一分钟扣两遍。16:00 半小时
中不可用时间为 10 分钟，185.1 kW 预测允许平均最多 123.4 kW；全段停用
这一已接受口径仍允许。因此没有新要求必须使用按分钟平均，亦没有要求
强程序改动。八种 PV 区间关系的算例实际通过。

这属于参考修复的针对性数据，不作为新 E 陷阱。三个强程序全部通过；
没有据此推断任何新模型漏掉概率。

## 完整结果矩阵

表中“执行失败”保留原 stderr，不能读成另一次独立的随机模型失败。

| 交付物 | 可见 | h1 | h2 | h3 | h4 |
|---|---|---|---|---|---|
| oracle | 过 | 过 | 过 | 过 | 过 |
| v16 run2 Claude | 过 | 过 | 过 | 过 | 过 |
| v17 run2 Claude + 部件补丁 | 过 | 过 | 过 | 过 | 过 |
| v17 run2 Codex + 部件补丁 | 过 | 过 | 过 | 过 | 过 |
| 冻结独立替身 | 过 | 可用性 | 可用性 | 可用性 | 可用性 |
| v17 run1 Claude | 过 | 执行失败 | 执行失败 | 执行失败 | 执行失败 |
| v17 run2 Claude 原件 | 过 | 可用性 | 可用性 | 可用性 | 可用性 |
| v17 run3 Claude | 过 | 可用性/接入/费用 | 可用性/接入 | 执行失败 | 接入/费用 |
| v17 run1 Codex | 过 | 执行失败 | 执行失败 | 执行失败 | 执行失败 |
| v17 run2 Codex 原件 | 过 | 可用性 | 可用性 | 可用性 | 可用性 |
| v17 run3 Codex | 过 | 执行失败 | 执行失败 | 执行失败 | 执行失败 |

原 pytest 入口另外执行 oracle 与三份强程序，各 **55/55**，防止开发矩阵
复用 MILP 结果或直接调用测试函数掩盖入口问题。最小补丁及其 v17 基线
位于 [opponents/](opponents/)。冻结替身源文件的 SHA-256 摘要保持
`89b4cbfad49a251e6a1d321cdae598264f6c6ff58beaf520015d0162a3e7d917`；
冻结前只得到可见信息，冻结后没有根据隐藏反馈修代码。此处是信息隔离，
不是操作系统级的文件访问隔离。

### B 的绝对成本复算

| 日 | 严格整天 MILP (£) | oracle−MILP (£) |
|---|---:|---:|
| visible | 6303.560319426553 | +0.000089763496 |
| h1 | 6426.647467103042 | +0.000276852054 |
| h2 | 8879.731991258708 | −0.000076112143 |
| h3 | 5375.538040469284 | −0.000009999140 |
| h4 | 7310.971840533033 | −0.000019991885 |

五天每一天执行两遍，所有计划确定，最大单次 6.010606 秒。最终三组 fresh
各 16 天全过；追加按保存 specs 重生并运行全部 48 天，最大单次 6.195931
秒、最大绝对成本差 £0.000456373814，使用明确的 120 秒 CLI 截止。

原严格 MILP 对 AC 辅机热/PV 部分时段仍使用已声明的保守口径，因而不应
称为所有合理物理读法并集上的精确最优。新增暖母管接受区间使用一个共同
温度的可行压缩机耗电范围，不允许无 EC 的虚构负载；11 个正反例均通过。
独立连续母管 MILP 在 v17 五天及 v18 五天与该严格基准的差额均为 0。

## 试过但未加入的候选

**任意经济性升温母管：** 三个低谷电力探针已经运行。550 kW 的案例中，
Codex 采用 24.259259°C，全天 £6014.361415，而仅枚举冷温策略的 MILP
为 £6034.446099。按真实共同温度重建后计划九项物理检查通过。两份 Claude
遗漏这种控制方式，但 Codex 已经正确；固定数据又没有唯一声明任意温度
控制的可达范围。因此接受这种物理解，不把它强加为新的必做优化任务。

**高温 LT radiator：** 对约 42°C 峰值的同一日（控制点 42°C，实际最高
41.9°C），额外加 ≥40°C 停机规则可令
三份强程序各错 7 个半小时，附加规则的 MILP 仍有解（£4261.517430）；
≥35°C 版本各错 17 段（£5528.366710）。但 radiator 的预冷方式和 40/35°C
是否硬上限均未唯一规定，不能采用。原输入、三份输出、独立可行见证及制造商
一手资料在 `fuzz/radiator-probe/` 和 `fairness/REJECTED_RADIATOR.md`。

**靠无解、数值差或超时：** 104 个无解随机组合、负无功第一轮 12 个无解
候选以及强程序约 £0.02 的数值差均排除。没有刻意卡两分钟限制，没有将
生成器的非法换钟日或未知数据格式设成隐藏陷阱。

**CSV 行序：** 将同一个可见日的 48 行需求及 96 行天气记录同时倒序，
保持时间戳、原行字节与全部数值不变，三份强程序会主动排序/按时刻连接。
实际各 9/9 物理汇报检查、MILP 成本检查通过。这项未进入原 480 次 fuzz。
当前参考自身的 demand 行序依赖可使隔离状态例少计一次 £38 启动，因此
不能直接拿原参考的顺序误判作 E。环境清理后的新重跑记录与边界见
[order-probe/README.md](order-probe/README.md) 和该目录 `FAIRNESS.md`。

## 复现命令

以下 `python` 指上述精确版本。每次重跑使用新的输出目录；已有 evidence
目录不要覆盖。设好 `PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1
OMP_NUM_THREADS=1`。

```sh
python tools/build_energy_days.py
python tools/check_v18.py --out results/checks-v18/replay-matrix --gate-v18
python tools/energy_mutants.py

python tools/fresh_days.py --days 16 --seed 2026 \
  --output results/checks-v18/replay-fresh-2026 tasks/energy-centre-dispatch/solution/app
python tools/fresh_days.py --days 16 --seed 2403 \
  --output results/checks-v18/replay-fresh-2403 tasks/energy-centre-dispatch/solution/app
python tools/fresh_days.py --days 16 --seed 87123 \
  --output results/checks-v18/replay-fresh-87123 tasks/energy-centre-dispatch/solution/app

python tools/verify_v18_evidence.py --out results/checks-v18/replay-evidence
python results/checks-v18/fairness/acceptance_regressions.py --require-fixed --label replay
```

原 pytest 入口复核的实际脚本是 `canonical_eval.py`；模糊测试与各候选重放
命令见各自 README 和 LOG。矩阵返回 1 是预计结果，因为三个强对手仍通过。

## 需要后续决定的事

本次没有证明固定可见规范下不存在任何可能反例；有限搜索不支持这种全称
结论。它已经提供 317 个未扩展参考的可行日、完整强程序建模审计和多条失败
候选，说明继续堆部件名/日期/检修组合缺乏有力成功依据。

若要继续追求更低的真实单场通过率，需要决定是否解除可见文件冻结。最小
的可复核实验是先写清母管控制范围，再复用现有暖水见证；它可验证两份
Claude 的不足，但已知不能击败 Codex。加入新的物理动态约束必须声明真实
设备与参数并重新试跑；新提示也可能提高模型对旧机制的注意力，尚未验证。
不能承诺任何这种替代方案将稳定 3+3 全挂。

第一次 fresh 的两个输入路径异常保留全部原记录；最终运行用唯一 draw
目录、输入哈希和 specs 精确重建闭合证据。其底层文件系统原因尚未查明，
详见 `fairness/FRESH_HARNESS_DIAGNOSIS.md`。本次没有用改 oracle 隐去异常。

正式 3+3 模型试跑、轨迹审查与 TB3 实现审阅仍需本地 Harbor/Docker 执行。
本分支应作为可审查候选和研究结论，不应以 E 已达标提交最终题库。

发布期间发生环境清理，主版本由已保存的原字节清单恢复，并验证本地与
远端 Git tree 均与实际完成全套测试的版本完全一致；附加行序实验另行
重跑。过程和完整性复核见 [PUBLISHING.md](PUBLISHING.md) 与
[publication-verification.json](publication-verification.json)。
