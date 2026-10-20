# 额外设计审计：LT 排热容量不是所有权，但尚不是合格的下一版

日期：2026-10-18。基线为 v19 `9db5808`。本审计是父任务在 C1/C2/C4
完整盲实现均正确解决新增规则后，要求进行的一次有限、独立复查。

## 结论

**不能由三个提示预检的失败推出所有设计均不可能；共享 LT 排热确实还有两份旧
程序会犯的、彼此不同的真实模型错误。** 本审计亲跑的内存图模型探针证明了这一点。
但是，**尚未找到英国 NHS 双发动机共享、可独立隔离 LT 散热能力的直接一手证据**；
补足容量和隔离语义后，它又成为相当显眼的共享资源约束。现有证据不足以把该方向
推荐为已经符合用户真实性与提示预检要求的 v20。

这里的否定对象是这个具体候选目前的证据链，不是整道题、所有热路拓扑、或所有
可见字段取值的潜力。C1 已经反驳过“原字段取值没有反例”的全称命题，不能再恢复它。

本审计只创建本文件，没有修改任务、候选包、工具、旧交付物或任何冻结盲实现。
没有接触盲作者、没有取得新的隐藏评分反馈；附带的独立资料检索代理只检索公开来源。

## 1. 为什么仍检查 LT，而不是再加一个燃气/PHE 容量

两强已经把当前 LT 散热器当成发动机运行的必要去向，但没有使用当前性能表中的
`lt_heat_kw` 数值。它们的依赖逻辑也不同：

| 旧工具 | 实际代码 | 容量之外还存在什么区别 |
|---|---|---|
| A16 | `planner/plant.py` 将所有 LT 出口加入 `parts[engine]`；`planner/optimize.py` 的 `_Period.__init__` 用 `all(...)` 判断 | 任一出口检修就停止该发动机，即使其他出口有剩余能力 |
| A19 | `planner/plant.py` 保存 `lt_sinks`；`planner/optimize.py` 的 `_half` 用 `any(up(x) ...)` 判断 | 只要有一个出口可用，就允许发动机全负荷，没有为同时运行的发动机分配有限能力 |

因此，单一共同出口的所有权和检修传播没有新难度；但并联出口在检修后的**剩余
能力**不是一个布尔所有权问题。适当参数可以让 A16 过度停机，同时让 A19 过度运行。
这比 C5 原实验“第三只足以容纳 GE1 全部 LT 热的散热器”严格更强：原 C5 只击破 A16。

不过，本轮其他容量规则的经验和 v13 的既有 LT 降额结果均不支持“因此新的完整作者
大概率会漏掉”这一跳跃。A16/A19 是固定代码，不会重新阅读新数据。

## 2. 亲跑的最小图模型实验

### 2.1 身份与范围

这是一个**尚未通过 NHS 真实性审计的图模型替身**，不是新的候选可见包，也不是三道
预检。所有修改只发生在当前 Python 进程的字典和数组中，原应用源码零适配、零改动。
测试调用真实旧实现的 `load_day`、`Plant`、`Tariff`、`plan_day`；没有执行 CLI 文件输出，
所以本实验不证明 CLI 确定性、输出舍入、全部五日合法性或整日最优性。

内存可见数据差异：

- 用一条 `engine_lt` 代替 `ge1_lt`、`ge2_lt`，保持 40/35°C；`from` 为两台
  intercooler，`to` 为 `LT radiator 1`、`LT radiator 2`。
- 明示 `branches: "parallel, individually isolatable"`。
- 两只散热器分别给出 `maximum_heat_rejection_kw: 220.0`；这里是抽象硬上限，
  **没有宣称它是经厂家工况认证的 220 kW NHS 散热器选型**。
- 同一天的 48 行固定为电 1250 kW、全站无功 450 kvar、建筑热 2000 kW、冷 500 kW；
  PV=0，湿球 18°C、干球 24°C。使用原价表，午夜仅 GE1 运行。
- 唯一检修为 radiator 1 的 12:00–14:00。

### 2.2 结果

| 指标 | A16 | A19 |
|---|---:|---:|
| 程序求解耗时 | 0.968919 s | 0.748841 s |
| 报告日费用 | £5390.732891 | £4934.822204 |
| 12:00 GE1 / GE2 kWe | 0 / 0 | 900 / 482.923077 |
| 12:00–14:00 每半小时 LT 排热 | 0 kW | 252.194615 kW |
| 此时实际剩余抽象容量 | 220 kW | 220 kW |
| 连接失败时段数 | 4 | 0 |
| 新机制问题 | 把可旁路检修误判成两机都必须停，导致四段超连接 | 同时占用共同剩余容量，超限 32.194615 kW，约 14.63% |

