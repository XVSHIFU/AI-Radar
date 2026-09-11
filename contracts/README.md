# 接口实施基线

以外部实施规格 v1.0 第 18–20 节为准。本文件补齐首轮协作字段，不声称兼容未知旧 fixture。

GET `/api/v1/events`: q/category/date_from/date_to/min_importance/limit/cursor，日期双端包含，limit 默认20最大100。entity_ids 为 UUID 数组，entity_match=all|any。返回 items,total,total_relation=eq,next_cursor,filters_applied,as_of,data_revision,request_id。稳定日期+ID排序；全库过滤；unknown 日期不进入严格日期范围。

Event: id(UUID), title_zh, summary_zh, category(model_release|agent_tool|framework_sdk|research|product|industry), importance(1..5), event_date(ISO date|null), date_precision(day|month|unknown), source_count, evidence_count, entities(string[]), content_version(int)。详情增加 evidence 数组与 articles 数组。

Evidence: id,event_id,article_version_id,paragraph_id,quote_text,source_url,title,verification_status,source_published_at,event_date。来源 URL 仅 http/https；不得伪造摘录。GET `/api/v1/events/{id}/evidence` 返回 items。

GET `/api/v1/stats`: total_events,total_sources,categories(代码到数量),scope='global',as_of,data_revision。GET `/api/v1/insights`: headlines(事件数组),tags(名称/数量数组),scope,as_of,data_revision。

GET `/api/v1/sources`: items（id,name,feed_url,enabled,health,last_success_at,consecutive_failures）。GET `/api/v1/ingest/runs`: items（id,status,started_at,finished_at,found,kept,cost,cost_status,error_summary），需要 Bearer 管理凭据。POST 同路径需要鉴权和 Idempotency-Key，接受 source_ids，返回202 {run_id,status}。

POST `/api/v1/ask`: {question,filters,timezone,answer_mode,client_request_id}。返回 answer,citations,execution_status,answer_status,query_plan_public,scope_total,retrieved_count,summarized_count,citation_count,coverage,as_of,filters_applied,request_id。未配置模型应明确503 MODEL_UNAVAILABLE；数据库失败503 RETRIEVAL_FAILED；真正空集 completed+no_answer。不得用模板答案冒充真实问答。

错误统一 {code,message,retryable,request_id,details?}。校验失败422。管理未配置503，缺失或错误凭据401。前端支持错误并保留条件。

SSE 新协议参考实施规格；模拟客户端与真实服务分别验收。meta→status*→token*→sources→done；异常 error→sources→done(failed)。EOF无done判失败；重试不得自动重新计费。

采集下一迁移约定：持久PG模式POST /ingest/runs接受已配置source_ids，Idempotency-Key绑定规范化payload；同键同payload返回已有运行，不同payload为409 IDEMPOTENCY_CONFLICT。GET返回真实found/candidates/versions/parser_failures及cost/cost_status；fixture或无执行配置503 INGEST_NOT_AVAILABLE，不伪造真实采集运行。管理未配置503 MANAGEMENT_UNAVAILABLE，有配置但凭据错误401。

采集金额用 Decimal 持久化，JSON cost 为十进制字符串或 null，前端不以浮点累加。cost_status=actual/estimated/unknown 分别显示实际/估算/未知。found=发现URL数，kept=已发布标准事件数；candidates=候选报道数，versions=本轮新增正文版本数，parser_failures/failed_jobs 分项显示。本切片不发布模型提取事件，kept保持0。

POST /api/v1/query-plan 已实现确定性计划，复用AskRequest，详见queryplan-v1.md；不调用模型。支持已确认实体、受控分类、相对自然日和ISO日期/区间。实体匹配按最长非重叠跨度，名称内部分类词不会追加硬过滤；UI显式entity_match优先且冲突有warning。

/ask复用同一计划：422 CLARIFICATION_REQUIRED、503 QUERY_UNSUPPORTED/MODEL_UNAVAILABLE/ASK_NOT_IMPLEMENTED均保留details.query_plan_public；真正结构化空集返回completed+no_answer。未知残余限制不会被清空后执行扩大范围。问答生成和真实SSE尚未实现；30项确定性计划通过不代表完整自然语言理解。

唯一OpenAPI快照为openapi/v1.json，由scripts/freeze-openapi.py检查或在主审批准结构变更后--write更新；删除了重复backend派生快照。
