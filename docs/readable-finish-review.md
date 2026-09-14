disposition: fix

输入说明：fresh 独立、无浏览器评审，实际打开全部 14 张指定 PNG；未提供独立 QUALITY BAR 卡或 critique-reference comp，Ceiling 依据本轮合同和继承的银蓝阅读身份。code-led 局部改造不要求 approved comp、comp-diff 或 concept-seed。主文件抽样审阅，后端合同不重审。

## Persistence

Pass（本轮文档同步待完成）：PRODUCT.md、方向合同、既有 DESIGN.md 与 .impeccable/design.json 存在。既有身份与画面的银蓝底、深蓝正文、白色辅助阅读面一致。旧文档仍记载上一版助手和统计组件，本轮已约定由 documenter 更新，不能将这个收尾步骤误判成预存身份漂移；交付前仍须同步新图表、会话和宽度规则。

证据通过：desktop-a、desktop-b、desktop-c、mobile-a、mobile-b、mobile-c、desktop-empty-assistant、desktop-conversation、desktop-history、desktop-reader-assistant、mobile-conversation、mobile-history、mobile-reader、user-1680-workspace 均已实际打开，内容与名称相符，无黑图或无效空白。固定面板仅覆盖首个 1000px 视口，fullpage 下方继续出现基础页不构成滚动锁失效证据。

## Fidelity

| 元素 / 承诺 | 判定 | 证据与边界 |
| --- | --- | --- |
| TYPE | match | 继承中文工作字体、标题级差和等宽统计数字；detector 的旧 Inter warning 不构成此次更换字体的理由。 |
| MATERIAL | match | 图表用真实几何编码，辅助面用白色和细分隔承载内容；没有伪造实体材质，也无 shipping raster。 |
| GROUND | match | 维持合同指定的冷银蓝浅底及白色助手 / 事件面；没有暖色主题或主题切换。 |
| A 分类排行 | contradicted（手机覆盖） | 横条、降序、数量和占比已实现；mobile-a 中“产品”的右侧数值被固定“提问”遮住。 |
| B 每日计数 | match | 各日数量、零值、日期和并列峰值可直接读取。 |
| C 日期×分类 | match | 源码默认 C；截图为紧密方格、零浅灰、正值深红、直接数字和统一色标。 |
| THESIS / STORY / FIRST VIEWPORT | match，受布局缺陷限制 | 范围、脚本摘要、图表和匹配事件顺序明确；统计由脚本计算。 |
| 欢迎态与首发后对话 | match | empty 截图为欢迎输入；conversation 截图为旧上新下、底部输入，引用和模拟流提示可见。 |
| 右侧历史 / 宽度 | contradicted | desktop-history 总助手仍为 340px（capture-results）；历史吞掉大半列，主标题、日期、消息和输入被挤成竖条。满足最多半屏不能代替主对话可读。 |
| 事件在助手左侧 | match | desktop-reader-assistant 与 user-1680-workspace 显示两者紧邻且互不覆盖；可同时操作的交互证据以提供的回归记录为限。 |
| 手机事件 / 对话 / 历史 | acceptable adaptation | 三张手机截图分别为单面板，通过返回、历史和加入当前对话控件衔接，符合手机切换约定；具体交互和焦点依赖提供的功能回归。 |
| 本地会话与协议 | match（非视觉证据） | conversation-store.ts 抽样确认 IndexedDB、多轮字段、导出、中断恢复和有限上下文；其余持久化 / 协议行为由提供的独立回归支持。 |
| Truth | match | 首页、事件和回答持续标明合成数据 / 模拟流；功能通过不等于真实 AI 答案质量验收。 |
| FORM | match | 合同明确用户指定局部改造且无需 concept-seed；无需重新探索或重建视觉世界。 |

## Ceiling

尚未达到阅读空间的交付标准：桌面历史展开使主要研究内容失去合理行宽，手机入口占用统计的事实标签。这两项是现有世界的空间分配问题，不需要新字体、装饰、图片或新设计方向。

一次 detector 的新 margin transition warning 应处理或记录：style.css 末尾给欢迎文字和 composer 过渡 margin。源码不足以证明可见卡顿，因此不单独升级成第三个 material fix。保留短暂、支持 reduced-motion 的数据入场，不用新增动效代替布局修复。

## Material fixes

1. **历史展开保住主对话可读宽度。** 位置：AssistantPanel.vue 的 panelWidth / historyOpen / widths，以及 style.css 的 .assistant-workspace、.assistant-main、.history-panel；失败证据为 desktop-history。目标：桌面展开历史时，先为主消息和输入列保留至少约 340px，再分配至少约 180px 历史，总宽限制在 50vw；恢复保存的小宽度与拖动历史也必须遵守。空间不足时沿用单面板历史模式。验收：1440 / 1680 宽度恢复旧宽度后展开历史，标题不变成窄竖条，问题、回答、输入可连续阅读，历史可切换 / 收起；总宽不超半屏，事件仍紧邻助手左侧。
2. **手机统计值避开固定提问入口。** 位置：style.css 手机 .assistant-trigger 与 A/B/C 内容布局；失败证据为 mobile-a 的“产品”数量 / 占比被遮住。目标：为入口保留独立空间或移到不覆盖事实标签的位置，不靠只增加 B 图下内边距处理全局覆盖。验收：390px 打开 A、B、C 并滚动经过完整图表，六类数量 / 占比、每日数值 / 日期、热图格 / 色标、数据表入口均不被“提问”遮挡，入口仍易触达。

## Keep

保留脚本事实摘要、直接数值编码、紧密红色热图、银蓝阅读面、上下消息与底部输入、事件在助手左侧的桌面布局、手机单面板及合成数据 / 模拟回答标识；不得把修复扩大成新世界探索或真实 AI 能力声明。
