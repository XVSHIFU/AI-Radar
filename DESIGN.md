---
name: AI 革新雷达
description: 桌面阅读空间，以云层切面承载证据，以对齐日期组织阅读节奏。
colors:
  blue: '#315e9e'
  blue-soft: '#e7edf7'
  aqua: '#e5f1f0'
  pill-ink: '#316b70'
  bg: '#f4f5f7'
  paper: '#ffffff'
  rail: '#eceff3'
  ink: '#202c3c'
  muted: '#5f6d7d'
  line: '#d1d9e3'
  focus: '#7893b0'
  pointer-focus: '#78b7d1'
  hover-line: '#9cb8d4'
  selection: '#b7d3ee'
  danger: '#a5342b'
  error-line: '#e8b5ae'
  danger-bg: '#fff0ef'
  status-bg: '#eef5ff'
  demo-bg: '#fff8e7'
  demo-ink: '#674b00'
  demo-line: '#f1d396'
  quote-bg: '#f3f7fb'
  quote-line: '#9db5ca'
  plan-bg: '#edf4fa'
  plan-line: '#c7dbe9'
  primary-hover: '#20538c'
  disabled-bg: '#e3e8ed'
  disabled-ink: '#647589'
  heat-zero: '#e8edf1'
  heat-red-start: '#f7eeeb'
  heat-step-2: '#f2dcd5'
  heat-step-3: '#eac7bd'
  heat-step-4: '#e4b4a6'
  heat-step-5: '#dba08e'
  heat-step-6: '#ce8673'
  heat-step-7: '#c2725d'
  heat-step-8: '#b65e49'
  heat-step-9: '#a94b3b'
  heat-step-10: '#9d3c2e'
  heat-step-11: '#8f3027'
  heat-red-max: '#822a23'
  heat-zero-ink: '#201511'
  assistant-answer-ink: '#16324c'
typography:
  control:
    fontFamily: Inter, "PingFang SC", "Microsoft YaHei", sans-serif
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
  display:
    fontFamily: Inter, "PingFang SC", "Microsoft YaHei", sans-serif
    fontSize: clamp(28px, 3vw, 38px)
    fontWeight: 600
    lineHeight: 1.12
    letterSpacing: -0.03em
  headline:
    fontFamily: Inter, "PingFang SC", "Microsoft YaHei", sans-serif
    fontSize: 20px
    fontWeight: 600
    lineHeight: 1.35
  event-title:
    fontFamily: Inter, "PingFang SC", "Microsoft YaHei", sans-serif
    fontSize: 20px
    fontWeight: 400
    lineHeight: 1.4
  body:
    fontFamily: Inter, "PingFang SC", "Microsoft YaHei", sans-serif
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.6
  reading:
    fontFamily: Inter, "PingFang SC", "Microsoft YaHei", sans-serif
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.7
  label:
    fontFamily: Inter, "PingFang SC", "Microsoft YaHei", sans-serif
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.6
  meta:
    fontFamily: Inter, "PingFang SC", "Microsoft YaHei", sans-serif
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.6
  date:
    fontFamily: Inter, "PingFang SC", "Microsoft YaHei", sans-serif
    fontSize: 15px
    fontWeight: 400
    lineHeight: 1.6
  pill:
    fontFamily: Inter, "PingFang SC", "Microsoft YaHei", sans-serif
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.6
  timeline-year:
    fontFamily: Inter, "PingFang SC", "Microsoft YaHei", sans-serif
    fontSize: 20px
    fontWeight: 650
    lineHeight: 1.3
    letterSpacing: -0.02em
  drawer-title:
    fontFamily: Inter, "PingFang SC", "Microsoft YaHei", sans-serif
    fontSize: 26px
    fontWeight: 600
    lineHeight: 1.28
    letterSpacing: -0.02em
  drawer-label:
    fontFamily: Inter, "PingFang SC", "Microsoft YaHei", sans-serif
    fontSize: 15px
    fontWeight: 650
    lineHeight: 1.35
  brand:
    fontFamily: Inter, "PingFang SC", "Microsoft YaHei", sans-serif
    fontSize: 17px
    fontWeight: 800
    lineHeight: 1.6
rounded:
  control: 6px
  heat: 3px
  panel: 14px
  reading: 16px
  pill: 999px
spacing:
  s1: 4px
  s2: 8px
  s3: 12px
  s4: 16px
  s6: 24px
  s8: 32px
  s12: 48px
