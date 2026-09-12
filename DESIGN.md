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
    backgroundColor: '{colors.paper}'
    rounded: '{rounded.reading}'
    padding: 28px
  home-reading-plane-compact:
    backgroundColor: '{colors.paper}'
    rounded: '{rounded.reading}'
    padding: 16px
  reading-plane:
    backgroundColor: '{colors.paper}'
    rounded: '{rounded.reading}'
    padding: 24px 28px
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

以桌面阅读空间为主体：冷银蓝底面托起白色连续阅读面，深蓝交互与深墨正文建立稳定层级。云层切面只表现为面板、浅色摘录和证据展开的层次；动作谱只表现为日期、节点与正文的对齐节奏。

这是依据已完成 Vue 页面与最终 CSS 层叠提取的实现记录，替代此前青绿色版本。中文工作字体、紧凑 SVG、留白与轻边界支撑日常阅读；没有栅格素材、云景或舞蹈符号。页面组成见方向契约，产品能力边界仍以 PRODUCT.md 为准。

**Key Characteristics:**
- 冷银蓝地面、白色阅读面与安静的上下文面板。
- 连续事件流采用完整日期和细线节点，移动端回到自然文档顺序。
- 证据在正文中展开，来源、段落和缺失信息保留明确文字。

## Colors

主色为沉稳深蓝，辅以很浅的青色标签；底面与阅读面保持冷而明亮。顶部令牌是规范值，CSS 中同名变量继续为运行时来源；未声明为 CSS 变量的组件颜色保留其实际字面值。

### Primary
- **深蓝 blue**：链接、活动导航、主要按钮和日期节点。
- **浅蓝 blue-soft**：普通按钮悬停。

### Secondary
- **浅青 aqua / 深青 pill-ink**：分类与实体标签的背景和文字；不是第二种主要动作色。

### Neutral
- **银蓝 bg / 白色 paper / 淡蓝 rail**：应用地面、阅读面与导航轨道。
- **深墨 ink / 灰蓝 muted / 分隔线 line**：正文、辅助信息及细边界。
- **quote-bg / quote-line、plan-bg / plan-line**：摘录和已解析检索条件的不同层次。
- **focus / pointer-focus、selection、hover-line**：键盘焦点、普通焦点、选中文本与普通按钮悬停边界。
- **danger / error-line / danger-bg**：错误文字、错误面板边框、日期校验背景；status-bg 是普通状态底色。
- **demo-bg / demo-ink / demo-line**：持续可见的合成数据与模拟模式提示。警示色同时配合实际说明文字。

**The Reading Plane Rule.** 深蓝用于链接、当前导航与主要动作；大面积承载阅读的是白色面与冷银蓝地面。

## Typography

**Display Font / Body Font:** Inter, PingFang SC, Microsoft YaHei, sans-serif。工程没有字体下载或 @font-face；Inter 是否存在取决于设备，中文使用可用系统回退。标题沿用同一工作字体，不建立新的装饰显示字体。数字使用 font-variant-numeric: tabular-nums，不引入独立等宽字体。

### Hierarchy
- **Display**：四页主标题，使用顶部 display 令牌；最大宽度30ch，常规外边距24px 0 12px。首页标题去掉顶部外边距，紧凑布局底部间距6px。
- **Headline / Event title**：阅读面章节标题为600字重、1.35行高；事件标题保留400字重、1.4行高，不能统一改写为同一角色。
- **Body / Reading**：界面正文行高1.6；摘要与回答正文行高1.7、最大宽度70ch。
- **Label / Meta / Date / Pill**：字段标签14px、辅助文字13px、日期15px、标签12px，各司其职。品牌17px、800字重；活动导航700字重。

**The Date Rhythm Rule.** 日期必须按正常阅读顺序完整显示；桌面日期列与节点对齐，移动端移到事件组上方。

## Layout

应用最小宽度320px。桌面布局使用196px固定导航轨道和可伸缩内容列；轨道粘在顶部、高度100vh，内边距28px 18px。内容 main 最大宽度1180px、内边距32px。首页是 minmax(0, 760px) 与250px上下文列、间距28px；问答为可伸缩阅读列与250px上下文列。详情为单个阅读面；管理页使用间距24px的等分双列，凭据与动作区横跨两列。

**布局断点是900px及以下，桌面细化规则从901px开始。** 紧凑布局将轨道改为顶部导航、导航单独一行并允许横向滚动；内容左右及底部内边距16px、最终顶部4px。首页、问答和管理页均为单列，上下文面板仍显示。首页阅读面内边距16px；详情和问答阅读面20px。问答三个研究条件在桌面并列、紧凑布局单列，位于提交按钮之前。

**筛选折叠另用768px边界。** HomePage 的 compact 为 innerWidth < 768，768px起隐藏折叠按钮并显示完整条件；768–900px因此是单列页面加完整筛选，不是桌面轨道。搜索字段占整行，手机折叠与清除在同一操作行；分类用原生单选项，日期用原生日期字段。

桌面日期组左内边距112px，日期标签 left:-8px / width:96px / nowrap / 右对齐，时间线 left:96px。节点继承10px外尺寸、2px描边，在事件内 left:-20px；这些值记录最终源码，不替代截图审查结论。紧凑布局隐藏纵线、日期恢复普通文档流，节点留在事件左侧；首页事件上下内边距14px。桌面事件内边距22px 0 22px 28px。4/8/12/16/24/32/48px是源码声明的间距词汇，20/28px等已实施阅读内边距保留，不强制舍入。

