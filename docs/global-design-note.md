# 正式首页、统计与全站助手设计同步

记录日期：2026-09-14。文档初始受审源码为 **4c26b77**；最终定向复核源码为 **3d73e29**，后者修正了两份样式中意外写入的字面量换行字符。此记录是 documenter 的源码与文档核验，不是浏览器执行记录，也不替代 finish reviewer 的最终裁决。

用户已明确批准持久化本轮设计：首页继续承担 AI 动态，事件直接落在银蓝背景；仅月份折叠；统计独立位于 /ask，保留 A/B/C；全站助手默认收起、桌面并排、手机覆盖；固定浅色；移除标题、月份、清除条件的下划线；维护页保留来源状态说明。因此本次按已批准方向合并既有 DESIGN.md，并同步其令牌与 sidecar，无须重新选择视觉身份。

本次只修改 DESIGN.md、.impeccable/design.json 和本文，不修改产品源码、PRODUCT.md、方向契约或审查结论，不提交代码。

## 实际实现与文档对应

| 实现 | 本轮同步 |
|---|---|
| 首页 | 最终 .home-stream 为 transparent、padding:0、border-radius:0、box-shadow:none；home-reading-plane 及 compact 令牌、sidecar 的首页预览同时更新，不能只改说明而继续渲染白色浮卡。 |
| 日期 | 年份改静态h2，20px/650/1.3/-0.02em；完整日日期为静态文本，只有月份按钮有aria-expanded。年份不再占148px侧栏，也不再画纵线；月份默认展开、分页保留选择。DESIGN 的 typography.timeline-year 与 sidecar 年/月/日HTML和CSS同步。 |
| 控件 | 清除条件透明底、0 4px内边距、6px圆角、最小44px高度；标题悬停变深蓝，月份保留浅蓝底。最终3d73e29中四处目标样式不含下划线声明，保留3px focus-visible轮廓；这是源码核验，不冒认已执行浏览器hover。 |
| 抽屉 | 活动事件/来源/兼容证据层均右距24px，后层事件/来源右距56px；桌面宽度依次740/708/676px并受视口限制。事件和来源直接显示保存摘录，用原生details收纳版本、段落与核验状态。普通流程为事件到来源，兼容证据query层仍存在。sidecar改为紧凑箭头返回和来源信息，不再展示已移除的关闭按钮与旧路径串。 |
| 助手 | 正式 App 的 RouterView 之外挂载；宽364px，桌面给正文留364px右侧空间，手机全宽覆盖。打开时顶部返回可达，背景隔离和移动Tab循环在组件中实现。文档与sidecar新增助手面板、触发按钮、紧凑布局及阴影数据。 |
| 范围与回答 | 首次提问前跟随页面；已有提问后范围变更须主动采用。只记录当前浏览会话内的最近回答、引用和绑定快照，不宣称完整多轮历史或持久存储。维护页仅提供公共资料范围，不带管理令牌。 |
| 统计 | /ask 保留“统计与问答”名称，主内容为确定性统计，输入问题移到助手。A为分类到日期的流向，B为堆叠面积与日期播放，C为日期×分类矩阵，使用同一daily_categories数据；超过31天按自然月汇总，边界月只含选定日期，数据表保留。 |
| 图例和横滚 | 新增六分类实际颜色令牌及sidecar元数据。B图例为深色文字加12px分类色块，A/B的720px图表可横滚并提供首末日期和手机提示，C保留横滚并在手机固定分类列。可聚焦容器、零值、表格和分类映射分别记录，不把无整页溢出当作图表完整可见证明。 |
| 模式与维护 | 正式外壳固定浅色，没有主题开关；“演示模式 / 连接服务”仅切换数据模式。维护页说明候选来源待人工核验、默认禁用、未验证前不自动采集或发布。 |

## 继承与新增令牌

保留既有 Inter、PingFang SC、Microsoft YaHei、sans-serif 字体栈，不加载或替换字体。继承主色blue、银蓝bg、paper、ink、muted、line、aqua，以及焦点、摘录、检索计划、错误和合成提示词汇；不改模型与成本语义，不把继承token目录的保留解释为全站每处样式重新审计。

保留4/8/12/16/24/32/48px间距词汇、8/14/16/999px圆角词汇和900/901px布局、768px筛选边界。首页覆盖为零内边距、零圆角，年份改小是本轮批准的实际差异；详情阅读面、普通控件与辅助面板继续沿用原身份。

本轮新增chart-model、chart-agent、chart-framework、chart-research、chart-product、chart-industry六色和heat-ink；这些前台令牌来自AskPage.vue与style.css的同一实际值。sidecar仅添加色名、角色与预览色阶扩展，不另设第二组规范原色。色阶是面板展示用的8步OKLCH扩展，不声称应用使用这些色阶。原色仍由DESIGN frontmatter拥有。

新增助手与统计组件令牌、清除及返回的透明变体，更新阅读面与月份变体。sidecar保留既有标准按钮、字段、导航、标签、管理块、摘录与状态预览，并同步首页、日期和抽屉，新增清除、助手、统计控件样本。所有预览均标明其状态/行为边界，不伪造模型回答或真实统计数据。

## 核验记录与边界

直接核对了正式 frontend/src/App.vue、HomePage.vue、AskPage.vue、AssistantPanel.vue、IngestPage.vue、EventDrawers.vue、style.css、home-timeline.css、assistant-scope.ts 和 insight-charts.ts；参考 PRODUCT.md、既有DESIGN及sidecar、.impeccable/surfaces/global-assistant.md、Impeccable document参考说明、docs/global-finish-review.md及随后完成的docs/global-finish-verdict.md。

发现4c26b77两份CSS存在字面量 `r`n 后向主任务报告，由源码owner机械修复。本次重新读取3d73e29，确认这些字面量已移除，清除条件、月份hover、首页标题hover与统计标题hover对应有效CSS块。主任务报告该源码production build通过；documenter未重复运行构建，未执行浏览器或逐张审看截图。

文档本地解析核验通过：DESIGN YAML与sidecar JSON可解析；8个规范章节顺序正确；32个颜色、31个组件令牌和15个组件预览的引用有效；颜色/字体元数据键与frontmatter一致，颜色扩展均有8步色阶；sidecar overview、特征、规则及Do/Don't与DESIGN逐项一致，未仅修改prose。

本记录不把此前14张截图、合成fixture交互或协议证据重新计算为全站通过。最终已读取同一reviewer的第1次裁决：docs/global-finish-verdict.md将三项有限修复均标为resolved，给出仅限本轮UI/fixture的ship。该结论属于独立reviewer，不是documenter重新执行浏览器或视觉检查所得，也不扩大为真实服务与全站通过。A/B动画的暂停与后台停止按源码说明，未扩张为实时减少动态效果偏好监听或暂停后保留当前帧。热力格现有32px，也不宣称全站满足44px目标或正式无障碍认证。

前端模拟、后端合成数据、未配置生成模型、真实PostgreSQL与历史材料尚未验收的边界保持原样。统计无需模型不等于真实生成问答已完成，来源说明不等于已自动采集发布，文档同步与工程构建均不构成公开上线批准。
