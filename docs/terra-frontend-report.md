# Terra 正式前端交付

位置：`frontend/`。默认请求相对 `/api` 和 `/health`，由 Vite 代理至 `RADAR_API_TARGET`（未设置时 `127.0.0.1:8000`）。仅 URL 显式 `?demo=1` 使用合成 fixture；API 故障不会自动回退为演示成功。

已实现：首页的 URL 同步、300ms 防抖、AbortController 取消旧请求、精确 total 与游标分页；独立可刷新详情；真实非流式问答与取消状态；内存令牌的采集管理；集中 API 类型、适配层与 SSE 解析器。演示模式对数据、摘录和问答限制均有可见标识。

验证命令：`pnpm typecheck`、`pnpm test`、`pnpm build`。最终均通过；SSE 测试覆盖 UTF-8 中文、CRLF、多行、心跳、error、无 done 的 EOF 和取消。首次 pnpm 安装因本机 pnpm 默认阻止 esbuild/Tailwind 构建脚本失败；在项目 `pnpm-workspace.yaml` 显式仅允许这两个依赖后重试通过。首次类型检查还修复了单文件组件分隔符、详情模板和 fixture 路径，最终构建约 0.6 秒。

未完成项：后端尚未提供流式问答端点，因此 UI 不会冒充真实 SSE 成功；模拟流开关尚未接入页面，集中解析器和测试已就绪。真实后端联调、管理端点行为和 390/768/1440 浏览器验收仍需在后端服务启动后完成。

启动：`cd frontend; pnpm dev --host 127.0.0.1 --port 5173`。

预审修订：SSE 解析器现保留跨块 CRLF 的末尾 CR、在 abort 时取消并释放 reader、拒绝未知事件、sources 后 token、重复/未知状态 done 与无 done EOF。冻结 normal/empty/failed/truncated 样本以单字节流验证通过；normal 保留非连续引用 index=2，failed 不被当作成功。后端响应 data_mode=fixture 也会触发演示标识。
