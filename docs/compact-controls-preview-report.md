# B 控件预览交付记录

预览：http://127.0.0.1:5175/controls-preview.html

本次只制作独立交互预览，正式首页、统计页和其持久化数据均未修改。

- 旧按钮静态对照与 B 轻量工具栏：桌面主控件32px、辅助28px、主操作实色、筛选浅底、辅助操作无框。
- 日期：单一范围入口，快捷范围、日历起止选择、应用/取消、非法范围反馈；按天统计，不显示时分秒。
- 助手：独立滚动会话、浏览器保存与刷新恢复、草稿、切换/重命名/导出/删除、折叠历史、窄分隔线拖宽，桌面总宽不超过半屏。预览脚本回复明确标注，不调用模型。
- 热力图：北京时间当天向前60天、六类、1029条确定性合成事件；默认近30天537条；微圆角红色格子、零值、点击查看同源事件清单、轻微入场动效。日期随打开当天移动，样本不代表新闻。

## 验证
- scripts/check-compact-preview.js：20/20，报告 compact-controls-interaction-results.json；覆盖统计总数、范围、下钻、色块对比度（最低5.59）、日期应用/取消/校验、消息布局、会话与草稿。
- 页面刷新恢复通过；390×844手机无整页横向溢出，手机及1024×768日期弹层保持在视口内。
- 真实鼠标拖拽助手从510到610px，历史从160到180px，见 compact-controls-drag-results.json。历史命中点位于边界内2px，外侧边框不属于感应区。
- JS语法检查通过；本地HTML入口HTTP200。
- 首轮检测器执行一次，机械修正文字字号、对比度和阴影；保留现有字体。
- 独立复核：compact-controls-finish-review.md 为 fix；修复后 compact-controls-finish-verdict.md 为 ship，仅评分其列出的三项修复全部resolved。
- 截图：.impeccable/review/compact-controls/；构建线程两轮、复核驱动一批修复与重拍。
- 设计说明另见 compact-controls-design-notes.md；全局 DESIGN.md 与 sidecar 保留正式实现规范，预览尚未整合。

## 范围限制
历史采用独立localStorage键radar-controls-preview-chats-v1，不读取正式助手IndexedDB。当前回答只按当前范围生成固定统计回复，不解释自由问题，不接入真实模型。无生产数据库或采集链路变更。样式参照用户本地OneSOC截图与CSS尺寸重新实现，未运行或复用压缩包脚本。