## Elevation & Depth

主阅读面使用柔和阴影，侧面板、管理块与状态块以浅色底和细边框分层。阴影只属于连续阅读面，不自动分配给每一条事件。没有毛玻璃、渐变光晕或栅格背景。

### Shadow Vocabulary
- **阅读面阴影**（box-shadow: 0 12px 30px rgba(34, 61, 93, 0.08)）：首页、详情与问答的白色阅读面。

**The Evidence Layer Rule.** 层次服务于阅读与核对：主阅读面使用柔和阴影，摘录使用浅色平面和细边界，不引入字面云景。

摘录插入时使用0.22s ease-out的clip-path展开，从 inset(0 0 100% 0) 到 inset(0)。内容默认可见，移除时没有独立收起动画。prefers-reduced-motion: reduce 下全局关闭动画与过渡；不增设滚动显现、漂浮或页面入场动作。

## Shapes

控件与模式提示使用8px圆角；辅助/管理面板14px；连续阅读面16px；分类与实体胶囊999px。通常边框1px，证据摘录只有左侧细线。时间节点是10px圆形、2px描边；它承载日期组织，不是装饰图标。导航 SVG 使用18px画布、1.8px圆头圆角描边，无填充。保留真实分类、日期与字段标签，不添加装饰性眉题。

## Components

### Buttons
普通按钮和模式切换链接采用白底、细边框、8px圆角、8px 12px内边距、最小高度44px。悬停改用浅蓝底与 hover-line 边框。主要按钮目前用于问答“开始分析”，使用深蓝底白字；主要按钮悬停维持同色。取消、清除、重试、采集操作和证据展开保持普通变体。当前没有单独按下样式或按钮过渡；不要在侧车预览里编造。禁用按钮透明度0.52、not-allowed光标。

### Inputs / Fields
字段全宽、最小高度44px、8px圆角与8px 10px内边距，字号16px；标签与字段间距4px。研究条件字段保留120px最小宽度。输入与文本域插入光标使用深蓝。普通 focus 为3px pointer-focus轮廓、偏移2px；focus-visible 使用3px深蓝focus轮廓、偏移2px并覆盖前者，也适用于可聚焦摘录。当前字段错误通过相邻明确文字与状态块表达，没有独立红色输入框变体。

### Navigation
桌面竖排、顶部品牌、底部模式切换；紧凑布局改为顶部两行。项目最小高度44px、水平内边距12px；默认灰蓝文字，活动项深蓝700字重。应用轨道明确去掉通用导航的活动底线。没有专用导航hover背景，键盘焦点沿用全局规则。

### Chips
分类和实体标签为浅青底、深青文字，3px 8px内边距、12px字号。它们是文本元数据，没有选中态、点击行为或hover装饰；筛选分类是单选控件，不是这类胶囊。

### Cards / Containers
基础管理/错误面板20px内边距、14px圆角与细边框；上下文面板16px内边距。首页阅读面桌面28px内边距，详情/问答24px 28px，均16px圆角并使用阅读面阴影。上下文面板自然高度、顶部对齐；事件之间使用底部分隔线，不各自抬起成卡片。

### Evidence layer
证据区顶部间距24px、顶部内边距20px和细分隔线；每项上下内边距16px。按钮以 aria-expanded / aria-controls 表达展开状态；插入的 blockquote 可程序聚焦，内边距12px 16px、外边距12px 0。详情显示保存的版本ID与段落ID；问答显示可用段落ID，并明确写“来源版本未提供”，缺少段落写“未提供”。来源链接只在有效HTTP(S)地址时呈现。摘录、计划、链接允许任意长串换行。

### Feedback / synthetic labels
模式提示持续说明“前端模拟”或“后端合成数据”；详情摘录与问答模拟流另保留就地标识。错误面板显示实际错误文案并用 role=alert，加载/提交/匹配与取消状态用实际文本及适用的 aria-live。首页加载区最小高度120px；空结果采用居中48px内边距。无资料、未读取、错误、取消与模拟完成分别呈现；费用“实际/估算/未知”保留文字区分。检索计划使用独立浅蓝平面；覆盖计数不能当作全网或真实模型能力证明。

## Do's and Don'ts

### Do:
- Do 保留合成数据、模拟流、检索范围、覆盖不足与错误的明确文字标识。
- Do 为按钮、字段与导航保留至少44px高度及可见焦点；原生分类单选项的当前行高为36px，不能将它当作44px合规证明。
- Do 保留日期、统计数字的等宽数字特性，让链接、计划与摘录长文本换行。
- Do 让证据展开可由键盘操作，聚焦已展开摘录，并保留来源与段落可用性说明。
- Do 使用已实现的平面层次、细线、SVG和中文字体回退，优先让内容可读。

### Don't:
- Don't 把服务失败、模拟回答或合成事件呈现成真实成功或真实新闻。
- Don't 只靠颜色传达错误、加载、取消或数据来源。
- Don't 将云层切面变成云雾、3D场景或图片，将动作谱变成舞蹈符号。
- Don't 把连续事件阅读区改成等尺寸摘要卡片墙。
- Don't 把尚未完成的真实数据库、模型、历史材料验收或待定审查写成设计合格或产品能力承诺。
