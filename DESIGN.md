---
name: AI 革新雷达
description: 桌面阅读空间，以云层切面承载证据，以对齐日期组织阅读节奏。
colors:
  blue: '#123d73'
  blue-soft: '#e8f0fa'
  aqua: '#dceff0'
  pill-ink: '#075f68'
  bg: '#edf2f7'
  paper: '#fff'
  rail: '#f7faff'
  ink: '#10223b'
  muted: '#5b6d82'
  line: '#d4dee9'
  focus: '#175b95'
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
  heat-zero: '#edf0f2'
  heat-red-start: '#a63a34'
  heat-red-max: '#5c1713'
  heat-zero-ink: '#172b3f'
  assistant-answer-ink: '#16324c'
typography:
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
  control: 8px
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
    backgroundColor: '{colors.paper}'
    textColor: '{colors.ink}'
    rounded: '{rounded.control}'
    padding: 8px 12px
    typography: '{typography.body}'
  button-secondary-hover:
    backgroundColor: '{colors.blue-soft}'
    textColor: '{colors.ink}'
  button-primary:
    backgroundColor: '{colors.blue}'
    textColor: '{colors.paper}'
    rounded: '{rounded.control}'
    padding: 8px 12px
    typography: '{typography.body}'
  button-primary-hover:
    backgroundColor: '{colors.blue}'
    textColor: '{colors.paper}'
  input:
    backgroundColor: '{colors.paper}'
    textColor: '{colors.ink}'
    rounded: '{rounded.control}'
    padding: 8px 10px
    width: 100%
    typography: '{typography.body}'
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
    rounded: '{rounded.control}'
    padding: 7px 10px
  timeline-month-hover:
    backgroundColor: '{colors.blue-soft}'
    textColor: '{colors.blue}'
  filter-clear:
    backgroundColor: transparent
    textColor: '{colors.muted}'
    rounded: 6px
    padding: 0 4px
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
    padding: 0 14px
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
    rounded: 0px
    padding: 2px
  heat-cell-positive:
    textColor: '{colors.paper}'
    rounded: 0px
    padding: 2px
  assistant-main:
    padding: 18px
    height: 100dvh
  assistant-answer:
    textColor: '{colors.assistant-answer-ink}'
  assistant-history:
    backgroundColor: '{colors.rail}'
    padding: 18px 12px 12px
  assistant-history-compact:
    backgroundColor: '{colors.rail}'
    padding: 20px 16px

  drawer-return:
    backgroundColor: transparent
    textColor: '{colors.blue}'
    padding: 0 6px
  drawer-return-hover:
    backgroundColor: transparent
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
    rounded: '{rounded.control}'
    padding: 8px 12px
  error-card:
    backgroundColor: '{colors.paper}'
    textColor: '{colors.danger}'
    rounded: '{rounded.panel}'
    padding: 20px
---

# Design System: AI 革新雷达

## Overview

**Creative North Star: "桌面阅读空间 · 云层切面 · 动作谱"**

以桌面阅读空间为主体：冷银蓝底面直接承载首页事件流和独立统计，深蓝交互与深墨正文建立稳定层级。白色保留给上下文面板、研究助手、详情阅读面和抽屉；云层切面表现为证据核对的层次，动作谱表现为日期与正文的连续节奏。

这是依据正式 Vue 页面与最终 CSS 层叠同步的实现记录，沿用现有中文工作字体、紧凑 SVG、留白与轻边界。固定浅色，不提供主题切换；没有新增字体下载、栅格素材、云景或舞蹈符号。页面策略见 `.impeccable/surfaces/readable-insights-conversations.md`，产品能力边界仍以 PRODUCT.md 为准；文档同步不等于视觉裁决或上线批准。

**Key Characteristics:**
- 冷银蓝直接阅读面、白色辅助面板与按需打开的研究助手。
- 年份和完整日日期负责定位，仅月份可折叠；桌面与移动端都按自然文档顺序阅读。
- 事件与来源抽屉直接呈现保存段落；统计默认紧密红色热图，另有分类排行和每日计数；助手多会话在本浏览器保存每轮范围、消息与引用。

## Colors

