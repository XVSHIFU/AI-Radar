# 动效、SVG 与六套布局提案验收记录

2026-09-15；比较基线 `002c48f`。本记录描述已落码的交互扩展与待选择提案，不代表全站批准、公开上线或真实数据链路验收。

## 交付与设计权威

正式站点保留 [DESIGN.md](../DESIGN.md) 的桌面阅读空间、冷银蓝阅读面、独立统计与 16 套主题。新增抽屉进退、全路由悬浮研究助手及 SVG 标识；六套全站布局是独立预览，尚未选定，不替换首页或重写 `.impeccable/design.json`。

预览入口：<http://192.168.194.129:5173/design-directions/index.html>（依赖本地预览服务与网络可达）。源码：[index.html](../frontend/public/design-directions/index.html)、[directions.js](../frontend/public/design-directions/directions.js)、[directions.css](../frontend/public/design-directions/directions.css)。研究依据和方向契约见 [设计调研](design-refresh-research.md)。

| 方向 | 相对现有布局的主要变化 | 取舍 |
| --- | --- | --- |
| A 阅读目录 | 顶部导航、主题侧索引、连续单栏 | 公共阅读与检索均衡，视觉较克制 |
| B 研究刊物 | 刊头、宋体标题、日期边注、窄阅读栏 | 长文更舒适，同屏数量较少 |
| C 即时电讯 | 窄侧栏、紧凑工具带、对齐事件行 | 扫描效率高，首次使用者需要引导 |
| D 编辑选刊 | 重点与短讯不对称组合 | 品牌层级明显，实际重点排序需解释 |
| E 数据图鉴 | 左导航、事件主栏、分类侧注 | 方便比较，辅助数字需要节制 |
| F 公共导览 | 黄色导航带、分类入口、编号事件 | 容易扫描，色带使用范围需控制 |

现有方案仍是有效比较项；本次并未证明任何提案整体优于现有站点。提案展示首页、统计、后台及事件/助手交互；内容、回答、探测均为合成示例，无真实后端采集或模型调用，不是完整生产功能复制。A/B 是供用户优先比较的建议，不是选定结果。

## 已实现的动效与生命周期

实际来源：[style.css](../frontend/src/style.css)、[EventDrawers.vue](../frontend/src/EventDrawers.vue)、[AssistantPanel.vue](../frontend/src/AssistantPanel.vue)、[App.vue](../frontend/src/App.vue)。以下是此扩展的实现值，未建立新的全站主题令牌。

| 对象 | 进入 | 退出 / 减少动态 |
| --- | --- | --- |
| 抽屉 | 420ms，`cubic-bezier(.16,1,.3,1)`；透明度与横移 32px | 260ms，`cubic-bezier(.4,0,1,1)`；反向横移与淡出；减少动态关闭位移动画 |
| 抽屉遮罩 | 180ms `ease-out` 淡入 | 260ms `ease` 淡出；退出期间继续挡住背景 |
| 助手面板 | 圆形裁切从 24px 展至 150vmax，420ms 同抽屉缓出；透明度 180ms | 裁切反向 260ms，透明度 160ms；减少动态使用 120ms 透明度过渡 |
| 助手浮标 | 圆形 48×48px，SVG 24px；悬停上移 2px、160ms | 面板进退期间隐藏浮标；减少动态取消悬停位移 |

助手浮标 Teleport 到 body，App 全局挂载，因此维护页和已有预览外壳也有入口。桌面距底 24px；900px 及以下距右、底各 16px。展开前读取浮标实际中心，写入 `--assistant-origin-right` / `--assistant-origin-y`，供裁切原点使用。图形通过 `currentColor` 跟随现有主题。

抽屉关闭先标记 leaving，260ms 后关闭 dialog；最外层退出后才清除遮罩、恢复背景交互、滚动和入口焦点。关闭中的面板拦截交互，重新打开会取消相应关闭计时。手机通过非模态 dialog、背景 inert 与键盘循环维持抽屉/助手入口可操作。手机从抽屉进入助手时先清除相关 query，等抽屉退出再展开助手。

