# energy-centre-dispatch 大改的隐性难点候选：调研与筛选报告

## 1 结论

**没有候选能满足全部标准。** 只有 T1 通过了全部 7 条定性淘汰标准，但按我的估计，它单独达不到"90% 把握让 3+3 全挂"所需的强度。

**定量差距：**
- 目标是 GPT≈0 时，Opus 单场通过率 ≤3.45%。现在约 12.5%（16 场里两个难点都做对 2 场）。
- 假设新难点与现有两个独立，它的做对率要 ≤0.28，也就是 Opus 漏掉率 ≥72%。
- T1 的漏掉率我估计 45–60%【推断】。加入 T1 后，Opus 单场通过率约 5–7%，3 场全挂的概率从约 0.67 升到 0.81–0.86，仍低于 0.9【计算】。

**其余候选不合格的原因分三类：**
- 与母管、部件检修或 T1 是同一个洞察；
- 必须写进数据的字段，一写就会被做对（L1）；
- 公平性、现实性或经济性有硬伤。

**前 5 名，每个一句话：**
1. **T1**：发动机中冷回路（LT，40/35 °C）的余热经 LT PHE 进一条气候补偿的 AHU 低温回路。冷天这条回路的回水高于 40 °C，一点热也回收不了，原工具却按能量母线照收。
2. **T2**：热泵最高出水温度（65 °C）低于气候补偿后的 LTHW 供水温度时，热泵只能预热回水，份额随天气变。原工具按设计温差给一个固定份额。
3. **J1**：非冷凝锅炉 B2 自带 shunt pump 保护回水温度。原工具在补偿后的系统回水低于 55 °C 时锁住 B2。
4. **T3**：工艺冷却环路的干冷器在环境温度低于回水温度时可以部分预冷。原工具只在能完全自然冷却时才开干冷器。
5. **F1**：午夜在运状态扩到有启动成本的 AC1。隐藏日的 running_at_midnight 里列出 AC1。

**系统结构本身能否制造独立难点：**
- 单纯扩大规模、叠加规则不能。K 把五条规则叠在一起，16/16 都被做对。
- 能起作用的结构特征都已经体现在 T1 里，算不上独立于具体机制的"结构难点"：
  - 让某个回路的温度随天气变化；
  - 让新子系统在可见日处于"顺风"状态，在隐藏日处于"逆风"状态；
  - 后果的方向反直觉（冷天反而回收不了）。母管也是这种反直觉方向。
- 另一种结构手段是给现有部件检修增加替代热汇，让检修后果变成有条件的。但这和部件检修相关，不独立。

**下一步：** 若要推进，先按仓库惯例给 T1 做两名隔离读者的公平性预检和 1 场盲测，盲测看工具有没有检查 LT PHE 的温度可行性。即使 T1 有效，还需要再有一个独立的中等难点，或者把部件难点的前缀捷径堵掉（这属于部件同一洞察，只作补充手段）。

## 2 前 5 名完整描述

标注约定：【推断】是我的推断；【计算】是我用题目 `tests/reference.py` 的副本在 scratchpad 里算的（`scratchpad/research-v24/milp_b1*.py`，没有改仓库）。

### T1 发动机 LT 余热进气候补偿的 AHU 低温回路（第二定律温度品位）

**机制**
- 新增一条给空调箱（AHU）加热盘管供热的低温回路，热源有两路：
  - 经 `LT PHE 1/2` 回收两台发动机 LT 回路（40/35 °C）的热；
  - 经混水阀从 LTHW 取热。
- 回路按室外干球做气候补偿，参考参数：−3 °C 时 55/47 °C，18 °C 时 34/29 °C。
- 夏天回路是 34/29 °C，LT 热可以全部承担（夏季除湿后的再热）。
- 冷天回水 ≥40 °C，40 °C 的 LT 水加热不了它，回收为零。

**数据和题面写明的内容**
- LT 回路 40/35（现有字段）。
- 新回路的 from/to。
- `flow_c_by_dry_bulb_c`、`return_c_by_dry_bulb_c` 两张表，沿用题面"表内线性、两端外平"的约定。
- demand.csv 新列 `ahu_heat_kw`。
- 题面加一句设备说明。
- 不写"只有回水低于 LT 水温时才能回收"。

