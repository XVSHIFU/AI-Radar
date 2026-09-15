# 助手布局比较：实现与设计系统核验

2026-09-15。本记录针对 `/assistant-preview` 六套可交互布局及本轮指定的小范围正式页面修复。它不是正式布局选定记录，也不替代完整方案验收。

## 核验结果

- **六套结构已实现，仍待用户选择。** `AssistantPreview.vue` 提供 A 侧栏阅读、B 轻气泡对话、C 证据优先、D 上下工作区、E 对话时间线、F 浮动便笺；共享 `preview/AssistantConcept.vue` 的本地演示状态。预览不调用模型、不读取真实会话，不表示专用 Agent 已完成。
- **沿用 16 套主题。** 预览直接使用 `themes.ts` 的 `themes`、`activeTheme`、`applyTheme`；样式以现有 `--bg`、`--rail`、`--paper`、`--blue-soft`、`--blue`、`--ink`、`--muted`、`--line` 表达层次。没有为六套布局另设固定配色或永久主题令牌。
- **保留字体 B 与中英文。** `reading-typography.css` 的阅读栈为 RadarInter / RadarSansSC，标题栈为 RadarSourceSerif / RadarSerifSC；预览继承这两个角色。正文 14px、行高 1.85，手机输入 16px；提示与操作元信息为较小字号。界面使用现有 `translate` / `locale` / `setLocale`，未另建语言状态。
- **交互分层有明确职责。** 范围与导航在顶部，对话区独立滚动，输入区在底部。六套通过气泡、资料区、页签、时间线或内缩轮廓区分结构，SVG 图标承担常用操作；输入焦点以主题描边表示。
- **正式页面仅做约定修复。** `assistant-controls.css` 修正助手位于 `.app-shell` 外造成的样式作用域遗漏，恢复主题背景、输入面的内边距与圆角；空态占据剩余对话空间。来源详情入口及指定日期/图表按钮的处理见调研记录，未将新背景反馈扩散至其他操作。

## 已有验证证据

本次文档核验只读代码和已有资料，没有再次启动浏览器或生成截图。

| 验证 | 证据及边界 |
| --- | --- |
| 六套桌面与手机布局 | 根任务已执行 1440px / 390px 合并检查。手机以 `.run/concept-desk-mobile.png`、`concept-bubble-mobile.png`、`concept-evidence-mobile.png`、`concept-workspace-mobile.png`、`concept-timeline-mobile.png`、`concept-note-mobile.png` 的最新真实视口截图为准 |
| 状态覆盖 | 已有空态、历史、来源、中断英语等 `concept-*-mobile.png`；流式为本地模拟，不是付费模型质量验收 |
| 工程检查 | 根任务报告 42 项前端测试、类型检查与构建通过 |
| 独立审查 | 历史状态旧定时器问题已修正；最终审查结论由根任务在发布记录中补充，不将尚未收到的结论写成通过 |
| 指定来源入口与悬停 | 已由独立任务验证；本记录不扩大其验证范围 |

## 系统边界与未处理漂移

本轮没有形成需推广至全站的新永久设计令牌。六套方案的尺寸、排列、轮廓和输入区位置仍属于候选表面，不写入全局设计规范。保留 `DESIGN.md`、`.impeccable/design.json` 和 `PRODUCT.md` 原状。

已发现旧 `DESIGN.md` 仍记录早期 Inter 标题与单套初始色值，`PRODUCT.md` 部分能力状态也早于当前部署；这些是既有文档漂移，本轮用户只要求助手布局比较及指定修复，因此不顺带刷新，更不以旧记录推翻已确认的字体 B、16 主题和实际工程能力。当前功能进度以 [完整方案审计](implementation-audit-2026-09-15.md) 为准。

设计依据、六方案取舍与公开资料访问限制见 [调研与方案记录](assistant-layout-research-2026-09-15.md)，表面约束见 [助手布局表面说明](../.impeccable/surfaces/assistant-layout-options.md)。

## 最终结果

独立 reviewer 的完整检查 disposition=fix，仅要求修复历史选择没有终止旧模拟流。已实现 selectHistory 先 stop()，实际新发送→生成中→打开历史→选择条目后 running=false、预置回答完整；最终 verdict=resolved，remaining=clear，disposition=ship，仅覆盖该修复项。

2026-09-15 已部署至用户授权的 Ubuntu。/assistant-preview 在线浏览器确认六套方案、输入区均加载，且没有重复正式助手；生产构建通过，API/worker/frontend 保持 active。方案没有替用户选择正式布局。旧元素裁剪截图出现偏移，手机有效证据仅使用最后一次不带selector的真实viewport截图。
