# AI 革新雷达

本仓库正在按实施规格 v1.0 落地。当前工作区是 `E:\AI-AGENT\AI-Radar-Implementation-Spec\codex`，覆盖旧方案中的 C 盘示例路径。

首页候选已实际运行比较，采用 Terra 研究工作台。两候选共用浏览器DOM回归 **14/14通过**，保留在 `prototypes/sol` 和 `prototypes/terra`。正式前后端正在集成，最终状态以 [验收矩阵](docs/acceptance-matrix.md) 为准，不能把原型通过算成 P0 完成。

## 工程结构

- `frontend/`：Vue3、TypeScript、Vite、Tailwind4 四页与API适配。
- `backend/`：FastAPI、SQLAlchemy、PostgreSQL仓储与显式合成演示仓储。
- `contracts/`：接口基线、共享演示数据、新版SSE协议样本。
- `scripts/`：本地启动/停止、验证、RSS入口验证和Codex周额度检查。
- `docs/`：设计、原型比较、实施记录和逐项验收证据。

## 本地安装与启动

工具基线：Node 24.15.0、pnpm 11.13.0、Python 3.12、uv 0.11.16。正式前后端合入后，从仓库根执行：

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

本机未安装可用Docker/PG，WSL启动返回HCS服务不可用；用户已同意先推进工程。环境就绪后：

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

默认模式为PostgreSQL；数据库未配置/不可用应显示明确故障，不返回虚假的空事件库。模型凭据和付费预算未配置时不得伪造问答。镜像采用规格的 `pgvector/pgvector:0.8.6-pg16-bookworm`，本机尚未拉取验证digest。

## 验证

```powershell
./scripts/verify.ps1
python scripts/validate-sources.py
./scripts/check-codex-quota.ps1
```

`verify.ps1` 的真实数据库测试依赖专用 `TEST_DATABASE_URL`；没有实例时会明确跳过。离线SQL编译和迁移SQL生成不等于真实PG迁移/向量测试。

原型比较：分别在两个 `prototypes/*` 目录执行 `npm ci` 和 `npm run dev -- --host 127.0.0.1 --port <4174或4173>`，再执行 `./scripts/check-prototypes.ps1`。运行前需本机已安装 `agent-browser` 及浏览器；结果写入 `docs/prototype-browser-results.json`。

## 当前边界

5个真实RSS入口均解析成功，完整正文/提取/Evidence链路尚未验收。没有历史原站ID与gold材料，没有模型凭据和付费预算，没有真实PG实例。100条真实标准事件、真实模型质量、原站旧API/SSE兼容、生产部署与恢复演练均不能标为完成。

详细证据：[原型比较](docs/prototype-comparison.md)、[来源探测](docs/source-validation.json)、[实施记录](docs/execution-log.md)、[验收矩阵](docs/acceptance-matrix.md)。

开发停止规则：仅看用户Pro周额度，起始剩余95%，**剩余到80%即停止所有模型工作**。检查脚本只读本地会话用量记录，未知/过旧记录需要复核；周额度变化不能换算实际现金费用。