**原工具和自然的建模默认**
- 原工具按能量母线处理：回收量 = min(在运发动机的 LT 热, AHU 需求)，不看温度。
- 仓库核实：13 份试跑交付物（v16、v19、v21 W/P、v22 S/K/D）都是这样：
  - 规划里读回路温度的地方，只有原工具已有的 AC1 热水下限检查、C4 的显式流量规则和 S1 推广的 AC1 热源检查；
  - 没有一份在规划里用过干球温度。

**没写明的后果**
- LT 回收上限 = AHU 需求 × clip((40 − T_回)/(T_供 − T_回), 0, 1)；T_供 ≤40 时为 1。
- 冷天必须为 0，AHU 全靠 LTHW（锅炉或 PHE1）供热。

**只在哪种隐藏日出现，为什么可见日不露面**
- 冬季干球 ≤约 5 °C 时回收为 0；春秋早晚是部分份额。
- 可见日干球 19.9–28.8 °C，份额恒为 1。
- 【计算】能量母线模型和正确模型在可见日的最优成本都是 £6290.99。
- 【计算】h2 上，能量母线宣称最多回收 340 kW（正确上界 ≤50 kW），锅炉少烧最多 393 kW，成本低估 £262。
- 【计算】h3 上，宣称 261 kW 对 174 kW，锅炉少烧最多 126 kW。

**为什么模型自己的检查器和测试日也会漏掉**
- 这是放宽型遗漏。能量母线模型在自造的冬季测试日里不会出现"无可行计划"。
- 独立整天 MILP 和计划检查器用的是同一条能量母线。
- 母管当初靠"冷天测试日无解"被发现，这条渠道在 T1 不存在，只剩读温度表和审查子代理两条路。
- 方向反直觉：直觉上冬天更需要热回收。

**为什么和母管、部件检修独立**
- 母管的洞察是"冷却水温是可控设定量"；部件的洞察是"检修可以落在拓扑里的部件名上"。T1 不涉及控制设定，也不涉及检修。
- 【推断】残余相关：三者都要求关注温度或热路，与母管弱正相关；审查子代理可能同时发现母管和 T1。
- LT 回路多了一个出口，`LT radiator` 检修时发动机理论上可以靠 LT PHE 继续运行。隐藏日应把散热器检修放在 AHU 吸收不了的时段（冬季，或夜间低需求），保持部件难点的语义不变。

**公平性风险**
1. **PHE approach 没给。** 份额在 0 和 1 之间的区间里结果依赖 approach。
   - 【计算】按 0、2、5 K approach 求最优：h3 差 £32.5，h2 差 £5.2，可见日差 0。
   - 处理办法：沿用题目已有的约定，可行性按最宽松读法（零 approach），MILP 按最严读法；或只在份额为 0 或 1 的清晰区间放 AHU 需求。
   - 写一个全局 approach 能消除歧义，但会提高显眼度。
2. **串联还是并联。** 在清晰区间与连接方式无关；中间区间按串联给上界。
3. **"LT 水温可以调高"。** 数据只给 40/35，没有依据。
4. **"补偿表是设计值不是运行值"。** 字段名和题面写"按室外干球运行"即可排除。
5. **设计合理性。** 内行可能会问为什么不用热泵把 40 °C 热提上去（Northwick Park 就用了热泵）。直接回收到低温回路只在温和季有效，属于现实中的折中设计。

**真实性出处**
- MWM《Layout of Power Plants》（2025-12）：
  - §8.2.2（p.134）：LT 回路温度低，热通常经散热器或冷却塔排掉；
  - §8.3.2（p.138）：LT 热排到环境，或用于低温供热回路；
  - 已核实。
- CIBSE CHP Group Datasheet 02（2012-01，p.1）原文："at too low a temperature for useful heat recovery (circa 40°C)"。同页还写了回水要低于供应商规定的上限，否则控制系统会停机。已核实。
- Vital Energi Northwick Park（London North West University Healthcare NHS Trust）：二级中冷回路约 40 °C，原来经干冷器排掉，后用水源热泵接入。已核实。
- Approved Document L Vol.2（2021 版，含 2023 修订）：
  - §5.10（p.36）：新装或整体更换的湿式供暖按最高供水 55 °C 设计；
  - §5.11(e)：条件允许时应有气候补偿；
  - 已核实。
