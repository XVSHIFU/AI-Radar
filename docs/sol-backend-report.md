# Sol 后端核心切片实施报告

## 已实现

后端使用 Python 3.12、FastAPI、Pydantic 2、SQLAlchemy 2 async、asyncpg 与 Alembic。稳定入口为 `app.main:app`，业务包为 `radar`。

默认 `RADAR_DATA_MODE=postgres`。配置从仓库根 `.env` 读取，数据库优先支持 `DATABASE_URL`，也支持 `DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD` 并通过 `URL.create` 安全构造。数据库未配置时数据端点返回 `DATABASE_UNAVAILABLE` 503。只有显式 `RADAR_DATA_MODE=fixture` 才加载 32 条 `synthetic-ui-v1` 数据，响应包含 `data_mode=fixture` 与 synthetic 标识。

实现端点：

- `/health`、`/health/live`、`/health/ready`；生产 ready 检查 Alembic head 与 pgvector，fixture 明确 `postgres_ready=false`。
- `GET /api/v1/events`：关键词、分类、日期双端、importance、entity all/any、精确 total、稳定 keyset 分页。游标签名并绑定过滤条件，篡改或跨条件复用返回 422。普通列表的 revision 明确不承诺跨页快照冻结。
- `GET /api/v1/events/{id}` 与 `/evidence`：只读 published 事件。Evidence 摘录必须定位到冻结 ArticleVersion JSONB 段落；fixture 只给一个独立定义的合成文章版本，其余缺证据事件保持空。
- `stats/insights/sources`：PG 统计用全库 SQL；头条在业务时区当天全部候选上按 importance、ID 排序后取 3。
- `POST /api/v1/ask`：无结构化范围且模型未配置时返回 MODEL_UNAVAILABLE；只有显式、受支持的结构化范围真正空集才返回 completed/no_answer。非空且未配置模型返回 503。
- 管理端未配置管理 token 返回 MANAGEMENT_UNAVAILABLE 503；已配置但缺失或错误 token 返回 401；通过鉴权后因队列尚未实现返回明确 503，不伪造 202。

## 验证记录

在 `backend/` 执行：

```powershell
uv sync --python 3.12
uv run ruff format .
uv run ruff check .
uv run mypy src app
uv run pytest -q
uv run alembic upgrade head --sql
$env:RADAR_DATA_MODE='fixture'
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

最终结果：

- uv 0.11.16，CPython 3.12.13；42 packages，`uv.lock` 已生成。
- Ruff 通过。首轮有 74 个格式/import 问题，自动格式化与修复后通过。
- mypy strict 通过。中间因 SQLAlchemy Row 到 dict 的类型推断失败 1 次，改为显式 comprehension 后通过。
- pytest：19 passed，2 个第三方弃用 warning，0 failed。首轮 9 passed；预审调整后出现 3 次单断言/旧语义失败并逐项修复。
- Alembic PostgreSQL offline 编译通过，输出 pgvector extension、核心表、外键与索引。
- HTTP 冒烟：`/health/ready` 返回 fixture_ready / postgres_ready=false；`/events?limit=1` 返回 total=32。
- `openapi.generated.json` 已生成并成功解析为 OpenAPI 3.1.0，供供公共 contracts 审查后搬运。

## 未通过或未实施

当前环境没有 PostgreSQL 实例，因此没有执行真实 PG migration、事务隔离、seed 后 repository 行为或 pgvector 集成测试；这些不计为通过。没有用 SQLite 替代。采集队列和真实问答模型不在本切片内，端点返回明确未配置/未实现状态。

补充：父任务独立 HTTP 验收 14/14 通过，结果由父任务维护。
