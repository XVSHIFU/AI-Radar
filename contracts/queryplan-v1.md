# 查询计划实施契约 v1

依据规格第 9–12、24 节；这是下一切片的接口约定，不表示已经实现或通过 36 题验收。

## 确定性理解

服务端注入 UTC aware Clock，再转换为请求 timezone；无效 IANA 时区返回统一 422。不依赖操作系统本地时区。列表仍使用现有包含两端的 date_from/date_to，计划内部可以额外展示 date_until_exclusive。

相对日期：今天=业务日，昨天=前一自然日，最近7天/最近一周=业务日减6至业务日，本周=周一至业务日，上周=上个完整周一至周日。明确历史区间永不改成当前日期。纯实体查询不加隐含日期。过去24小时在只有日精度时返回 clarification_required。

受控分类覆盖六种 Category 代码与中文名称，agent工具/agent与工具/智能体工具映射 agent_tool。未知分类参数拒绝；问题中无法可靠解析的限制保留为 free_text 或澄清，不能被悄悄删除。DeepSeek/deepseek/深度求索/全角兼容字符使用公共 NFKC 规范化及已确认别名；模糊拼写和多义别名返回澄清候选。

显式 UI 参数优先。若与当前问题的确定性日期/分类/实体冲突，返回公开 warnings 和采用条件；不得把两个区间合并扩大。P0 不从失败消息或前一轮任意文本推断会话指代，follow_up 明确未启用。

## 服务边界

QueryPlanner.parse(question, filters, timezone, clock, entity_resolver) -> QueryPlan。QueryPlan 为可序列化结构，含 intent、filters、constraints_origin、free_text、requires_clarification、clarification_candidates、warnings；不含 SQL 或隐藏推理。

/ask 复用计划与同一个 repository。规则足够时无需模型解释问题；没有模型配置只阻止生成，不阻止计划/完整范围查询。无资料仅来自已成功执行且确认为空的完整范围；数据库失败返回业务故障。

通道 A 完整枚举匹配 ID/content_version，不受 embedding 状态、向量 top-k 或单页 limit 限制。数据库快照结束后才调用模型，避免网络期间持有事务。上下文截断或预算不足时 scope_total 保持完整数量，coverage=partial，summarized_count 表示实际处理数量。任何跨页动态写入严格快照能力须单独实现并验证，不能仅凭 as_of 声称冻结。

通道 B 后续增加全文/向量/RRF；硬过滤在两个召回通道一致。无 embedding 时结构化和关键词仍工作。语义 top-k 不冒充精确总数。

## 合成结构回归

单独命名 synthetic-regression-v1，不当历史 gold。36 个启用题号完整建账，每题含 fixed_clock/timezone、输入问题/filters、期望计划、expected_event_keys/forbidden_event_keys、断言层级与状态。不能用题目占位或缺少期望自动通过。

T01 和 E01 先验证合成日期边界与完整实体集合；历史原站 ID 与来源支持仍未验收。实体集至少包含主体、中文别名、比较提及负例、无向量正例，all/any 都需正负事件。日期需含未知/月级负例、跨年昨天、UTC午夜时区边界。

N 类通过注入失败 provider/repository 验证错误分型、无证据与虚构引用拦截。RRF/profile 没有实现时，相应主用例保持未实现；不能把 SQL 字符串编译等同真实 PG 行为或语义质量。报告分别列出结构通过、真实证据未验收、尚未实现和 P1/P2 未启用数量。
