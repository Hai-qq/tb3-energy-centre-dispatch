# v18 执行日志

## 范围、运行环境和计时

- 开始：2026-10-17 **07:24:39 UTC**（实际时钟工具记录）。
- 基线：`12a1116c5e545b4c30ff43cf8ac6503c9fd14473`，分支从
  `hardening-v9-v12` 创建为 `v18-gptpro`。
- 仓库：`/workspace/scratch/3a594630faca/tb3-energy-centre-dispatch`。
- Python：`/workspace/scratch/3a594630faca/ecd-venv/bin/python`，版本 3.13.16。
- NumPy 2.3.4 / SciPy 1.17.0 / pytest 9.1.1。
- 下文 `python` 均指上述 venv；执行时设置
  `PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1`。
- 没有运行 Harbor、Docker、新的指定模型试跑、轨迹审查或远端 CI。
- 本次只有一个正式写入 `tasks/` 的候选修订。前面的四轮负无功参数实验、
  母管、拓扑与散热器实验全部位于 `results/checks-v18/`，没有改动当时的
  task。每个正式候选必须完整执行 B/C/E/F；本候选的记录见后半部分。

## 基线复现（task 未改动）

先阅读 `HARDENING.md`、`results/checks-v17/README.md`、题面/原工具和
保存试跑。实际执行：

```sh
python tools/eval_energy.py tasks/energy-centre-dispatch/solution/app
python tools/check_v18.py --task archive/energy-centre-dispatch-v17 \
  --out results/checks-v18/baseline \
  --apps oracle strong-v16-claude v17-run1-claude v17-run2-claude v17-run3-claude \
         v17-run1-codex v17-run2-codex v17-run3-codex
python tools/check_v18.py --task archive/energy-centre-dispatch-v17 \
  --out results/checks-v18/baseline-mutants --mutants
python tools/fresh_days.py --days 16 --seed 2026 \
  --output results/checks-v18/baseline-fresh/seed-2026 tasks/energy-centre-dispatch/solution/app
python tools/fresh_days.py --days 16 --seed 2403 \
  --output results/checks-v18/baseline-fresh/seed-2403 tasks/energy-centre-dispatch/solution/app
python tools/fresh_days.py --days 16 --seed 87123 \
  --output results/checks-v18/baseline-fresh/seed-87123 tasks/energy-centre-dispatch/solution/app
```

结果：原 oracle 五天测试全过；最强 v16 Claude 五天全过；六份原 v17
程序仍全部失败；**39/39** 旧变异被抓；三组 fresh 各 **0/16 失败**。
各命令的完整输出在同名前缀 `.log` 中。

但绝对成本复核发现旧 oracle 的 h1/h4 分别比 MILP 低
£5.812224697746 / £14.878995913985；因此旧文档的 B 精度声明不能复现。
原因已读代码确认是 AC 辅机排热口径。不能把“pytest 通过”等同于绝对成本
差 <£0.001。

两份近通过程序加最小通用部件补丁，使用原 `eval_energy.evaluate` 独立执行
五天两遍。三份强程序各 **55/55** 通过，完整补丁、程序、命令和结果在
`opponents/`。另外八份旧同源程序实际重放在
`fairness/same_visible_history_replayed.json`，不是照抄旧评分。
其中 v8 Docker 镜像 pin 与 v8.1/v16/v17 有差别，题面、数据和原工具相同；
报告没有把这个历史集合当独立同分布模型试跑样本。

## 独立替身冻结与评测

另一个没有继承历史上下文的协作代理，只得到题面和完整可见目录的复制品，
以及运行环境路径。冻结前没有收到隐藏数据、参考模型、旧交付物或评测反馈。
它完成九组自检、96 个自造可行单时段例和两次相同 CLI 输出后冻结。

根代理复制到 `blind/`，逐项核验冻结清单。源码摘要：
`89b4cbfad49a251e6a1d321cdae598264f6c6ff58beaf520015d0162a3e7d917`。

```sh
python tools/check_v18.py --task archive/energy-centre-dispatch-v17 \
  --out results/checks-v18/baseline-blind --apps blind
```

结果：可见日通过，h1–h4 全部在
`test_units_within_ratings_and_availability` 失败。没有在评测后修补替身。
冻结后可以另作代码审查；这部分必须单独标注为 `POST_FREEZE_REVIEW.md`，
不能回流到已冻结 E3 交付物。

