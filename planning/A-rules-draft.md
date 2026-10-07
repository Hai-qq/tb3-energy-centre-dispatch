# 方案 A 规则草稿（供审阅）

这里是将来放进任务环境的三份文档的草稿：交易所规则书、组合技术模型、报价单格式。正文用英文写，因为题目是英文。参数的具体数值等你审完 `proposal-A.md` 的"初定参数"后再填。

题面 `instruction.md` 要你亲手写，这里只列它必须包含的要点。

## 需要你拍板的设计决定

1. **利润要求的写法。** 原方案写的是"不低于标准答案的 X%"，模型没法自测。建议改成：在隐藏的历史日上，平均利润不低于 θ 乘以同一批日子的"完全预知最优利润"。θ 用基线标定，初估 0.8。这样题面能写成明确的数字，模型也能在给定场景上自己算，而且不泄露标准答案的成绩。
2. **启动和停机那一小时，出力固定为最小出力。** 这是机组组合模型里常见的简化。
3. **边际成本的形式。** 第一版建议用"空载成本 + 常数边际成本"，边际成本由热耗率、气价、碳价算出。暂不用分段热耗率曲线。
4. **储能的两条规则。** 同一小时不能既充又放；放电按每 MWh 计损耗成本。
5. **时段和数据。** 第一版用小时制，价格取 2024 年历史日，来自 SMARD 公开数据；那时日前市场还是小时制。如果 pilot 太容易，再改成 15 分钟。
6. **关联块的成交规则。** 取父子闭合、每个子树盈余非负的子集里总盈余最大的那个。这是 EUPHEMIA 规则的简化，在价格接受者假设下可以唯一算出。
7. **第一版不引入"盈利的块订单也可能被拒"**（悖论拒绝），留作加深难度的手段。
8. **执行要求覆盖任意价格。** 价格上下限是 −500 和 4000 €/MWh，要求任意价格向量下都能执行。

## 题面必须包含的要点（你来写）

- 交付 `/app/orders.json`，格式见 `/app/market/ORDER_SCHEMA.md`，规则见 `/app/market/RULEBOOK.md`。
- **要求 1：** 对价格上下限内的任意价格向量，按规则成交后的头寸都能由组合按 `/app/portfolio/TECHNICAL_MODEL.md` 实际执行。
- **要求 2：** 在与 `/app/forecast/price_scenarios.csv` 同来源的隐藏历史日上，平均利润不低于 θ × 平均完全预知最优利润。
- 结尾固定句。

---

## RULEBOOK.md（草稿）

```markdown
# NSPX Day-Ahead Auction: Participant Rulebook

## 1 Scope

- One bidding zone and one delivery day split into 24 hourly periods H01–H24 (H01 is 00:00–01:00).
- The participant submits one order file. Clearing produces one price p_h per period with
  −500.00 ≤ p_h ≤ 4000.00 EUR/MWh.
- The participant is a price-taker: its orders never change clearing prices.
- Quantities are in MW with a 0.1 MW tick; 1 MW held for one period is 1 MWh.
  Prices have a 0.01 EUR/MWh tick.
- Sign convention: positive quantities sell (inject), negative quantities buy (withdraw).

## 2 Hourly orders

- At most one hourly order per period. An hourly order is a list of breakpoints
  (price, quantity), at most 32 of them.
- The first breakpoint price is −500.00. Prices strictly increase. Quantities never decrease.
- At clearing price p, the accepted quantity is the quantity of the last breakpoint whose
  price is less than or equal to p.
- A period without an hourly order has an accepted hourly quantity of 0.

## 3 Block orders

- A block has an id, a side (sell or buy), first_hour and last_hour (inclusive), one
  non-negative quantity per period in that range (at least one positive), and a limit price.
- Blocks are all-or-nothing: an accepted block delivers every quantity in its range;
  a rejected block delivers nothing.
- Surplus of a block at clearing prices p:
  - sell: S = Σ_h q_h · (p_h − limit_price)
  - buy:  S = Σ_h q_h · (limit_price − p_h)
- At most 50 blocks per order file.

## 4 Block acceptance

Every block is exactly one of the following.

1. Single block (no parent, children, loop partner or exclusive group):
   accepted if and only if S ≥ 0.
2. Linked family: blocks connected through `parent`. A block has at most one parent,
   a parent at most 6 children, a family at most 7 blocks, and there are no cycles.
   The exchange accepts the set A of family blocks that
   (a) contains the parent of every block in A,
   (b) gives every block in A a non-negative value when its surplus is added to the
       surplus of all its descendants in A, and
   (c) has the largest total surplus.
   Ties: more blocks first, then the lexicographically smallest sorted list of ids.
   The empty set is always allowed.
3. Loop family: exactly two blocks that name each other in `loop_with`. Both are accepted
   if their combined surplus is ≥ 0; otherwise both are rejected. Loop blocks have no
   parent, children or exclusive group.
4. Exclusive group: up to 24 blocks with the same `exclusive_group`. At most one is
   accepted: the block with the highest surplus among those with S ≥ 0; ties go to the
   smallest id. Exclusive blocks have no parent, children or loop partner.

## 5 Cleared position

X_h = accepted hourly quantity in h
      + Σ quantities of accepted sell blocks in h
      − Σ quantities of accepted buy blocks in h.

## 6 Delivery obligation

Company policy: the portfolio must physically deliver X_h in every period; imbalance is
not allowed. Whether a position can be delivered is defined in
/app/portfolio/TECHNICAL_MODEL.md.
```