components:
  button-secondary:
    backgroundColor: transparent
    textColor: '{colors.ink}'
    rounded: '{rounded.control}'
    padding: 4px 10px
    typography: '{typography.control}'
    height: 32px
  button-secondary-hover:
    backgroundColor: '{colors.blue-soft}'
    textColor: '{colors.ink}'
  button-primary:
    backgroundColor: '{colors.blue}'
    textColor: '{colors.paper}'
    rounded: '{rounded.control}'
    padding: 4px 10px
    typography: '{typography.control}'
    height: 32px
  button-primary-hover:
    backgroundColor: '{colors.primary-hover}'
    textColor: '{colors.paper}'
  input:
    backgroundColor: '{colors.paper}'
    textColor: '{colors.ink}'
    rounded: '{rounded.control}'
    padding: 5px 10px
    width: 100%
    typography: '{typography.control}'
  nav-item:
    textColor: '{colors.muted}'
    padding: 0 12px
    typography: '{typography.body}'
  nav-item-active:
    textColor: '{colors.blue}'
  pill:
    backgroundColor: '{colors.aqua}'
    textColor: '{colors.pill-ink}'
    rounded: '{rounded.pill}'
    padding: 3px 8px
    typography: '{typography.pill}'
  card:
    backgroundColor: '{colors.paper}'
    textColor: '{colors.ink}'
    rounded: '{rounded.panel}'
    padding: 20px
  context-panel:
    backgroundColor: '{colors.paper}'
    rounded: '{rounded.panel}'
    padding: 16px
  home-reading-plane:
    backgroundColor: transparent
    rounded: 0px
    padding: 0px
  home-reading-plane-compact:
    backgroundColor: transparent
    rounded: 0px
    padding: 0px
  reading-plane:
    backgroundColor: '{colors.paper}'
    rounded: '{rounded.reading}'
    padding: 24px 28px
  timeline-month:
    backgroundColor: '{colors.blue-soft}'
    textColor: '{colors.blue}'
    rounded: 5px
    padding: 4px 8px
  timeline-month-hover:
    backgroundColor: '{colors.blue-soft}'
    textColor: '{colors.blue}'
  filter-clear:
    backgroundColor: transparent
    textColor: '{colors.muted}'
    rounded: 6px
    padding: 2px 6px
  filter-clear-hover:
    backgroundColor: transparent
    textColor: '{colors.blue}'
  assistant-panel:
    backgroundColor: '{colors.paper}'
    textColor: '{colors.ink}'
    padding: 0px
    width: var(--assistant-width, 460px)
    height: 100dvh
  assistant-panel-compact:
    backgroundColor: '{colors.paper}'
    padding: 0px
    width: 100%
    height: 100dvh
  assistant-trigger:
    backgroundColor: '{colors.blue}'
    textColor: '{colors.paper}'
    rounded: '{rounded.control}'
    padding: 6px 12px
  statistics-plane:
    backgroundColor: transparent
    rounded: 0px
    padding: 18px 0
  chart-tab-active:
    backgroundColor: '{colors.blue}'
    textColor: '{colors.paper}'
  rank-bar:
    backgroundColor: '{colors.blue}'
    height: 18px
    rounded: 0px
  daily-bar:
    backgroundColor: '{colors.blue}'
    rounded: 0px
  heat-cell-zero:
    backgroundColor: '{colors.heat-zero}'
    textColor: '{colors.heat-zero-ink}'
    rounded: '{rounded.heat}'
    padding: 0px
  heat-cell-positive:
    textColor: '{colors.heat-zero-ink}'
    rounded: '{rounded.heat}'
    padding: 0px
  assistant-main:
    padding: 18px
    height: 100dvh
  assistant-answer:
    textColor: '{colors.assistant-answer-ink}'
  assistant-history:
    backgroundColor: '{colors.rail}'
    padding: 16px 10px
  assistant-history-compact:
    backgroundColor: '{colors.rail}'
    padding: 16px 10px

  drawer-return:
    backgroundColor: transparent
    textColor: '{colors.ink}'
    padding: 4px 8px
  drawer-return-hover:
    backgroundColor: '{colors.blue-soft}'
    textColor: '{colors.ink}'
  drawer-panel:
    backgroundColor: '{colors.paper}'
    textColor: '{colors.ink}'
    rounded: '{rounded.reading}'
    padding: 0px
  drawer-body:
    padding: 24px
    typography: '{typography.reading}'
  drawer-body-compact:
    padding: 20px
    typography: '{typography.reading}'
  quote:
    backgroundColor: '{colors.quote-bg}'
    textColor: '{colors.ink}'
    padding: 12px 16px
  demo-notice:
    backgroundColor: '{colors.demo-bg}'
    textColor: '{colors.demo-ink}'
    rounded: 8px
    padding: 8px 12px
  error-card:
    backgroundColor: '{colors.paper}'
    textColor: '{colors.danger}'
    rounded: '{rounded.panel}'
    padding: 20px
  button-utility:
    backgroundColor: transparent
    textColor: '{colors.muted}'
    rounded: '{rounded.control}'
    padding: 2px 6px
    height: 28px
  date-range-trigger:
    backgroundColor: '{colors.paper}'
    textColor: '{colors.ink}'
    rounded: '{rounded.control}'
    padding: 4px 10px
    height: 32px
  date-range-popover:
    backgroundColor: '{colors.paper}'
    rounded: 8px
    padding: 16px
    width: 440px
  calendar-day:
    rounded: 4px
    padding: 0px
    height: 30px
  control-mobile:
    height: 44px
  heat-cell-dark:
    textColor: '{colors.paper}'
    rounded: '{rounded.heat}'
    padding: 0px

