# v20 候选实验、冻结盲修和可复查证据

**本轮没有取得合格的正式v20。** C1/C2/C4都能击破两份旧强工具，却均被完整冻结盲修正确识别了新增要求，按用户门槛必须淘汰；不把旧检修失败记作新难点成功。

基线为 `v19` / `9db580817b1dc46ac6c500f8c472faaafce0a997`，工作分支为 `v20-gptpro`。本目录提供完整候选任务、可见数据、独立参考、标准答案、固定日与差分原始回放、盲修及淘汰记录。正式 `tasks/energy-centre-dispatch/` 保持基线逐字节一致。本分支用于审阅实验及负结果，不是已经建议采用的新题版。

## 阅读入口

| 文件 / 目录 | 内容 |
|---|---|
| [ANALYSIS.md](ANALYSIS.md) | 用户第一阶段四个问题、五候选机制、实测因果证据、边界和去留 |
| [LOG.md](LOG.md) | 实际工作起止、修改与重跑、失败保留、完整执行命令 |
| [MATRICES.md](MATRICES.md) / [SUMMARY.json](SUMMARY.json) | 从原始 JSON 生成的五日全应用、变异、fresh 与 200 日摘要 |
| [VISIBLE_CHANGES.md](VISIBLE_CHANGES.md) | 全部可见字段的原值/新值、完整 diff 和工程出处 |
| [prechecks/PROTOCOL.md](prechecks/PROTOCOL.md) | 隔离阅读范围、冻结及三道预检判定方法 |
| [audit/STRONG_IMPLEMENTATIONS.md](audit/STRONG_IMPLEMENTATIONS.md) | 两份最强交付物的逐项源码假设审计 |
| [research/mechanisms-sources.md](research/mechanisms-sources.md) | 原始一手来源调查及明确的真实性缺口 |
| [research/ADDITIONAL_DESIGN_AUDIT.md](research/ADDITIONAL_DESIGN_AUDIT.md) | 三项淘汰后追加的有限LT拓扑审计、NHS来源边界及最小证伪实验；附父任务真实重放JSON/log |
| [prechecks/BLIND_C1_REVIEW.md](prechecks/BLIND_C1_REVIEW.md) | 冻结后独立审查 C1 新规则、旧部件名缺口及实际结果 |
| [prechecks/BLIND_C2_REVIEW.md](prechecks/BLIND_C2_REVIEW.md) / [BLIND_C4_REVIEW.md](prechecks/BLIND_C4_REVIEW.md) | 另两份冻结盲修的独立源码与绑定输入审查 |
| [prechecks/BLIND_RESULTS.md](prechecks/BLIND_RESULTS.md) / [DECISIONS.json](prechecks/DECISIONS.json) | 三个完整预检的合并结论与五候选逐项去留 |
| [prechecks/EVIDENCE_REVIEW.md](prechecks/EVIDENCE_REVIEW.md) | 独立重新计算文件散列、回放保存和验收声明范围 |
| [prechecks/FINAL_REVIEW.md](prechecks/FINAL_REVIEW.md) | 最终独立一致性复核；131变异、144fresh日、828冻结文件及全部去留声明相符 |

## 当前已完成的实验

五个方向均有实际参数或应用实验；C1/C2/C4 各具完整可评测任务包，位置为 `candidates/cX/task/`。这不等于已获得三个合格的加固方案。

| 候选 | 改变 | 标准答案五日 / 变异 / 两强 / 旧失败 | 完整盲修预检 |
|---|---|---|---|
| C1 | 原有进口/出口价 7p/12p，三个数值 | 同口径 B 通过；43/43；两强失败；七旧失败仍失败 | 已完成：新方向规则正确，因旧检修名整题失败，**仍应淘汰** |
| C2 | 四机共同 550 Sm³/h、39.6 MJ/Sm³ 燃气入口 | 同口径 B 通过；44/44；两强失败；七旧失败仍失败 | 已完成：正确处理含锅炉的共享入口；旧部件名拒绝，**仍应淘汰** |
| C3 | 冷机馈线与 PF | 初筛：三冷机 400 kVA 不绑定；低值可能无解；单 EC1 方案可行但未完整预检 | 未运行，未入选 |
| C4 | PHE1 一次侧最大 20 kg/s、cp=4.18 | 同口径 B 通过；44/44；两强失败；七旧失败仍失败 | 已完成：正确处理 PHE 支路上限，因旧检修遗漏整题失败，**仍应淘汰**；另有运行温度解释风险 |
| C5 | GE1 并联独立隔离的 LT 散热支路 | 仅 A16 失败、A19 五日全过；精确 NHS 一手出处不足 | 已在初筛淘汰 |

