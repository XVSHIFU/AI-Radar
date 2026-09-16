# P3 Python 沙箱开发记录

日期：2026-09-16。**候选代码，Python 工具仍关闭，未通过真实隔离验收。**

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

Ubuntu 已有 Docker，但目前无 runsc，当前账号没有免交互 sudo。未借 Docker 权限修改宿主系统。源码运行入口尚未接入公开 API，`policy.json` 的 Python 开关保持 false；只有 `--runtime=runsc` 参数也不能替代对实际运行时路径/版本/隔离效果的验证。

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
- 新增运维脚本 `scripts/install-gvisor-runtime.sh`：要求管理员在 Ubuntu 执行，重新校验写入 root 私有目录的固定包，保留原 Docker 配置备份，只添加具名 runsc 运行时、校验配置后 reload；不改变默认运行时。失败时恢复原配置；不自动开放 Python。脚本尚未以 root 执行。

需要 Ubuntu 管理员完成的操作（当前 SSH 账号没有免交互 sudo）：

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