助手采用 Vue Transition 与 `v-show`，退出动画保留正文、历史和会话 DOM；关闭取消当前生成，但不丢弃历史。`after-leave` 才恢复外层布局和浮标；焦点恢复检查当前抽屉 query 与打开的 dialog，避免抢走新弹层焦点。最终审查确认焦点恢复保护及提案主要装饰性 kicker 删除两项修复已解决，结论为 ship，仅适用于这两项受审范围。

## 素材与字体来源

- 品牌 [RadarMark.vue](../frontend/src/RadarMark.vue) 与助手 [AssistantMark.vue](../frontend/src/AssistantMark.vue)：Lucide `radar`、`bot-message-square`，经 Iconify 获取；原始 SVG、来源链接和许可证见 [icons/README.md](../frontend/public/icons/README.md)、[LUCIDE-LICENSE](../frontend/public/icons/LUCIDE-LICENSE) 及同目录 SVG。
- [favicon.svg](../frontend/public/favicon.svg)：自定义小尺寸雷达几何，由 [frontend/index.html](../frontend/index.html) 引用。预览导航 SVG 为同一线条语言的自定义几何。
- 提案自托管 Noto Sans SC / Noto Serif SC 子集：[sans.woff2](../frontend/public/design-directions/fonts/sans.woff2)、[serif.woff2](../frontend/public/design-directions/fonts/serif.woff2)；随附 [sans-OFL.txt](../frontend/public/design-directions/fonts/sans-OFL.txt)、[serif-OFL.txt](../frontend/public/design-directions/fonts/serif-OFL.txt)，均为 SIL OFL 1.1。无运行时外部字体依赖；这些字体没有应用到正式站点。

## 验证证据与边界

执行主代理报告全部代码修复后前端 38 项测试及生产构建通过；本记录整理过程未重跑测试。浏览器证据位于 [.impeccable/review/motion-report.json](../.impeccable/review/motion-report.json) 与 [screenshots](../.impeccable/review/screenshots/)：

- 共 41 张截图：40 张矩阵截图（A–F × 首页/统计/后台 × 1440/390px 共 36 张，加正式助手/抽屉 × 两宽度共 4 张），另加 `production-390-attachment-handoff.png`。
- JSON 含 46 条观察记录（不是 46 张截图）：36 个提案布局状态及 10 个正式交互观察。已记录状态无水平溢出；两宽度记录浮标可命中、抽屉退出途中仍打开且遮罩存在、结束后 dialog 关闭且背景解除 inert。
- 补充 [handoff-report.json](../.impeccable/review/handoff-report.json) 的 7 项检查记录来源层退出时正文保留；手机助手转附件后焦点为 drawer-event、助手隐藏；从抽屉浮标进入助手后抽屉关闭；/ingest、/ask、/preview 浮标均可命中；减少动态检查中抽屉 animation 为 none。
- 截图和尺寸记录只覆盖所列状态；不证明所有主题、键盘序列、辅助技术及真实 API 均已通过。最终审查的 ship 结论仅覆盖焦点恢复和主要装饰性 kicker 两项修复，不构成全站批准。

## 上下文漂移登记

既有 PRODUCT.md 仍以“四条主要路径”概括产品；DESIGN.md 已明确 `/ask` 为独立统计与问答页。这是本次之前已有的描述粒度差异，本次不调整产品范围。

本扩展使 DESIGN.md 中“移动正常流提问入口”“手机 showModal”及旧助手入口组件描述不再完全对应当前代码；当前改为悬浮 SVG 入口与显式背景保护。它们属于本次扩展产生的待同步项，不能借此把任何提案视觉写入正式设计系统。正式视觉权威文件保持原样，后续同步需沿用已确认设计世界并区分提案选择。


