# 查询计划实施契约 v1

依据规格第 9–12、24 节。确定性计划切片已实现并有30项独立HTTP检查；以下通道A完整快照、通道B和模型生成仍属后续边界，不表示通过36题完整验收。

## 确定性理解

服务端注入 UTC aware Clock，再转换为请求 timezone；无效 IANA 时区返回统一 422。不依赖操作系统本地时区。列表仍使用现有包含两端的 date_from/date_to，计划内部可以额外展示 date_until_exclusive。

相对日期：今天=业务日，昨天=前一自然日，最近7天/最近一周=业务日减6至业务日，本周=周一至业务日，上周=上个完整周一至周日。明确历史区间永不改成当前日期。纯实体查询不加隐含日期。过去24小时在只有日精度时返回 clarification_required。

受控分类覆盖六种 Category 代码与中文名称，agent工具/agent与工具/智能体工具映射 agent_tool。未知分类参数拒绝；问题中无法可靠解析的限制保留为 free_text 或澄清，不能被悄悄删除。DeepSeek/deepseek/深度求索/全角兼容字符使用公共 NFKC 规范化及已确认别名；模糊拼写和多义别名返回澄清候选。

显式 UI 参数优先。若与当前问题的确定性日期/分类/实体冲突，返回公开 warnings 和采用条件；不得把两个区间合并扩大。仅对下文定义的有界 user 历史启用确定性 follow_up；不从失败消息、assistant 内容或无明确指代的任意文本推断会话条件。

## 服务边界

QueryPlanner.parse(question, filters, timezone, clock, entity_resolver, history) -> QueryPlan。QueryPlan 为可序列化结构，含 intent、filters、constraints_origin、free_text、requires_clarification、clarification_candidates、warnings、history_turns_considered、history_user_turns_used、event_targets；不含 SQL 或隐藏推理。

/ask 复用计划与同一个 repository。规则足够时无需模型解释问题；没有模型配置只阻止生成，不阻止计划/完整范围查询。无资料仅来自已成功执行且确认为空的完整范围；数据库失败返回业务故障。

通道 A 完整枚举匹配 ID/content_version，不受 embedding 状态、向量 top-k 或单页 limit 限制。数据库快照结束后才调用模型，避免网络期间持有事务。上下文截断或预算不足时 scope_total 保持完整数量，coverage=partial，summarized_count 表示实际处理数量。任何跨页动态写入严格快照能力须单独实现并验证，不能仅凭 as_of 声称冻结。

通道 B 后续增加全文/向量/RRF；硬过滤在两个召回通道一致。无 embedding 时结构化和关键词仍工作。语义 top-k 不冒充精确总数。

## 合成结构回归

单独命名 synthetic-regression-v1，不当历史 gold。36 个启用题号完整建账，每题含 fixed_clock/timezone、输入问题/filters、期望计划、expected_event_keys/forbidden_event_keys、断言层级与状态。不能用题目占位或缺少期望自动通过。

T01 和 E01 先验证合成日期边界与完整实体集合；历史原站 ID 与来源支持仍未验收。实体集至少包含主体、中文别名、比较提及负例、无向量正例，all/any 都需正负事件。日期需含未知/月级负例、跨年昨天、UTC午夜时区边界。

N 类通过注入失败 provider/repository 验证错误分型、无证据与虚构引用拦截。RRF/profile 没有实现时，相应主用例保持未实现；不能把 SQL 字符串编译等同真实 PG 行为或语义质量。报告分别列出结构通过、真实证据未验收、尚未实现和 P1/P2 未启用数量。

## 第一实现切片公开接口（主审确认）

新增 POST /api/v1/query-plan，复用 AskRequest 请求结构；响应 QueryPlan 包含：intent、filters（现有Filters）、timezone、business_date、date_until_exclusive（可null）、constraints_origin、free_text、requires_clarification、clarification_candidates（对象列表，含label/entity_id可null）、warnings（字符串列表）、entity_roles（固定subject/product）、data_mode、request_id。

提供可通过FastAPI dependency override注入的 get_clock，返回UTC aware datetime；生产用实际时钟，测试用固定时刻。完整公开计划在 /ask 成功响应 query_plan_public 内返回；需要澄清返回 HTTP422、code=CLARIFICATION_REQUIRED、details.query_plan_public；模型未配置或未实现返回503并同样带details.query_plan_public，已解析约束可见。自由文本语义检索未实现时不能先查一个扩大范围再说无资料，应明确QUERY_UNSUPPORTED或澄清。

实体来自仓储统一的已确认规范名/别名目录，不把生产DeepSeek UUID硬编码为fixture ID。不自动纠正模糊拼写。第一切片允许明确标记未支持的表达，但已识别日期/实体不能被静默丢弃；UI显式字段优先，冲突有warnings。公开独立计划端点不触发模型调用。

此切片不实现模型生成、向量、全文排名或完整集合快照；对应验收仍未完成。结构化查空时必须基于计划过滤；有残余限制未理解时不能输出no_answer。

## 有界追问与事件附件

AskRequest 可选 history 最多 6 条、合计最多 12000 字符；单条 content 为 1..4000 字符，role 只接受 user/assistant，并可携带该 user 轮当时的 Filters 冻结快照。当前轮只在窄明确指代下查找最近一个有关 user 轮。字段优先级固定为显式 filters > 当前问题 > 历史。assistant 轮不参与筛选、事实或证据推断；公开 metadata 与 warning 说明是否使用了历史，不能静默接收后忽略。

历史 user 轮中的“今天/昨天/最近7天/最近一周/本周/上周/过去24小时”仅在同一轮 filters 已冻结完整绝对 date_from/date_to 时可继承。没有冻结日期时可继承同轮其他确定性约束，但日期本身不按当前 clock/timezone 重解释，计划 requires_clarification=true 并给出公开 warning。最近有关 user 轮若仍有 free_text、歧义或其他待澄清内容，可以公开其确定部分，但必须继续 requires_clarification，不能把剩余约束静默丢弃。历史与当前单侧日期合并后仍执行完整日期范围校验，并重新计算 date_until_exclusive。

AskRequest 可选 event_ids 最多 3 个 UUID。服务端将它规范到 Filters.event_ids，与其他硬过滤取交集，并从权威 repository 读取事件标题和发布可见性。QueryPlan.event_targets 对每个附件公开 matched、filtered_out 或 not_found。任一附件非 matched 时计划要求澄清；/ask 返回422 CLARIFICATION_REQUIRED。有效非空附件仍遵守现有生成边界：无模型配置返回503 MODEL_UNAVAILABLE，即使配置模型也因本切片未实现生成而返回503 ASK_NOT_IMPLEMENTED。
