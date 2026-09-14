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
  chart-model: '#1d5f95'
  chart-agent: '#4f7d4d'
  chart-framework: '#92602a'
  chart-research: '#7b5a9e'
  chart-product: '#a04d5d'
  chart-industry: '#3d7f80'
  heat-ink: '#102a43'
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
    padding: 22px
    width: 364px
    height: 100dvh
  assistant-panel-compact:
    backgroundColor: '{colors.paper}'
    padding: 18px 16px
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
  chart-legend:
    backgroundColor: '{colors.rail}'
    textColor: '{colors.ink}'
    rounded: '{rounded.control}'
    padding: 8px 12px
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

这是依据正式 Vue 页面与最终 CSS 层叠同步的实现记录，沿用现有中文工作字体、紧凑 SVG、留白与轻边界。固定浅色，不提供主题切换；没有新增字体下载、栅格素材、云景或舞蹈符号。页面策略见 `.impeccable/surfaces/global-assistant.md`，产品能力边界仍以 PRODUCT.md 为准；文档同步不等于视觉裁决或上线批准。

**Key Characteristics:**
- 冷银蓝直接阅读面、白色辅助面板与按需打开的研究助手。
- 年份和完整日日期负责定位，仅月份可折叠；桌面与移动端都按自然文档顺序阅读。
- 事件与来源抽屉直接呈现保存段落；统计 A/B/C 共用日期与分类计数，助手回答保留提问时的范围快照。

## Colors

主色为沉稳深蓝，辅以很浅的青色标签；底面保持冷而明亮。顶部令牌是规范值，CSS 中同名变量继续为运行时来源；未声明为 CSS 变量的组件颜色保留其实际字面值。

### Primary
- **深蓝 blue**：链接、活动导航、主要按钮和时间节点。
- **浅蓝 blue-soft**：普通按钮悬停、月份入口与选中的筛选条件。

### Secondary
- **浅青 aqua / 深青 pill-ink**：分类与实体标签的背景和文字；不是第二种主要动作色。
- **统计六分类 chart-model / chart-agent / chart-framework / chart-research / chart-product / chart-industry**：依次对应模型发布、智能体工具、框架与 SDK、研究、产品、产业。A 流向、B 面积和 B 图例色块采用同一映射；不扩展为全站动作色。

### Neutral
- **银蓝 bg / 白色 paper / 淡蓝 rail**：应用地面、辅助面板与导航轨道。首页和统计内容面为透明，直接露出 bg。
- **深墨 ink / 灰蓝 muted / 分隔线 line**：正文、辅助信息及细边界。heat-ink 是热力矩阵浅色格的数字色。
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

研究助手在正式 App 的 RouterView 之外挂载，默认收起。桌面面板固定右侧，宽364px、高100dvh、内边距22px；打开时内容预留364px右侧空间，形成并排阅读。触发按钮距右/下24px。900px及以下助手宽100%、内边距18px 16px，触发按钮距右/下16px；此时覆盖页面，背景内容与导航设置 inert 并锁定页面滚动。顶部返回随面板滚动粘住，长答仍能返回；不增加内容位移过渡。

A/B SVG 保留720px宽、最小高度300px，放在可聚焦的横向滚动容器；A 的实际高度按日期桶数量计算。C 左分类列最小90px，日期列最小56px；紧凑布局分类列粘在左侧。手机 A/B 显示首末日期与“左右滑动查看全部日期”，C 显示同一滑动提示。横滚用于保留标签和数字可读性，不将图表整体缩小成不可读图片。

抽屉沿用900px边界：桌面上下距视口24px、高calc(100dvh - 48px)，活动事件/来源/兼容证据层右距均24px，宽度依次min(740/708/676px, calc(100vw - 48px))；非活动事件或来源层右移为56px，保留后层边缘。900px及以下所有层100vw × 100dvh、贴边无圆角。

## Elevation & Depth

首页事件流、统计图表及匹配事件采用透明平面，没有浮卡阴影。白色辅助面板和管理块以细边界分层；详情保留既有阅读面阴影。助手与抽屉的阴影用于标明空间和核对层级，不复制给每条事件。没有毛玻璃、渐变光晕或栅格背景。

### Shadow Vocabulary
- **阅读面阴影**（box-shadow: 0 12px 30px rgba(34, 61, 93, 0.08)）：保留的详情阅读面；不再用于首页、统计或助手内提问区。
- **助手阴影**（box-shadow: -12px 0 30px rgba(34, 61, 93, 0.10)）：右侧研究助手。
- **抽屉阴影**（box-shadow: -18px 10px 34px rgba(34, 61, 93, 0.16)）：事件与来源核对叠层；事件层背景遮罩为rgba(16, 34, 59, 0.16)，后续层遮罩透明。

