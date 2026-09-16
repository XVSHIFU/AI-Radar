# P3 Python 沙箱开发记录

日期：2026-09-16。**单任务 gVisor 隔离、独立崩溃回收，以及独立 HTTP 网关→授权数据集→产物下载链路均已通过真机验收；生产启动门槛、pi/SSE 与公开接入仍未完成，Python 工具保持关闭。**

## 本次实现

- `agent/sandbox/`：Python 3.12 的独立镜像构建文件、锁定的 numpy/pandas/matplotlib 依赖及哈希清单。构建必须显式提供经核对的基础镜像摘要，运行层移除 pip/ensurepip。未挂载业务源码、数据库、密钥或备份。
- `sandbox_protocol.py`：代码最多 16 KiB、最多四个数据集/10,000 行/2 MiB。JSON 转义造成的额外字节有独立传输上限。模型提交的数据集仍必须通过后续归属网关解析，不能直接信任本模块的入参。
- `worker.py`：只在临时容器内执行代码，输出限额，文件以不跟随符号链接和非阻塞方式打开，检查普通文件与硬链接数量并限制实际读取字节。worker 自报成功不作为可信证明；外部控制器重新验证所有结果。
- 产物只允许 JSON/CSV/PNG，限制文件名、个数、总量、真实格式和 UTF-8。JSON 拒绝重复字段与非有限数字；CSV 对公式前缀转义；PNG 校验 CRC、结构、尺寸、解压后的精确栅格长度和行过滤字节，清除辅助元数据。初版仅接受 matplotlib 常用的非交错 8 位灰度/RGB/RGBA，拒绝调色板 PNG。
- `sandbox_executor.py`：独立受信控制器内使用固定 Docker 程序和 socket；不继承模型密钥等环境变量、不经 shell、不将代码拼进命令。仅允许已审核的本地镜像 ID。强制 runsc、无网络、非 root、只读根目录、删除所有 capabilities、no-new-privileges，1 CPU/256 MiB/32 PIDs/32 MiB 临时目录，执行限时 10 秒，不自动重启、不拉取镜像。
- stdout/stderr 同时限量读取；异常、超时、取消均尝试强制销毁任务。清理失败后该控制器实例停止接纳新任务。实例内最多两个任务；跨实例限流、认证网关和独立 watchdog 尚待接入。
- `scripts/prepare-gvisor-bundle.py`：仅下载官方固定版本 `20260907.0` x86_64 包、核验官方 SHA-512 和归档路径/文件类型/展开大小、生成文件哈希清单。不会安装、执行下载的程序或重启 Docker。