C1/C2/C4各自完成3 seed ×16 fresh日，合计144个候选随机日全部通过。C1另完成四份应用各200个合法可行日的真实CLI回放；没有把这200日算作C2/C4的差分证据。所有随机日均在调用被测应用前按输入合法性及独立参考可行性筛选。

### 200 日结果

| 应用 | 通过 / 失败 | 解释 |
|---|---:|---|
| Oracle | 200 / 0 | 对独立同口径 MILP 最大绝对差 £0.000489197 |
| 原样 A16 | 117 / 83 | 83 日比已有可行参考方案更贵 |
| 原样 A19 | 0 / 200 | 全部虚拟双向交易及费用报告错误；113 日另有真实次优 |
| C1 冻结盲修 | 91 / 109 | 所有 109 次失败均为旧部件名称拒绝；91 个计划全部通过新增方向及其他判分 |

四季日数为 53/66/17/64，21 个检修名称全覆盖。200 日先按合法性和独立参考可行性选定，再回放应用；77 个拒绝输入及理由也完整保留。拒绝只针对所用参考口径，不声称其在每种较宽运行解释下都不可能。

## A–F 验收如何阅读

**不要把计算门槛与候选资格合并成一个 PASS。** 标准答案、两强与变异矩阵可以全部达到数值要求，但如果盲修识别了新难点，仍必须按用户规则淘汰。

| 要求 | 证据及适用范围 |
|---|---|
| A 可见变化与真实性 | `VISIBLE_CHANGES.md`、各 `visible.diff`、研究一手来源。C1 三个合成合同数值；C2/C4 合成选型。C5 的来源缺口明确导致淘汰 |
| B 标准答案与 fresh | C1/C2/C4各自 `gates-r1/apps.json`、`oracle-pytest-r1.log`及`fresh-2026/`、`fresh-2403/`、`fresh-87123/`全部通过。B的£0.001只认证保留相同口径的独立MILP一致性 |
| C 全部错读变异 | C1 43/43、C2/C4 各44/44；每项新限制均有实际语义错读变异，逐日原计划与断言保存于 `gates-r1/mutants/` |
| D 题意与读者原文 | 六份 `prechecks/reader_c*_*.md` 及其摘要；C4 仅在 90/70°C 为固定模型运行工况的条件下收敛，不声称完全排除歧义 |
| E 两强与盲修 | 两强均原目录运行，零适配；`adapters/` 内两个补丁为空。C1 h2 净报表控制与方向修复控制证明真实次优；盲修正确新规则应淘汰。点名近通过实现的全部原始失败同样保存 |
| F 七份旧失败回归 | 六份 v18 app 及 v19-run1-Claude 在三个候选中仍失败。旧名称解析拒绝只用于 F，未冒充 E 的新机制难度 |

### 原有验收口径边界

v19 参考优化最低许可公共冷凝水温与较严格 AC 辅助排热，实际物理检查允许较宽的合理运行解释，部分 PV 检修亦有原先保留的验收边界。因此同口径 MILP 给出的是较宽集合中的可行费用上界。负费用差不应判为错误；正差额与这个更便宜可行证人比较，仍足以证明次优。本轮没有为了制造额外失败而收紧这套既有公平容许。

实际模型试跑、Harbor、Docker、28 项正式静态检查、35 条正式实现审查及 CI 轨迹审查均未运行，按用户要求留给本地。六位读者与三个盲修来自本会话模型的全新上下文；它们不是指定 Opus/GPT 的正式样本，也不是操作系统级沙箱隔离。