主色为沉稳深蓝，辅以很浅的青色标签；底面保持冷而明亮。顶部令牌是规范值，CSS 中同名变量继续为运行时来源；未声明为 CSS 变量的组件颜色保留其实际字面值。

### Primary
- **深蓝 blue**：链接、活动导航、主要按钮和时间节点。
- **浅蓝 blue-soft**：普通按钮悬停、月份入口与选中的筛选条件。

### Secondary
- **浅青 aqua / 深青 pill-ink**：分类与实体标签的背景和文字；不是第二种主要动作色。
- **统计 heat-zero / heat-red-start / heat-red-max**：C 的零值为浅灰，正值按同图最大计数变深红；A 横向条和 B 每日柱统一深蓝。热图红色只编码收录数量，不代表风险或行业热度。

### Neutral
- **银蓝 bg / 白色 paper / 淡蓝 rail**：应用地面、辅助面板与导航轨道。首页和统计内容面为透明，直接露出 bg。
- **深墨 ink / 灰蓝 muted / 分隔线 line**：正文、辅助信息及细边界。heat-zero-ink 是热图零值数字色，正值数字为白色；assistant-answer-ink 用于助手消息。
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

**The Date Rhythm Rule.** 年份和完整日日期保持可见的定位层级，仅月份承担折叠；不把静态年、日标签重新变成按钮或独立侧栏。

## Layout

应用最小宽度320px。桌面使用196px导航轨道和可伸缩内容列；轨道粘在顶部、高度100vh，内边距28px 18px。内容 main 最大宽度1180px、内边距32px。首页为 minmax(0, 760px) 与250px全库上下文列、间距28px；首页内容自身无内边距、圆角或阴影。统计 /ask 为独立页面，主区最大宽度1080px，图表单列。管理页保留间距24px的等分双列，凭据与动作区横跨两列。

**布局断点是900px及以下，桌面规则从901px开始。** 紧凑布局将轨道改为顶部导航，导航单独一行并允许横向滚动；main 左右及底部内边距16px、顶部4px。首页与管理页改为单列，全库上下文仍显示。首页内容自身仍为0内边距，详情阅读面保留20px紧凑内边距。

**筛选折叠另用768px边界。** HomePage 的 compact 为 innerWidth < 768，768px起显示完整条件；768–900px是单列页面加完整筛选。搜索字段占整行，手机筛选折叠与清除在同一操作行；分类用原生单选项，日期用原生日期字段。分类行最小高度44px，选中项使用浅蓝底，字段与控件保留触摸高度。4/8/12/16/24/32/48px是继承间距词汇，20/22/28px等已实施内边距保留，不强制舍入。

当前首页年份组上间距20px、左内边距0、无纵向时间线；年份与已加载计数沿基线排列。月份上内边距8px，完整日日期行最小高度44px、内边距7px 0。事件内边距12px 0 12px 28px；继承节点top:21px，桌面left:-20px，紧凑布局left:0。旧的148px年份侧栏和年/日按钮规则仍留在样式文件，但已被最终覆盖或不再有模板入口，不是当前布局规范。

研究助手在正式 App 的 RouterView 之外挂载，默认收起。桌面固定右侧，高100dvh，外壳内边距0、主列18px；无历史时初始宽460px，可调最小340px、最大50vw，正文随实际宽度留位。历史默认收起，超过1120px才采用右侧并列历史：总宽至少520px且不超过50vw，历史180–360px并受总宽减340px限制，主列约保留340px。901–1120px历史覆盖助手右侧，宽min(360px, 85%)。外缘和历史分隔处可拖动，Alt+左右方向键每次20px，宽度存localStorage并随窗口夹紧。

桌面触发按钮距右/下24px。900px及以下入口通过Teleport进入sticky顶部导航的正常流专用槽，按钮最小44px。助手宽100%、主列18px，背景main与导航inert并锁定页面滚动；事件、对话、历史分别切换。历史全宽覆盖助手、20px 16px内边距，提供返回对话。消息区独立滚动，输入保留在面板底部；窄屏消息区上限calc(100dvh - 250px)。