## task 修改前的候选实验

### 连续母管升温

三种 16:00 低谷负荷（500/550/600 kW）。见
`fuzz/water-probes/`、`fuzz/verify_water.py`、
`fairness/check_water_witness.py`。550 kW 时 Codex 的 24.259259°C 共同
水温计划成本 £6014.361415，旧 MILP £6034.446099；物理复核全部通过。
原电平衡误报 13.158879 kW。控制可达范围不唯一且 Codex 本来就正确，
**不选作难度陷阱**。

### 更平滑的夜间负无功

运行了四轮各 12 个候选，原始规格、输入、结果均在：

- `candidates/negative-q/`：第一轮；12 个无解，原因是 24h 插值回绕叠加
  23:30 时 GE1 LT radiator 检修，使夜间负荷不能被供应。
- `candidates/negative-q-r2/`：调整检修后有解，但未抓住正 Q 单侧变异。
- `candidates/negative-q-r3/`：进一步改变凌晨 GE2 检修与用电；未形成有效
  超限。
- `candidates/negative-q-r4/`：2380 kW、Q/P=0.10 的 q02 有解，变异在
  00:00/00:30 超出 1220 kVA **9.373251/8.232199 kVA**。

工具随后固定读取归档 v17 生成器，并补充 `--spec-dir` 重放接口，防止
未来 task 变化污染实验。实际用最终重放接口又执行 q02，成本、两项超限及
全部五个输入文件与原实验一致：

```sh
python tools/probe_v18_negative_q.py \
  --spec-dir results/checks-v18/candidates/negative-q-r4 --case q02 \
  --out results/checks-v18/candidates/negative-q-replay-q02
```

这是旧圆约束机制的更自然覆盖，三份完整圆模型不应因此失败。

### 未用过的部件

```sh
python tools/probe_v18_topology.py
```

实际运行 h2 GE2/GE1 `jacket water and exhaust` 各 18:20–18:40、h3
`AC1 generator` 12:40–12:50。每个算例三份强程序都过九项物理/汇报检查
和 MILP 成本比较。两项 HT 部件触发归档参考 KeyError；工具仅对此做了显式
标记的参考扩展，不能冒称 unmodified v17 通过。详见
`candidates/topology/` 和 `candidates-topology.log`。

### 高温 LT radiator

42°C 峰值控制点（生成后实际最高 41.9°C）、约 1000 kW 用电/1200 kW 热/700 kW 冷的合成日，在额外强制
dry bulb≥40°C 停发动机时，三份强程序均违反停机条件，约 £3524.49；
附加约束下独立 MILP 仍有解，£4261.52。全日发动机停机的明确可行方案也
通过九项物理/汇报检查。35°C 门槛另作了条件实验。

但纯干式空气冷却、空气进口等于干球温度、40/35 是绝对运行限制都没有
唯一规定。独立公平审查及制造商资料提供了预冷/额定工况的合理另一读法。
**三份同时失败也不计 E**。完整条件、数据、程序及结论在
`fuzz/radiator-probe/` 与公平审查文件中。

## 正式候选修订 r1（07:56 UTC 左右开始）

变更在 `ANALYSIS.md` 第一稿之后进行。一次性写入：

- 参考模型补齐 HT 源部件；PV 检修时长取区间并集；正 AC 出力即启用至少
  22°C 母管；用有上下界的共同母管 EC 耗电区间接受物理一致的暖水计划。
- 最优性说明明确现有不同口径的保守成本上界；独立连续母管 MILP 复核五个
  评分日的最优成本均未改变。
- 标准答案加入 HT 部件依赖、采用与 MILP 一致的严格 AC 辅机热口径。
- h2 采用 q02 平滑曲线、Q/P=0.10、调整 GE2 凌晨和 GE1 深夜检修，并加
  GE2 HT 部件 18:20–18:40；h3 加 AC1 generator 12:40–12:50；h4 加
  16:25–17:10 的嵌套 PV 检修。
- 原 39 个变异更新两个必要的文本匹配锚点，增加 HT 源部件/AC 发生器各一
  个语义变异；fresh 生成器增加两项可见 HT 名称。

