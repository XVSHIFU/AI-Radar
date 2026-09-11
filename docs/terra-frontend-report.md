# Terra 正式前端交付

位置：`frontend/`。默认请求相对 `/api` 和 `/health`，由 Vite 代理至 `RADAR_API_TARGET`（未设置时 `127.0.0.1:8000`）。仅 URL 显式 `?demo=1` 使用合成 fixture；API 故障不会自动回退为演示成功。

已实现：首页的 URL 同步、300ms 防抖、AbortController 取消旧请求、精确 total 与游标分页；独立可刷新详情；真实非流式问答与取消状态；内存令牌的采集管理；集中 API 类型、适配层与 SSE 解析器。演示模式对数据、摘录和问答限制均有可见标识。

验证命令：`pnpm typecheck`、`pnpm test`、`pnpm build`。最终均通过；SSE 测试覆盖 UTF-8 中文、CRLF、多行、心跳、error、无 done 的 EOF 和取消。首次 pnpm 安装因本机 pnpm 默认阻止 esbuild/Tailwind 构建脚本失败；在项目 `pnpm-workspace.yaml` 显式仅允许这两个依赖后重试通过。首次类型检查还修复了单文件组件分隔符、详情模板和 fixture 路径，最终构建约 0.6 秒。

未完成项：后端尚未提供流式问答端点，因此 UI 不会冒充真实 SSE 成功；模拟流开关尚未接入页面，集中解析器和测试已就绪。真实后端联调、管理端点行为和 390/768/1440 浏览器验收仍需在后端服务启动后完成。

启动：`cd frontend; pnpm dev --host 127.0.0.1 --port 5173`。

预审修订：SSE 解析器现保留跨块 CRLF 的末尾 CR、在 abort 时取消并释放 reader、拒绝未知事件、sources 后 token、重复/未知状态 done 与无 done EOF。冻结 normal/empty/failed/truncated 样本以单字节流验证通过；normal 保留非连续引用 index=2，failed 不被当作成功。后端响应 data_mode=fixture 也会触发演示标识。

本轮继续修复：首页保留 ?demo=1、立即取消旧请求并以 generation 防止旧响应覆盖；移动端恢复筛选折叠、清除及范围卡片。详情在路由参数改变时取消旧请求并显示未找到。问答演示模式已接入明确标记的可取消模拟 SSE 流。SSE 冻结样本在本地未提交副本下以单字节验证。尚未宣称正式验收完成，需后端及浏览器四页验收。

本轮协议测试扩展为 5 项：冻结 normal/empty/failed/truncated 的逐字节 CRLF、状态终态、协议顺序、挂起 read abort/cancel/release、真实延迟竞态。首页已实际浏览器验证 ?demo=1 首屏精确匹配32；stats 单独请求与错误态、两栏网格均已修复。

采集管理修订：sources 与 runs 独立读取、独立加载/401/503/重试状态；读取或提交期间禁用动作。令牌仅页面内存。提交防重，失败重试保留同一 Idempotency-Key，成功后才轮换；submission 单测覆盖重复点击只取得一次请求键与失败重试复用。

问答修订：演示 SSE 在 150–1600ms 分段产生状态、token、来源、done，取消会清除全部 timer；分类与日期条件可见、会校验并随真实请求发送。真实与模拟引用均按 index 展开、受安全 URL 限制，统计来自 done/API 响应；每个 await/帧按 generation 守卫，卸载取消。

审查修订：isDemo 仅由 URL 显式 demo=1 决定，服务端 fixture 仅显示合成标识；SSE 在 error 后拒绝 completed/cancelled done；采集仅在存在启用来源时可提交。

SSE 终态修订：sawError 后仅允许 done.status=failed；新增 error-before-token completed 拒绝、error-after-token completed 拒绝、error+failed 通过三项测试。当前 pnpm test 共9项通过。

问答结果提取修订：新增 ask-result 强类型校验，服务端 index 原样呈现；缺失、非正、重复索引成为协议错误。新增 index=2、索引缺失/重复、no_answer/partial/failed/cancelled 业务状态测试。pnpm test 共12项通过。

AskPage 实际接入修订：真实响应调用 askView、使用原始 citations 与其 index、状态取 view.status；页面显示 no_answer 与 partial 提示。AskPage rg 已确认无数组重编号或 ref<any；问答结果测试覆盖零/负/小数索引。

本轮返修：RouterView key 改为响应式 route.path 与 route.query.demo；样式重构为单一主题变量集，移除旧 padding/状态覆盖重复规则，补标题正文间距和侧栏 align-self:start。仅执行 typecheck/build，均通过。
