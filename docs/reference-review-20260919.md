# 参考调研轻量审查（2026-09-19）

输入目录：`E:\AI-AGENT\AI-Radar-Implementation-Spec\AI-Radar-参考`。本轮只读审查，没有修改原始调研资料，也没有把参考数据写入生产数据库。

结论：**可以择要使用，不能按“全部核验、可直接入库”整包导入。** 检查覆盖全部 CSV 的结构/数量、所附脚本的关键判断、几个官方页面与实体链接、两个 feed 的一次实际 XML 抽样。没有重新抓取全部 64 个源或运行外部脚本。

## 数据检查

| 文件 | 实际结果 | 采用方式 |
| --- | --- | --- |
| sources.csv | 64 行、16 列，结构正常 | 来源候选清单；导入时按 URL 与已有来源去重，默认禁用，不照抄 verified 为当前健康状态 |
| validation_report.csv | 64 行；首次 parse=ok 共 64，repeat_ok=2/2 共 63，1/2 共 1 | 历史可达性线索，不能代替生产环境连续性和正文验证 |
| entities_seed.csv | 67 行，其中 58 行填有 QID | “填有 QID”不等于实体匹配正确；有明显错误，不整体导入别名 |
| category_taxonomy.csv | 六个业务分类 + needs_review；第 8 行多一列 | 前六个代码兼容；needs_review 作为待审状态；保留既有中文 UI 名称 |
| action_taxonomy.csv | 21 行、5 列，结构正常，已有歧义标记 | 用于规则建议，不把“发布/支持”等单个词当作确定事件分类 |
| source_fetch_policies.csv | 8 行，5 行列数错误（第 2–6 行） | 仅作文字建议；重建逐源、有数字上限的策略，不直接当运行配置 |
| first_party_monitors.csv | 10 行，第 2、9 行 notes 未正确引用导致多列 | 修复后仍逐页判断公告区域，不因 HTTP 200 就视为可用公告源 |
| query_dictionary.txt / ai_feeds.opml | 作为词表及订阅候选资料 | 词表按当前 tokenizer 导入约定适配；OPML 不作为第二份独立核验证据 |

共发现 **8 个错列记录**。`source_fetch_policies.csv` 首行数据既有未引用的范围列表，也存在表头与行内展示名称不匹配，不能简单补个逗号后就执行。抓取策略中的“3 次退避”不适用于模型生成，模型调用仍不自动重试。

报告中 S034 Reddit r/LocalLLaMA 的 repeat_ok 为 1/2，S063 MiMo Releases 条目数为 0。S001/S002 的原核验报告条目数和首条内容相同，应作为疑似入口别名进行实际 canonical URL 核对，不能算两份独立来源。

所附 `validate_feeds.py` 的 `stable = len(set(...)) <= 2` 在只有两次抓取时总为 True，所以 `stable_titles` 不能证明稳定性；63/64 只表示两次均成功的数量。脚本也没有执行文档宣称的新鲜度阈值判定。空 feed、旧内容、短时失败与长期失效应分开记录。

## 实体错误与适配

至少 14 行的 QID 描述明显偏离目标实体：JAX、Claude、ERNIE、GLM、Gemini、Gemma、Hunyuan、Llama、BAAI、Huawei Ascend、MiniMax、Perplexity、Runway、xAI。判断依据包括资料自身的 wikidata_desc；其中三项已回查原站：

- JAX → Q1111626，实际是法国市镇 Jax。[Wikidata 原项](https://www.wikidata.org/wiki/Q1111626)
- Gemini → Q8923，实际是双子座。[Wikidata 原项](https://www.wikidata.org/wiki/Q8923)
- MiniMax → Q1058962，实际是电视频道 Minimax。[Wikidata 原项](https://www.wikidata.org/wiki/Q1058962)

这些行连同由错误实体带出的中文名和别名一起隔离，不仅清空 QID；未复查的其余 QID 不标为本轮已验证。LangChain、LlamaIndex、Weaviate 等还需区分公司与框架/产品。

参考类型包含 benchmark/framework/model_family/protocol；现有提取合同只接受 company/person/product/model/organization/technology。框架/协议可映射到 technology、模型家族映射到 model；benchmark 与公司/产品混同项逐项确认，保留原类型供追溯，不能直接向现有枚举新增值。

## 有限在线抽查

| 入口 | 本轮观察 | 结论 |
| --- | --- | --- |
| https://huggingface.co/blog/feed.xml | HTTP 200，XML 根 rss，862 条 item | 可采用为接入候选；条目数只是本次快照，不代表篇篇含完整正文 |
| https://github.com/groq/groq-changelog/commits/main.atom | HTTP 200，合法 Atom，20 条 entry | 可采用；需从提交记录定位真正变更说明，不把每次提交等同于产品事件 |
| https://github.com/groq/groq-changelog | 仓库说明为 Groq 官方 API/SDK changelog | 支持其作为官方来源；不证明社区转载 feed 同样新鲜 |
| https://api-docs.deepseek.com/news/ | 本轮读取结果主体是 Your First API Call，存在 News 导航 | 不认定该路径就是可直接监控的公告列表；接入时定位真实 News 页面和内容区 |
| https://platform.minimaxi.com/document/Announcement | 本次网页读取工具未取得内容 | 未确认；不能推断网站不存在，也不能复用“已确认公告页”结论 |

Groq 官方属性依据[仓库说明](https://github.com/groq/groq-changelog)；DeepSeek 路径观察依据[实际读取页面](https://api-docs.deepseek.com/news/)。XML 抽样在本地用标准库 HTTP 请求与 XML 解析完成，单源一次，15 秒超时、2 MiB 上限；不调用模型。网页工具对 HF 的 RSS 内容类型不支持，已用 XML 解析检查代替，不把工具不支持当成源失效。

## 本轮纳入整合方案

采用：官方源优先、社区中转标记、聚合线索回原站、去重后处理、动作与分类词表、来源最近成功时间、限定公告区域的页面变化检测。

暂不采用：错误实体映射、未经适配的 CSV 策略、所有官方首页均可直接作为公告源的结论、普遍无 RSS 的绝对表述、将第二次抓取成功等同长期稳定。FOFA 只是可选发现线索，不为这次节费流程引入付费依赖。

原 v1.0 规格中的证据定位、日期区分和幂等思想继续使用；它不覆盖当前用户已确认的 5 次公众额度、同机备份、手动优先和无自动付费重试等新决定。下一步安排见 [内容生产整合方案](content-pipeline-plan.md)。
