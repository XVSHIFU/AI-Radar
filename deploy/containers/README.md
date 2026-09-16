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
- 历史归档扫描、付费事件提取和向量索引的原有维护任务尚未迁移到此编排。不能停掉原维护任务后声称它们已由本文件接管；接入和对应费用/模型文件配置是后续工作。
- 独立存储备份、恢复到独立卷、数据库权限映射、额度账本与 HMAC 保留、无双 worker、旧助手回退等仍待实现和演练。
- 本机 WSL 虽有 Ubuntu 登记，但启动返回 `HCS_E_SERVICE_NOT_AVAILABLE`；没有为此修改 Windows 虚拟化或系统服务。Linux 文件权限和真实容器验收仍未完成。

详见 [P5 交付记录](../../docs/research-agent-p5-progress.md)。
