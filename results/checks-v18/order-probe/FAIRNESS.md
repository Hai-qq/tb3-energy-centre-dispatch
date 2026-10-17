# 最后候选的独立公平边界：CSV 行序

## 恢复说明

本报告与 `../fairness/order_contract.py` 根据会话中保留的完整源文本，在工作区环境清理后恢复。原始未提交的 JSON/stdout 未从记忆伪造。脚本已于 **2026-10-17T11:02:14.776198+00:00** 恢复后重跑，退出 **0**；新 JSON/stdout 明确带有 `post-cleanup recovery rerun`、实际执行 UTC 时间、运行时版本和当前 reference 哈希。这些是新执行证据，不是旧日志的恢复副本。

## 审查意见

**可以作为时间戳语义和程序健壮性的诊断探针；当前不应仅凭乱序能击败交付物，就批准它作为满足 E 的新陷阱。**

完整、唯一的时间戳确实唯一确定医院实际经历的时间顺序。把同一组记录重新排列，不能合理地改变哪段发生在午夜、哪个时刻需要哪些负荷，或发动机实际启动几次。这一点没有物理上的第二种读法。

另一个问题是输入接口是否已经要求支持任意排列。可见文件没有明确保证 CSV 必定有序，也没有明确说生产方可能交付无序记录；全部可见样例和原工具的数据结构都采用自然时间顺序。因此，不能把“原代码依赖行序”当成明确的输入排序保证，但也不能仅凭“未写 sorted”就把任意表示变换都认定为题目主要难点。这里仍有接口预期和 TB3 实质困难度的风险。

在用户要求“新陷阱不能有第二种合理读法”的标准下，我的建议是：**保留探针结果，不把它作为无争议的 E 成功证据。** 如果最终考虑提升，必须先证明失败是按真实时间重新对齐后仍存在的启动计费、实际供需或整天最优性错误，并单独说明为什么生产输入顺序变化属于既有接口范围。仅输出数组未排序、检查器按位置匹配失败、或者参考模型自己用错顺序，都不满足 E。

## 亲手检查的可见原文

`instruction.md` 描述 demand：

> the site's forecast demand for each half-hour of the plan date, by local start time

描述 weather：

> the latest weather and PV forecast run, as half-hour averages by UTC start time

要求整天计划满足需求、限值和最小费用，并说明午夜运行状态以及没有夏令时切换日。

这些信息足以把记录中的时间戳与物理时段绑定。它们没有明确写出“CSV rows are sorted”或“CSV rows may be in any order”。“by start time”支持时间戳身份语义，但不宜被单独宣称为详尽的输入顺序合同。

可见 `environment/planner/data.py` 的相关注释是：

```python
starts: list[str]  # local clock time of each half-hour, "HH:MM"
first_start: datetime  # start of the first half-hour, with its UTC offset
```

原 loader 随后直接保留 demand 行序，并赋值 `first_start=starts[0]`；weather 也依靠筛选后的行序对齐。**没有独立的输入 schema 声明保证外部 CSV 已排序。** 这些是已知待修实现的假设，不能像显式输入合同一样具有决定性权威。另一方面，`first_start` 的文字和全部顺序样例确实说明了作者原本采用的常规数据布局，应在审查中披露。

可见 `dispatch.py` 的 `held for the whole half-hour` 约束的是一段内恒定输出，不是 CSV 序列化顺序。不能把这句话当作任意乱序输入的直接授权。

## 隔离探针及恢复后重跑

脚本和新执行输出的位置：

```text
../fairness/order_contract.py
../fairness/order_contract.json
../fairness/order_contract.stdout.txt
```

清理前的会话记录显示脚本曾退出 0；该旧日志文件已丢失。恢复后的脚本保持同样的物理检查逻辑，并加入明确的新执行溯源字段，只创建自己的 fixture，不修改 task。已亲手执行以下命令生成新的实测输出：

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  /workspace/scratch/3a594630faca/ecd-venv/bin/python \
  results/checks-v18/fairness/order_contract.py \
  > results/checks-v18/fairness/order_contract.stdout.txt