```sh
python tools/build_energy_days.py
python tools/check_v18.py --out results/checks-v18/final-matrix --gate-v18
python tools/energy_mutants.py
python tools/fresh_days.py --days 16 --seed 2026 \
  --output results/checks-v18/final-fresh/seed-2026 tasks/energy-centre-dispatch/solution/app
python tools/fresh_days.py --days 16 --seed 2403 \
  --output results/checks-v18/final-fresh/seed-2403 tasks/energy-centre-dispatch/solution/app
python tools/fresh_days.py --days 16 --seed 87123 \
  --output results/checks-v18/final-fresh/seed-87123 tasks/energy-centre-dispatch/solution/app
python results/checks-v18/fairness/acceptance_regressions.py --require-fixed --label v18
```

A：与归档 v8.1 比较，13 个可见文件逐字节一致，原始哈希在
`visible-byte-check.json`。没有改动 archive、旧 results 或固定 plant/supply。

`--gate-v18` 实际返回 **1**：B 五天通过、E1/E2 未达、E3 完成、F 完成。
完整机器矩阵保留这两个 false，不以六份旧交付物失败替代 E。

## 第一次 fresh 异常、诊断和完整重跑

第一次 `final-fresh/` 报告 seed2026 的 f4 和 seed2403 的 f7 失败。
没有在此时将 B 写成已通过，也没有修改 oracle 去配合失败数据。

实际分别重跑参考 MILP、标准答案和禁用 LP presolve 的诊断，发现磁盘文件
本身已与控制台接受的 draw 不同。精确重生 RNG 序列后确认：两处磁盘五个
输入文件均匹配前一个被排除的无解 draw；日志中真正接受的 draw 在独立
目录全过，参考选择的 96 个时段状态 LP 全部可行。错误目录与日志不一致的
底层文件系统/生命周期原因仍不明，没有把猜测写成确定原因。

修订 `tools/fresh_days.py` 的实验路径与证据记录：每个尝试使用不复用的
`fN-draw-AAAA` 目录，显式输出目录必须是新目录，保存每次 draw 的完整
spec、接受/拒绝状态、MILP 费用和输入/参考哈希，评测前后再次验证文件，
任何失败均以非零退出。这里没有改变 task、参考物理或 oracle，因此没有
另一个正式 task 修订。

三种 seed **全部完整重跑**，分别 16 个可行日：

```sh
python tools/fresh_days.py --days 16 --seed 2026 \
  --output results/checks-v18/final-fresh-verified/seed-2026 tasks/energy-centre-dispatch/solution/app
python tools/fresh_days.py --days 16 --seed 2403 \
  --output results/checks-v18/final-fresh-verified/seed-2403 tasks/energy-centre-dispatch/solution/app
python tools/fresh_days.py --days 16 --seed 87123 \
  --output results/checks-v18/final-fresh-verified/seed-87123 tasks/energy-centre-dispatch/solution/app
python tools/verify_v18_evidence.py
```

前三个命令均退出 0，各 **0/16 失败**。最后命令不只读取成功标志：按保存
specs 将全部 48 天输入逐字节重生，检查原参考/输入哈希后，再以 120 秒
截止实际调用 oracle 48 次并重算物理、报告和绝对成本差。**48/48 通过**，
最大 6.195931 秒，最大绝对差 £0.000456373814。日志与完整 JSON 保留在
`final-fresh-verified-*` 和 `evidence-verification/`。

## 额外独立入口与针对性回归

```sh
python results/checks-v18/canonical_eval.py
python tools/check_v18.py --out results/checks-v18/targeted-mutants --mutants \
  --mutant-names ht_source_outage_ignored ac_generator_outage_ignored kva_positive_reactive_only
python results/checks-v18/fairness/postfix_checks.py
python results/checks-v18/fairness/warm_envelope_benchmark.py \
  --reference tasks/energy-centre-dispatch/tests/reference.py \
  --days-root tasks/energy-centre-dispatch/tests/days --label v18
```

前三强和 oracle 在原 eval/pytest 入口各 **55/55**，四者没有错误和失败；
三项针对性变异 **3/3** 被抓。11 项母管正反例、8 项 PV 区间关系、两个
HT 名称各三段检修、3 项独立排热算式均通过。连续母管 MILP 与严格参考
在五个 v17、五个 v18 评分日成本全相同。最终再次复核当前源码哈希并
重跑 11 项与五日连续 MILP，仍全部相同，输出在公平目录的 `final_recheck`
文件中。可行暖水见证的 £20.084684 差额保留为一般性边界反例。

