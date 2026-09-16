# Agent 候选容器部署

这是本地准备中的候选部署，**尚未在 Ubuntu 构建镜像或执行恢复演练，不能视为 P5 验收通过**。现有宿主服务没有被这些文件替换。

`compose.agent.json` 使用 Compose 支持的 JSON 表达。Docker 官方 Compose 2.39.2 已在本机完成三种配置的解析；它只证明配置有效，不证明镜像可构建、服务能启动或隔离已经生效。

## 服务与启动组

| 配置组 | 服务 / 行为 |
| --- | --- |
| 默认 | 仅数据库；恢复准备阶段不会启动应用、采集或模型调用 |
| `active` | 迁移、API、pi、前端代理、采集 worker、配额清理 |
| `rss-schedule` | 显式启用 RSS 定时调度；旧环境已停用它，迁移不能擅自重新开启 |
| `sandbox` | 独立 watchdog、沙箱控制器；不会修改 Agent 的 Python 策略 |
| `operations` | 迁移与来源登记等操作员任务；应指定单个服务执行 |
| `history` | 历史归档扫描：每次成功完成后间隔一小时；独立缓存/报告卷 |
| `paid-extraction` | 使用后台已保存模型配置的事件提取；明确选择后才启动 |
| `embedding` | 本机 CPU 增量向量索引；无公网网络，固定只读模型 |
| `embedding-operations` | 操作员首次回填/激活索引；与增量索引共享同一把锁 |

Agent 开关固定为 false，Python 策略也保持 false。完成 P4/P5 后才准备单独的发布覆盖配置。开启 `sandbox` 只启动私有控制面，不会自动把 Python 工具提供给公众。

## 构建内容与信任边界

Python / Node / Caddy / Docker CLI / pgvector 基础镜像都固定摘要；本轮从公开镜像仓库读取了 Node、Caddy、Docker CLI 和 pgvector 的摘要。Node 为 22.19.0，pnpm 固定 11.22.0（其 npm 元数据要求 Node >=22.13）。Python 依赖从已提交的 `backend/uv.lock` 导出并包含包哈希：

```powershell
uv export --project backend --frozen --no-dev --no-emit-project --format requirements-txt --output-file deploy/containers/backend-requirements.txt
```

`.dockerignore` 排除私有配置、密钥、数据库导出、工作目录和本地依赖。构建文件只 COPY 所需源目录；pi 镜像只得到其固定策略、运行时和专属服务凭证。没有将模型供应商密钥、数据库连接或 Docker socket 交给 pi。

只有可信控制器和 watchdog 挂载 Docker socket。它们是宿主控制面，不是模型执行环境。生成的 Python 继续由现有执行器启动为无网络、无宿主挂载的受限 gVisor 任务。

入口仅绑定 `127.0.0.1:18443`，使用内部 TLS。Caddy 到 API 使用固定私网 `172.30.248.0/29`，仅代理地址 `.2` 被 Uvicorn 视为可信转发来源；启动前需确认这个网段没有冲突。若改变网段，须同时修改可信代理地址并重新验证客户端 IP 与配额防伪造行为。

所有服务为 UID/GID 10001、只读根文件系统、关闭新增权限、丢弃 capabilities，并有内存/进程/CPU 上限。容器根文件系统只读不代表数据无写入：数据库、模型配置、TLS 数据和共享进程锁使用各自命名卷。

## 凭证与空安装准备