---

# Design System: AI 革新雷达

## Overview

**Creative North Star: "桌面阅读空间 · 云层切面 · 动作谱"**

以桌面阅读空间为主体：冷银蓝底面直接承载首页事件流和独立统计，深蓝交互与深墨正文建立稳定层级。白色保留给上下文面板、研究助手、详情阅读面和抽屉；云层切面表现为证据核对的层次，动作谱表现为日期与正文的连续节奏。

这是依据正式 Vue 页面与最终 CSS 层叠同步的实现记录，沿用现有中文工作字体、紧凑 SVG、留白与轻边界。保持浅色阅读界面，新增16套可切换配色；导航左下角的四分之一轮盘支持拖动、滚轮与键盘，点击后应用并保存在本浏览器。没有新增字体下载、栅格素材、云景或舞蹈符号。阅读策略见 `.impeccable/surfaces/readable-insights-conversations.md`；已获用户批准的 B 控件整合见 `.impeccable/surfaces/compact-controls-integration.md`。本次将正式实现的紧凑控件写入持久设计规范，产品能力边界仍以 PRODUCT.md 为准，不代表公开上线或真实模型验收。

**Key Characteristics:**
- 冷银蓝直接阅读面、白色辅助面板与按需打开的研究助手。
- 年份保持静态定位，月与日均可折叠；日只显示数字与“日”；桌面与移动端都按自然文档顺序阅读。
- 事件与来源抽屉直接呈现保存段落；统计默认紧密红色热图，另有分类排行和每日计数；助手多会话在本浏览器保存每轮范围、消息与引用。

## Colors

主色为沉稳深蓝，辅以很浅的青色标签；底面保持冷而明亮。顶部令牌是规范值，CSS 中同名变量继续为运行时来源；未声明为 CSS 变量的组件颜色保留其实际字面值。

### Primary
- **深蓝 blue**：链接、活动导航、主要按钮和时间节点。
- **浅蓝 blue-soft**：普通按钮悬停、月份入口与选中的筛选条件。

### Secondary
- **浅青 aqua / 深青 pill-ink**：分类与实体标签的背景和文字；不是第二种主要动作色。
- **统计 heat-zero / heat-red-start / heat-red-max**：C 的零值为浅灰，正值按同图最大计数映射到12级浅红至深红；A 横向条和 B 每日柱统一深蓝。热图红色只编码收录数量，不代表风险或行业热度。

### Neutral
- **银蓝 bg / 白色 paper / 淡蓝 rail**：应用地面、辅助面板与导航轨道。首页和统计内容面为透明，直接露出 bg。
- **深墨 ink / 灰蓝 muted / 分隔线 line**：正文、辅助信息及细边界。heat-zero-ink 用于热图0–7级数字，8–12级数字为白色；assistant-answer-ink 用于助手消息。
- **quote-bg / quote-line、plan-bg / plan-line**：摘录和已解析检索条件的不同层次。
- **focus / pointer-focus、selection、hover-line**：继承的焦点、选中文本与悬停边界词汇；可见键盘焦点以当前 focus 轮廓为准。
- **danger / error-line / danger-bg**：错误文字、错误面板边框、日期校验背景；status-bg 是普通状态底色。
- **demo-bg / demo-ink / demo-line**：持续可见的合成数据与模拟模式提示。警示色同时配合实际说明文字。

**The Reading Plane Rule.** 深蓝用于链接、当前导航与主要动作；首页和统计直接落在冷银蓝底面，白色用于辅助面板、详情与证据核对。

## Typography

**Display Font / Body Font:** Inter, PingFang SC, Microsoft YaHei, sans-serif。工程没有字体下载或 @font-face；Inter 是否存在取决于设备，中文使用可用系统回退。标题沿用同一工作字体，不建立新的装饰显示字体。数字沿用 font-variant-numeric: tabular-nums，不引入独立等宽字体。

