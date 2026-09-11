# 合成结构与查询计划回归

这里全部为人工合成数据，不能代替历史gold、真实采集、真实PG或模型质量验收。

- synthetic-structure-v1.json：13个事件，包含日期两端/范围外/未知/月级日期、主体/比较提及负例、多主体交集和第三方负例。
- cases-v1.json：完整36个P0题号；24项已绑定显式过滤结构检查，12项标为pending。逐项比较所有分页ID与精确total，不只看第一页数量。N01/N02使用中性ask_question提交已冻结过滤条件，question保留原场景名称；不靠删除否定词绕过未理解限制。
- query-plan-cases-v1.json：30项独立确定性计划HTTP检查，含固定Clock、相对日期/历史区间、NFKC/中文别名、实体内部与外部分类区分、显式all/any双向冲突、排他日期端点。它们不直接填充原36题尚未绑定的整套场景。

从backend执行：

```powershell
uv run --frozen python ../scripts/check-structure.py
uv run --frozen python ../scripts/check-query-plan.py
```

结果分别写docs/structure-regression-results.json和docs/query-plan-regression-results.json，含输入SHA256、逐项结果及验证层级。所有请求使用固定业务时钟；独立真实HTTP冒烟仍单独记录。P1/P2另12题未启用，不计通过。

活动结构用例缺少expected_event_keys、未知逻辑key、数据集版本或题号不匹配时直接报配置错误；已实际测试缺少期望的清单被拒绝。

T01合成目标是date_start/deepseek_no_embedding/date_end_both_entities，不能替代历史漏检的两个事件。只有一个冻结合成摘录可用于定位验证；不声称其他事件具有真实来源支持。E01也不代表真实DeepSeek资料完整。

日期计划等能力虽已有独立检查，原36题的完整结果集合、快照、故障、语义和生成质量仍需逐题绑定。当前P0整体保持NO-GO。
