---
version: 1
slug: "frontend-src-homepage-vue"
primary_target: "frontend/src/HomePage.vue"
related_targets: ["frontend/src/DetailPage.vue","frontend/src/AskPage.vue","frontend/src/IngestPage.vue","frontend/src/App.vue"]
---

# Four-page redesign
Scope: /, /events/:id, /ask, /ingest. Visitor mode: Operate with Read-first home. User confirmed 2026-09-12: personal + public audience; read AI developments before deeper query; code-first; desktop reading space + cloud cross-sections + notation rhythm, with the hierarchy below. The prior accidental choice is superseded by this explicit chat approval.

## Direction contract
THESIS: A continuous reading workspace, not a wall of interchangeable dashboard cards. Events lead; filters and evidence stay within reach.
OWN-WORLD: Light is chosen for everyday daylight desktop/mobile reading. Restrained silver-blue ground, distinct white reading planes, deep blue active controls, dark ink. Consistent compact SVG icons and workhorse Chinese UI type; no decorative cloud pictures, fog, 3D scenery or dance symbols.
STORY: Scan dated AI events, narrow the complete library, open a readable event, then unfold saved source paragraphs. Ask and ingestion inherit the same structure and states.
FIRST VIEWPORT: Desktop has a compact left navigation rail, broad central dated event stream, and quiet narrow context pane. A clear page title and integrated search/filter strip sit above the stream; events dominate height. Mobile uses top navigation and a single readable column; secondary range controls collapse. Primary action is search or opening an event, not a marketing CTA.
FORM: Grounded candidate 7, desktop reading space, seed a7d9cf2b. User combines cloud-quarry's clearly separated planes and labanotation's aligned temporal rhythm. Dates read top-to-bottom normally. Six challenger discipline raises remain in planning notes; user selection overrides previous declined verdicts for cloud and notation.
INTERACTION: One signature is the evidence layer unfolding inline with visible source/version/paragraph anchoring; date alignment carries scan rhythm. Short height/clip or grid-row transition, already-visible defaults, reduced-motion equivalent. Every hover/disabled/loading/empty/error state, selection/caret/focus and numeric alignment belongs to the same system.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

Constraints: Keep API/SSE, exact total/paging, URL state, request cancellation, citation indexes, plan/error guards, safe links and memory-only admin token. Synthetic data remains visibly labeled. No new backend, no generated news/metrics, no automatic paid requests. Review desktop/mobile all four pages. No raster is required by the agreed interpretation.

## 2026-09-13 · 时间层级与叠层抽屉

用户明确要求在现有首页扩展功能和个性，保留已认可的简洁银蓝阅读界面。无需重新选择视觉世界；默认代码优先。

THESIS: 在同一阅读位置逐层深入事件、来源与证据；时间线可折叠成日期档案。
OWN-WORLD: 沿用深蓝文字、银蓝底、白色纸面，以年份标记、月份页签与真实抽屉边缘建立辨识度。没有无内容的装饰面板。
STORY: 点击年/月/日收回其后代；展开事件→来源→证据，逐层返回后恢复列表位置。保留详情直链、新标签打开及筛选状态。
FIRST VIEWPORT: 日期层级简明可操作，事件内容仍主导阅读；桌面叠层保留上一层边缘，手机全宽前景层显示返回路径。
FORM: 既有世界的明确功能扩展；沿用先前seed a7d9cf2b，不进行新的方向抽签。
INTERACTION: 短促的抽屉平面位移是主要动效；键盘Esc、返回、焦点恢复与减少动态效果等效可用。每层有加载、缺失、错误与重试状态。
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

数据约束：年/月/日分组只统计当前已加载匹配事件，标明“已加载”，不冒充完整周期统计；精确匹配总数保持来自API。折叠不删除数据，翻页追加不擅自展开已关闭分组；无日期明确归类。来源或全文不存在时如实说明，不能由前端生成报道。抽屉URL保留现有过滤条件，返回层级不触发列表无条件重载。
