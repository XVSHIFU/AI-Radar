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

## 修订：移动筛选与数据措辞

- 390px 宽度下保留关键词输入，分类和日期默认折叠到“分类与日期”按钮；按钮最小高度 44px，带 `aria-controls` 与 `aria-expanded`。
- 日期起始值晚于截止值时显示“日期范围无效”说明，避免将倒置区间误报为无结果。
- `evidence_count` 统一展示为“条关联证据（演示）”，不再将 fixture 计数描述为已核验。
- 使用独立本地浏览器会话在 390×844 验收：默认 `expanded=false`；键盘聚焦按钮并按 Space 后变为 `expanded=true` 且分类/日期控件出现；再次按 Space 后恢复 `expanded=false`。

本次修订首次构建因模板中遗留三元表达式而失败（约 9.7 秒），修正后复验在约 8.2 秒通过；失败/重试为 1/1。