- CIBSE Journal Module 219：混合系统要保证锅炉侧回水不超过热泵最高出水温度，属于同一温度品位原则。子代理核实。
- 夏季再热需求的依据：HTM 03-01 Part A 要求手术部湿度 35–60%。这是经 AfPP（2026）转述的二手来源。

**实现草图**
- plant.json：
  - `ge1_lt.to = ["LT PHE 1","LT radiator 1"]`，`ge2_lt` 同理；
  - 新增 `heat_circuits.ahu_lt`，含两张温度表，from 为 `LT PHE 1/2` 和 `LTHW mixing valve`，to 为 `AHU heating coils`；
  - `lthw.to` 加 `LTHW mixing valve`。
  - LT PHE 只出现名字，不带属性，避免 L3。
- demand.csv 加 `ahu_heat_kw`：夏季 60–150 kW，冬季 300–500 kW。
- 题面加两句：一句说设备，一句说新列。
- 原工具：
  - 按能量母线把 LT 热计入 AHU，这就是陷阱本身；
  - 原来"中冷热算作可回收热"那处 bug 改掉，不在 LT 路径上再设显眼的 bug。
- reference.py：
  - 干球按本地时间对齐（与湿球同法），算出 T_供、T_回；
  - heat balance 的接受区间改为 [heat+loss+AHU−R_max, heat+loss+AHU]，R_max 按零 approach 计；
  - MILP 加变量 R_t：R_t ≤ 严格份额 × AHU_t，且 R_t ≤ 在运发动机的 LT 热（与 heat_terms 一样分段线性）；
  - 散热器检修时 LT_k 只能进 R_k。
- 新变异体：能量母线；从不回收；用设计温度（份额恒为 0）；干球不做时区对齐。
- 【计算】"从不回收"读法在可见日、h1、h4 分别多花 £26.3、£22.3、£34.6，超出成本容差。

**估计 Opus 漏掉率：45–60%（中值约 50%）**
- 抬高漏掉率的因素：
  - 放宽型，没有报警渠道；
  - 可见日两种模型结果完全一致；
  - 历史交付物从不在规划里用干球或做换热器温度检查；
  - 方向反直觉。
- 降低漏掉率的因素：
  - 两张温度表是新字段，Opus 会追问用途；
  - 同类的温度份额一旦写明下限和顺序就被推出来了：v10 的 AC1 预冷器 3/3（2 场 Claude、1 场 Codex）；
  - 审查子代理可能指出。

### T2 热泵最高出水温度对气候补偿 LTHW（预热份额）

**机制**
- 新增热泵 HP1，最高出水 65 °C；LTHW 改为气候补偿，例如 −3 °C 时 80/60，15 °C 时 60/45。
- 供水温度高于 65 °C 时，热泵只能预热回水，份额 = (65 − T_回)/(T_供 − T_回)；温和天可以全额。

**写明的内容：** HP1 的 `max_leaving_water_c`、容量和 COP 表、LTHW 补偿表、连接顺序。为公平必须写明顺序，见下文公平性。

**原工具：** 两种做法。
- (a) 能量母线：冬季过宽。
- (b) 按设计 80/60 给固定份额 25%：温和天过严。(b) 是一条看似有物理依据的固定规则，属判断型。

**后果：** (a) 冬季宣称的热泵供热超出可达份额；(b) 温和夜间少用了便宜的热泵热。

**隐藏日和可见日：**
- 隐藏日：(a) 在冬季热泵经济时出现，(b) 在春秋温和夜间出现。
- 可见日夏季 LTHW 已被发动机 HT 热占满，热泵不运行，不露面。

**为什么检查器漏掉：** 同 T1，没有报警渠道；(b) 的 MILP 也用同一个固定份额。

**独立性：** 与 T1 是同一洞察，只能二选一；与母管弱相关；与部件无关。

