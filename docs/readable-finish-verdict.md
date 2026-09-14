## verdict

评分基准：HEAD 230a44a；仅复核 readable-finish-review.md 原列出的两项修复。已重新实际打开同路径全部 14 张 PNG，均内容有效、视口合理，无需 recapture；固定面板之下的 fullpage 基础页不作为滚动回归。另读取 readable-capture-results.json 与 readable-finish-layout-results.json。

1. **resolved — 历史展开保住主对话可读宽度。** desktop-history 中研究助手标题、范围、消息、引用与输入恢复正常行宽，历史保留独立右栏。截图几何确认展开后总宽从 340px 增至 520px；1440 / 1680 恢复旧 340px 宽度的记录均为主列 339px（边框后）、历史 180px、总宽 520px，符合约 340px 主列和不超过半屏的目标。desktop-reader-assistant 与 user-1680-workspace 仍保持事件紧邻助手左侧。
2. **resolved — 手机统计值避开提问入口。** mobile-a 的六类数量 / 占比完整可读，原被挡住的“产品 4 · 16%”已清楚显示；mobile-b 的每日数值 / 日期和 mobile-c 的格值 / 色标均无入口覆盖。提问入口进入导航的独立正常流位置，44px 触点记录和 A/B/C 逐段滚动检查的 overlaps: [] 支持这一修复持续有效。

## remaining

clear。未见本批修复引入的 material regression。本次 ship 仅覆盖以上两项已评分修复，不替代文档收尾，也不代表真实新闻链路或真实 AI 答案质量验收。

disposition: ship