A为CSS网格排行，行间距8px，列为8em / minmax(24px, 1fr) / auto，条高18px。B为水平可滚动柱图，柱间距4px，每项最小宽44px、高240px，数量基线距底18px、最大柱高180px，数字位于柱顶、日期在底部。C为可滚动网格：分类列minmax(88px, auto)，每个日期列minmax(34px, 1fr)，单元最小高30px、内边距2px、字号12px、间隔1px、无边框及圆角。分类列目前不粘住，模板没有上一版横滚提示或日期表头下钻；保留数字、原生按钮键盘操作及展开数据表。

抽屉沿用900px边界。助手收起时桌面抽屉上下距视口24px、高calc(100dvh - 48px)，活动事件/来源/兼容证据层右距24px，宽min(740/708/676px, calc(100vw - 48px))；非活动事件或来源层右距56px。助手打开时事件紧邻助手左侧，右距实际助手宽、高100dvh、无圆角、宽min(740px, 剩余视口宽)；来源和兼容证据层再左移32/64px、上限708/676px，并相应扣除可用宽度。900px及以下所有抽屉100vw × 100dvh、贴边无圆角。

## Elevation & Depth

首页事件流、统计图表及匹配事件采用透明平面，没有浮卡阴影。白色辅助面板和管理块以细边界分层；详情保留既有阅读面阴影。助手与抽屉的阴影用于标明空间和核对层级，不复制给每条事件。没有毛玻璃、渐变光晕或栅格背景。

### Shadow Vocabulary
- **阅读面阴影**（box-shadow: 0 12px 30px rgba(34, 61, 93, 0.08)）：保留的详情阅读面；不再用于首页、统计或助手内提问区。
- **助手阴影**（box-shadow: -12px 0 30px rgba(34, 61, 93, 0.10)）：右侧研究助手。
- **抽屉阴影**（box-shadow: -18px 10px 34px rgba(34, 61, 93, 0.16)）：事件与来源核对叠层；手机模态事件层背景遮罩为rgba(16, 34, 59, 0.16)，后续层遮罩透明；桌面非模态dialog无模态背景遮罩。901–1120px覆盖历史使用-12px 0 28px rgba(34, 61, 93, 0.14)阴影。

**The Evidence Layer Rule.** 层次服务于核对：主页和统计保持平面，助手与抽屉区分空间，摘录用浅色平面和细边界，不引入字面云景。

继承摘录插入动画0.22s ease-out，以clip-path从 inset(0 0 100% 0) 展开到 inset(0)，无独立收起动画。活动抽屉使用0.2s cubic-bezier(0.2, 0.8, 0.2, 1)，从translateX(14px)到translateX(0)，无独立退出动画。月份指示符为0.18s ease-out；统计原生details指示符为160ms ease。

统计图表挂载使用insight-in 0.22s ease-out，从opacity .55到1，自动结束，无播放开关。欢迎文字及输入区声明transform / opacity 0.18s ease-out过渡；首条消息出现后通过布局切换把输入放到底部，当前未实现位置插值动画。prefers-reduced-motion关闭这些CSS动画与过渡。回到最新消息仍调用JavaScript smooth滚动，未针对减少动态偏好分支处理，不能宣称所有动态行为均已关闭。

## Shapes

控件与模式提示沿用8px圆角；辅助/管理面板14px；详情阅读面和桌面抽屉16px；分类与实体胶囊999px。首页与统计内容面圆角为0。通常边框1px，证据摘录只有左侧细线。时间节点继承10px圆形、2px描边。导航和返回SVG使用18px画布、1.8px圆头圆角描边，无填充。保留真实分类、日期与字段标签，不添加装饰性眉题。

## Components

### Buttons
普通按钮和数据模式切换链接采用白底、细边框、8px圆角、8px 12px内边距、最小高度44px；悬停改浅蓝底与hover-line边框。主要按钮用于助手“发送”，深蓝底白字，悬停维持同色。禁用按钮透明度0.52、not-allowed光标。

首页清除使用透明底、0边框、0 4px内边距、6px圆角与最小44px高度，灰蓝文字悬停变深蓝。首页与统计事件标题悬停只改深蓝文字，月份保留浅蓝底与悬停边界，均不增加下划线。抽屉返回使用紧凑箭头加“返回”，0 6px内边距、0边框、透明底、最小44px高度；悬停由深蓝转深墨。以上控件均保留键盘焦点。