**公平性风险**
- 热泵上限本身是水温，没有 approach 二义。
- 但中间区间的份额取决于水力连接：CIBSE Module 265 说混合系统要用 low-loss header 解耦，两侧流量不同时份额不等于温度比。
- 所以必须写明"回水先过 HP1"。写明后就与 v10 预冷器同构，而 v10 那条 3/3 被推出。

**真实性出处**（子代理核实）
- Grantham Health Centre（NHS Property Services 项目，Hamworthy 案例）：室外 7–10 °C 时热泵抬高回水、锅炉为主；低于 7 °C 时热泵切除。
- CIBSE Module 265 和 Module 251 的 partially parallel mode：热泵预热回水，锅炉补最后的温升。
- 厂家资料里商用热泵最高出水约 55–75 °C，且随室外温度下降，例如 Mitsubishi CAHV 最高 70 °C；Trane、York 有条件表。
- Homerton、Kingston 的 HDP：NHS 现有锅炉按 70–80 °C 设计，热泵宜按约 50 °C 设计。

**实现草图：** 新增 heat_pumps 表、LTHW 补偿表、`order` 字段；原工具用固定份额；判分按补偿温度算份额。

**估计漏掉率：30–45%。**
- 硬伤是经济性【计算】：按现行电价，空气源热泵冬季的热成本约 13.8 p ÷ 2.3 ≈ 6 p/kWh，高于锅炉的 4.35 ÷ 0.905 ≈ 4.8 p/kWh，所以约束很少起作用。
- 改成以 LT 回路为热源的水源热泵才经济，但那样会和发动机、散热器检修耦合。

### J1 非冷凝锅炉的回水温度保护（可控量被当成结果）

**机制**
- B2 改为非冷凝锅炉，`min_return_c: 55`（防止烟气冷凝腐蚀），并写明带 shunt pump。
- LTHW 改为气候补偿，温和天的系统回水 <55 °C。

**原工具：** 把补偿曲线给出的系统回水当成锅炉进水，回水 <55 °C 时锁住 B2。

**后果：** shunt pump 把锅炉自己的出水回流到进口，进水温度不受系统回水影响，B2 可以运行。

**隐藏日和可见日：**
- 隐藏日：温和天、B1 检修、发动机加 PHE1 不够供热。
- 可见日 B2 全天检修，不露面。

**检查器：** 锁死 B2 时若发动机能顶上，只是更贵；若顶不上，会出现无解报警，母管就是靠这种报警被发现的。

**独立性：** 局部回流和系统设定是两回事，但同属"温度下限靠控制满足"，恰好是母管第二读法 R1（AC1 自带混水环）的反面，与母管明显正相关。

**公平性：** shunt pump 必须写明，写明后后果几乎是直接的（接近违反 L1）。厂家阈值 55、60、65 °C 都有。

**真实性出处**
- Grundfos 关于非冷凝锅炉 shunt pump 的白皮书：锅炉温度低于推荐的 60 °C 时 shunt pump 动作，防烟气冷凝腐蚀，65 °C 时停。已核实。
- ADL2 §5.11(e)：气候补偿。已核实。

**实现草图：** boilers[B2] 加两个字段；LTHW 补偿表；原工具锁 B2；隐藏日放在温和天、B1 检修。

**估计漏掉率：25–40%。**

### T3 工艺冷却环路的部分自然冷却

**机制**
- 新增 MRI 或 IT 用的工艺冷却环路 14/20 °C，干冷器 DC1（approach 4 K）与电制冷机 EC3 串联，回水先过 DC1。
- 干球 + 4 < 20 时，DC1 可以预冷回水，份额 = (20 − (db+4))/6。

**原工具：** 只在干球 + 4 ≤14 时才开 DC1。

**隐藏日和可见日：**
- 春秋干球 10–16 °C 时出现。
- 可见日干球 ≥19.9 °C，DC1 本来就不可用，两种规则一致。

**检查器：** 过严规则只是多花电，不报警；MILP 用同一规则。

**独立性：** 与母管物理上无关；与 T1、T2 是同一洞察。

**公平性：** 串并联必须写明，厂家做法不同：
- ICS 写的是水先经 free cooler，再进压缩机；
- Kaltra 写的是与压缩机并行补冷。
- 写明后与 v10 同构。