### Hierarchy
- **Display**：正式页面主标题，使用顶部 display 令牌；最大宽度30ch，常规外边距24px 0 12px。首页标题去掉顶部外边距，紧凑布局底部间距6px。
- **Headline / Event title**：阅读面章节标题为600字重、1.35行高；首页事件标题保留400字重、1.4行高。统计匹配事件标题为18px、500字重。
- **Body / Reading**：界面正文行高1.6；摘要与回答正文沿用1.7阅读行高与现有正文宽度约束。
- **Label / Meta / Date / Pill**：字段标签14px、辅助文字13px、日期词汇15px、标签12px。首页月份15px/650字重，完整日日期13px；年份使用更新后的 timeline-year 令牌，已加载计数12px。品牌17px、800字重；活动导航700字重。

**The Date Rhythm Rule.** 年份保持静态标题；月与日承担折叠，日仅显示“14 日”等简写，完整日期保留在辅助标签中。

## Layout

应用最小宽度320px。桌面使用196px导航轨道和可伸缩内容列；轨道粘在顶部、高度100vh，内边距28px 18px。内容 main 最大宽度1180px、内边距32px。首页为 minmax(0, 760px) 与250px全库上下文列、间距28px；首页内容自身无内边距、圆角或阴影。统计 /ask 为独立页面，主区最大宽度1080px，图表单列。管理页保留间距24px的等分双列，凭据与动作区横跨两列。

**布局断点是900px及以下，桌面规则从901px开始。** 紧凑布局将轨道改为顶部导航，导航单独一行并允许横向滚动；main 左右及底部内边距16px、顶部4px。首页与管理页改为单列，全库上下文仍显示。首页内容自身仍为0内边距，详情阅读面保留20px紧凑内边距。

**筛选折叠另用768px边界。** HomePage 的 compact 为 innerWidth < 768，768px起显示完整条件；768–900px是单列页面加完整筛选。搜索字段占整行，手机筛选折叠与清除在同一操作行；分类保留原生单选语义，日期改为共享范围入口及弹层。桌面分类标签最小28px、选中浅蓝底，普通字段最小32px；900px及以下控件恢复44px触摸高度。4/8/12/16/24/32/48px是继承间距词汇，20/22/28px等已实施内边距保留，不强制舍入。

当前首页年份组上间距20px、左内边距0、无纵向时间线；年份与已加载计数沿基线排列。月份上内边距8px，完整日日期行最小高度44px、内边距7px 0。事件内边距12px 0 12px 28px；继承节点top:21px，桌面left:-20px，紧凑布局left:0。旧的148px年份侧栏和年/日按钮规则仍留在样式文件，但已被最终覆盖或不再有模板入口，不是当前布局规范。

研究助手在正式 App 的 RouterView 之外挂载，默认收起。桌面固定右侧，高100dvh，外壳内边距0、主列18px；无历史时初始宽460px，可调最小340px、最大50vw，正文随实际宽度留位。历史默认收起，超过1120px才采用右侧并列历史：总宽至少520px且不超过50vw，历史180–360px并受总宽减340px限制，主列约保留340px。901–1120px历史覆盖助手右侧，宽min(360px, 85%)。外缘和历史分隔处是宽6px、默认不可见的可聚焦 separator（div，非按钮），悬停只显示1px引导线；可拖动，Alt+左右方向键每次20px，宽度存localStorage并随窗口夹紧。

桌面触发按钮距右/下24px。900px及以下入口通过Teleport进入sticky顶部导航的正常流专用槽，按钮最小44px。助手宽100%、主列18px，背景main与导航inert并锁定页面滚动；事件、对话、历史分别切换。历史全宽覆盖助手、16px 10px内边距，提供返回对话。消息区独立滚动，输入保留在面板底部；窄屏消息区上限calc(100dvh - 250px)。

A为CSS网格排行，行间距8px，列为8em / minmax(24px, 1fr) / auto，条高18px。B为水平可滚动柱图，柱间距4px，每项最小宽44px、高240px，数量基线距底18px、最大柱高180px，数字位于柱顶、日期在底部。C为可滚动网格：分类列minmax(88px, auto)，每个日期列minmax(34px, 1fr)，单元桌面最小高30px、内边距0、字号12px、间隔3px、无边框、3px微圆角。分类列粘在左侧；900px及以下日期列最小44px、格高44px。保留数字、原生按钮键盘操作、横滚说明及展开数据表；日期表头不下钻。

