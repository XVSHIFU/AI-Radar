# 个人部署：当前状态、持久化与恢复

更新：2026-09-16。按最新用户要求上线新 Agent，采用 Docker Compose，保留一份同机备份。此前“独立备份盘”“大规模付费质量评测”不再作为本次交付的前置条件，原方案保留为历史和后续参考。

## 当前已经上线

- 入口：`http://192.168.194.129:5173/`，由 Caddy 提供生产前端并转发 API，不再使用 Vite 开发服务。
- Agent：pi-agent-core + FastAPI 业务工具；只读查询、精确统计、受限 Python 分析、流式回答和受授权的分析文件下载已接入。
- Python：固定 gVisor / 镜像，每次独立任务容器；无网络、无宿主挂载、无 Docker socket、非 root、资源与执行时间限制。控制器和 watchdog 为单独的可信服务，不是模型工具。
- 同一 IP 滚动 48 小时 5 次发送问题，追问计入；前端不常驻显示额度。保留已有签名密钥和额度账本，没有通过迁移重置额度。
- API、PostgreSQL、pi、Caddy、quota-cleaner、沙箱控制器、watchdog 均以容器运行。旧 API/前端及维护定时器停用；旧数据库保留并停止，不再随主机重启。
- **worker 和 history-extract 均未启动；收费提取保持暂停。** 历史发现与索引维护代码仍提供为可选 profile，本次不自动开启。

应用构建基于 `5f60663`，加上已验证的 Gateway Dockerfile 构建路径修正；镜像使用 `5f60663` 标签，准确内容以备份 manifest 的镜像 ID 为准。最终源码归档包含该修正和本说明。原 `/home/xvsf/ai-radar` checkout 是迁移前工作树；活动 Compose 位置如下，不能再用旧 systemd 服务启动应用。

## 文件放在哪里

| 位置 | 内容 |
| --- | --- |
| `/home/xvsf/ai-radar-data/compose.json` | 当前 Docker Compose 配置，包含明确的主机挂载路径 |
| `/home/xvsf/ai-radar-data/database` | PostgreSQL 持久化文件 |
| `/home/xvsf/ai-radar-data/model_config` | 后台模型供应商配置 |
| `/home/xvsf/ai-radar-data/secrets` | 数据库和服务凭证、既有签名密钥 |
| `/home/xvsf/ai-radar-data/agent-policy` | 已启用 Python 的只读 Agent 规范、Skills 和策略 |
| `/home/xvsf/ai-radar-data/gateway_data`、`gateway_config` | 网关持久化目录 |
| `/home/xvsf/ai-radar-backup/current` | 一份约 986 MB 的完整恢复副本 |
| `/home/xvsf/ai-radar/.run/personal-agent-5f60663` | 本次镜像构建源码目录 |

检索模型的活动只读路径见 Compose 中 `/opt/radar-embedding` 挂载，模型文件也包含在配置备份中。`database` 挂载是实时数据；`database.dump` 是 PostgreSQL 一致性导出。不要直接复制运行中的数据库目录当作数据库备份。

备份包含 `images.tar.gz`、`database.dump`、`configuration.tar.gz`、`source.tar` 和校验清单 `manifest.json`。它们仅保存在 Ubuntu，配置归档含私有凭证，目录权限 0700。旧数据库和迁移前 dump 另保留为此次切换的回退点。

这是按用户要求保留的同机副本，适用于容器损坏、重建与数据恢复；没有配置异地备份或新增收费服务。

## 常用操作

容器坏了但持久数据还在，直接重建服务，不需要恢复数据库：

```bash
docker compose -f /home/xvsf/ai-radar-data/compose.json \
  --profile active --profile sandbox up -d --no-build
docker compose -f /home/xvsf/ai-radar-data/compose.json \
  --profile active --profile sandbox ps
```

上述默认服务不包含收费提取，不要添加 `collection` 或 `paid-extraction` profile，除非主动决定恢复采集/提取。

以后生成新备份：以 xvsf 身份运行 `scripts/personal-backup.py`，指定当前数据目录、**新的**输出目录和对应版本源码 tar。脚本不会覆盖现有备份，也不会调用模型。确认新副本后可自行只保留需要的一份。

```bash
python3 scripts/personal-backup.py \
  --data-dir /home/xvsf/ai-radar-data \
  --output /home/xvsf/ai-radar-backup/next \
  --source-archive /home/xvsf/ai-radar-backup/current/source.tar
```

如果数据库也损坏，先停止旧 stack，然后用备份恢复到新目录，原目录不会覆盖。新机器需要先安装 Docker 和项目固定版本 gVisor；同机恢复不需要重复安装。

```bash
docker compose -f /home/xvsf/ai-radar-data/compose.json \
  --profile active --profile sandbox down
python3 scripts/personal-restore.py \
  --snapshot /home/xvsf/ai-radar-backup/current \
  --data-dir /home/xvsf/ai-radar-data-restored \
  --source-dir /home/xvsf/ai-radar-restored
docker compose -f /home/xvsf/ai-radar-data-restored/compose.json \
  --profile active --profile sandbox up -d --no-build
```

恢复脚本核验文件摘要和镜像 ID，恢复原凭证、政策、数据库与配额，并修改绑定路径。它只先启动数据库和迁移；最后一条命令才启用应用。恢复内容对应备份时刻，之后新增的数据需要更新的备份。

## 本次验收证据

- Ubuntu 实际公开入口 → pi → PostgreSQL → gVisor → 分析文件端到端用例通过；只有模型上游使用夹具，模型费用为零。
- 迁移前后 26 张原有表计数一致，293 条事件保留；数据库从 0011 升级到 `0013_public_quota_retention`。
- 线上实际 preflight：Agent=true，pi 就绪，Python=true，双方策略一致，独立控制器健康；未发送模型问题。
- 网关/API/数据库/pi/控制器/watchdog 健康，公开 session 返回 limit=5/window_hours=48。
- 实际镜像构建成功，前端生产构建成功。页面检查覆盖日期范围、图表切换、事件加入按钮底色、来源原文摘录和手机布局。
- 本次迁移真实执行了数据库导出/恢复/升级；备份脚本也已实际执行。新整理的通用恢复包装脚本未再做第二次完整恢复演练，避免重复工作。

## UI 和“提取失败”的含义

统计页的日期快捷项和三种图表都应可点击，不是展示标签；本次保留它们在数据加载/无数据期间的位置，并增加明确的指针及选中反馈。“加入当前对话”默认使用主题浅色底。

事件抽屉展示来源标题及首段摘录，进入“阅读摘录”查看全部相关原文并提供“阅读原文”入口。公开页面不再展示版本 UUID、段落 ID、`unverified` 等内部核对字段，后台证据链仍保留。

“事件提取”指把采集文章交给模型，整理成标题、摘要、分类、日期和关联原文等结构化事件；不是用户下载或 Python 工具。失败通常表示模型输出未通过结构/证据/日期等校验，或网络调用失败。不同原因应从后台折叠日志区查看，不能把某一个原因解释为所有失败。本次保持收费提取停用，没有重新批跑失败任务。