### Inputs / Fields
字段全宽、最小高度44px、8px圆角与8px 10px内边距，字号16px；标签与字段间距4px。输入和文本域插入光标使用深蓝，focus边框变深蓝；focus-visible为3px focus轮廓、偏移2px，也适用于按钮、链接及可聚焦摘录。错误通过相邻明确文字与状态块表达，没有新增独立红色输入框变体。

### Navigation
正式桌面竖排、顶部品牌、底部数据模式切换；紧凑布局改顶部导航，并在正常流助手入口槽保留“提问”。入口仍为“事件”“统计与问答”“采集管理”；首页标题为“AI 动态”。导航最小高度44px、水平内边距12px，默认灰蓝文字，活动项深蓝700字重，无活动底线。固定浅色；“演示模式 / 连接服务”是数据模式，不是主题开关。实验和预览外壳不替代正式导航。

### Chips
分类和实体标签为浅青底、深青文字，3px 8px内边距、12px字号。它们是文本元数据，没有选中态、点击行为或hover装饰；首页筛选分类仍是单选控件。A分类排行整行是筛选按钮，C数字格是分类与日期筛选按钮，不套用胶囊的非交互语义。

### Cards / Containers
基础管理/错误面板20px内边距、14px圆角与细边框；全库上下文面板16px内边距，自然高度、顶部对齐。详情阅读面沿用24px 28px内边距及16px圆角。首页、统计图表、统计匹配事件与助手内提问区透明无阴影；统计图表和匹配事件内边距18px 0。事件之间用底部分隔线，不各自抬起成卡片。

### Month disclosure
年份使用静态h2，完整日日期使用文本行，只有月份使用原生按钮及aria-expanded。收起隐藏该月后代，月份默认展开，追加分页保留已有选择；不显示全年/全部折叠操作。月份采用浅蓝底、8px圆角、7px 10px内边距、最小44px高度，边线指示符随展开状态旋转，焦点继承全局规则。

年、月、日计数只统计已加载匹配事件；缺少日期独立标明“日期未知”，不能将这些数值代替精确匹配总量。

### Event / source drawers
首页和统计匹配事件的普通点击打开原生dialog抽屉（桌面show非模态，手机showModal）；标题href保留独立详情地址，支持新标签页。事件层直接列出原始来源链接、保存段落与可展开的“来源信息”，来源详情打开第二层。来源层同样直接显示关联摘录；不可变版本、段落和核验状态置于原生details内。源码保留evidence查询参数的兼容第三层，但当前普通阅读流程不再以“逐条打开证据”进入第三层。

顶部保留紧凑返回和当前层标题，正文独立滚动。返回与Esc退出当前层；桌面点击抽屉和助手之外的页面退上一层，操作助手不会误关事件；手机点击面板外的模态遮罩退出当前层；首页或统计的筛选query、滚动与可用触发点焦点保持衔接。非活动层隐藏标题内容和正文，并禁止指针操作，只保留白色边缘。桌面顶部16px 20px内边距、正文24px，紧凑正文20px。正文事件标题使用drawer-title，紧凑22px；分节18px/600字重、1.35行高。

仅安全HTTP(S)地址呈现原始来源链接；无关联证据、缺失段落、加载失败和重试均保留实际文字，不能伪造全文。合成模式提示在活动层内可见。详情页仍保留既有正文证据展开。

### Global research assistant
助手跨正式路由保留多会话。IndexedDB数据库ai-radar-conversations保存会话名称、当前会话ID、草稿、下一问附件、已采用范围，以及按序消息的角色、正文、时间、范围/筛选、数据模式、状态、引用、计划、覆盖统计和错误。支持新建、切换、重命名、删除及单会话JSON导出；完整本地记录与API上下文分开。存储失败显示仅内存保存并仍可导出，不保存维护令牌或模型密钥。刷新把running消息恢复为interrupted，不自动重试；cancelled/error保持各自语义。

初始欢迎入口和问题框位于上部；首次发送将问题写成首条用户消息，随后旧上新下、独立滚动消息区、底部输入。读取旧消息时不强制滚回，距底小于30px时继续跟随，否则显示“回到最新消息”。每轮冻结提交时的范围和数据模式；无消息时范围跟随页面，已有消息后新范围需显式“采用此页面的新范围”。首页和统计各自提供当前公共筛选；维护页只提供公共资料范围。