抽屉沿用900px边界。助手收起时桌面抽屉上下距视口24px、高calc(100dvh - 48px)，活动事件/来源/兼容证据层右距24px，宽min(740/708/676px, calc(100vw - 48px))；非活动事件或来源层右距56px。助手打开时事件紧邻助手左侧，右距实际助手宽、高100dvh、无圆角、宽min(740px, 剩余视口宽)；来源和兼容证据层再左移32/64px、上限708/676px，并相应扣除可用宽度。900px及以下所有抽屉100vw × 100dvh、贴边无圆角。

## Elevation & Depth

首页事件流、统计图表及匹配事件采用透明平面，没有浮卡阴影。白色辅助面板和管理块以细边界分层；详情保留既有阅读面阴影。助手与抽屉的阴影用于标明空间和核对层级，不复制给每条事件。没有毛玻璃、渐变光晕或栅格背景。

### Shadow Vocabulary
- **阅读面阴影**（box-shadow: 0 12px 30px rgba(34, 61, 93, 0.08)）：保留的详情阅读面；不再用于首页、统计或助手内提问区。
- **助手阴影**（box-shadow: -12px 0 30px rgba(34, 61, 93, 0.10)）：右侧研究助手。
- **抽屉阴影**（box-shadow: -18px 10px 34px rgba(34, 61, 93, 0.16)）：事件与来源核对叠层；手机模态事件层背景遮罩为rgba(16, 34, 59, 0.16)，后续层遮罩透明；桌面非模态dialog无模态背景遮罩。901–1120px覆盖历史使用-12px 0 28px rgba(34, 61, 93, 0.14)阴影。

**The Evidence Layer Rule.** 层次服务于核对：主页和统计保持平面，助手与抽屉区分空间，摘录用浅色平面和细边界，不引入字面云景。

继承摘录插入动画0.22s ease-out，以clip-path从 inset(0 0 100% 0) 展开到 inset(0)，无独立收起动画。活动抽屉使用0.2s cubic-bezier(0.2, 0.8, 0.2, 1)，从translateX(14px)到translateX(0)，无独立退出动画。月份指示符为0.18s ease-out；统计原生details指示符为160ms ease。

统计图表挂载使用insight-in 0.22s ease-out，从opacity .55到1，自动结束，无播放开关。欢迎文字及输入区声明transform / opacity 0.18s ease-out过渡；首条消息出现后通过布局切换把输入放到底部，当前未实现位置插值动画。prefers-reduced-motion关闭这些CSS动画与过渡。热图格使用0.35s cubic-bezier(.16,1,.3,1)淡入，并在减少动态偏好下关闭；回到最新消息在该偏好下使用auto，其余情况使用smooth滚动。

## Shapes

普通紧凑控件使用6px圆角，月份与分类筛选5px，热图3px，日历日期4px；模式提示、日期弹层与助手输入容器保留8px圆角；辅助/管理面板14px；详情阅读面和桌面抽屉16px；分类与实体胶囊999px。首页与统计内容面圆角为0。通常边框1px，证据摘录只有左侧细线。时间节点继承10px圆形、2px描边。导航和返回SVG使用18px画布、1.8px圆头圆角描边，无填充。保留真实分类、日期与字段标签，不添加装饰性眉题。

## Components

### Buttons
正式共享控件采用 B 的角色层级：桌面普通按钮32px、14px字号、4px 10px内边距、6px圆角、透明底和无边框；悬停浅蓝。主要动作深蓝底白字，悬停使用 primary-hover；次级日期快捷项、图表标签、清除与历史管理入口最小28px，选中状态浅蓝底深蓝字。禁用状态使用 disabled-bg / disabled-ink，透明度1与默认光标。数据模式切换和日期范围入口保留内描边。

900px及以下按钮、分类选项、字段及日历日期恢复最小44px高度；图标按钮宽44px。桌面图标按钮通常32px，历史更多入口28px。按钮键盘焦点使用2px focus轮廓、偏移2px；热图与分隔拖动区焦点向内。事件标题、月份和清除操作不增加hover下划线。抽屉返回使用32px桌面 / 44px移动高度、4px 8px内边距。

### Inputs / Fields
普通字段全宽，桌面最小32px高、6px圆角、5px 10px内边距与14px字号；移动最小44px。标签与字段间距4px。焦点与插入光标沿用深蓝体系；错误以相邻文字及状态块表达。助手输入框置于白色8px圆角细边容器（10px 12px内边距），文本域自身透明无边框、14px字号与8px 0内边距，最高30dvh。

