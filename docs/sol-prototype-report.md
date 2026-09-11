# Sol 首页候选 A 实施报告

## 结果

已在 `prototypes/sol/` 实现 Vue 3 + TypeScript + Vite + Tailwind CSS v4 的编辑式资讯首页。页面直接导入 `contracts/prototype-events.json`，使用完整 32 条 `synthetic-ui-v1` 合成数据，并在首屏和页脚明确声明其不是新闻。

功能包含关键词搜索、分类筛选、双端包含日期筛选、倒置日期校验、精确匹配总数、每页 8 条分页、日期加 ID 稳定排序、详情入口，以及加载、空、失败和重试状态。fixture adapter 在筛选变化时取消旧请求并保留输入。

响应式包含 390px 单列与可折叠筛选、768px 主流布局、1440px 内容加 280px 全库态势侧栏。控件最小高度 44px，提供键盘焦点、语义区域、`aria-live`、`aria-busy`、搜索可访问名称和日期错误提示。

## 实际命令与验证

工作目录：`prototypes/sol/`。

| 命令 | 结果 | 失败 / 重试 | 实测耗时 |
| --- | --- | --- | --- |
| `npm install` | 成功，生成 `package-lock.json`；63 packages，0 vulnerabilities | 0 / 0 | npm 报告 3s |
| `npm run typecheck` | 首轮发现 `aria-busy` 字面量类型错误；修复后通过；响应式修复后再通过 | 1 / 1，随后额外回归 1 次 | 失败约 3.0s；通过 3.0s；回归 3.0s |
| `npm run build` | 首轮因同一类型错误失败；修复后通过；响应式修复后再通过 | 1 / 1，随后额外回归 1 次 | 失败约 3.0s；通过 5.9s；回归 4.2s（Vite 511ms） |
| `npm run dev -- --host 127.0.0.1 --port 4173` | 成功启动；4173 已占用，Vite 自动使用 4174 | 0 / 0，端口自动回退 1 次 | 364ms |
| `agent-browser --session sol open http://127.0.0.1:4174` | 页面标题与 URL 正确 | 0 / 0 | 约 6.4s |
| `agent-browser --session sol set viewport 390 844` + DOM 宽度检查 | `scrollWidth=clientWidth=375`，无页面横向溢出 | 0 / 0 | 约 4.9s |
| 浏览器搜索 `DeepSeek` | 精确返回 6 条；结果均为模型发布合成事件 | 0 / 0 | 约 5.9s |
| 移动筛选展开 | `aria-expanded` 从 false 变为 true；首轮命令因 PowerShell 未引用 `@ref` 失败，引用后成功 | 1 / 1 | 成功重试约 4.6s |

首轮浏览器复核发现自定义 CSS 覆盖 Tailwind 的响应式 `hidden`，已改为显式媒体查询；同时补齐搜索框可访问名称与倒置日期独立错误态。最终 `typecheck`、`build` 与 `git diff --check` 通过。

生产构建产物：HTML 0.49 kB，CSS 14.51 kB（gzip 4.16 kB），JS 89.24 kB（gzip 31.45 kB）。

## 启动

```powershell
cd prototypes/sol
npm install
npm run dev -- --host 127.0.0.1 --port 4173
```

若端口 4173 被占用，以 Vite 输出的下一个本机端口为准。