**真实性出处**（都是厂商营销页，本人核实）
- ICS Cool Energy（2017）：环境温度比工艺回水低约 1 °C 起开始部分自然冷却。
- Kaltra：环境温度低于回水温度时开始部分自然冷却。

**估计漏掉率：20–35%。**

### F1 午夜在运状态扩到有启动成本的 AC1（预见型）

**机制**
- 题面改一句：status.json 给出"午夜在运的设备"。
- AC1 加 `start_cost_gbp`（启动和停机稀释的热、电与磨损）。
- 可见日的 running_at_midnight 只有 GE1；隐藏日列出 AC1。

**原工具和自然实现：** 只按发动机处理午夜状态。

**后果：** 00:00 多收一次 AC1 启动费，并可能为了躲这笔费用改变 AC1 的调度。

**隐藏日和可见日：** 夏季 AC1 午夜在运的日子；可见日不出现。

**检查器：** 自造测试日的 running_at_midnight 一般只放发动机。

**独立性：** 与母管无关；与部件检修同属"可见日的列表值类型不代表全部"，正相关。

**公平性：** 要改题面；内行读法一致；但可能被审查看成针对 LLM 的小把戏（rubric 的 difficult 条目）。

**真实性出处：** BROAD USA 2021 培训资料（已核实）：
- p.17：停机稀释 30–90 min；
- p.31：冷却水温度对启动没有下限，对运行有下限。
- 启动成本的数值是合成的。

**估计漏掉率：15–30%。** 多数实现会按名字把初始状态泛化到所有设备。

## 3 其余候选（一句话加淘汰理由）

| 编号 | 候选 | 淘汰理由 |
|---|---|---|
| J2 | LTHW 补偿设定可人为上调，以驱动 LTHW 供热的低温吸收机 AC2 | 与母管同一洞察（天气重设的温度设定可改）；AC1 检修日会出现无解报警 |
| J3 | 发电机功率因数可调，多发无功缓解进口 kVA | G99 规定功率因数的控制方式和整定值写进并网协议、改动须 DNO 同意，有第二读法；写明可调范围则违反 L1 |
| J4 | LT 回路防凝露最低温度靠散热器风机保持 | 与母管同一洞察 |
| J5 | 冷冻水供水温度重设，扩大 AC1 的预冷份额 | 与 v10 预冷器同构，显式温度份额 3/3 被推出 |
| J6 | 发动机可短时低于连续最低负荷（MWM 表 10：305 kW，45 min 告警、60 min 停机，之后须 >120 min 高于连续限值） | 必须写新字段（L1） |
| B3 | AC1 热水出口温度与发动机 HT 回水上限的混水约束 | 要给 AC1 热水温差（显式）；现实设计用大温差机或 dump；夏季可见日就受约束 |
| B4 | HT 串联（AC1 在前），使 PHE1 进口低于 LTHW 供水温度 | 须写明顺序（v10 式提示），夏季可见日露面 |
| B5 | 冷却塔水侧免费供冷 | 需要冷母管，与 AC1 的 22 °C 互斥，是母管洞察的延伸；塔最低出水 21 °C 也挡住了 |
| B6 | 蓄热罐分层，可用能量随放热温度变化 | 新字段多，第二读法多 |
| B7 | LTHW 低 ΔT、回水过高使 CHP 排不出热 | 现象真实（CIBSE DS02、Module 130），但需要逐日回水温度输入（显式），夏季可见日即露面 |
| B8 | 冷凝锅炉效率随回水温度变化 | 要效率曲线（L1） |
| C2 | 吸收机停机稀释与再启动间隔 | 要新字段，厂家给 30–90 min 不一 |
| C3 | 检修结束后的启动、同步时间决定第一个可用半小时 | 要新字段（L1）；可见日 GE1 在 11:00 检修结束即露面 |
| C4 | 蓄热罐期末状态 | 不写期末条件则最低成本解会把罐掏空，不可唯一推出；写明则违反 L1 |
| C5 | 热、冷启动成本随停机时长变化 | 显式（L1） |
| D2 | 冷机馈线或变压器的局部 kVA（v20 C3） | 显式容量（L1），v20 已筛 |
| D3 | 停机发动机的缸套水预热器待机用电 | 写明即 L1，不写则无从推出 |
| D4 | 功率因数补偿电容组可投切 | 需求口径是否已含补偿有二义；作为设备写明则 L1 |
| D5 | 超容按 2×√(AI²+max(RI,RE)²) 计（SSEN、NGED 现行说明） | 与物理视在功率等价，不产生新后果 |
| E1 | 发动机燃料以 Nm³（0 °C）给出，计费按 15 °C 标准体积（差约 5.5%） | 真实（Jenbacher 的 Nm³ 为 0 °C/1013 mbar；燃气热量计算规例用 15 °C/1013.25 mbar），但可见日就生效、属知识题，题面"燃气低于表计"的症状直接指向燃气 |
| E2 | 银行假日按周末电价 | SSEN、NGED 的 DUoS 时段写明周一到周五包括银行假日；供应商合同口径未核实，不可唯一推出 |
| E3 | 线损系数 LLF | 只用于结算到 GSP，DNO 明说不影响 DUoS；账单是否放大未查到；写明即 L1 |
| E4 | 超额无功电费（每半小时超过 0.33×有功进口的部分） | 显式电价（L1） |
| F2 | 电气单线图上的配电盘检修 | 与部件检修同一洞察（可用来堵前缀捷径，但不独立） |
| F3 | DNO 网络限制写进 status 的新键 | 可见日没有该键就不公平；有则会被处理 |
| F4 | PV 预测超过逆变器额定，或夜间出现负 PV | 强交付物已按 min(预测, 逆变器) 处理；负 PV 不是明确合法的输入（v20 审计） |
| G1 | 可逆（2-pipe）热泵同一时刻只能制热或制冷 | York 资料写明 2-pipe 只能二选一，"reversible"一词即提示；按现行电价很少同时需要两种模式 |
| G2 | 混水阀检修使 AHU 只能靠 LT 热，发动机因此必须运行 | 与部件检修同一洞察 |
| G3 | PHE1 检修叠加冷天母管 | 两个现有难点的合取，不是新机制 |
| G4 | T1 与 LT 散热器检修的交互 | 会加强部件难点，但与之相关，不独立 |
| G5 | 单纯扩大系统规模或叠加规则 | K 的五条规则 16/16 被做对 |