## 差分模糊测试完成

主批次 384 次尝试，补充批次 96 次尝试，完整命令见 `fuzz/README.md`。
实际主批次 1945.8124 秒、补充 479.7709 秒，顺序运行，每批最多两进程。
合计 375 个有效可行日、三份对手 1125 次运行、10125 次物理/汇报检查，
全部通过。317 天未扩展归档参考；58 天显式扩展遗漏的 HT 名称；额外成本
比较合并去重后 130 天，全部通过。104 个无解组合和一个非法换钟日已排除。
所有部件、四季、午夜四种状态均覆盖，344 个保留目录重生内容审计零差异。

## 最终结果与结束时间

核心结论：A、B、C、D 的上述有限声明、E3、F 达成，E1/E2 未达。

**2026-10-17 08:30:57 UTC** 读取完整变异日志，最后一项
`hangs_after_writing` 已完成；主进程退出 **0**，**41/41** 均为 CAUGHT。
开始计时到完整验收证据收齐至少 **1 小时 6 分 18 秒**，随后继续整理提交。

全量变异中非确定性变异曾有一段触发开发用 20 秒短限，但其他日已因实际
输出不一致被抓。为排除这个偶发超时是唯一检出原因，又单独执行：

```sh
python tools/energy_mutants.py plan_varies_between_runs
```

退出 0，没有超时；visible、h1、h3、h4 实际输出不一致，变异被抓。
这项变异本身故意加随机扰动，不能要求每次两个舍入值都不同。20 秒是变异
开发工具的短限，绝非给强对手设置的限制；正式矩阵和 48 天独立验证均用
120 秒。故意挂起/错误退出变异按执行错误检出，没有用于 E。

```sh
python results/checks-v18/summarize_release.py
git diff --check
```

均退出 0。汇总脚本再次验证当前 task、oracle 和数据哈希仍与完整测试证据
相同，再检查 41 个预期变异的名称与 CAUGHT 记录完整相等。输出：

```text
B: oracle 5/5, fresh 48/48; C: 41/41 caught
E1_strongest_defeated: false
E2_patched_defeated: false
E3_blind_measured: true
F_six_originals_fail: true
promotable_as_stable_six_failures: false
```

修改范围检查没有发现允许路径之外的 tracked diff 或新增文件；所有五天
plant/supply 字节与 v17 一致。清除了本次运行自行产生的两项归档未跟踪
bytecode，归档源文件和旧结果均无修改。原 visible 13 文件与 v8.1 的字节
证据已单独保存。提交前没有发现凭据模式进入新增交付物。

远端 `v18-gptpro` 已存在于 `183cacb0`，实测它是本地基线的祖先；
`hardening-v9-v12` 远端仍是 `12a1116`。后续推送只允许快进，不强推，
PR 以未达 E 的草稿状态提出，不合并到 main。

暂存全部原始证据后，完整 `git diff --cached --check` 返回 2，项目是日志
尾空格、统一补丁的空白上下文、两份 fixture CSV 的 CRLF，以及冻结替身
`plant.py` 的一个原有空白行。保持这些证据及冻结代码字节不变。限定 task、
tools、编写的文档及其余 Python 源码的检查退出 0；具体路径和分类保存在
`staged-whitespace-check.json`。这不是未执行的“全部空白检查通过”声明。

## 发布恢复与附加证据

继续执行时发现本地工作副本和 Python 安装受到环境清理影响。根据先前
保存的原字节上传清单恢复 5,553 个文件变更，重建 tree 与原实测提交严格
相等；远端发布 tree 经重新 fetch 后也相同。实际 r1 commit 为
`682f76acceef1658e23cd6d234134cf4335eabaa`，没有强推。

原始 B/C/E/F 日志与源码证据完整恢复；没有把恢复过程冒称整套重测。
`publication_verify.py` 另行执行输入、源码、固定文件及盲替身哈希复核。
未入主提交的 CSV 行序附加实验没有可恢复的旧输出，恢复脚本后重新运行，
用实际的新时间与输出记录。详见 `PUBLISHING.md`、`order-probe/README.md`
和 `fairness/order_contract.json`。这些附加文件没有改动任务或原 480 次
fuzz 的计数，E1/E2 未达标的结论保持不变。