### Shared date range
首页与统计复用 DateRangePicker：一个范围入口打开 Teleport 至 body 的固定弹层；桌面宽440px、内边距16px、圆角8px，最大宽高为视口减24px。移动左右留12px、内边距12px，快捷项从侧列变为横向换行。弹层包含两个原生日期输入、今天/昨天/近7天/近30天/本月、月份前后切换、周一开头的42格月历和取消/应用。桌面日历格30px高，移动44px。

输入、预设和两次点击选起止只修改草稿；应用校验通过才提交，取消、Esc或点击外部放弃草稿。打开聚焦开始日期，应用/取消/Esc返回入口焦点；外部点击不夺回焦点。先后颠倒的日历点击自动排序；手填倒置和无效日期报错，有限区间最多366天且起止均含。今天按Asia/Shanghai确定，日期运算使用UTC日历计算。首页 allowUnbounded 支持不限日期与单侧边界，“不限日期”立即清除并关闭；统计要求完整起止且仍默认今天。

### Navigation
正式桌面竖排、顶部品牌、底部数据模式切换；紧凑布局改顶部导航，并在正常流助手入口槽保留“提问”。入口仍为“事件”“统计与问答”“采集管理”；首页标题为“AI 动态”。导航最小高度44px、水平内边距12px，默认灰蓝文字，活动项深蓝700字重，无活动底线。固定浅色；“演示模式 / 连接服务”是数据模式，不是主题开关。实验和预览外壳不替代正式导航。

### Chips
分类和实体标签为浅青底、深青文字，3px 8px内边距、12px字号。它们是文本元数据，没有选中态、点击行为或hover装饰；首页筛选分类仍是单选控件。A分类排行整行是筛选按钮，C数字格是分类与日期筛选按钮，不套用胶囊的非交互语义。

### Cards / Containers
基础管理/错误面板20px内边距、14px圆角与细边框；全库上下文面板16px内边距，自然高度、顶部对齐。详情阅读面沿用24px 28px内边距及16px圆角。首页、统计图表和统计匹配事件透明无阴影；助手提问区使用白色细边输入容器；统计图表和匹配事件内边距18px 0。事件之间用底部分隔线，不各自抬起成卡片。

### Month disclosure
年份使用静态h2，月与日使用原生按钮及aria-expanded。日显示数字加“日”，辅助名称保留完整日期。收起隐藏对应后代，月/日默认展开，追加分页保留已有选择；不显示全年/全部折叠操作。月份采用浅蓝底、5px圆角、4px 8px内边距、桌面最小32px / 移动44px高度，边线指示符随展开状态旋转，焦点继承全局规则。

年、月、日计数只统计已加载匹配事件；缺少日期独立标明“日期未知”，不能将这些数值代替精确匹配总量。

### Event / source drawers
首页和统计匹配事件的普通点击打开原生dialog抽屉（桌面show非模态，手机showModal）；标题href保留独立详情地址，支持新标签页。事件层直接列出原始来源链接、保存段落与可展开的“来源信息”，来源详情打开第二层。来源层同样直接显示关联摘录；不可变版本、段落和核验状态置于原生details内。源码保留evidence查询参数的兼容第三层，但当前普通阅读流程不再以“逐条打开证据”进入第三层。

共享抽屉CSS由main.ts全局加载，直接访问/ask也保持同样的层级和控制样式。顶部保留紧凑返回和当前层标题，正文独立滚动。返回与Esc退出当前层；桌面新增独立遮罩，点击遮罩只退出当前层，背景主内容与导航inert、页面滚动锁定，防止鼠标事件穿透。助手区域仍可操作；手机点击面板外的模态遮罩退出当前层；首页或统计的筛选query、滚动与可用触发点焦点保持衔接。非活动层隐藏标题内容和正文，并禁止指针操作，只保留白色边缘。桌面顶部16px 20px内边距、正文24px，紧凑正文20px。正文事件标题使用drawer-title，紧凑22px；分节18px/600字重、1.35行高。

仅安全HTTP(S)地址呈现原始来源链接；无关联证据、缺失段落、加载失败和重试均保留实际文字，不能伪造全文。合成模式提示在活动层内可见。详情页仍保留既有正文证据展开。

### Global research assistant
助手跨正式路由保留多会话。IndexedDB数据库ai-radar-conversations保存会话名称、当前会话ID、草稿、下一问附件、已采用范围，以及按序消息的角色、正文、时间、范围/筛选、数据模式、状态、引用、计划、覆盖统计和错误。输入底部保留历史和新建操作；历史以单行省略标题展示，每行更多入口打开Teleported上下文操作面板，对目标会话执行重命名、自定义原生dialog编辑、单会话JSON导出或删除；头部只保留历史标题和收起/返回。重命名要求非空、最多60字符，取消不改名；支持新建和切换；完整本地记录与API上下文分开。存储失败显示仅内存保存并仍可导出，不保存维护令牌或模型密钥。刷新把running消息恢复为interrupted，不自动重试；cancelled/error保持各自语义。