**The Evidence Layer Rule.** 层次服务于核对：主页和统计保持平面，助手与抽屉区分空间，摘录用浅色平面和细边界，不引入字面云景。

继承摘录插入动画0.22s ease-out，以clip-path从 inset(0 0 100% 0) 展开到 inset(0)，无独立收起动画。活动抽屉使用0.2s cubic-bezier(0.2, 0.8, 0.2, 1)，从translateX(14px)到translateX(0)，无独立退出动画。月份指示符为0.18s ease-out；统计原生details指示符为160ms ease。

A 流动需主动播放，使用1.2s ease-in-out infinite的虚线偏移动画；B 主动播放每900ms推进日期桶、更新面积和游标。暂停可操作，离开统计页或页面进入后台停止播放。加载时读取减少动态效果偏好，播放按钮禁用；全局prefers-reduced-motion规则关闭动画与过渡。不把这些实现记录扩张为实时偏好监听、暂停保留当前帧或实时采集证明。

## Shapes

控件与模式提示沿用8px圆角；辅助/管理面板14px；详情阅读面和桌面抽屉16px；分类与实体胶囊999px。首页与统计内容面圆角为0。通常边框1px，证据摘录只有左侧细线。时间节点继承10px圆形、2px描边。导航和返回SVG使用18px画布、1.8px圆头圆角描边，无填充。保留真实分类、日期与字段标签，不添加装饰性眉题。

## Components

### Buttons
普通按钮和数据模式切换链接采用白底、细边框、8px圆角、8px 12px内边距、最小高度44px；悬停改浅蓝底与hover-line边框。主要按钮用于助手“开始分析”，深蓝底白字，悬停维持同色。禁用按钮透明度0.52、not-allowed光标。

首页清除使用透明底、0边框、0 4px内边距、6px圆角与最小44px高度，灰蓝文字悬停变深蓝。首页与统计事件标题悬停只改深蓝文字，月份保留浅蓝底与悬停边界，均不增加下划线。抽屉返回使用紧凑箭头加“返回”，0 6px内边距、0边框、透明底、最小44px高度；悬停由深蓝转深墨。以上控件均保留键盘焦点。

### Inputs / Fields
字段全宽、最小高度44px、8px圆角与8px 10px内边距，字号16px；标签与字段间距4px。输入和文本域插入光标使用深蓝，focus边框变深蓝；focus-visible为3px focus轮廓、偏移2px，也适用于按钮、链接及可聚焦摘录。错误通过相邻明确文字与状态块表达，没有新增独立红色输入框变体。

### Navigation
正式桌面竖排、顶部品牌、底部数据模式切换；紧凑布局改顶部两行。入口仍为“事件”“统计与问答”“采集管理”；首页标题为“AI 动态”。导航最小高度44px、水平内边距12px，默认灰蓝文字，活动项深蓝700字重，无活动底线。固定浅色；“演示模式 / 连接服务”是数据模式，不是主题开关。实验和预览外壳不替代正式导航。

### Chips
分类和实体标签为浅青底、深青文字，3px 8px内边距、12px字号。它们是文本元数据，没有选中态、点击行为或hover装饰；首页筛选分类仍是单选控件。B 的分类图例是可点击按钮，使用深墨标签和对应12px色块，不能套用胶囊的非交互语义。

### Cards / Containers
基础管理/错误面板20px内边距、14px圆角与细边框；全库上下文面板16px内边距，自然高度、顶部对齐。详情阅读面沿用24px 28px内边距及16px圆角。首页、统计图表、统计匹配事件与助手内提问区透明无阴影；统计图表和匹配事件内边距18px 0。事件之间用底部分隔线，不各自抬起成卡片。

### Month disclosure
年份使用静态h2，完整日日期使用文本行，只有月份使用原生按钮及aria-expanded。收起隐藏该月后代，月份默认展开，追加分页保留已有选择；不显示全年/全部折叠操作。月份采用浅蓝底、8px圆角、7px 10px内边距、最小44px高度，边线指示符随展开状态旋转，焦点继承全局规则。

年、月、日计数只统计已加载匹配事件；缺少日期独立标明“日期未知”，不能将这些数值代替精确匹配总量。

### Event / source drawers
首页和统计匹配事件的普通点击打开原生dialog抽屉；标题href保留独立详情地址，支持新标签页。事件层直接列出原始来源链接、保存段落与可展开的“来源信息”，来源详情打开第二层。来源层同样直接显示关联摘录；不可变版本、段落和核验状态置于原生details内。源码保留evidence查询参数的兼容第三层，但当前普通阅读流程不再以“逐条打开证据”进入第三层。

