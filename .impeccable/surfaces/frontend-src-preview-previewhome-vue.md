---
version: 1
slug: "frontend-src-preview-previewhome-vue"
primary_target: "frontend/src/preview/PreviewHome.vue"
related_targets: ["frontend/src/preview/PreviewReader.vue","frontend/src/preview/preview.css","frontend/src/App.vue","frontend/src/AskPage.vue"]
---

# 简化阅读预览 MVP · 2026-09-14

模式：Read，辅助操作按需出现。用户要求在当前基础上按简洁、设计、使用优先重新审视UI，生成可体验修改MVP。沿用已确认银蓝桌面阅读空间、抽象平面层次与日期节奏；代码优先。本轮是既有视觉世界的流程简化，不重新选择品牌或构图世界。

用户已明确确认：事件内直接显示关键证据，来源细节按需展开。制作可比较的独立预览，原版完整保留。证据仍须来自保存段落，不编造支持关系或重要性排名。

THESIS: 先读事件，一次打开就能看见已保存的证据，次要操作不抢占阅读。
OWN-WORLD: 保留银蓝地面、白色阅读面、深蓝文字和自然中文字体；用紧凑日期与连续正文体现个性。
STORY: 打开/preview→读动态→直接搜索或分类→点事件即读摘要与证据→按需看来源信息→一次关闭回原位置。问答预览将研究条件按需展开。
FIRST VIEWPORT: 紧凑顶栏与搜索/分类控件，单一阅读主体，事件较旧版更早出现；避免侧边全库统计重复卡和三行大日期标题。手机操作区44px，日期筛选选择后有可见状态。
FORM: 现有界面的简化MVP，不是新视觉世界；无新图片、无概念竞赛或生成comp。
INTERACTION: 输入即筛选、年月日可折叠、单阅读抽屉及来源信息原生展开；进入与返回保留URL、焦点、滚动、请求取消；短动效继承并支持减少动态效果。
FINISH: 有界桌面/手机自查，独立finish review，文档核对后完成。所有新增图片若存在须记录来源；本轮不需要位图。

范围：新增/preview、/preview/ask及专用组件；原/、详情、问答和采集管理仍可访问。仅App添加预览shell分支、Ask可加默认false的streamlined prop。API/后端/数据语义不变。
数据：服务端精确total和next_cursor，不将已加载数量当完整周期统计。多条证据真实呈现，不由前端编造“核心主张”或确认支持关系。合成标识在前景可见；无证据、失效ID、失败、取消各自真实说明。
