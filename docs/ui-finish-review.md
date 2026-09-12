disposition: fix

## persistence

通过。PRODUCT.md 和当前四页方向契约存在；FORM 的候选 7 / seed a7d9cf2b 已由 .impeccable/planning/redesign-candidates.md 与 selection-status.json 交叉佐证。本轮明确为用户批准的代码优先实现，没有批准构图稿，也没有栅格素材义务。旧 DESIGN.md 与 sidecar 按交付安排在本次审查后重写，不作为旧世界保真要求。

证据有效：已逐一打开 round-2 的 desktop.png、mobile.png、desktop-viewport.png、mobile-viewport.png、detail-desktop.png、detail-mobile.png、ask-desktop.png、ask-mobile.png、ingest-desktop.png、ingest-mobile.png。页面与名称相符，顶部可见，没有黑屏、空白渲染或错页；长图的高度由正文决定。已阅读四份 QUALITY BAR 图片、五个 Vue 文件的主要实现及 style.css。浏览器结果文件记录 42/42，通过范围包括合成数据分页、响应式无溢出、引用焦点与故障分支；这些通过项不能替代下面的视觉问题。未启动浏览器或再次运行 detector。

## fidelity

| 对象 / 契约承诺 | 状态 | 证据与判断 |
| --- | --- | --- |
| TYPE / OWN-WORLD | adaptation | 采用普通中文工作字体与清楚的标题层级，符合明确批准的“workhorse Chinese UI type”。参考图的拉长英文、模板字和舞谱字形不构成复制义务。Inter detector 提示不单独构成换字体的理由；中文实际主要走系统回退。 |
| MATERIAL / OWN-WORLD | match | 银蓝背景、独立白色阅读面与浅色摘录层成立；没有伪造石材、云雾、3D 或舞蹈图形。用户批准的是平面层次和证据展开，因此无需生成栅格资产。 |
| GROUND / OWN-WORLD | match | 截图呈冷银蓝地面和白色阅读面，与 --bg: #edf2f7、--paper: #fff 及契约相符，没有漂向暖奶油色或深色仪表盘。 |
| THESIS / 工作区拓扑 | match | 桌面左导航、中央连续事件流、窄上下文面板和移动端顶部导航均成立；首页没有被等尺寸摘要卡片替代。 |
| STORY / 问答条件可达性 | contradicted | ask-desktop.png 的分类标签竖排，选择框仅剩约 22px 宽和一个箭头；style.css 中条件区标题 width:100% 与三个 flex 条件争抢同一行。ask-mobile.png 把研究条件排在完整回答和证据之后，修改范围必须越过结果。 |
| FIRST VIEWPORT / 事件优先 | contradicted | desktop-viewport.png 的首条事件在约 y=560 才开始，mobile-viewport.png 的首条事件在约 y=710 才开始。标题上方留白、分散的条件与独占一行的清除共同使表单占据首屏，未兑现“events dominate height”。桌面日期范围还拆成两行。 |
| FORM / 日期节奏 | contradicted | desktop.png 两个日期组均把 YYYY-MM-DD 拆成 YYYY-MM- 与日两行；固定 74px 日期槽不足以容纳实际文本，破坏所选方向最具体的时间对齐特征。移动端完整日期可读。 |
| INTERACTION / 证据展开与锚点 | missing | 详情截图展示了来源标题、原文版本和段落标识；问答展开后仅显示摘录。AskPage.vue 的引用模板没有渲染已有 paragraph_id，也没有版本可用性说明，未兑现全产品可见的来源 / 版本 / 段落锚定。 |
| INTERACTION / 状态与浏览器细节 | match | 源码具有选择色、插入光标色、焦点、tabular numerals、展开 clip 动画和 reduced-motion 分支；截图显示引用焦点与禁用按钮，42/42 报告覆盖关键状态。运动质量没有动态录像证据，只确认源码实现存在。 |
| TRUTH / 产品边界 | match | 首页与详情显式标明合成数据，问答显式标明模拟流，采集页未读取状态没有冒充健康结果；没有新增商业声称。真实 PostgreSQL、模型与历史素材验收不在此次界面批准范围。 |
| FLOOR / 页面结构 | match | SVG 图标一致、无装饰 kicker、渐变字、硬偏移阴影或伪物理纹理；独立管理功能块没有演变成首页卡片墙。类别与事件日期是实质检索元数据。 |

## ceiling

尚未达到参考图的对齐纪律与空间效率：参考图让框架、时间轴和主要内容共用清楚的秩序，本实现的日期断行、筛选换行和问答条件挤压打断了这种秩序。需要吸收的是紧凑比例、稳定列宽与阅读先后关系。无需加入参考图中的模板字、摄影材质、装饰测量线、云景或舞谱符号；用户已明确排除这些字面表达。现有证据层颜色分区和展开动作可保留。

## material_fixes

1. [STORY / 条件可达性] 重排 AskPage 的条件区：标题独立占行，分类与两个日期使用有最小可读宽度的网格；移动端将条件或可展开的当前范围摘要放在提交操作之前，不放在回答之后。证明：同名桌面截图能完整显示“分类”和当前选项；移动端无需经过回答即可查看并修改范围，390/768/1440 均无挤压。
2. [INTERACTION / 缺失锚点] 在问答展开引用内显示已有段落标识及来源版本；接口未提供版本时明确写出“来源版本未提供”，不要编造。沿用详情的轻量元数据层。证明：ask-desktop.png 与 ask-mobile.png 同时显示来源标题、摘录和可读的真实可用锚点，合成数据仍标注。
3. [FIRST VIEWPORT / 事件优先] 压缩首页标题与筛选之间的累计留白，将桌面分类和完整起止日期组织成清楚的紧凑行，并把清除并入条件操作；移动端保留折叠范围并减少无信息占高，使事件流占首屏主要阅读面积。证明：两张同名 viewport 截图在既定 1000px 高度下，事件区超过半屏且首条摘要完整可读，控件仍达到所需触摸尺寸。
4. [FORM / 日期节奏] 为桌面完整日期提供足够宽且禁止断行的日期列，同步调整时间线与正文偏移；使用 tabular numerals 保持组间节奏，避免挤窄正文。证明：desktop.png 的每个日期组都完整显示 YYYY-MM-DD 一行，日期、节点、正文沿同一稳定网格对齐，移动端仍保持完整日期。

## keep

保留连续事件阅读面、窄上下文区域、明确的合成数据标识、可键盘展开的证据、44px 导航与现有 API / SSE / 分页 / 凭据语义；修复应强化用户批准的抽象平面与日期节奏。
