# AI 革新雷达

本仓库正在按实施规格 v1.0 落地。当前工作区是 `E:\AI-AGENT\AI-Radar-Implementation-Spec\codex`，覆盖旧方案中的 C 盘示例路径。

首页候选已实际运行比较，采用 Terra 研究工作台。两候选共用浏览器DOM回归 **14/14通过**，保留在 `prototypes/sol` 和 `prototypes/terra`。四页、确定性查询计划与持久采集工程已集成，最终状态以 [验收矩阵](docs/acceptance-matrix.md) 为准，不能把原型通过算成 P0 完成。

最新实施顺序与管理员后台扩展见 [实施方案续篇](docs/implementation-roadmap.md)。

## 工程结构

- `frontend/`：Vue3、TypeScript、Vite、Tailwind4 四页与API适配。
- `backend/`：FastAPI、SQLAlchemy、PostgreSQL仓储与显式合成演示仓储。
- `contracts/`：接口基线、共享演示数据、新版SSE协议样本。
- `scripts/`：本地启动/停止、验证、RSS入口验证与 Ubuntu 服务管理。
- `docs/`：设计、原型比较、实施记录和逐项验收证据。

## 当前 Ubuntu 开发环境

已将工程迁移到 Ubuntu，真实 PostgreSQL、API、采集 worker 和每小时调度已启动。
页面：http://192.168.194.129:5173/ 。详细环境、备份恢复与服务命令见 [Ubuntu 开发记录](docs/ubuntu-development.md)。
前端已由用户接受；数据库、脚本采集、Flash 事件提取与真实 JSON 问答已接通。
管理员入口为 /ingest，支持来源、探测、采集记录、模型配置与用量。使用与最新验收见 [后台与真实问答](docs/admin-backoffice-and-qa.md)。

## 本地安装与启动

工具基线：Node 24.15.0、pnpm 11.22.0、Python 3.12、uv 0.11.16。从仓库根执行：

```powershell
Set-Location backend
uv sync --frozen
Set-Location ../frontend
pnpm install --frozen-lockfile
Set-Location ..
./scripts/start-dev.ps1 -Fixture
```

首页 `http://127.0.0.1:5173`，API文档 `http://127.0.0.1:8000/docs`。服务后台启动，日志在 `.run/`。关闭使用 `./scripts/stop-dev.ps1`。

`-Fixture` 显式启用合成数据，不调用付费模型。前端独立演示入口使用 `?demo=1`；普通API失败不会自动改为演示成功。合成数据不计入真实采集或历史gold验收。

## 接入 PostgreSQL

Windows 本机原先无可用 Docker/PG；现已在 Ubuntu 上运行，参见上述记录。新环境初始化示例：

```powershell
# 仅首次复制，不覆盖已填好的配置
Copy-Item .env.example .env
# 在本机填写数据库密码、管理凭据等
docker compose up -d db
Set-Location backend
uv run alembic upgrade head
Set-Location ..
./scripts/start-dev.ps1
```

默认模式为PostgreSQL；数据库未配置/不可用应显示明确故障，不返回虚假的空事件库。模型凭据和付费预算未配置时不得伪造问答。镜像采用规格的 `pgvector/pgvector:0.8.6-pg16-bookworm`，Ubuntu 已拉取并记录 digest，见 Ubuntu 开发记录。

## 验证

```powershell
./scripts/verify.ps1
./scripts/check-frontend.ps1 -BaseUrl http://127.0.0.1:5173
python scripts/check-api.py --base-url http://127.0.0.1:8000
python scripts/validate-sources.py
```

`verify.ps1` 执行静态检查、单元测试、24项显式过滤结构回归、30项确定性计划HTTP检查、3项连接拒绝检查、OpenAPI对齐和离线迁移 SQL 生成；新增真实 PostgreSQL 集成测试及运行条件见 docs/db-live-validation.md。离线SQL编译和迁移SQL生成不等于真实PG迁移/向量测试。

原型比较：分别在两个 `prototypes/*` 目录执行 `npm ci` 和 `npm run dev -- --host 127.0.0.1 --port <4174或4173>`，再执行 `./scripts/check-prototypes.ps1`。运行前需本机已安装 `agent-browser` 及浏览器；结果写入 `docs/prototype-browser-results.json`。

## 当前边界

5 个真实 RSS 与正文样本已通过生产抓取，原文持续保存到 Ubuntu 的真实 PG。备份/隔离恢复已通过。没有历史原站 ID 与 gold 材料，也没有模型凭据和付费预算。100 条真实标准事件、模型质量、旧 API/SSE 兼容和生产部署仍未完成。

详细证据：[原型比较](docs/prototype-comparison.md)、[来源探测](docs/source-validation.json)、[实施记录](docs/execution-log.md)、[验收矩阵](docs/acceptance-matrix.md)。

用户已取消周额度 80% 停止规则；历史额度脚本不再作为继续开发的门槛。

## 生产抓取路径与网络配置

早期系统 DNS 返回 Fake-IP，生产抓取器按预期拒绝。Ubuntu 已使用显式配置的 Cloudflare DoH，
保持公网地址验证和 IP 固定；五源正文样本已通过。默认 FETCH_DNS_MODE=system，仅需时选择 cloudflare。

```bash
backend/.venv/bin/python scripts/validate-source-bodies.py
```

报告为 docs/source-body-validation.json，只取每源1篇正文，不写数据库、不调用模型、不发布事件。此前 urllib RSS入口5/5与本次生产transport结果分开记录。即使正文解析成功，仍需后续完整提取、证据与入库验收。

## 采集进程（数据库环境就绪后）

从 backend 目录执行：

```powershell
uv run alembic upgrade head
uv run radar-register-sources
# 上一步仅注册5个候选，默认禁用。完成生产抓取验证后才显式启用：
uv run radar-register-sources --enable
# 以下两个进程分别运行，API不会兼任定时器或worker：
uv run python -m app.scheduler
uv run python -m app.worker
```

注册命令按来源名幂等更新；再次不带 --enable 运行会把这些候选设为禁用。来源健康表示RSS发现状态，正文解析失败与最终任务失败在运行记录中分别统计。当前采集止于冻结正文版本与待审候选，已发布事件数保持0；模型提取、发布、embedding及回答生成尚未完成。预算预留表和调用账本表已建模，实际计费执行与结算仍未实现。
