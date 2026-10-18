# 可见文件逐项差异（相对固定 v19）

本文件只记录可见文件；参考模型、标准答案和测试的变化见各候选 `MODELS_SHA256.json`。所有候选均保留原 `instruction.md`。参数是合成工程场景，来源支持机制或量级，不是声称某医院的实测铭牌或真实合同。

完整文件包在各候选的 `visible/`；两位读者和盲修实际看到的文件由 `VISIBLE_SHA256.json` 固定。C2/C4 的参数在任何隔离预检之前选定；其初始取值另有 `INITIAL_VISIBLE_SHA256.json`。后来从初始值重建的 `initial-visible/` 已逐文件匹配原散列，重建经过在 `INITIAL_RECONSTRUCTION.json` 明示，不能误称它们一直以原文件形式保留。

## 逐字段清单与工程出处

| 候选 | 可见 JSON 路径 / 项目 | 原值 → 冻结值 | 真实性及解释范围 |
|---|---|---|---|
| C1 | `supply.electricity.import_rates_p_per_kwh.weekday[0].rate`，00:00–07:00 | 13.8 → 7.0 p/kWh | [Octopus 商业分时采购公式](https://octopus.energy/help-and-faqs/articles/how-calculate-prices-shape-shifters-agile/)支持采购价随批发价格变化；7p 是合成值 |
| C1 | 同一价格表 `weekend[0].rate`，00:00–07:00 | 13.8 → 7.0 p/kWh | 同上 |
| C1 | `supply.electricity.export_rate_p_per_kwh` | 5.9 → 12.0 p/kWh | [Drax 商业 CHP PPA](https://energy.drax.com/sell-power/)支持独立的固定/浮动/定制出口合同；12p 是合成值 |
| C2 | `supply.gas.entry.id` | 新增 `GAS-IN` | [NHS Foresterhill 能源中心](https://www.gov.scot/publications/annual-state-nhsscotland-assets-facilities-report-2012/pages/9/)存在额定能力的燃气 booster；不是声称两站设备相同 |
| C2 | `gas.entry.maximum_standard_m3_per_hour` | 新增 550.0 | 合成站点的共同标准体积供气上限，不把工作体积铭牌当成标准体积 |
| C2 | `gas.entry.standard_temperature_c`、`standard_pressure_bar_absolute` | 新增 15.0°C、1.01325 bar absolute | [National Gas 标准体积定义](https://data.nationalgas.com/technical-guidance)；字段直接定义标准状态，不使用室外天气再次换算 |
| C2 | `gas.entry.gross_calorific_value_mj_per_standard_m3` | 新增 39.6 MJ/Sm³ | [National Gas 方法文件](https://www.nationalgas.com/sites/default/files/documents/Gas%20Demand%20Forecasting%20Methodology%202020_v1.pdf)，印刷页 54 的参考值；并非每一日实际交付 CV |
| C2 | `gas.entry.supplies` | 新增 `[GE1, GE2, B1, B2]` | 唯一列出共享入口的四个消耗者；发动机 net/gross 数据及锅炉效率原值均不变 |
| C3 | EC1、EC2、AC1 的 `electrical_power_factor`、`electrical_power_factor_control` | 各新增 0.9、`fixed, lagging` | 合成固定功率因数；不默加至已含全站负载的 kvar 预测 |
| C3 | `electrical_distribution.feeders[0]` 的 `id`、`rated_kva`、`loads` | 新增 `CH-MCC`、400.0、`[EC1, EC2, AC1]` | [NHS HTM 06-01](https://www.england.nhs.uk/wp-content/uploads/2021/05/Health_tech_memo_0601.pdf) §10.45 支持大型冷机站独立变电供电；本候选仍仅为初筛 |
| C3 | 上述馈线 `other_load_kw`、`other_load_kvar` | 各新增 0.0 | 排除未给出的其他支路负载；并未认证“rated”一定排除短时超载的解释 |
| C4 | `heat_exchangers[0].id`、`primary_circuit`、`secondary_circuit` | 新增 `PHE1`、`engine_ht`、`lthw` | [AEL 医院 LTHW 说明](https://aelheatexchangers.co.uk/central-heating-system-break-heat-exchangers/)支持这一已有换热器用途；连接端点与旧热路一致 |
| C4 | `primary_maximum_water_flow_kg_per_s` | 新增 20.0 kg/s | 合成最大一次侧流量；读者预检前已弃 15 kg/s 的不可行参数 |
| C4 | `water_specific_heat_kj_per_kg_k` | 新增 4.18 | 模型明示的恒定水比热；[Alfa Laval 换热理论](https://www.alfalaval.com/globalassets/documents/microsites/heating-and-cooling-hub/alfa_laval_heating_and_cooling_hub_the_theory_behind_heat_transfer.pdf)支持质量流量×比热×同侧温降的关系，不声称 4.18 是所有温度下的精确实测值 |
| C5 | `heat_circuits.ge1_lt.to` | 增加 `LT radiator 3` | NHS 同类并联 CHP LT 散热器的精确一手出处未核实；此真实性缺口是淘汰理由之一 |
| C5 | `heat_circuits.ge1_lt.branches` | 新增 `parallel, individually isolatable` | 明示并联、独立隔离，防止把多出口列表本身误当成唯一拓扑证明 |
| C5 | `lt_radiators` | 新增 radiator 1/2/3 三项，每项 `maximum_heat_rejection_kw=250.0` | 合成且足以容纳单发动机全 LT 排热；仅击破 A16，A19 全过 |

表中短路径省略了实际文件名层级；确切拼写、完整对象和唯一的文本差异以下方 diff 为准。除了上述字段，五个候选的可见日期、负荷、天气、检修、程序代码和 instruction 均未改变。C3 后续 EC1 独立馈线参数扫描位于 `remaining-screens/`，不混同于冻结的三冷机 400 kVA 可见包。

## C1

变化文件：app/data/supply.json。

完整逐字节文本差异：[visible.diff](candidates/c1/visible.diff)。

## C2

变化文件：app/data/supply.json。

完整逐字节文本差异：[visible.diff](candidates/c2/visible.diff)。

## C3

变化文件：app/data/plant.json。

完整逐字节文本差异：[visible.diff](candidates/c3/visible.diff)。

## C4

变化文件：app/data/plant.json。

完整逐字节文本差异：[visible.diff](candidates/c4/visible.diff)。

## C5

变化文件：app/data/plant.json。

完整逐字节文本差异：[visible.diff](candidates/c5/visible.diff)。

