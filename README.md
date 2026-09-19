# AI 革新雷达

一个自托管的 AI 资讯汇总站。脚本自动读取来源、清洗和去重，再直接展示原站标题、简介与链接；日常收录不需要模型 API，也不需要逐篇复制和导入。

当前为 **v0.1.0 本地发行候选**。镜像和代码暂不推送远端。完整工作范围见 [首版计划](docs/first-release-plan.md)；`docs/` 中旧部署与验收记录仅代表当时状态。

## 功能

- 自动收录 RSS/Atom，保留原文语言；正文抓取失败时仍可阅读有效的来源简介和原文链接。
- 时间线、关键词搜索、分类、日期过滤、统计、多套主题和手机布局。
- 后台管理来源、采集故障、隐藏/恢复文章。手动编辑和内容 Agent 是可选精选功能。
- 可选 pi 研究助手：读取收录内容并给出来源；每个 IP 滚动 48 小时 5 次提问，追问计入。
- 数据保存在指定主机目录。Docker 镜像不携带你的数据库、模型凭据或会话。

资讯列表按文章发布时间展示，缺失时明确使用收录时间。已有精选事件保留，关联原始文章不重复列出。规则分类不能确定时显示“未分类”，不会编造事件日期或重要度。

## Docker 启动

需要 Linux、Python 3、Docker Engine 和 Docker Compose。基础模式无需 Node、Python 依赖环境、API Key、向量模型或 gVisor。Windows 可以在 Linux Docker 主机/WSL 中运行以下命令。

在项目根目录执行；当前用户需能使用 Docker：

```bash
# 如已有离线镜像，先加载；否则 init/build 会从源码构建。
docker load -i /path/to/ai-radar-v0.1.0-images.tar

python3 scripts/release.py init --data-root "$PWD/.local-data"
python3 scripts/release.py build --data-root "$PWD/.local-data"  # 已加载全部镜像时省略
python3 scripts/release.py up --data-root "$PWD/.local-data"
```

访问 `http://127.0.0.1:8080`；管理员入口 `/ingest`。`init` 生成的管理员口令位于数据目录 `secrets/admin_token`，用本机管理员权限读取并妥善保管，不要提交到 Git。首次空库登记少量默认来源；已有来源开关不会被启动命令重置。

`init` 只用于新目录，升级或重启不要重新初始化。默认仅监听本机。局域网试用可以在启动前设置 `RADAR_BIND_IP=0.0.0.0`；通过 `RADAR_HTTP_PORT` 修改端口。公网部署使用 HTTPS，并限制管理入口和服务器端口。

```bash
# 停止服务，保留持久数据
python3 scripts/release.py down --data-root "$PWD/.local-data"
# 同版本重启
python3 scripts/release.py up --data-root "$PWD/.local-data"
# 导出本地镜像，旁边生成摘要清单；目标文件必须不存在
python3 scripts/release.py export --data-root "$PWD/.local-data" \
  --output /absolute/path/ai-radar-v0.1.0-images.tar
```

基础服务由数据库、API、网关、采集 worker 和调度器组成。不会启动旧的收费事件提取。镜像标签使用 `v0.1.0`，可通过 `RADAR_RELEASE` 覆盖；实际镜像 ID 以导出清单为准。

## 可选助手与 HTTPS

```bash
python3 scripts/release.py assistant-up --data-root "$PWD/.local-data"
# 然后在后台配置自己的模型。没有 Key 时，基础采集/浏览照常可用。

RADAR_DOMAIN=radar.example.com python3 scripts/release.py https-up \
  --data-root "$PWD/.local-data"
```

域名需指向服务器，HTTPS 部署前核对端口及已有反向代理。首次启用助手会构建尚未提供的 pi 镜像；后续可直接加载预构建镜像。可选模式会保存在数据目录，之后的 `up` 会保留选择。

向量检索可通过 `embedding-up` 和 `RADAR_EMBEDDING_MODEL_DIR` 使用已校验的本地模型；默认用文本搜索。基础发行包不开放 Python 执行；现有 gVisor 控制器实现保留在源码中，启用必须配齐独立隔离环境，不能退回宿主执行。

## 备份和升级

保留一份镜像归档和一份一致性数据备份即可；不要直接复制运行中的 PostgreSQL 数据目录。

```bash
python3 scripts/release.py backup --data-root "$PWD/.local-data" \
  --output /absolute/path/radar-backup
# 恢复到新目录；并行运行时为副本选择独立项目名、端口和未占用的前端子网/IP。
RADAR_STACK=ai-radar-restored \
RADAR_HTTP_PORT=8081 \
RADAR_FRONT_SUBNET=172.31.250.0/29 \
RADAR_GATEWAY_IP=172.31.250.2 \
RADAR_API_IP=172.31.250.3 \
python3 scripts/release.py restore \
  --data-root "$PWD/.restored-data" --snapshot /absolute/path/radar-backup
python3 scripts/release.py up --data-root "$PWD/.restored-data"
```

备份含数据库、私有配置和凭据，只保存在你指定的位置。恢复命令校验摘要并启动数据库，应用需另行执行 `up`。升级前先备份，再加载新镜像并运行 `up`；涉及数据库变化时，不能仅换回旧镜像就认为已完成回退。同机副本不能应对整块磁盘损坏。

运行时可用 `docker ps` 查看容器健康状态、`docker logs --tail 100 <容器名>` 查看故障，使用 `docker system df` 和 `df -h <数据目录>` 检查空间。容器日志已限制为每份 10 MB、最多 3 份；采集失败在后台查看。

## 开发与反馈

- `frontend/`：Vue 3、TypeScript；`pnpm --dir frontend install --frozen-lockfile`。
- `backend/`：Python 3.12、FastAPI、PostgreSQL；`uv sync --frozen --project backend`。
- `agent/`：可选 pi 运行时、研究规则、Skills 和隔离 Python 实现。
- `deploy/containers/`、`compose.release*.json`、`scripts/release.py`：发行构建和部署。

开发时只验证受影响功能；首次部署再做一次采集、浏览和重启检查。默认不调用收费模型做测试。提交问题时提供版本、系统、复现步骤和已脱敏日志，不上传 API Key、管理员口令、数据库或用户会话。

项目许可证待维护者在公开发行前确定。第三方字体和图标的许可证见 [第三方说明](THIRD_PARTY_NOTICES.md)。