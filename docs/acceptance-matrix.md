# 验收状态

项目 P0 整体仍未验收通过。2026-09-14 已在 Ubuntu 运行真实 PostgreSQL 16 + pgvector，
迁移到 0005、readiness、五源生产抓取样本和隔离备份恢复演练通过。持久采集运行中，
标准事件发布及模型仍未实现。最新数据库证据见 db-live-validation.md，环境见 ubuntu-development.md。
下表保留此前各轮 UI/合成回归记录，不合并计算通过率。

| 检查 | 当前结果 | 证据与限制 |
| --- | --- | --- |
| 早期两版原型比较 | 采用Terra，持续由Terra负责前端 | design-requirements.md、prototype-comparison.md；同32条合成数据，主观评分Sol88/Terra90 |
| 两原型共用浏览器检查 | 14/14 | prototype-browser-results.json |
| 本轮四页重设计 | 四项独立审查修复均resolved，ship | ui-redesign-report.md、ui-finish-verdict-final.md；仅该修复范围，不代表完整P0通过 |
| 时间层级与叠层抽屉 | 浏览器24/24；动效2/2；四项修复resolved，ship | drawer-browser-results.json、drawer-motion-results.json、drawer-ui-report.md |
| 简化阅读预览 MVP | 浏览器27/27；两项修复resolved，ship | simple-mvp-report.md、simple-mvp-finish-verdict.md；独立预览，8张最终截图，合成数据 |
| 月份阅读与规则统计总览 | 新交互36/36、问答协议12/12、统计HTTP12/12、前端单元18/18与构建通过 | reading-insights-report.md；默认今日，纯程序汇总，14张桌面/手机截图；真实日采集、PG与模型未验收 |
| 正式四页浏览器（此前记录） | 42/42 | frontend-browser-results.json；390/768/1440、分页、取消、引用、错误、实际计划与长文本 |
| 实际HTTP合成API | 14/14 | api-smoke-results.json；确切ID、日期、别名、分页和证据定位 |
| 独立确定性计划HTTP | 30/30 | query-plan-regression-results.json；固定Clock、日期、别名、实体跨度、UI冲突 |
| 原36题的显式结构部分 | 24通过，12待验收 | structure-regression-results.json；不代表36题完整题义全部通过 |
| 后端单元测试 | 94/94 | local-checks.json、verification日志；无真实PG |
| 前端单元测试 | 18/18 | 新增跨年/月、未知日期及分页折叠状态；drawer-ui-report.md |
| 统一工程检查 | 11/11 | local-checks.json；静态/类型/单测、两层回归、OpenAPI、离线迁移、构建 |
| 真实连接拒绝故障协议 | 3/3 | database-unavailable-results.json；保留未监听loopback端口，未使用PG服务 |
| 仅生产依赖启动导入 | 通过 | runtime-validation.json；独立no-dev环境导入API/worker/scheduler，未安装pytest |
| 原RSS入口探测 | 5/5 XML解析 | source-validation.json；使用旧入口探测脚本，不能代替生产transport |
| 生产抓取/正文样本 | 5/5 | source-body-validation.json；Ubuntu 显式 DoH，保留公网校验和 IP 固定 |
| 完整来源链路、真实标准事件 | 0/5、0/100 | 当前止于正文版本与待审候选；未完成模型提取/发布 |
| PostgreSQL16+pgvector真实迁移 | 0001→0005、ready、备份/隔离恢复通过 | ubuntu-development.md、db-live-validation.md；不替代模型与事件质量验收 |
| 历史T01/E01 gold | 未执行 | 用户暂无原站ID/材料，明确同意合成结构回归 |
| 全文/向量/RRF及真实问答 | 未完成 | 无真实模型调用；预算表/账本基础不等于执行结算 |
| 旧API/SSE兼容、生产恢复 | 旧接口及生产部署未验收；开发库恢复已通过 | 缺原站抓包；隔离恢复见 ubuntu-development.md |

浏览器JSON每项layer区分真实fixture API、模拟SSE、模拟JSON及故障注入。模拟流通过只证明客户端行为；普通API不会自动改为模拟答案。无模型的问答仍显示真实错误和已解析条件。

固定双轴审查见review-575d571.md、review-0b5cbb9.md、review-4eb258e.md。查询计划发现的实体漏检、冲突提示和日期上界问题均经过原负责人修复与固定复验；仍不等于真实PG语义/事务验收。

简化阅读预览 http://127.0.0.1:5175/preview ，原版 http://127.0.0.1:5175 ，API http://127.0.0.1:8002/docs 。启动/停止脚本已实际验证。后续依赖和验收顺序见next-acceptance.md。

用户已取消周额度 80% 停止规则。历史观测不再作为开发停止条件。