初始欢迎入口和问题框位于上部；首次发送以580ms指数缓出展开会话区，输入框随之下移至底部。后续发送用380ms滚动将最新用户消息贴到会话区顶部；动态尾部留白保证短回答也能贴顶。旧轮完整保留，可上翻阅读；用户滚轮、触摸或按住消息区时停止自动定位。减少动态偏好下直接定位。每轮冻结提交时的范围和数据模式；无消息时范围跟随页面，已有消息后新范围需显式“采用此页面的新范围”。首页和统计各自提供当前公共筛选；维护页只提供公共资料范围。

每个会话最多持有一个下一问事件附件，可从事件“加入当前对话”加入、移除或再次查看；提交时冻结到用户消息，清空待发附件，并向API传event_ids。范围不匹配或事件未找到时保留明确错误及附件状态，旧回答不重解释。API历史仅选最近最多3对已完成问答，最多6条、总计12000字符，每条先截4000字符，当前问题和未完成/取消/错误回答不作为完整历史对发送；不把完整本地历史等同于全部模型上下文。

“按问题筛选”生成可检查的规则预览；范围改变或页面无法完整表达实体/未理解条件时禁止直接应用。每轮分别保留查询计划、来源编号、摘录、可用段落ID、覆盖计数与实际错误。来源编号与消息ID共同隔离引用展开状态。模拟流和合成数据继续明确标示；真实生成后端仍未实现，MODEL_UNAVAILABLE不可替换成假总结。

手机助手打开聚焦输入，Tab在助手控件间循环，返回或Esc关闭并恢复已有入口焦点；关闭、切换会话或新建会取消进行中请求。事件“加入当前对话”在手机关闭事件转到对话，“查看事件”关闭助手再打开事件；历史作为单独覆盖面板。桌面事件和助手可同时操作。

### Independent statistics
/ask仍为独立“统计与问答”页，首页仍是“AI 动态”。默认今天，页面快捷项为今天、近7天、近30天、本月，共享日期弹层另提供昨天与自定义；更多筛选中的分类/关键词/重要度共同控制统计和匹配事件；范围最多366天，起止包含，显示Asia/Shanghai。缺少日期、倒置日期和过宽范围分别报错。事实摘要由脚本根据完整统计计算最多类别及并列，不调用模型，不将收录数称为行业热度。

默认C日期×分类；A横向分类排行按数量降序，同数按分类标识排序，显示整数数量与四舍五入占比，零值条宽为0；点击行筛选分类。B显示每日数量，基线0、柱高count/max × 180px，标注所有并列峰值；只有一个桶时提示“只有一天数据，不显示趋势”。点击柱采用其日期范围。A读取完整categories，B读取daily，C和数据表读取daily_categories；均来自同一完整统计响应，不从第一页事件推算。超过31天按自然月聚合，边界桶保留选定范围，数据表列出完整起止日期；当前B单桶提示按桶数判断，跨日但同月单桶也会显示该文字。

C展示全部日期×六分类含零值，点击格子同时筛选分类和日期桶。令M=max(1, 同图所有格计数)，n为格计数；n=0取第0级，n>0取max(1, ceil(n/M × 12))级。颜色依次对应顶部 heat-zero、heat-red-start、heat-step-2至heat-step-11、heat-red-max，共13色（零值加12级）。0–7级使用heat-zero-ink，8–12级白字。这是按当前完整图最大值动态归一化的离散色阶，不沿用隔离预览的绝对计数色阶，也不使用旧版连续RGB公式。图例宽88px、高8px、圆角2px，以零值/第4级/最高级构成渐变，并显示“0 浅灰 · M 深红”。每格直接显示真实计数。

桌面格子最小34px宽、30px高，移动格子最小44px宽高；微圆角3px，悬停内描边深蓝，分类粘列辅助横向阅读。三种视图共享展开数据表；没有旧版flow、area、分类彩色图例及循环播放入口。0条保留空态和恢复入口，不画虚构趋势。

### Feedback / synthetic labels / maintenance
模式提示持续说明“前端模拟”或“后端合成数据”；助手模拟流另保留就地标识。错误面板显示实际错误并用role=alert，加载、提交、匹配与取消状态使用实际文本及适用aria-live。首页加载区最小高度120px；空结果采用居中48px内边距。无资料、未读取、错误、取消与模拟完成分别呈现；费用“实际/估算/未知”语义保持原样。

