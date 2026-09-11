# Terra 候选 B：研究工作台首页

## 交付范围

实现位于 `prototypes/terra`，技术栈为 Vue 3、TypeScript、Vite 与 Tailwind CSS v4。

- 直接导入共享 `contracts/prototype-events.json`，页面顶部明确标注 `synthetic-ui-v1` 合成 fixture 和 32 条数据范围。
- 实现关键词（标题、摘要、实体）、分类、双端包含日期筛选；结果区展示精确匹配总数和已采用条件。
- 固定每页 6 条，提供上一页/下一页，事件标题与“查看详情”都指向 `/events/{id}`。
- 包含延迟加载骨架、保留条件的模拟可重试错误态和说明合成数据日期范围的空态。
- 响应式为 1440px 三栏、768px 内容流适配、390px 单列；包含可见焦点、`aria-live`、`aria-busy` 与非纯颜色的状态文案。

## 实际验证

在 `prototypes/terra` 运行：

```powershell
npm install
npm run typecheck
npm run build
npm run dev -- --host 127.0.0.1 --port 4173
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:4173/
```

结果：`typecheck` 与 `build` 均通过；Vite 开发服务器约 426ms 就绪，本机 HTTP 请求返回 200。

安装耗时约 6 秒。构建验证共 3 次：第 1 次（约 7.6 秒）发现 fixture 相对导入路径错误及其引发的推断类型错误；第 2 次（约 8.6 秒）发现模板中的分类标签索引类型错误；第 3 次（约 9.0 秒）通过。失败/重试次数为 2/2。`npm install` 报告 1 个 high severity 的传递依赖审计项，未在原型内执行破坏性升级。

## 启动命令

```powershell
cd E:\AI-AGENT\AI-Radar-Implementation-Spec\codex\.worktrees\terra\prototypes\terra
npm run dev -- --host 127.0.0.1 --port 4173
```
