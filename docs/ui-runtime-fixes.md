# 2026-09-15 前端交互修复

- 非 localhost 的 HTTP 页面没有 crypto.randomUUID：新建会话抛异常，
  导致提问和加入事件均失败。共用 secureUuid，使用 getRandomValues 生成 UUID v4 回退；
  同时修复采集提交幂等键的同类用法。
- 轮盘展开期间以非被动 capture wheel 监听整个矩形边界；命中时取消滚动与传播，
  关闭及卸载清理监听。关闭动画中不继续旋转。
- 一级事件抽屉保留保存摘录，二级来源抽屉只显示版本、段落与核验信息；
  引用段落不误标为多个原文版本。
- DeepSeek 新闻入口默认中文阅读；英文摘录仍保留对应的采集原文链接。
  未修改数据库原文、Evidence 或其定位信息。全站语言切换不在此次实现范围。

真实 HTTP 新会话、桌面附件并排、手机附件、抽屉去重与 DeepSeek 双入口已验收。
轮盘使用 CDP 明确坐标发送原生事件复测（agent-browser 的 mouse wheel 实际坐标为0,0，
不能用它冒充指定区域的滚轮测试）。31项单元测试、生产构建通过。
结果见 [ui-runtime-fixes-results.json](ui-runtime-fixes-results.json)。

本次没有启用后端真实问答生成。完整数据链路及缺口见
[data-pipeline-current.md](data-pipeline-current.md)。
