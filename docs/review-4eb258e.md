# 双轴审查：确定性查询计划 4eb258e

固定范围55df2f2...4eb258e7e2e51e4e0cee2af2b641cd3e79b363f0。两名独立Astra审查只读固定源码，使用冻结fixture或模拟实体目录复现；未运行真实PG/模型。

| 问题 | Spec | Standards | 固定证据与影响 |
| --- | --- | --- | --- |
| 实体名内部分类词额外成为过滤 | P1 | P2 | queryplanner.py:155–167；纯“示例研究团队”增加research分类，冻结UI语料实体26条被缩为5条 |
| 显式entity_match被推断值覆盖 | P1 | P2 | queryplanner.py:194–198；UI any+问题“DeepSeek 和 示例研究团队”变all且无warning，可能错误空集；反向也会扩大范围 |
| 短实体在长实体名内重复命中 | P1 | P2 | postgres_repository.py:109–115，fixture_repository.py:59；Meta/Metaflow或Qwen/Qwen3同时加入默认all，添加用户未请求的实体 |
| 最大合法日期的排他端点溢出 | — | P2 | queryplanner.py:216；date_to=9999-12-31触发OverflowError，API只捕获ValueError，逃出统一错误响应 |

两轴分级分别保留，重叠问题不相加当独立缺陷数。主审另要求单ISO日期和非法单日的确定性处理、intent枚举structured_summary与规格一致。

已确认的良好边界：未知free_text在检索前被拒绝，组合Filters已再校验；未发现用户文本直接生成SQL。httpx已移入运行依赖，根独立no-dev环境成功导入API/worker/scheduler，pytest未安装。

原24项计划HTTP检查只断言实体ID，未断言隐含分类。主审补category=null及纯实体名用例后扩大为25项，固定4eb为22/25，三项复现分类污染。原显式过滤36题中的N01/N02场景标题不作为自然语言能力验收，增加中性ask_question后保留原q/date及空集断言，结构24/24不变。后续修复须重新检查固定提交。

## 最终固定复验

59f57cf修复原3项实体漏检及日期上界；复验又发现外部“研究”分类被全局屏蔽、显式entity_ids分支遗漏mode冲突提示两个P2。2eeb330改为实体实际命中跨度遮罩并统一显式mode处理，固定4项复验4/4通过：纯TEAM无分类、TEAM的研究为research，以及有UI实体ID时any/all双向冲突保留UI值并返回warning与request来源。

根独立计划清单扩为30项，修复前27/30，最终30/30。后端全量94/94，前端14/14，统一11组检查通过。上述审查问题已关闭；真实PG/模型/完整P0仍未验收。