不能比较这两个报告费用来宣称节省：A16 违反连接，A19 违反新增抽象 LT 约束，
都是不合法计划。本实验没有算该图模型的最优费用。

反对“这只是不可行输入”的直接可行证据是：全天固定 GE1=1200 kWe、GE2=0、
B1=785 kW、B2=0、EC1=500 kW、EC2=AC1=0、PV=0。按原数据计算：

| 约束 | 亲算结果 |
|---|---:|
| GE1 LT 排热 / 单只剩余容量 | 201 / 220 kW |
| 建筑热 | 1290+785−75 = 2000 kW |
| 冷量 | 500 kW |
| 自然冷凝水 / EC1 COP | 22°C / 6.5 |
| 有功进口 | 158.923077 kW |
| 净无功 | 55.579074 kvar |
| PCC 视在功率 / 限值 | 168.361450 / 1220 kVA |
| 塔排热 / 两塔能力 | 576.923077 / 3500 kW |

发动机、锅炉和电冷机也均在原额定范围内；唯一检修出口已由另一只散热器承担，
午夜 GE1 已运行，没有新增启动状态问题。这证明上述**抽象模型**的日期可行，不证明
其现实水力设计已经得到认证。

### 2.3 执行纪律与第一次探针错误

第一次运行 A16 已产生预期四段超连接，但统计脚本错把输出键写成 `engines`，
在读取 `engines_kwe` 前退出；当时还没有运行 A19。改正本次内存脚本的统计键后
重跑两份应用，得到上表，退出码 0。没有改动任何旧应用，也没有把第一次脚本异常
算作对手失败。

## 3. 真实性审计：得到的证据和没有得到的证据

所有来源在本次审计打开或检索核验；下面只使用原厂家、项目实施方或 NHS 文档。

### 3.1 NHS 的真实近邻

