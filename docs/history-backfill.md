# 2026 年 8–9 月历史回填与 Flash 提取

本次用户授权使用 DeepSeek Flash，依赖 key 自带的 10 元额度，不另作费用计算。
范围为 2026-08-01 至当天（最多 2026-09-30），Asia/Shanghai，起止日包含。

## 已运行

- 官方来源：Hugging Face、arXiv cs.AI、Google Research、AWS Machine Learning、NVIDIA Technical Blog、OpenAI、Anthropic、DeepSeek。
- 2026-09-15 首次发现 603 条来源/URL 记录：30、270、13、140、51、89、8、2。
- RSS 可覆盖起始日的来源直接筛选；AWS 使用分页新闻归档；Anthropic 解析官方新闻归档；DeepSeek 使用带明确日期的更新链接。
- arXiv 历史 API 受到 429 限流，目前 270 条来自已存当天 RSS，不能代表两个月完整论文覆盖。
- OpenAI 部分正文返回 403，保留失败记录；不绕过站点访问限制。
- 首次小批量 3/3 发布；随后 80 篇批次中 62 发布、10 过滤、8 校验失败。快照共 65 条事件、299 条引用，全部引用匹配冻结原文。
- API readiness、事件列表、统计接口均 HTTP 200，synthetic=false。详见 history-live-validation.json；后台运行后数量会继续变化。

## 自动化与手动续跑

Ubuntu：/home/xvsf/ai-radar。页面：http://192.168.194.129:5173/ （不要带 ?demo=1）。

```bash
bash scripts/history-pipeline.sh discover
bash scripts/history-pipeline.sh extract
systemctl --user list-timers 'ai-radar-history-*'
journalctl --user -u ai-radar-history-discover -n 20
journalctl --user -u ai-radar-history-extract -n 20
```

discover 每小时扫描；extract 每次结束后 10 分钟再处理最多 80 个版本。
独立 worker 按来源冷却、按默认 10 秒任务间隔保存原文。锁避免同一脚本重入。
旧的无日期范围 scheduler 已停用。重装服务后应再运行
`bash scripts/install-history-timers.sh`，以恢复本次日期范围流水线。
抓取结果缓存 24 小时；CLI --refresh 可显式重新读取归档。

## 正确性与边界

- 复用不可变原文，重复扫描不重复创建来源发现/任务；失败状态不会被后续扫描改成成功。
- Flash 版本级唯一调用登记；401/402/余额不足持久停止模型调用；未知超时不自动重付。
- 仅 Flash，关闭 thinking，JSON 模式；中文字段、分类、实体、逐字引文校验后发布。
- 这里的事件日期取来源报道发布日期，并不保证等于报道中提到的实际发生日。缺失日期不补造。
- 引文保持 unverified：字符串命中是结构校验，不等于事实与语义已人工审定。
- 目前一个文章对应一个提取事件；跨文章语义合并、全网穷尽采集、人工历史 gold 验收尚未完成。
- 公开研究助手真实模型问答、向量检索未在本次启用。
- 校验失败的模型输出不自动重试；调整解析后需受控重新处理，避免重复付费。
- 密钥只在 Ubuntu .env，0600；Git 不含凭证。更换/补充 key 后，旧认证/额度失败闸门需人工确认后解除。

## 验证

合并后真实 PostgreSQL 与全部后端测试 184 项通过；Ruff/mypy 通过。
双轴审查发现并修复 run 行锁与失败终态覆盖问题；补充重跑失败状态回归。

0006 数据库备份已在独立临时库恢复成功；主库不受恢复演练影响。