顶部保留紧凑返回和当前层标题，正文独立滚动。返回、Esc与点击面板外的遮罩逐层退出；首页或统计的筛选query、滚动与可用触发点焦点保持衔接。非活动层隐藏标题内容和正文，并禁止指针操作，只保留白色边缘。桌面顶部16px 20px内边距、正文24px，紧凑正文20px。正文事件标题使用drawer-title，紧凑22px；分节18px/600字重、1.35行高。

仅安全HTTP(S)地址呈现原始来源链接；无关联证据、缺失段落、加载失败和重试均保留实际文字，不能伪造全文。合成模式提示在活动层内可见。详情页仍保留既有正文证据展开。

### Global research assistant
助手默认收起，在正式路由切换时保留问题、最近一次回答、引用及绑定范围；不宣称持久存储或完整多轮历史。首次提问前范围跟随页面，已提问后新页面范围进入待采用状态，用户点击“采用此页面的新范围”才用于下一次提问。回答与错误保留发起时的范围和适用数据模式，不因跨页悄悄重新解释。

首页提供当前列表筛选，统计提供当前统计筛选；维护页只提供公共资料范围，不携带管理令牌。“按问题筛选”显示规则预览及拟应用条件，明确采用并应用；包含当前筛选无法表达的实体或未理解条件时保留错误说明。提问支持取消、查询计划、来源编号、可聚焦摘录、覆盖计数与实际错误；MODEL_UNAVAILABLE显示模型尚未配置，不能改成假总结。来源摘录显示可用段落ID，版本信息以实际返回和可核对来源为准。

手机覆盖时背景隔离、Tab循环在助手内，打开聚焦顶部返回，返回或Esc关闭并恢复触发按钮焦点；关闭进行中的问答会取消。桌面保留并排操作，不把移动焦点循环强加到正文。

### Independent statistics
/ask 标题保留“统计与问答”，统计由库内事件计算，无需模型。今天、近7天、本月及自定义范围，更多筛选中的分类、关键词、重要度，与明确日期范围共同控制总览和匹配事件；范围最多366天，起止包含，显示Asia/Shanghai。缺少日期、倒置日期和过宽范围分别给出错误。

A 分类流向从六类连接到日期，连接对应真实非零分类计数；点击或Enter可选择分类与日期。B 堆叠面积共享同一计数，通过图例选择分类，播放推进日期。C 热力矩阵显示每个日期×分类计数，包括零；点击日期或格子下钻。大于31天按自然月合并，边界月只含选定日期。三种视图均保留数据表，合计来自联合计数；不把第一页事件数量当成全范围统计。

B 图例采用淡蓝底、深墨字及六类对应色块；C 使用blue系透明度0.14 + count/max × 0.78，超过相对最大值0.52时数字为白色，否则为heat-ink。热力格当前最小32px，不宣称所有图表目标均达44px。移动横滚提示和可聚焦容器属于当前组件要求。0条保留空态和恢复入口，不画虚构趋势。

### Feedback / synthetic labels / maintenance
模式提示持续说明“前端模拟”或“后端合成数据”；助手模拟流另保留就地标识。错误面板显示实际错误并用role=alert，加载、提交、匹配与取消状态使用实际文本及适用aria-live。首页加载区最小高度120px；空结果采用居中48px内边距。无资料、未读取、错误、取消与模拟完成分别呈现；费用“实际/估算/未知”语义保持原样。

采集管理明确说明候选来源用于人工核验和后续采集，默认来源仍禁用，未验证前不会自动采集或发布。此说明不表示来源已验证或已经接入生产。管理令牌仅存当前页面内存，管理权限不扩展给助手。

## Do's and Don'ts

### Do:
- Do 保留合成数据、模拟流、检索范围、覆盖不足与错误的明确文字标识。
- Do 为按钮、字段与导航保留至少44px高度及可见焦点；热力格当前32px，不把它当作全站触摸目标合规证明。
- Do 保留日期、统计数字的等宽数字特性，让链接、计划与摘录长文本换行。
- Do 让证据展开可由键盘操作，聚焦已展开摘录，并保留来源与段落可用性说明。
- Do 使用已实现的平面层次、细线、SVG和中文字体回退，优先让内容可读。
- Do 在提问后明确采用页面新范围，并保留回答绑定范围；窄屏图表提供横向浏览提示。

### Don't:
- Don't 把服务失败、模拟回答或合成事件呈现成真实成功或真实新闻。
- Don't 只靠颜色传达错误、加载、取消或数据来源。
- Don't 将云层切面变成云雾、3D场景或图片，将动作谱变成舞蹈符号。
- Don't 把连续事件阅读区改成等尺寸摘要卡片墙或恢复首页大白浮卡。
- Don't 把尚未完成的真实数据库、模型、历史材料验收或待定审查写成设计合格或产品能力承诺。
- Don't 恢复年/日折叠、主题开关，或为标题、月份、清除条件添加hover下划线。
