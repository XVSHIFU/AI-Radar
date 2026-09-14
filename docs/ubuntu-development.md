# Ubuntu 数据库与采集开发记录

2026-09-14，用户授权将开发转到 Ubuntu，并明确本阶段先完成数据库和采集，暂不接入模型。

## 环境与入口

- SSH：`xvsf@192.168.194.129`；工程：`/home/xvsf/ai-radar`，分支 `ubuntu-integration`。
- 页面：http://192.168.194.129:5173/；API 仅监听本机 8000，经前端代理访问。
- PostgreSQL 16 + pgvector 0.8.6：Docker Compose 项目 `ai-radar`，主机仅监听 127.0.0.1:55432。
- 镜像摘要：`pgvector/pgvector@sha256:ccc6e83d6e35e931dc7c5def2022729d5a6c370318d099181995567ff1fb4d6b`。
- Python 3.12.13、uv 0.11.16、Node 22.22.1、pnpm 11.22.0。
- 密钥仅保存在 Ubuntu 工程根的 `.env`，权限 0600；没有提交或输出其内容。
- sudo 非交互认证仍需密码。Docker 与用户目录安装已满足本阶段需求，未变更 sudo 策略。
- 用户服务驻留 `Linger=yes`，服务可在 SSH 断开后运行，并由用户管理器启动。
- 未改动虚拟机中原有的其他容器。

## 已实现

1. Alembic 使用应用的数据库配置，支持含特殊字符的密码；真实升级至 `0005_source_cooldown`。
2. 每个新候选绑定不可变的正文版本，同源同版本去重，正文变化生成新版本、新候选。
3. 来源发布时间转换到 UTC；缺失、非法或没有时区的日期不补造。
4. 旧候选无法可靠判断所属版本时保留为空，并将待审状态标为需要重新抓取；迁移不猜测历史关联。降级遇到同 URL 多版本会拒绝有损去重。
5. 可选 Cloudflare DoH 解决本机 Fake-IP DNS。默认仍用系统 DNS；公网校验、每跳校验和连接 IP 固定均保留。DoH 查询仅发送目标域名给固定供应商。
6. 五个公开来源 RSS 和最新正文样本均通过生产抓取路径；首轮持久队列发现 1,352 个链接并开始逐篇落库。
   批量抓取遇到 Hugging Face 429 后，新增默认 10 秒任务间隔与按来源持久化冷却；遵守 Retry-After，缺省冷却 15 分钟，其他来源可继续。
7. 首次领取任务即显示运行中；失败重试、租约续期和过期恢复继续使用持久队列。
8. 提供数据库备份和隔离恢复验证脚本；恢复只写临时 `radar_restore_*` 数据库，结束清理。
9. API、worker、scheduler、前端作为独立 systemd 用户服务运行。定时器每小时入队，API 不兼任调度进程。

## 日常操作

```bash
cd ~/ai-radar
systemctl --user status ai-radar-api ai-radar-worker ai-radar-scheduler ai-radar-frontend
journalctl --user -u ai-radar-worker -n 50
curl http://127.0.0.1:8000/health/ready

# 停止/恢复自动采集
systemctl --user stop ai-radar-scheduler ai-radar-worker
systemctl --user start ai-radar-worker ai-radar-scheduler

# 备份并验证可恢复性
archive="$(bash scripts/db-backup.sh)"
bash scripts/db-restore-check.sh "$archive"
```

重新安装服务可执行 `bash scripts/install-ubuntu-dev-services.sh`，只覆盖本工程的四个用户服务。当前使用 Vite 开发服务，尚不是公网生产部署。

## 验证边界

- 主库真实 readiness：ready / postgres / synthetic=false。
- 首次 0004 备份恢复演练在隔离库成功，样本备份含 5 个来源、135 篇原文、135 个版本、135 个候选、0 个事件；之后主库持续采集，数量会变化；0005 限流迁移后也再次通过隔离恢复。
- 前端：29 项单元测试通过，TypeScript 与生产构建通过。
- 后端静态、单元和真实 PG 验证以 `db-live-validation.md` 及本轮执行结果为准。
- 已采集原文不是已发布标准事件；事件、证据语义质量、模型回答、向量检索尚未验收。
- 没有付费模型调用。供应商与预算确定后，再完成提取/发布/问答。
- 历史 gold 和旧站 API/SSE 抓包仍未提供；P0 整体验收未完成。
- 用户已取消周额度 80% 停止规则。

DoH 接口依据：[Cloudflare 官方 DNS JSON 文档](https://developers.cloudflare.com/1.1.1.1/encryption/dns-over-https/make-api-requests/dns-json/)。