## TECHNICAL_MODEL.md（草稿）

```markdown
# Portfolio Technical Model

Parameter values are in /app/portfolio/units.yaml.

## Thermal units

- In every period a unit is online or offline. Offline output is 0.
  Online output is between Pmin and Pmax.
- In a start-up period (online now, offline in the previous period) and in a shut-down
  period (online now, offline in the next period) the output equals Pmin.
- Between two consecutive online periods the output changes by at most the ramp limit
  (MW per period).
- Minimum up time: after a start-up in period h the unit stays online through h + MU − 1,
  or to the end of the day. Minimum down time: after going offline in period h it stays
  offline through h + MD − 1, or to the end of the day.
- The initial state counts: hours already online or offline before H01 count toward MU
  and MD, and the ramp and shut-down rules apply between the initial output and H01.
- Cost per online period: no-load cost + marginal cost × output, where
  marginal cost = heat rate × gas price + emission factor × CO2 price.
- Start-up cost depends on how many consecutive hours the unit was offline before the
  start, counting hours before H01: hot (< 8 h), warm (8–48 h), cold (> 48 h).

## Battery

- In every period: charge c and discharge d with 0 ≤ c, d ≤ Pmax; c and d are not both
  positive in the same period.
- SoC_h = SoC_{h−1} + η_c · c_h − d_h / η_d, with SoC_min ≤ SoC_h ≤ SoC_max.
  SoC_0 is given; SoC_24 must be at least the end target.
- Cost: degradation cost per MWh discharged.

## Delivery, cost and profit

- A position X can be delivered if a schedule exists that satisfies every rule above and
  has total thermal output + d_h − c_h = X_h in every period (tolerance 1e-6 MW).
- Execution cost of X: the minimum total cost over all such schedules.
- Profit on a price day: Σ_h p_h · X_h − execution cost of X.
- Perfect-foresight profit on a price day: the maximum of Σ_h p_h · y_h − cost(y) over all
  schedules y, with no order structure.
```

## ORDER_SCHEMA.md（草稿）

```markdown
# Order File Format (normative)

/app/orders.json is a JSON object:

{
  "delivery_day": "YYYY-MM-DD",
  "hourly_orders": [
    {"hour": <integer 1..24>, "curve": [[<price>, <quantity>], ...]}
  ],
  "block_orders": [
    {
      "id": "<1–16 characters from A–Z a–z 0–9 _ ->",
      "side": "sell" | "buy",
      "first_hour": <integer 1..24>,
      "last_hour": <integer first_hour..24>,
      "quantities": [<number>, ...],
      "limit_price": <number>,
      "parent": "<id>" | null,
      "loop_with": "<id>" | null,
      "exclusive_group": "<string>" | null
    }
  ]
}

- All numbers are finite. Prices are multiples of 0.01, quantities multiples of 0.1.
- `hour` values are unique. `quantities` has last_hour − first_hour + 1 entries.
- Block ids are unique. Every `parent` and `loop_with` names an existing block.
- Anything not listed here is invalid, and an invalid file fails the task.
```
