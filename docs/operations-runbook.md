# Ubuntu 运行、验证和恢复

当前地址 `http://192.168.194.129:5173/` 为私网开发入口，API 仅在 loopback 8000，数据库仅在 loopback 55432。
API、worker、frontend 为独立用户服务；历史发现和提取由 `ai-radar-history-discover.timer`、`ai-radar-history-extract.timer` 调度。
历史回填替代了旧 APScheduler 服务，不能同时启用两个周期生产者来重复抓取。

## 自动检查

`bash scripts/install-operations-timers.sh` 安装本工程两个用户定时器：每日03:30备份并验证恢复、每5分钟检查运行状态。
`systemctl --user list-timers 'ai-radar-*'` 查看计划，`journalctl --user -u ai-radar-health -n 20` 查看告警。
健康报告位于 `.run/operations/status.json`，只记录计数和错误类型，不含文章、口令或供应商错误原文。
未完成采集、来源连续失败、租约失联和证据无法定位会使检查返回非零；这不代表公开查询也不可用。
当前告警写到 systemd 状态和本地报告；没有配置外发邮件或第三方告警服务。

## 备份与恢复

`bash scripts/backup-maintenance.sh` 保存 PG 自定义格式 dump、校验和，以及独立的私有配置归档。
配置包括工程 `.env` 和默认 `~/.config/ai-radar/model.json`；更改模型配置位置后需要相应扩充备份清单。
文件权限由 umask 0077 限制，保留14天，只有本脚本命名的过期文件会清理。
备份保存在 `.run/backups`，包含凭据的配置归档不得提交或公开。

每次备份恢复到新的 `radar_restore_*` 隔离数据库，校验迁移、vector、数量、所有 Evidence 的逐字段落定位及实体关系，再清理隔离库。
不会覆盖主库。测试备份可单独执行 `bash scripts/db-restore-check.sh <dump>`。
同机备份无法抵御整台虚拟机或磁盘丢失；独立备份目标尚需提供，不能把这称为完整异地灾备。
手动恢复主服务时应先停写入进程、保留原库、恢复到新命名数据库并验证，再切换配置重启；不要直接覆盖唯一现存数据库。

## 工程验证

Ubuntu 执行 `bash scripts/verify-linux.sh --postgres`：冻结依赖下的静态检查、单元/协议回归、真实PG隔离库测试、OpenAPI比对和前端构建。
数据库测试要求loopback并仅创建/删除 `radar_test_*` 数据库，不调用付费模型。
`.github/workflows/verify.yml` 定义同一检查链和独立PG16+vector服务；工作流存在不等于已在GitHub实际运行。
CI容器网络依据 [GitHub PostgreSQL服务文档](https://docs.github.com/en/actions/tutorials/use-containerized-services/create-postgresql-service-containers)。

## 私网发布候选与回滚

先构建前端 `cd frontend && pnpm install --frozen-lockfile && pnpm build`，再从根目录执行：

```bash
docker compose -p ai-radar-release -f compose.prod.yml up -d
```

网关通过 loopback `https://localhost:18443` 提供已构建页面，转发到现有API。它不改变当前5173开发入口，也不重复启动采集进程。
`deploy/Caddyfile` 保留SPA路由回退，API和health走后端，未知API不会变成HTML。
SSE设置立即flush，见 [Caddy reverse_proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)。
证书由本地CA签发；测试需明确使用其CA，不使用跳过证书检查来宣称TLS验证通过。
公网域名/独立部署目标未提供，仍未完成公网发布；正式公网配置需使用实际域名和公开受信任证书，参见 [Caddy HTTPS文档](https://caddyserver.com/docs/automatic-https)。

回滚前记录commit、镜像digest及数据库迁移revision；保留前一份dist和备份。UI回滚恢复上一dist并重启网关。
有新迁移时，先核对代码与schema兼容性；不要盲目downgrade有新业务数据的生产库。

## 本轮实测

2026-09-15：0007数据库备份在隔离库恢复，8来源、1483报道、1485版本、293事件、1145条可定位Evidence，DeepSeek主体检索2条。
恢复流程数秒内完成，主库未受影响；计数是该备份快照，不能代替事件质量验收。

## 本地向量索引维护

BGE-M3 模型固定在 `~/.local/share/ai-radar/models/bge-m3-7698c0c30eafe2736771e96d733545270cdec56f`，不依赖 `/tmp`。
配置 `EMBEDDING_MODEL_DIR` 与 `EMBEDDING_MODEL_REVISION` 后，安装 `uv sync --frozen --extra embedding-local`。
首次回填用 `backend/.venv/bin/radar-index-embeddings --limit 500 --activate`；只有全库当前版本都已有索引才允许激活。
`bash scripts/install-index-timer.sh` 安装15分钟增量维护，每批最多100条，已就绪的当前版本会在限额前排除。
模型输入或事件版本变化后会重新计算；版本不一致的向量不能进入语义检索。该过程只运行本机CPU，不调用Flash或其他付费API。
定时任务的内存上限2GiB，单次最长15分钟，文件锁防止同一工程重入。
## 2026-09-15 运行服务升级记录

用户明确批准后部署 `60e76dd`（含已验证源码 `5678d13`），迁移至0010，API/worker/前端和历史采集、健康、备份定时器均已恢复。293条本地BGE向量已建立并激活，15分钟增量索引任务首次运行成功。readiness、事件列表、混合检索、未登录管理员401和私网TLS均通过。
升级后备份 `.run/backups/radar-20260915T125109-536008.dump` 已隔离恢复验证，事件与证据计数和升级前一致。原有一次partial采集告警继续保留；数据质量与公网发布边界见完整实施审计。