使用逐服务挂载的 secret 文件，**不要使用 env_file 加载整份 `.env`**。Compose 对文件来源的 secret 使用挂载；不能依靠其 uid/gid/mode 声明改变宿主文件权限。参见 [Docker secrets 说明](https://docs.docker.com/compose/how-tos/use-secrets/) 和 [Compose 服务参考](https://docs.docker.com/reference/compose-file/services/)。

每个文件应由容器 UID 10001 所有，权限 0400，值不带换行。下面仅适用于明确为空的新安装，需在操作员 Linux 终端执行；本轮没有执行：

```sh
sudo install -d -m 0700 /etc/ai-radar
sudo python3 scripts/prepare-container-secrets.py --new-install --directory /etc/ai-radar/candidate
```

脚本独占创建新目录和文件，拒绝覆盖已有凭证。它不输出密钥值。若中途失败，先核对已创建的目录，不能自动覆盖重试。

**既有数据迁移或恢复禁止运行这个生成流程替换旧值。** `public_assistant_secret` 和 `cursor_secret` 必须从原受控配置逐字节保留，模型配置也要迁移；否则签名身份、分页或 IP 配额键会改变。`container_entry.private_value` 不裁剪签名密钥、不生成后备密钥。数据库角色密码与恢复后的权限映射也须单独验证，不能把旧数据库管理员密码塞给 API。

数据库只在新数据卷初始化时创建 bootstrap、owner、api、ingest 角色。API 与 ingest 获得业务表 CRUD，不具有超级用户、建库、建角色或 schema DDL 权限；迁移使用独立 owner。它们当前不是按业务表进一步细分的身份，不应宣称已做到逐表最小权限。

## 操作员元数据与候选命令

准备以下非秘密元数据；应随版本清单保存，但不能把 secret 值写入其中：

```sh
export RADAR_STACK=radar-candidate
export RADAR_RELEASE=<唯一源码版本>
export RADAR_SECRET_DIR=/etc/ai-radar/candidate
export RADAR_DOCKER_GID=<宿主Docker-socket的GID>
export RADAR_SANDBOX_IMAGE_ID=<已验证的sha256镜像ID>
export RADAR_SERVICE_LOCK_VOLUME=radar-service-locks
export RADAR_SANDBOX_LOCK_VOLUME=radar-sandbox-locks
```

Compose 会解析未启动的服务定义，因此只验证默认组也需要这些元数据；恢复时可从原版本清单读取镜像 ID，不代表必须启动沙箱。

共享锁卷由操作员预先创建，升级时不能换名或删除重建：

```sh
docker volume create radar-service-locks
docker volume create radar-sandbox-locks
docker compose -f compose.agent.json --profile active --profile sandbox config --quiet
docker compose -f compose.agent.json --profile active --profile sandbox build
```

镜像构建完成后还要记录实际 image IDs / RepoDigests；候选 tag 本身不等于不可变部署清单。随后对空候选或已验证的恢复库分步执行：

```sh
docker compose -f compose.agent.json up -d db
docker compose -f compose.agent.json --profile operations run --rm migrate
docker compose -f compose.agent.json --profile active up -d
```

默认数据库健康只检查 PostgreSQL 是否接受连接；API 健康额外核验仓储就绪。沙箱的两个健康检查都经过认证，控制器还核验 runtime、镜像和独立 watchdog 的新鲜证明。容器进程存在不代表已经健康。

## 切换和恢复仍待完成

- 同一宿主的所有活动/备用槽位必须共享服务锁卷，防止第二份 API 或 worker 同时写入。旧 systemd 服务不持有这些新锁，因此首次切换仍必须停止并确认旧写入方已经退出。
- 同一宿主两个 Compose 组也不能共用本文固定的前端子网同时启动；恢复先启动独立数据库，切换时停旧前端网络再启新。跨宿主恢复不能依赖文件锁，仍需部署层隔离旧实例。
- 固定 gVisor 二进制只读挂载的路径、属主、摘要和宿主 runtime 参数都要真机核验；新控制器不能与仍持有不同锁路径的旧控制器重叠运行。
- 历史扫描、付费提取和向量索引现已接入候选定义，尚未在容器中启动验证。实际切换时还需停止旧 systemd 维护任务；这些旧进程并不持有新的共享锁，不能依赖新锁阻止它们重叠运行。
- 独立存储备份、恢复到独立卷、数据库权限映射、额度账本与 HMAC 保留、无双 worker、旧助手回退等仍待实现和演练。
- 本机 WSL 虽有 Ubuntu 登记，但启动返回 `HCS_E_SERVICE_NOT_AVAILABLE`；没有为此修改 Windows 虚拟化或系统服务。Linux 文件权限和真实容器验收仍未完成。

详见 [P5 交付记录](../../docs/research-agent-p5-progress.md)。


## 历史维护与向量检索接线（本地新增）

四个维护服务均为显式配置组，`restart: no`；成功批次才按周期继续。失败、超时或提取器返回供应商中止状态，会停止监督进程并等待操作员处理，不自动付费重试。容器引擎重启后也需操作员明确恢复这些任务。

历史窗口使用 `RADAR_HISTORY_FROM` / `RADAR_HISTORY_TO`，默认沿用旧脚本的 2026-08-01 至 2026-09-30。每次执行重新取业务时区当天日期，结束日为当天与指定结束日中较早者；尚未到开始日时不运行。扫描每批最多 40 页，提取每批最多 80 条；完成后分别等待 3600 / 600 秒。扫描与提取单批截止时间分别为 3600 / 7200 秒。

增量索引每批最多 100 条，单批 900 秒；成功后等待 900 秒。首次激活任务最多处理 500 条，沿用“全部当前事件均已索引才允许激活”的仓储检查；它与增量任务共用 `embedding-index.lock`，不能重叠运行。首次激活前需停止增量任务。

监督进程处理 SIGTERM / SIGINT，先终止本批独立进程组，五秒后仍未退出则强制终止。即使取消恰好发生在子进程创建中，也要先取得句柄并完成清理，再退出释放锁。相关异步时序已由夹具验证；真实 Linux 信号/进程组验收尚未执行。

扫描的 `/app/.run` 使用项目自己的 `archive_reports` 卷。提取器仅额外得到后台模型配置卷的只读挂载；它不拿管理员、匿名身份或模型运行时 token。启动付费提取是独立操作，本轮没有执行。

索引与语义查询需要 `embedding` 构建阶段及固定模型。API 必须一并加载 `compose.embedding.json` 覆盖配置，避免只有索引容器能计算向量、API 仍只做关键词检索。设置 `RADAR_EMBEDDING_MODEL_DIR` 指向操作员已准备的公开模型目录，目录可由 UID 10001 遍历、两文件可读；容器内固定挂载为 `/opt/radar-embedding`，禁止自动创建不存在的宿主目录。

启动前同时核验 ONNX 和 tokenizer 文件长度与 SHA-256，任何不匹配都拒绝启动；不在线下载或安装模型。固定版本为 `7698c0c30eafe2736771e96d733545270cdec56f`，制品表在 `backend/src/radar/container_model.py`。ONNX 摘要沿用已有真机记录，tokenizer 摘要在本轮从 Ubuntu 已安装的公开文件只读核对。这不是供应商签名验证。

候选检查/构建命令（仅描述，尚未执行实际构建或启动）：

```sh
docker compose -f compose.agent.json -f compose.embedding.json --profile active --profile embedding config --quiet
docker compose -f compose.agent.json -f compose.embedding.json --profile active --profile embedding build
```

在完成切换验收、停止旧实例后，再选择所需服务启动。`paid-extraction` 不包含在上述命令中，公开 Agent / Python 的开关也没有因此改变。

本轮官方 Compose CLI 完成基础三种配置以及向量覆盖配置解析：全部配置共十五项服务；确认覆盖配置保留 API 原有的后台模型配置卷、固定可信代理地址和关闭中的 Agent 开关。维护与部署、控制器回归共 **63 passed / 16 skipped**，三模块 Linux 严格 mypy 与 Ruff 通过。尚未证明镜像构建、真实模型加载、网络隔离或 Docker 内取消清理成功。
