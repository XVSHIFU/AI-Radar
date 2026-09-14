# B 控件正式整合：设计记录

用户已接受隔离 B 预览并授权整合到正式前端。本轮把实现后的共同规则合并到 [DESIGN.md](../DESIGN.md) 与 [.impeccable/design.json](../.impeccable/design.json)，保留原有北极星、蓝色、银蓝底面、中文字体回退、首页连续阅读布局及无主题开关约定。范围契约见 [compact-controls-integration.md](../.impeccable/surfaces/compact-controls-integration.md)。此前仅限预览的说明不再约束本次已授权的持久设计变更。

- 控件：桌面普通32px、次级28px，普通6px圆角；移动44px。热图保留桌面34px最小列宽 / 30px高，移动44px宽高、3px微圆角、3px间距和分类粘列。
- 日期：首页与/ask使用共享DateRangePicker；今天、昨天、近7天、近30天、本月与日历都先修改草稿，应用才提交。取消、Esc和外部点击放弃草稿。今天按上海时区，日运算按UTC；有限区间最多366天、含首尾；首页允许不限/单侧日期，统计仍默认今天并要求完整边界。日历桌面30px高、移动44px。
- 色阶：正式统计按同图最大计数M归一化，正值级别为max(1, ceil(n/M × 12))，13色包含零值与12个正值级别。0–7级深字，8–12级白字。没有继承预览的绝对计数映射或旧连续深红公式。统计使用完整响应，超过31天仍按月聚合，A/B/C及数据表和点击筛选语义保留。
- 助手：6px不可见可聚焦separator保留拖动及Alt方向键调整。桌面总宽最多半屏，历史180–360px且受主列约340px的既有边界限制；移动隐藏拖动区。历史逐行更多菜单Teleport至body，对目标会话改名、导出或删除；改名使用自定义原生dialog。历史与新建仍在输入底部，原有范围快照、引用和流式取消语义保留。
- 存储与抽屉：正式会话继续使用IndexedDB ai-radar-conversations，不使用隔离预览的localStorage会话实现；localStorage仅沿用面板尺寸等既有配置。原生浏览器前进/后退与查询参数抽屉拓扑保留。main.ts全局加载共享抽屉CSS，直接访问/ask也有完整样式。
- 数据：扩展仅在正式前端演示模式生效，原始32条加60天内生成的1029条，共1061条；生成分布包含一个零事件日。保留“合成事件/模拟流”标识。原始后端fixture仍32条，真实API未改变，新增样本不是新闻或真实AI能力验收。

本次读取compact-controls.css、DateRangePicker.vue、date-range.ts、AssistantPanel.vue、AskPage.vue、HomePage.vue、main.ts、demo-events.ts与PRODUCT.md，按最终层叠记录令牌及组件行为；未顺带刷新无关设计漂移，未新增栅格素材。

根任务报告前端测试25/25及构建通过；[浏览器结果](compact-integration-browser-results.json)13/13、[会话协议结果](conversation-protocol-results.json)13/13。[完成审查](compact-integration-finish-review.md)记录本次UI裁决及余留边界。以上仅验证本次前端整合与合成/协议回归，不表示真实模型、生产数据库、真实新闻链路或公开部署通过验收。