容器参数参考 [Docker 官方运行参数](https://docs.docker.com/reference/cli/docker/container/run/)。gVisor 的运行文件与配套 `gvisor-bin/` 必须一起安装；准备脚本按[官方安装说明](https://gvisor.dev/docs/user_guide/install/)选用版本固定的完整归档。

## 验证与明确限制

本地沙箱协议、执行控制器和进程传输测试 40 项通过；另有真实供应商验证器的输出范围测试 1 项。Ruff 与两个沙箱模块的严格 mypy 通过。测试使用恶意字节输入和替代 Docker/进程对象，**没有在宿主执行模型生成代码，也没有证明 gVisor 实际隔离有效**。

这一切片开始时 Ubuntu 已有 Docker、尚无 runsc，当前账号没有免交互 sudo；用户随后完成管理员安装，最新结果见文末。未借 Docker 权限修改宿主系统。源码运行入口尚未接入公开 API，`policy.json` 的 Python 开关保持 false；只有 `--runtime=runsc` 参数也不能替代对实际运行时路径/版本/隔离效果的验证。

## 后续门槛

1. 核验固定版本包，准备可审查的安装和回退步骤；安装 gVisor 并核对运行时实际路径/摘要，构建并记录分析镜像摘要。
2. 独立执行控制器认证网关、全局并发、启动清理及外部 watchdog；控制器不可与持有业务数据/备份的应用合并。
3. 数据集从当前运行的授权注册表取出，产物绑定匿名会话、执行与数据集范围；下载核对所有权并提供正确 MIME/nosniff/附件响应。
4. 真机验证禁止网络、宿主读取、跨任务访问、写根目录、路径逃逸，以及超时/取消/OOM/后台进程清理；Python 库在 256 MiB/10 秒内完成正常分析。
5. 接入受限工具/SSE/图表来源并执行安全用例，全部通过才允许启用 Python。若运行时不可用，明确返回能力未开放，不退回宿主解释器或普通 Docker 运行。

P3 尚未完成；P4 研究质量与 P5 容器迁移/独立恢复同样保持待验收。


## Ubuntu 准备结果

- 候选补丁 `691b97f`、`dbc3f21` 已同步；沙箱 40 项及验证边界 2 项共 42 项在 Ubuntu 全部通过，全部使用替身 Docker/进程，不触发收费模型。
- gVisor `20260907.0` x86_64 官方完整包下载、SHA-512 和六个文件结构校验通过，保存在 `.run/gvisor-20260907.0/`，只下载未安装。
- 基础镜像固定 `python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254`。Ubuntu 沙箱构建成功，Python 依赖全部通过哈希校验；镜像配置摘要 `sha256:b31ef8f03b4715f362586e3227b56d61093ff2da86badbe54e90972122ac3c73`。未在普通 runc 容器内执行模型代码。
- 新增运维脚本 `scripts/install-gvisor-runtime.sh`：要求管理员在 Ubuntu 执行，重新校验写入 root 私有目录的固定包，保留原 Docker 配置备份，只添加具名 runsc 运行时、校验配置后 reload；不改变默认运行时。失败时恢复原配置；不自动开放 Python。当时脚本尚未以 root 执行；用户随后已安装，见文末实际版本核对。

已由 Ubuntu 管理员完成的操作（当前 SSH 账号没有免交互 sudo）：

```bash
sudo bash /home/xvsf/ai-radar/.run/research-validation/scripts/install-gvisor-runtime.sh
```

该操作只准备隔离运行时。安装完成后仍需真实隔离、安全、资源限制和退出清理测试，不能直接打开 Python 开关。


## 安装后真实隔离验收（2026-09-16）

用户完成管理员安装后，已核对 `runsc release-20260907.0`、实际 Docker 运行时路径 `/opt/ai-radar/gvisor/20260907.0/runsc`、`--platform=systrap` 及 runsc 二进制 SHA-256。实际镜像 ID 为 `sha256:7a72dfb14070c165eeba7eb388220b1462181225f96e8720e29ec1a0268b5021`，与前文记录的镜像 config 摘要是不同对象，执行控制器使用 image inspect 返回的镜像 ID。

首轮 15 项实测有 14 项通过，进程数量测试失败。最小复现连续两次失败；单个子进程正常，多次派生时运行时在打印第 3 个子进程后以 2 退出。已有 `--pids-limit=32` 是宿主层约束，guest 的 NPROC 原为无限；gVisor 中任务与宿主线程并非一一对应，见[官方资源模型](https://gvisor.dev/docs/architecture_guide/resources/)。不能仅凭 Docker 参数宣称 guest 进程上限已验收。

对照实验保留所有原限额，只补 `RLIMIT_NPROC=2:2` 后，第二次派生返回 EAGAIN，父任务正常完成清理。提交 `9a45428` 固定这一更严格限制，包含主进程在内两个 guest 进程/线程；不放大宿主 32 PIDs、256 MiB 或 1 CPU 上限。硬限额也不能被 guest 提高。原始最小复现修复后连续两次通过。

完整第二轮 15 项全部通过，报告保存在 Ubuntu `.run/sandbox-acceptance-20260916-02.json`：

- numpy/pandas/matplotlib 分析约 1.38 秒，产出 JSON/CSV/PNG 共 4,651 bytes，合成数据求和 5、均值 2.5 正确。
- 非 root、capabilities/no-new-privileges、只读根目录、无宿主配置/SSH/Docker socket、无模型凭证或 pip/ensurepip。
- TCP 回环/宿主地址/元数据地址/公网地址均不能连接；每个任务独立临时目录，前一任务 canary 不可见。
- 符号链接产物、输出超量、伪造返回信封均被拒绝，输出目录外文件不被导出。
- 无限 CPU 约 10.2 秒超时，内存耗尽被终止，32 MiB 临时空间限额生效，guest 派生任务受限。
- 后台子进程与取消均完成容器销毁；每项检查真实 Docker 隔离参数，所有测试容器已删除。

独立回收器提交 `96d256f` 只处理本项目标签、名称、runsc/无网络/非 root/只读配置均匹配且创建超过 30 秒的任务。每五秒运行的用户级 `ai-radar-sandbox-watchdog.timer` 已安装并 active；实现不读取业务配置或模型密钥，当前代码路径为隔离候选工作树。正常控制器仍执行 10 秒超时，故障后独立定时回收会多一个轮询间隔，不能写成严格 30 秒无偏差。

控制器崩溃演练通过：只强制杀死测试控制器（退出 -9），它留下的睡眠容器由独立 timer 在约 32.32 秒回收，而非测试 fallback 删除。回收器另有 11 项归属、时间边界、并发删除、失败不可忽略等测试，当前相关单元回归合计 53 项通过。永久验收入口为 `scripts/verify-python-sandbox.py` 与 `scripts/verify-sandbox-watchdog.py`，不调用真实模型。

这些结果是固定版本、当前宿主下的具体边界测试，不是 Docker/gVisor 绝对无法逃逸的证明。Python 和线上 Agent 仍未启用；P3 还缺独立工具网关、数据集/产物归属与下载控制、公开 SSE 接入及最终组合验收。P4/P5 同样未完成。


### 最终复核

正式保留的 `verify-sandbox-watchdog.py` 再次通过故障演练，测试控制器退出 -9，独立回收耗时约 37.03 秒（包含创建、轮询和调度）。两次故障演练分别约 32.32/37.03 秒；不能把五秒 timer 配置误写成无调度偏差的五秒回收保证。最终检查没有残留带本项目沙箱标签的容器，API、前端和采集 worker 均为 active/running，watchdog timer 为 active。没有新增收费模型调用。

最新源码提交：`9a45428`（guest 限额与 15 项真实验收）、`96d256f`（独立回收器与 11 项测试）、`baa43d5`（永久崩溃验收工具）。完整 P0–P5 目标继续未完成，下一步是独立工具网关、授权数据集交接、匿名会话产物下载与公开 SSE 集成。


## 工具网关与产物归属切片（候选，2026-09-16）

- 新增独立 `sandbox_http.py`，进程内最多两个请求（含读入阶段）；服务凭证与模型 capability 分离。仅接受固定字段 job_id/code/datasets，不接受镜像、挂载、shell、网络参数或 owner。请求体有大小与读入时限，任务标识保留十分钟且有总量上限，失败和取消也不允许自动重跑。此注册表仅在本进程有效，公开问题的持久去重仍由已有数据库账本负责。
- API 侧 `sandbox_client.py` 只通过两个运维允许的私有地址访问控制器，无 Docker 导入/权限；不跟随重定向、不自动重试、拒绝压缩响应并限制实际返回字节，重新验证 JSON/CSV/PNG。运行时和独立 watchdog 的启动健康门槛尚待与部署入口连接，不能单独运行这个工厂就宣称生产就绪。
- `research_python.py` 只接收模型的代码和当前运行登记的数据集 ID；拒绝额外权限字段、未知/重复数据集，复制服务器登记的数据快照，执行前后检查本轮 capability/deadline。每轮最多一次 Python，失败也消耗此次数；执行取消或轮次关闭后不发布结果。该适配器尚未注册到公开 pi 工具集。
- `research_artifacts.py` 将产物绑定 signed-cookie owner、run 和 dataset IDs。全局最多 32 MiB、1,024 个文件/轮次标识；容量满时原子拒绝，不挤掉其他用户产物。下载逻辑到期十五分钟立即失效，后台每三十秒清理过期内存，重启后链接失效。当前设计要求单 API worker，P5 多实例必须共享存储或固定所有者路由，不能直接横向扩容。
- 下载路径使用服务端 UUID，重新校验文件名/内容，跨 owner、跨 run、匿名或过期访问统一 404，返回附件、正确 MIME、no-store、nosniff、同源资源策略和禁脚本 CSP。路由已接入，当前公开 Python 无法生成文件。
- 本地针对认证、并发、跨用户下载、重复执行、授权数据集、真实 ASGI 断连以及现有沙箱/API 的 138 项回归通过；四个新模块严格 mypy 通过。取消回归发现旧 is_disconnected 轮询可能拖到三十二秒截止，改为完整读入请求体后独立监听 ASGI disconnect，新增两秒清理断言通过。
- `scripts/verify-sandbox-gateway.py` 准备独立控制器进程、loopback HTTP、真实 runsc、分析产物与下载归属验收，只发送合成分类计数；随机服务凭证仅通过子进程 stdin 传递，不进入 argv、报告或模型。

本切片仍不改变 `policy.json` 的 Python=false。剩余 P3 工作包括生产启动健康/孤儿清理门槛、pi 工具与模型预算/技能/SSE/图表来源接入，以及公开链路综合验收；P4/P5 保持待完成。


### Ubuntu 网关真实链路结果

候选源码补丁 `c5b81d3` 已同步到 `/home/xvsf/ai-radar/.run/research-validation`。验收报告 `/home/xvsf/ai-radar/.run/sandbox-gateway-20260916-01.json` 全部通过：

- 控制器是独立子进程，凭证只经 stdin；私有 HTTP 监听仅绑定 127.0.0.1:8092，测试结束进程和端口均退出。使用已经审核的 runsc 实际路径/哈希、systrap 配置及固定镜像 ID。
- 授权适配器→真实 HTTP→runsc→重新校验产物→所有者下载，共生成 3 个 JSON/CSV/PNG 产物，求和 5、均值 2.5 正确，分析 1,661 ms。
- 未认证请求、其他运行的数据集 ID、跨签名会话下载、重复 job ID 均拒绝。下载响应检查附件和 nosniff；不依赖“链接不可猜测”作为权限控制。
- CPU 无限循环在客户端主动断连后 104 ms 完成容器清理；独立控制器内检查实际 Docker 隔离参数与两个任务均已删除。
- 模型调用 0；未发送真实事件正文或用户会话。Ubuntu 同一组 138 项回归通过，API、前端、worker 和 watchdog timer 均 active，任务标签下没有遗留容器。

这证明了候选网关及授权适配器的真实执行链路，不代表公开助手已经可以调用 Python。实际模型工具注册、研究工具预算、分析技能加载、SSE 产物/图表来源显示与生产健康门槛仍待接入。未迁移线上数据库、未改变公开 Agent/Python 开关。
