# 验收状态

这是可启动工程与合成回归阶段的验收记录，项目P0整体仍为NO-GO。未执行项目不计通过，各层数量不相加。

| 检查 | 当前结果 | 证据与限制 |
| --- | --- | --- |
| 早期两版原型比较 | 采用Terra，持续由Terra负责前端 | design-requirements.md、prototype-comparison.md；同32条合成数据，主观评分Sol88/Terra90 |
| 两原型共用浏览器检查 | 14/14 | prototype-browser-results.json |
| 本轮四页重设计 | 四项独立审查修复均resolved，ship | ui-redesign-report.md、ui-finish-verdict-final.md；仅该修复范围，不代表完整P0通过 |
| 时间层级与叠层抽屉 | 浏览器24/24；动效2/2；四项修复resolved，ship | drawer-browser-results.json、drawer-motion-results.json、drawer-ui-report.md |
| 正式四页浏览器 | 42/42 | frontend-browser-results.json；390/768/1440、分页、取消、引用、错误、实际计划与长文本 |
| 实际HTTP合成API | 14/14 | api-smoke-results.json；确切ID、日期、别名、分页和证据定位 |
| 独立确定性计划HTTP | 30/30 | query-plan-regression-results.json；固定Clock、日期、别名、实体跨度、UI冲突 |
| 原36题的显式结构部分 | 24通过，12待验收 | structure-regression-results.json；不代表36题完整题义全部通过 |
| 后端单元测试 | 94/94 | local-checks.json、verification日志；无真实PG |
| 前端单元测试 | 18/18 | 新增跨年/月、未知日期及分页折叠状态；drawer-ui-report.md |
| 统一工程检查 | 11/11 | local-checks.json；静态/类型/单测、两层回归、OpenAPI、离线迁移、构建 |
| 真实连接拒绝故障协议 | 3/3 | database-unavailable-results.json；保留未监听loopback端口，未使用PG服务 |
| 仅生产依赖启动导入 | 通过 | runtime-validation.json；独立no-dev环境导入API/worker/scheduler，未安装pytest |
| 原RSS入口探测 | 5/5 XML解析 | source-validation.json；使用旧入口探测脚本，不能代替生产transport |
| 生产抓取/正文样本 | 0/5，本机DNS阻断 | source-body-validation.json；域名解析至198.18/私有IPv6而被拒绝 |
| 完整来源链路、真实标准事件 | 0/5、0/100 | 当前止于正文版本与待审候选；未完成模型提取/发布 |
| PostgreSQL16+pgvector真实迁移 | 未执行 | 无Docker/PG；用户同意先推进工程，离线DDL不替代落库/并发/恢复 |
| 历史T01/E01 gold | 未执行 | 用户暂无原站ID/材料，明确同意合成结构回归 |
| 全文/向量/RRF及真实问答 | 未完成 | 无真实模型调用；预算表/账本基础不等于执行结算 |
| 旧API/SSE兼容、生产恢复 | 未验收 | 缺原站抓包和运行环境 |

浏览器JSON每项layer区分真实fixture API、模拟SSE、模拟JSON及故障注入。模拟流通过只证明客户端行为；普通API不会自动改为模拟答案。无模型的问答仍显示真实错误和已解析条件。

固定双轴审查见review-575d571.md、review-0b5cbb9.md、review-4eb258e.md。查询计划发现的实体漏检、冲突提示和日期上界问题均经过原负责人修复与固定复验；仍不等于真实PG语义/事务验收。

当前预览 http://127.0.0.1:5175 ，API http://127.0.0.1:8002/docs 。启动/停止脚本已实际验证。后续依赖和验收顺序见next-acceptance.md。

Pro周额度用户起始报告95%；2026-09-12 13:39观测83%，最新2026-09-13 11:22观测97%，分别记录观测值；<=80%即停止所有模型工作。实际货币费用与用户返工时间unknown，不能用周百分比推算现金或补填0。
