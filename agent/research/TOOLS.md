# 工具合同

本文件是实现合同；列出工具不等于已上线。工具注册、Schema 验证与授权代码是最终控制点。所有工具请求关联服务器签发的 run_id 和 scope_id，客户端或模型不能自行替换作用域。

| 工具 | 模型可选入参 | 服务器输出 |
| --- | --- | --- |
| resolve_entities | 名称、允许的类别 | 稳定 ID、歧义候选 |
| search_events | 关键词、分页游标、允许的排序 | 范围内事件摘要、精确总数、as_of、覆盖信息 |
| get_event_evidence | 本轮范围内 event_ids | 冻结段落、版本、citation ID；不任意抓 URL |
| aggregate_events | date/category 维度、允许粒度 | 数据库精确聚合、dataset_id、日期口径 |
| compare_periods | 两个明确日期区间、同一筛选 | 数量、差值、零基期/重叠/资料缺口，以及绑定本会话/run/scope 的 dataset_id、字段、单位和日期口径 |
| build_chart | 本轮 dataset_id、允许图型 | 经过校验的图表描述与原数据范围 |
| run_python | 本轮 dataset_ids、分析代码 | 受限 stdout、结构化数值、artifact IDs、执行状态 |
| load_research_skill | 已注册 skill 名称 | 只读技能正文与版本，无路径、URL 或脚本执行 |

scope_id 不暴露为模型可修改的普通筛选字段；服务端逐次注入。跨期比较的两个区间须包含于已授权范围，否则返回 SCOPE_CHANGE_REQUIRED 并交由用户发起新范围请求。某对象曾出现在历史里，不代表本轮可读取。

所有入参禁止额外字段；UUID/枚举/日期/长度/行数/数量必须校验。数据集、产物绑定匿名会话和运行 ID，并设置到期时间。工具调用序号由服务器递增，重复 call_id 不再执行。

错误分类：INVALID_ARGUMENT / SCOPE_CHANGE_REQUIRED / NOT_FOUND / TOOL_UNAVAILABLE / EXECUTION_TIMEOUT / RESOURCE_LIMIT / BUDGET_EXCEEDED。错误供模型决定是否给出部分结果，不包含数据库连接、完整异常栈、环境变量或宿主路径。

模型不能提供 SQL、容器配置、宿主文件路径、镜像名、网络策略、命令或 API endpoint。Python code 是唯一允许的代码字段，只交给专用沙箱，不在 API/pi 进程内执行。所有工具受服务端预算控制；load_research_skill 只读且最多 2 次/轮，不另触发模型调用。