## 4 参考清单

**本人打开核实（WebFetch，PDF 用 pdftotext 读取）**
- MWM, *Layout of Power Plants*（Installation directive），Customer Level，2025-12：§8.2.2 p.134，§8.3.2 p.138，§8.3.3 p.139，表 10 pp.55–56。https://www.mwm.net/files/upload/mwm/issuu/MWM-Layout-of-Power-Plants_US.pdf
- CIBSE CHP Group, *Datasheet 02: Spark-ignition gas-engine CHP*，2012-01，p.1。https://www.cibse.org/media/zcsofqea/datasheet-2-spark-ignition-engines.pdf
- Vital Energi, *Northwick Park Hospital* 案例，未标日期。https://www.vitalenergi.co.uk/case-studies/northwick-park-hospital/
- HM Government, *Approved Document L Vol.2*（2021 版，含 2023 修订），§5.10–5.11，p.36。https://assets.publishing.service.gov.uk/media/63d8edbde90e0773d8af2c98/Approved_Document_L__Conservation_of_fuel_and_power__Volume_2_Buildings_other_than_dwellings__2021_edition_incorporating_2023_amendments.pdf
- Grundfos, *Deep dive into the function of boiler shunt pumps in non-condensing boiler systems*，未标日期。https://api.grundfos.com/literature/Grundfosliterature-6153788.pdf
- BROAD USA, *2021 Service Webinar #2: Control Sequence and Interface*，2021，pp.17、24、31。https://broadusa.com/broad/wp-content/uploads/2021/06/2.-Control-Sequence-and-Interface-Webinar-2021.pdf
- ICS Cool Energy, *Reduce Energy Costs by up to 80% with Free Cooling*，2017-02-08 更新（厂商页）。https://www.icscoolenergy.com/reduce-energy-costs-70-free-cooling/
- Kaltra, *Free Cooling*，未标日期（厂商页）。https://www.kaltra.com/free-cooling
- CIBSE Journal CPD Module 130, *Applying CHP in heat networks*，Tim Dwyer，2018-07。https://www.cibsejournal.com/cpd/modules/2018-08-chp/
- AfPP, *Managing Extreme Heat in the Operating Theatre Environment*，2026；其中 HTM 03-01 为二手转述。https://www.afpp.org.uk/wp-content/uploads/2026/07/AfPP-Managing-Extreme-Heat-in-the-Operating-Theatre-Environment-3.pdf

