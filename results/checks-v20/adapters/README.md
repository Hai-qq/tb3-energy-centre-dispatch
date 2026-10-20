# 对手适配审计

C1、C2、C4 的两份历史通过工具均直接运行原交付路径，未作任何读取或语义修改。新 JSON 字段被现有 json.load 正常接受；没有新增输出字段。每次矩阵中 `source_sha256` 保存实际执行源码散列。下面两个 .diff 是有意为空的零适配补丁。

- `strong-v16.diff`: v16 第 2 场 Claude，零改动。
- `strong-v19.diff`: v19 第 2 场 Claude，零改动。

`audit/arbitrage/diagnostic-direction-fixed/` 内另外保存了仅修购售方向的因果诊断副本。它们是增加正确物理理解的修复，不是格式适配，也不计入击破结果。
