# 合成结构回归 v1

此处完全为人工合成数据，不是历史 gold、真实采集或性能数据。13 条事件与 36 个 P0 题号分别冻结在 synthetic-structure-v1.json 和 cases-v1.json。

本轮实际执行其中 24 项显式过滤结构检查，其余 12 项逐项报告 not_implemented，不能算通过。问题字段仅用于与规格题号对应；当前脚本把已冻结的 filters 交给真实 ASGI API，并不调用自然语言解析器。因此分类中文/英文理解、相对日期、消歧、语义融合、生成质量等完整题义仍未验收。

数据包含：09-08/09-10 边界、区间前后事件、未知与月级日期、DeepSeek 主体、比较提及负例、两主体共同正例、无关联第三方负例，以及无 embedding 的主体事件。每项都比较全部分页 ID 与精确 total，而非只比较第一页数量。R02 分别查询 MCP、SDK、Example-Agent；R06 强制每页一条。

从 backend 执行：

```powershell
uv run --frozen python ../scripts/check-structure.py
```

输出 docs/structure-regression-results.json，包含逐题状态、真实执行范围以及 false 的 PostgreSQL/历史gold/自然语言/模型验收标志。P1/P2 的 12 题不启用，不计为通过。

活动用例缺少 expected_event_keys、未知逻辑 key、数据集版本不匹配或题号重复时评估器直接报配置错误。主审已实际删除一项期望后执行，确认退出失败，未覆盖正常结果报告。

T01 的合成目标是 date_start/deepseek_no_embedding/date_end_both_entities，不能替代历史遗漏的两个事件。只有一个冻结合成摘录由演示仓储提供；不声称三个日期事件都有真实来源支持。E01 也不代表历史 DeepSeek 数据完整性。

下一切片的自然语言与检索规则见 ../queryplan-v1.md。