每个会话最多持有一个下一问事件附件，可从事件“加入当前对话”加入、移除或再次查看；提交时冻结到用户消息，清空待发附件，并向API传event_ids。范围不匹配或事件未找到时保留明确错误及附件状态，旧回答不重解释。API历史仅选最近最多3对已完成问答，最多6条、总计12000字符，每条先截4000字符，当前问题和未完成/取消/错误回答不作为完整历史对发送；不把完整本地历史等同于全部模型上下文。

“按问题筛选”生成可检查的规则预览；范围改变或页面无法完整表达实体/未理解条件时禁止直接应用。每轮分别保留查询计划、来源编号、摘录、可用段落ID、覆盖计数与实际错误。来源编号与消息ID共同隔离引用展开状态。模拟流和合成数据继续明确标示；真实生成后端仍未实现，MODEL_UNAVAILABLE不可替换成假总结。

手机助手打开聚焦输入，Tab在助手控件间循环，返回或Esc关闭并恢复已有入口焦点；关闭、切换会话或新建会取消进行中请求。事件“加入当前对话”在手机关闭事件转到对话，“查看事件”关闭助手再打开事件；历史作为单独覆盖面板。桌面事件和助手可同时操作。

### Independent statistics
/ask仍为独立“统计与问答”页，首页仍是“AI 动态”。今天、近7天、本月、自定义及更多筛选中的分类/关键词/重要度共同控制统计和匹配事件；范围最多366天，起止包含，显示Asia/Shanghai。缺少日期、倒置日期和过宽范围分别报错。事实摘要由脚本根据完整统计计算最多类别及并列，不调用模型，不将收录数称为行业热度。

默认C日期×分类；A横向分类排行按数量降序，同数按分类标识排序，显示整数数量与四舍五入占比，零值条宽为0；点击行筛选分类。B显示每日数量，基线0、柱高count/max × 180px，标注所有并列峰值；只有一个桶时提示“只有一天数据，不显示趋势”。点击柱采用其日期范围。A读取完整categories，B读取daily，C和数据表读取daily_categories；均来自同一完整统计响应，不从第一页事件推算。超过31天按自然月聚合，边界桶保留选定范围，数据表列出完整起止日期；当前B单桶提示按桶数判断，跨日但同月单桶也会显示该文字。

C展示全部日期×六分类含零值，点击格子同时筛选分类和日期桶。令M=max(1, 同图所有格计数)，n为格计数；n=0使用heat-zero底和heat-zero-ink字；n>0令t=n/M，背景为rgb(166-round(74t) 58-round(35t) 52-round(33t))，数字白色。最大值是heat-red-max，正值低端趋近heat-red-start；零值与正值之间不是连续灰红插值。图例宽88px、高12px，使用三站点灰/红/深红渐变和“0 浅灰 · M 深红”文字。每个格子直接画真实计数，无模糊插值。

C格子目前34px最小宽、30px最小高，不能宣称所有图表目标均达44px。三种视图共享展开数据表；没有旧版flow、area、分类彩色图例及循环播放入口。0条保留空态和恢复入口，不画虚构趋势。

### Feedback / synthetic labels / maintenance
模式提示持续说明“前端模拟”或“后端合成数据”；助手模拟流另保留就地标识。错误面板显示实际错误并用role=alert，加载、提交、匹配与取消状态使用实际文本及适用aria-live。首页加载区最小高度120px；空结果采用居中48px内边距。无资料、未读取、错误、取消与模拟完成分别呈现；费用“实际/估算/未知”语义保持原样。

采集管理明确说明候选来源用于人工核验和后续采集，默认来源仍禁用，未验证前不会自动采集或发布。此说明不表示来源已验证或已经接入生产。管理令牌仅存当前页面内存，管理权限不扩展给助手。

## Do's and Don'ts

### Do:
- Do 保留合成数据、模拟流、检索范围、覆盖不足与错误的明确文字标识。
- Do 为按钮、字段与导航保留至少44px高度及可见焦点；热力格当前最小34×30px，不把它当作全站触摸目标合规证明。
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
- Don't 恢复年/日折叠、主题开关，或为标题、月份、清除条件添加hover下划线。