```

本次运行环境为 Python **3.13.16**、NumPy **2.3.4**、SciPy **1.17.0**。当前 `reference.py` 的 SHA-256 为：

```text
9a76ed87d2ef7ab13f9734ddfffec29ba8715a61ada2745851e63efe480970b4
```

检查内容为：

1. 将 visible 日的 weather 记录完全逆序，同时保留每行所有内容。检查当前 reference 的湿球、PV 和时段对齐结果逐值相同。
2. 将 demand 的后 24 行移动到前面，形成从 12:00 开始的同一组 48 个记录。检查每个时间戳对应的需求、天气和 PV 数值全部保持相同，同时记录 reference 是否保留这个新的数组顺序。
3. 对一个独立的状态计数例子：GE1 午夜已运行，00:00–12:00 停机，12:00–24:00 开机。检查真实时间顺序下启动一次，而从 12:00 开始遍历行时计零次、少计 **£38** 的现有 chronology 依赖。

三项断言在新执行中全部通过：逆序 weather 未改变任何参考输入；移位 demand 的全部时间戳关联数值保持相同，而 reference 的首时段从 0 分钟变为 720 分钟；隔离状态例子按真实顺序计 **1 次启动、£1103.33108**，按从中午开始的行序计 **0 次启动、£1065.33108**，相差 **£38**。

第三项是用于验证 chronology 依赖的隔离状态例子，**不是满足医院全部负荷的完整调度计划，也不是对手的失败结果**。实测结果说明现有 reference 不能直接作为 demand 乱序探针的独立裁判，不能用其原始 pass/fail 宣布新陷阱成立。

## 若继续实验，必须遵守的边界

- 输入仍须恰好包含每个合法时段一次，时间戳、偏移、数值、CSV 列名和字段类型均不变。不要混入缺行、重复冲突记录、DST、跨日错配或格式变化。
- demand 和 weather 应按各自时间戳关联。发动机初始条件始终属于当地午夜，启动转移必须沿真实时间进行。
- 对手输出首先按明确的 `start` 身份重新对齐，再核验物理与计费。若只有 JSON 列表顺序不同，不能将其夸大为调度理解错误。
- 原参考、oracle 和评测器都要避免按输入行位置定义时间；否则可能同时把正确程序判错、把错误程序判对。
- 必须区分“程序没有支持某种输入表示”与“程序把时间戳当作无意义标签”。前者的接口范围需要说明；后者若造成实际计费/计划错误，才接近用户要求的真实理解缺陷。

## TB3 审查风险与最小替代实验

清理前亲手读取的官方本地 checkout 为 `tb3-guidelines`，提交
`2e29ca91d5f1cb6fb60924bf867acc755565c044`。这里保留其来源记录，不把恢复报告的过程声称为再次访问该 checkout。

`task-implementation.toml` 的 `essential_difficulty` 要求难度来自实质推理，不是输出格式细节；`test_instruction_alignment` 要求测试行为源于已说明任务。`CONTRIBUTING.md` 同时提醒避免通过大量筛选专门寻找当前模型很容易修补的能力角落。这些条款不能自动禁止所有记录重排测试，但意味着：打乱记录后发现程序漏了一次 `sorted()`，本身并不足以证明这是有意义且稳定的领域难题。

如果允许日后最小可见修改，可以只补一句：记录由其时间戳标识，CSV 行可能不按时间顺序排列。这样接口范围明确；再比较真实时间启动费用与最优计划。这个补充很小，但用户已指出可见提示可能让模型进入全面细查，因此需要新的真实模型实验，不能外推当前交付物的失败率。

本报告没有运行对手。其他代理的等价行序探针应独立列出其运行命令、真实时间重算结果及输出顺序影响，不要把那些实验归到本审查名下。