1. **Edina，Hywel Dda University Health Board。** 项目实施方说明 Withybush General
   和 Prince Philip 两个医院安装 MWM CHP，散热器布置在锅炉房外。文章描述两个
   医院、两个 CHP 站；不能从标题的两台发动机推出同一站共享散热器。
   [项目原文](https://www.edina.eu/case-studies/hywel-dda-university-health-board)，
   Scope of Supply、Challenges and solutions、Innovative features；检索/打开标识
   `turn37view0`。
2. **Edina，Queen Elizabeth University Hospital。** 同一 NHS 站点有三台 MWM TCG
   2020 V12；低品位中冷热没有用户，设计把它排入 CHP 通风风道，避免外置干冷器。
   这是明确的 LT 排热拓扑，但文章没有证明三机的能力共享、独立支路隔离或检修后
   的可转移排热额定值。
   [项目原文](https://www.edina.eu/case-studies/queen-elizabeth-university-hospital)，
   Scope of Supply、Innovation；`turn57view0`。
3. **Vital Energi，Northwick Park Hospital。** 项目方明确把水源热泵接到 CHP 的约
   40°C 第二级中冷器回路，回收原本要去干冷器的热。它是真实 NHS 的 LT 替代热汇，
   但不是双发动机共享并联散热器的证明。
   [项目原文](https://www.vitalenergi.co.uk/case-studies/northwick-park-hospital/)，
   Our Solution；`turn57view1`。
4. **NHS Scotland，SHTM 2011 Part 2。** §§4.48–4.53 描述发动机一次冷却水经
   换热器向二次水传热、二次水再由散热器冷却，支持液压隔离的架构。该文件为
   2001 年指导、2015 年已归档；不能拿它作当前规范要求，也没有从中找到跨机共享
   LT 能力的具体设计。
   [NHS 原 PDF](https://www.nss.nhs.scot/media/2892/shtm-2011-part-2-v2-jun-2001-jul-2015-archived.pdf)，
   `turn57view2`。

这些来源支持“LT 热必须有适当去处”以及“可以有不同于独立外置散热器的去处”。
它们**不支持将上述 220 kW 图模型直接称为已有 NHS 设计**。多个机组在同一院区、
多个冷却器出现在同一项目和 N+1 设计原则，也均不能替代具体连接与隔离证据。

### 3.2 MWM 原厂手册给出的边界

[MWM，Layout of Power Plants，2025-12](https://www.mwm.net/files/upload/mwm/issuu/MWM-Layout-of-Power-Plants_US.pdf)
是本次可直接打开的现行手册副本，适用于其列明的机组系列；`turn48view0`、
`turn50view0`、`turn50view2`。

- §8.2.4、印刷页 135 对多机系统写道：
  **“it is not permitted to connect the engine cooling circuits together”**，理由是各台
  入口水温控制不能保证。但手册将 HT 的 *engine cooling circuit* 和 LT 的
  *mixture cooling circuit* 分开称呼。**不能把这一句话扩大为所有共享 LT 二次侧
  布置的禁令，更不能用它证明本任务没有其他设计。**
- §8.5.3、印刷页 152 的 sandwich LT/HT radiator 讨论把这种双芯、共风机布置
  限于纯发电用途，并解释热利用负荷变化造成的控制问题。因此，“厂家有共风机
  散热器”也不能自动成为 CHP 共享容量方案的出处。
- 手册允许适当的耦合换热器/二次回路，故两个受控一次回路经 PHE 接到公共二次
  排热仍是可以继续调查的工程可能。本次没有验证其具体 NHS 实施。

早先检索也找到 2023-09 版，但直接打开失败；上述结论以已打开的 2025-12 版为准，
不把失败的页面下载说成已保存的 PDF 证据。

## 4. 若继续，怎样使可见数据足够且不偷加现实假设

可考虑的**条件性结构**是：GE1、GE2 各保留独立受控 LT 一次回路，各有自己的
液压隔离 PHE；两只 PHE 的二次侧进入一个明确的公共排热回路；该回路有两只可
独立隔离的并联冷却器。只有可用的二次侧能力能共同接收两台发动机的 LT 热。

但把第 2 节的简图落实为这个结构，至少要补足以下可见事实：

| 可见资料 | 它必须排除的第二种合理读法 |
|---|---|
| 每台发动机的一次回路、PHE 两侧和共同二次回路的全部连接 | 直接混接发动机内部冷却水，或把两个各自的盘管误当成可相互替代 |
| PHE 两侧运行温度/能力，或完整可用工况包络 | 默认零温差无限传热、把名义供回水当成任何负荷均不变的硬值 |
| 冷却器能力随所需水温和天气的适用范围 | 用 220 kW 名义铭牌推导所有季节均有 220 kW，或重演 v19 的高温硬停假设 |
| 并联、独立隔离，以及阀门/泵足以支持的实际路径 | 一支路检修隔离了整个母管，或支路存在但不能在负荷下切换 |
| 功率预测如何包含新泵和风机 | 在全站电力里漏算或双算辅助负载 |

上述内容不能通过误导注释、不解释的新名字或隐去必要部件来“降低显眼程度”。
若 PHE 等端点使旧代码拒绝新图，则拒绝本身只算读取格式/能力边界。E 必须在
单列的最小适配后仍观察到第 2 节的过度停机和容量超用，不能把异常当成两强真实
物理误解的完成证据。

## 5. 提示难度判断和有限的下一步

在这个小图中，只要新作者读取硬容量和并联拓扑，约束就是：

`LT_GE1(P1) + LT_GE2(P2) <= sum(available secondary rejection capacities)`。

有一个共同池时没有困难的路径分配问题。把它换成多个不完全相连的池可以增加
流量分配，但这需要更多真实设备与明确的边，不会自动变成较不显眼的行业推论。
本审计及独立资料代理都判断：**目前的 LT 容量提案，没有证据证明比 C2/C4 更可能
逃过完整盲实现**。该判断是基于结构和既有盲预检的推断，不是新一次模型试跑结果，
也不能转写成 Opus/GPT 的量化漏读概率。

### 最小证伪实验（尚未执行，按顺序）

1. 先拿到一份项目 P&ID、调试/运行说明或厂家项目资料，直接证明两个 LT 热源、
   独立一次侧、共享二次侧和剩余冷却能力。没有这份资料，不冻结新候选。
2. 冻结一份最小完整可见包；两名独立读者只回答正常运行与单支路检修下可如何运行。
   必须同时说出“仍可能运行”和“剩余能力共享”，并对隔离/PHE 工况没有第二种读法。
3. 只开**一次**完整最佳努力实现的提示预检，允许独立检查器和测试日。作者冻结后，
   使用预先固定的三类日期：两支路可用、单支路检修而一机合法、单支路检修而两机
   仅低负荷合计可行。不能只问一条容量公式后把回答算完整提示预检。
4. 若盲工具正确限制合计 LT，马上淘汰该机制，不跑为了累积旧代码失败次数而扩大的
   矩阵。若确实漏掉新机制，再完成五日、两强最小适配、所有历史失败工具、独立
   MILP、变异、3×16 fresh 和不少于 200 个合法日，才可能把它升为 v20。

第 2 节已完成了廉价旧代码机制探针，避免对源码猜测的争论。当前未执行上面的
两读者或盲实现，也没有补成一个合格候选；所以不能称“三道预检通过”、A–F 完成，
或“两强在 v20 都失败”。

若寻找更有直接 NHS 出处的不同设计，Northwick Park 的 **LT 热泵作为替代热汇**和
QEUH 的 **通风风道排出 LT 热**值得优先做资料建模。但二者目前同样没有完整可见包、
唯一约束或盲实现结果；不能拿真实项目存在替代难度证据，也没有在本审计重做储热、
gateway、batch 或 v11 的显式冷却塔控制。

## 6. 内存探针的完整复现命令

本命令不创建文件；设置 `PYTHONDONTWRITEBYTECODE=1` 防止读历史应用时写字节码。
它只复现第 2 节尚未获工程真实性批准的共享图假说。

```sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
/workspace/scratch/e1216eed3f00/ecd-venv/bin/python - <<'PY'
import sys, json, time, math
from pathlib import Path
import numpy as np
root = Path('/workspace/scratch/e1216eed3f00/tb3-energy-centre-dispatch')
apps = [
    ('A16', 'results/v16-trials/ecd16-run2-claude/app'),
    ('A19', 'results/v19-trials/ecd19-run2-claude/app'),
]
for tag, app in apps:
    for key in list(sys.modules):
        if key == 'planner' or key.startswith('planner.'):
            del sys.modules[key]
    sys.path.insert(0, str(root / app))
    from planner.data import load_day
    from planner.plant import Plant
    from planner.tariff import Tariff
    from planner.optimize import plan_day
    day = load_day(root / 'tasks/energy-centre-dispatch/environment/data')
    day.elec[:] = 1250
    day.kvar[:] = 450
    day.heat[:] = 2000
    day.cool[:] = 500
    day.pv[:] = 0
    day.wet_bulb[:] = 18
    day.dry_bulb[:] = 24
    circuits = day.plant['heat_circuits']
    del circuits['ge1_lt']
    del circuits['ge2_lt']
    circuits['engine_lt'] = {
        'flow_c': 40, 'return_c': 35,
        'from': ['GE1 intercooler', 'GE2 intercooler'],
        'to': ['LT radiator 1', 'LT radiator 2'],
        'branches': 'parallel, individually isolatable',
    }
    day.plant['lt_radiators'] = [
        {'id': 'LT radiator 1', 'maximum_heat_rejection_kw': 220.0},
        {'id': 'LT radiator 2', 'maximum_heat_rejection_kw': 220.0},
    ]
    day.status['running_at_midnight'] = ['GE1']
    day.status['outages'] = [
        {'unit': 'LT radiator 1', 'from': '12:00', 'to': '14:00'},
    ]
    plant = Plant(day.plant)
    tariff = Tariff(day.supply, day.date)
    start = time.perf_counter()
    periods, starts = plan_day(day, plant, tariff)
    elapsed = time.perf_counter() - start
    totals = []
    for p in periods:
        total = 0.0
        for e in day.plant['engines']:
            output = p['engines_kwe'][e['id']]
            if output > 0:
                total += float(np.interp(
                    output,
                    [r['kwe'] for r in e['part_load']],
                    [r['lt_heat_kw'] for r in e['part_load']],
                ))
        totals.append(total)
    print(json.dumps({
        'probe': 'unapproved shared-LT graph surrogate, not an NHS-validated candidate',
        'app': tag, 'elapsed_s': elapsed,
        'period_1200': periods[24],
        'cost_gbp': sum(p['cost_gbp'] for p in periods),
        'starts': starts,
        'grid_failed_periods': sum(not p['grid_ok'] for p in periods),
        'lt_outage_window_kw': totals[24:28],
        'maximum_lt_kw': max(totals),
    }, sort_keys=True))
    sys.path.pop(0)
p = 1250 + 32 + 500 / 6.5 - 1200
q = 450 - 1200 * math.sqrt(1 - 0.95**2) / 0.95
print(json.dumps({
    'certificate': 'constant GE1 full output; GE2 and AC1 stopped; EC1=500; B1=785',
    'lt_kw': 201, 'available_lt_capacity_kw': 220,
    'ht_kw': 1290, 'lthw_delivered_kw': 1290 + 785 - 75,
    'electric_cop': 6.5, 'grid_p_kw': p, 'grid_q_kvar': q,
    'grid_s_kva': math.hypot(p, q),
    'tower_kw': 500 + 500 / 6.5, 'tower_capacity_kw': 3500,
}, sort_keys=True))
PY
```

复核边界：本次没有修改额定功率、性能点、COP、电价或热损失；只替换了上面明确
列出的内存图和测试日数组。它的设备可行证据是在简化图下计算的，不应导入正式
判分器而略去第 3–4 节尚未解决的真实性和可见资料缺口。
