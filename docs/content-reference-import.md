# 参考数据整理与受控接入

本目录的可用数据由 [prepare-content-reference.py](../scripts/prepare-content-reference.py) 从只读的 `AI-Radar-参考/data` 生成。输入文件 SHA-256 与输出文件 SHA-256 均写入 [manifest.json](../data/content-reference/manifest.json)。复现命令（在仓库根目录）：

```powershell
python scripts/prepare-content-reference.py
python -m unittest discover -s data/content-reference -p test_reference_data.py
```

生成的数据只用于建议和人工审查，不是运行配置，也没有写入生产库。八处 CSV 错列已按原记录修复：分类 1 条、抓取策略 5 条、页面监控 2 条。抓取策略与页面监控保留 `advisory_only` / `requires_page_review` 标记，范围、重试和「verified」均不得直接转为调度设置或当前健康状态。尤其不能把抓取退避策略用于模型调用。

`categories.csv` 只有现有六个公开分类。`workflow_status.csv` 单独保留修正后的 `needs_review` 行；它是处理状态，不是第七类。`action_suggestions.csv` 对每个动作都要求上下文，单个词不自动确定事件分类。无可靠单一类别的动作留空。`entity_candidates.csv` 保留原类型、QID、描述、来源和原始别名供复核，但 `approved_aliases` 均为空，未核验 QID 不视为可信身份。benchmark 不强行映射；framework/protocol 建议为 technology，model_family 建议为 model。歧义项与 LangChain、LlamaIndex、Weaviate 标为 `needs_review`。`entity_quarantine.csv` 隔离 14 条明显错误的身份映射及其中文名和别名，它们不会出现在候选导入集。

`disabled_feed_seeds.json` 只有先前 XML 抽检的 Hugging Face 博客和 Groq 官方 changelog Atom。两者均为 `enabled:false`、`health:unverified`。Hugging Face 已在内置来源中；接入脚本按 URL 和名称跳过现有来源。Groq 提交记录还需检查实际变更说明，不能把每个 commit 直接当作事件。64 个来源没有整体导入；社区 Groq 转发源也没有代替官方源启用。

2026-09-19 生产接入结果：Hugging Face 已存在并跳过；Groq 官方 Atom 的三字段请求符合 SourceCreate，但当前生产 DNS 将 github.com 解析为非公网地址，API 返回 SOURCE_URL_UNSAFE（HTTP 422）。脚本将此记录为 deferred_unsafe，未导入 Groq、未启用来源。保持 URL 安全检查，不使用社区镜像绕过。

部署包只含生成数据时，用以下命令检查 manifest 与每个输出文件的哈希，再通过已有管理员来源 API **显式创建缺失的禁用源**：

```powershell
$env:RADAR_ADMIN_TOKEN = '<admin token>'
python scripts/prepare-content-reference.py --apply-prepared --apply-seeds --base-url http://127.0.0.1:8000
```

也可使用 HTTPS API origin。HTTP 仅接受 loopback；不要将管理员 token 发往局域网 HTTP 地址。脚本拒绝重定向，不跟随到其他主机。默认执行仅生成数据；不访问网络。显式接入会登录管理员会话、GET 来源表并 POST 缺失的来源，POST 后确认 `enabled:false`。它不会启用、探测或抓取这些源。真正启用前仍需逐源检查正文获取、健康与成本边界。

免费采集的入口 `backend/app/worker.py` 仅运行 `WorkerService` 的 `feed_discovery`、`article_fetch`，保存 `ArticleVersion` 并生成 `needs_review` 候选。`backend/app/scheduler.py` 仅为已启用来源排队。付费提取另由 `python -m radar.extract_events` 入口调用 `ExtractionService.run`，其中 `DeepSeekClient.complete_json` 发起模型请求；该命令必须保持单独停用。管理员「模型测试」接口以及公众研究助手也有各自的模型调用路径，不能作为采集验收的一部分启动。