`fresh_days.py`及单独`eval_energy.py`遵循原工具行为，会删除临时CLI计划；fresh的输入、完整生成规范、manifest及pytest摘要保存，固定日与200日的原始计划由独立回放脚本保存。盲修C2/C4也明确标注未完整归档的中间开发版本；最终冻结前后文件完整性全部验证。

## 重现命令

使用 Python 3.13、NumPy 2.3.4、SciPy 1.17.0、pytest 9.1.1，从仓库根目录执行。以下 `OUT` 必须换成新的输出目录，以免覆盖证据。若要重现 C2/C4，将 `c1` 及 `--candidate` 同时替换。

### 固定日 B/C/E/F 和完整 pytest

```sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python tools/check_v20.py --candidate c1 \
  --task results/checks-v20/candidates/c1/task --out OUT

ECD_TASK="$PWD/results/checks-v20/candidates/c1/task" ECD_RUN_TIMEOUT=120 \
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python tools/eval_energy.py results/checks-v20/candidates/c1/task/solution/app
```

`check_v20.py` 运行实际测试函数、每应用每日至少两个真实 CLI、独立整天 MILP，并保存计划、stdout/stderr、耗时和源文件散列。其 E 布尔量只统计两旧强是否失败，不能自动代替新的提示预检资格判断。

### 三个 seed 的 fresh

```sh
ECD_TASK="$PWD/results/checks-v20/candidates/c1/task" ECD_RUN_TIMEOUT=120 \
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python tools/fresh_days.py --days 16 --seed 2026 --output OUT \
  results/checks-v20/candidates/c1/task/solution/app
```

另两次将 seed 改为 `2403` 和 `87123`，并各自使用新的 OUT。原日志记录了三次实际全部通过。

### 冻结盲修的固定日判分

```sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python tools/check_v18.py --task results/checks-v20/candidates/c1/task \
  --out OUT --apps blind --app blind=results/checks-v20/blind/c1/app
```

它没有 `--gate-v18` 时不会以自身退出码表示盲修是否通过；应读取 OUT 内 `matrix.json` 的逐日结果，不能将检查脚本退出 0 误认为候选应用全过。原始作者冻结清单与父任务评分前后校验在 `blind/c1/FREEZE.json` 和 `prechecks/c1-freeze-*.json`。

### 新建相同规则的 200 日四方差分

```sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python tools/fuzz_v20.py --task results/checks-v20/candidates/c1/task \
  --out OUT --days 200 --seed 200019 --workers 3 \
  --app oracle=results/checks-v20/candidates/c1/task/solution/app \
  --app strong-v16=results/v16-trials/ecd16-run2-claude/app \
  --app strong-v19=results/v19-trials/ecd19-run2-claude/app \
  --app blind=results/checks-v20/blind/c1/app
```

本轮实际为先 `--prepare-only`，再回放前三份应用，最后盲修冻结后 `--resume --extend-apps` 追加；具体命令在 LOG。这个新输出目录的一次命令同样在调用任何应用前完成全部输入筛选。

### 因果控制与汇总

`tools/explain_v20.py` 保存 h2 只改报告、不改出力的控制及容量峰值；`tools/explain_v20_fuzz.py` 对 200 日最大费用损失做仅改方向的语义诊断控制。诊断修复不属于对手格式适配。汇总可用以下命令重新生成：

```sh
PYTHONDONTWRITEBYTECODE=1 python tools/report_v20.py
```

`build_v20_candidates.py`、`build_v20_models.py` 属于候选构建历史，不应直接在已有冻结目录上重复运行；它们对覆盖已有输出设置了保护。

发布前实际执行`tools/verify_v20_evidence.py`，证明正式任务及基线快照相同、六读者未变、三份盲修共828文件未变、全部评测模型/历史应用未变、九组fresh的144个日期输入及结果匹配。证据见[FINAL_INTEGRITY.json](FINAL_INTEGRITY.json)。它是文件及结果一致性审查，不是正式TB3静态检查或轨迹CI。
