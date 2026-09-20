# 从零开发的验收绑定

2026-09-15 用户确认没有旧站。旧站兼容、抓包及 T01/E01 历史样本不适用；
同名用例对新系统日期、实体、引用的要求仍保留。下列证据按层分开，不合并成质量通过率。

| 用例 | 当前可执行证据 | 边界 |
| --- | --- | --- |
| T01–T03、T10、C01–C06、E01–E07、N01–N02、N05、R02、R04–R06 | `scripts/check-structure.py`，24项显式筛选/完整分页结构断言 | 合成数据；不称为历史原站复现或语义召回通过 |
| T04–T09 | `backend/tests/test_acceptance_boundaries.py::test_relative_plan_exact_event_ids`，7组时钟/范围/确切事件ID场景 | 固定业务时钟，跨月跨年；不限于检查日期字符串 |
| E08 | `test_acceptance_boundaries.py::test_e08_ambiguous_and_fuzzy_entities_are_not_silently_confirmed`；`test_queryplanner.py` 澄清协议 | 歧义与模糊实体不会静默确认为单一实体 |
| N03 | `test_hybrid.py::test_embedding_failure_degrades_without_becoming_empty_scope`；真实PG本地模型测试 | 嵌入失败保留关键词范围；不把故障当无资料 |
| N04 | `scripts/check-database-unavailable.py` | 真实拒绝连接；v0.1.0要求启动故障关闭且根因为连接拒绝，不将故障当无答案 |
| N06 | `test_qa_service.py::test_citation_whitelist_rejects_urls_unknown_or_mismatched_indices`；流式失败用例 | 引用白名单/原文定位已验证；逐主张语义复核随专用Agent阶段实现，当前不标“语义已核验” |
| R01 | `test_retrieval.py::test_chinese_search_document_uses_overlapping_bigrams_and_ascii_tokens`；查询计划分类别名；真实BGE检索 | 中文词法与本地嵌入功能已实现；真实标注集Recall仍须单独报告 |
| R03 | `test_hybrid.py::test_hard_scope_is_complete_and_both_channels_are_isolated`；`test_retrieval.py` RRF | 两通道融合、去重与硬范围隔离 |
| D类归并/撤销 | `test_postgres_data_quality.py`、`test_postgres_event_write_concurrency.py` | 真实PG完整迁移；保留成员证据、来源计数和操作日志，禁止归并链 |
| F类专用Agent | `docs/research-agent-plan.md` | 用户指定下一阶段，不计本次遗漏 |

运行后端完整套件会执行上述 pytest 绑定；结构、计划、连接拒绝检查由
`scripts/verify-linux.sh --postgres` 执行。真实BGE另需显式启用
`RADAR_RUN_EMBEDDING_TESTS=1` 并指定固定模型目录/revision。

全部工程检查成功也不自动代表语义Recall、人工事件质量、公网部署及异机灾备通过。