**调研子代理打开核实**
- Hamworthy Heating, Grantham Health Centre 混合供热案例，未标日期。https://hamworthy-heating.com/case-studies/new-hybrid-heating-system-installed-at-grantham-health-centre
- CIBSE Journal：
  - Module 265（2026-05）：https://www.cibsejournal.com/cpd/modules/2026-06-da/
  - Module 251（Andy Pearson，2025-08）：https://www.cibsejournal.com/?p=34932
  - Module 219（2023-07）：https://www.cibsejournal.com/cpd/modules/2023-08-monobloc/
  - Kirkwood, *Designing efficient hybrid heat pump systems*（2021-10）：https://www.cibsejournal.com/technical/designing-efficient-hybrid-heat-pump-systems/
- Homerton Healthcare NHS FT, *Heat Decarbonisation Plan*，2023-12，Salix 托管。
- 厂家资料：Mitsubishi Ecodan CAHV PI sheet（2022）；Trane EDU-SLB071-EN（2026）；York YMAE-130 flyer（2023）。链接见子代理记录，均已打开。
- SSEN SEPD, *Use of System Charging Statement 2026/27* v1.1：§2.41–2.56，Annex 1 p.39。https://www.ssen.co.uk/globalassets/library/charging-statements-sepd/202627/sepd-duos-charges-2026-27_v1.1.pdf
- NGED East Midlands, 2026 年收费说明。https://commercial.nationalgrid.co.uk/downloads-view-reciteme/684677
- ENA, *EREC G99 Issue 2*，2025-03-10：§11.1.5–11.1.6，§12.5.1、§12.5.3，Annex D.4。https://dcode.org.uk/assets/250307ena-erec-g99-issue-2-(2025).pdf
- Joint Office, *Gas (Calculation of Thermal Energy) Regulations 1996* 汇编。https://gasgovernance.co.uk/sites/default/files/related-files/2024-05/thermal_energy_regs.pdf
- INNIO Jenbacher 经销商文件, *Technical Description JGS 416*，2024-03，爱尔兰 EPA 档案：Nm³ 为 0 °C、1013 mbar。https://epawebapp.epa.ie/licences/lic_eDMS/090151b2808ea723.pdf
- Elexon, *Line Loss Factors*。https://www.elexon.co.uk/operations-settlement/losses/

**未核实或没查到**
- Finning Rotherham Hospital 案例：页面打不开。
- ESBE VTC511、Paw RHT：只见搜索摘要。
- DCUSA Schedule 16 本体，以及 UKPN、NPg、ENWL、SPEN 自家的收费说明：均返回 403。
- 供应商合同对银行假日的口径：只见摘要。
- CIBSE AM17 正文：在登录墙后。
- NHS Net Zero Building Standard 的低温供暖条款：没找到，改用 ADL2。
- HSG274 Part 2、HTM 04-01 的条款，发动机从启动到满载的时间，Yazaki 热水 88/83 °C：负责这些的子代理因额度限制中断，本轮没有补查。
- Reddit、Eng-Tips 论坛：检索没有返回相关帖子。

**仓库记录（只读）**
- `HARDENING.md`；`results/checks-v20/`（含 audit）、`checks-v21`、`checks-v22` 的 README；`results/official-v10.md` 和 v10 交付物（预冷器 3/3 被推出）；13 份试跑交付物对回路温度和干球的 grep；上一轮的 `research-v23/REPORT.md`。
- 本轮草稿计算在 `scratchpad/research-v24/`。