采集管理明确说明候选来源用于人工核验和后续采集，默认来源仍禁用，未验证前不会自动采集或发布。此说明不表示来源已验证或已经接入生产。管理令牌仅存当前页面内存，管理权限不扩展给助手。

## Do's and Don'ts

### Do:
- Do 保留合成数据、模拟流、检索范围、覆盖不足与错误的明确文字标识。
- Do 按角色使用桌面32px普通 / 28px次级控件与30px日历格；900px及以下恢复44px触摸高度与热图格宽高，始终保留可见焦点。
- Do 保留日期、统计数字的等宽数字特性，让链接、计划与摘录长文本换行。
- Do 让证据展开可由键盘操作，聚焦已展开摘录，并保留来源与段落可用性说明。
- Do 使用已实现的平面层次、细线、SVG和中文字体回退，优先让内容可读。
- Do 在提问后明确采用页面新范围，并保留每轮绑定范围与本地会话；窄屏图表允许横向滚动。

### Don't:
- Don't 把服务失败、模拟回答或合成事件呈现成真实成功或真实新闻。
- Don't 只靠颜色传达错误、加载、取消或数据来源。
- Don't 将云层切面变成云雾、3D场景或图片，将动作谱变成舞蹈符号。
- Don't 把连续事件阅读区改成等尺寸摘要卡片墙或恢复首页大白浮卡。
- Don't 把尚未完成的真实数据库、模型、历史材料验收或待定审查写成设计合格或产品能力承诺。
- Don't 恢复年份折叠或明暗切换，或为标题、月份、清除条件添加hover下划线。月、日折叠与浅色配色轮盘保留。

### 2026-09-14 已知交互问题修复
范围摘要移到“研究助手”标题旁的紧凑details，默认收起；范围变化时标注“范围已变化”，展开后可显式采用新范围。新建会话采用当前页面范围，已有会话和旧消息保留提交时快照。
输入框Enter发送、Ctrl+Enter显式插入换行；中文输入法组合状态及229键码不发送。问题原文保留在textarea，预览/继续编辑切换Markdown；用户与助手正文共用MarkdownText。支持标题、强调、列表、代码、表格和换行，关闭原始HTML与图片语法，仅允许http(s)链接，外链noopener noreferrer；存储仍保留原始Markdown。
日期弹层只有一个共享日历；桌面遮罩层z44低于抽屉z45，助手打开时遮罩右界止于助手左缘。移动端继续使用原生modal dialog背景保护。验证见docs/interaction-fixes-report.md。

### 助手元信息色彩细节（2026-09-14）
角色“你”与统计数字使用克制蓝#315f97；角色“助手”与complete覆盖标签使用青绿#267064；模拟模式与partial覆盖提示使用琥珀#86601c。范围正文保留原有弱化墨色，标签和值保留文字，颜色不单独承担语义。complete底#edf6f2，partial底#faf2e3；complete表示数据覆盖，不表示答案已证实。
问题输入框焦点为1px雾蓝#7893b0，圆角4px，保留键盘可见性；只在此输入框覆盖旧3px强制规则，Windows强制颜色模式使用2px Highlight。桌面/手机各一次初检，修正旧!important覆盖后各一次确认，无额外视觉扩展。


## 全局主题轮盘（2026-09-14）

用户已选择保留全部五套预览，并授权扩展与正式接入。现有单主题约束由本节替代；不改变首页优先、统计独立、平面阅读与并排助手布局。

主题的完整运行令牌以 frontend/src/themes.ts 为唯一实现来源；默认雾白钴蓝，原五套均保留，扩展为16套。四套的辅助文字为适配侧栏略微加深。操作、背景、纸面、边界、标签、焦点、摘录和会话角色随主题变化；错误/警示/成功语义与热力图数值红色色标保留。

桌面入口在左侧导航底部、数据模式切换上方。展开380px四分之一轮盘，浏览与应用分离：拖动、滚轮、方向键浏览，点击色块或在轮盘上按Enter应用；Home/End到首末主题，Tab循环访问，Escape/空白处收起并恢复焦点。移动端入口随导航正常流排布，轮盘停靠左下并限制在视口内。

应用时以色块为原点进行650ms圆形揭示，使用浏览器View Transition与Web Animations；浏览器不支持或用户减少动态时直接更新。连选以最后一次为准。localStorage仅保存主题ID，跨标签页同步；不可写时当前页仍可使用并提示保存失败。无主题循环播放。

验证记录见 docs/theme-wheel-report.md。没有新增图片资产、字体或依赖。
