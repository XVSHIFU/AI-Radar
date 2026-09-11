# 双轴审查：575d571

基线80221e1，受审提交575d5710dbf862f7f89902cff6bad8e8a970d8da。命令：git diff 80221e1...575d571。两名独立Astra审查代理并行只读检查，修复由原负责人处理。

## Standards

1. P2：SSE记录sawError却允许error→sources→done(completed)。实际解析器复现，违反异常序列契约。
2. P2：真实JSON回答把服务端引用index覆盖为数组下标+1，非连续编号错配，违反显式index映射要求。
3. P2：articles_for内session.get缺少统一数据库异常转换；静态路径发现，未声称真实PG实测。
4. P2：详情错误态没有显式重试入口，违反设计错误态要求。
5. P3：字号/颜色/间距硬编码，出现基线外9/10/13px间距，设计tokens未完全落实。

## Spec

1. P1：Windows锁定环境构造PostgresRepository时ZoneInfo(Asia/Shanghai)抛ZoneInfoNotFoundError，缺tzdata，配置DB后连接前就可能启动失败；本机实际复现。
2. P2：PG仅strip/casefold，fixture采用NFKC与空白归一，全角DeepSeek在两路径参数不同；定向SQL编译确认。
3. P2：独立/evidence接口绕过articles_for的摘录检查；模拟ORM段落与quote不匹配仍返回Evidence，须在共享读取边界验证。
4. P2：SSE失败后允许done(completed)，实际执行复现，与协议不符。

规范轴5项，最高P2（错误流误判完成）；规格轴4项，最高P1（Windows数据库模式启动失败）。两轴保留原结论，重叠项不凑成独立缺陷数量。

## 修复追踪

已分配Sol：tzdata与构造/lifespan回归，共用Unicode规范化，Evidence共有校验及统一异常边界。
已分配Terra：错误流终态断言、引用编号、详情重试、集中tokens；主审补充演示数据与模拟问答模式分离，避免服务端fixture响应触发本地模拟答案。

后续修复提交和复验结果在完成后追加。PG、模型、历史gold缺环境或材料是已披露验收限制，不计入上述新缺陷。

### 2026-09-12 01:25 复验

- Windows 时区、NFKC 参数规范化、articles_for 异常转换：cbf0111；本地 20 项单测及统一检查通过。PG 行为仍未实测。
- 独立 Evidence 共有校验：复查发现 cbf0111 实际未接入 evidence_for，仍开放，已再次退回 Sol；不能据报告关闭。
- SSE 错误终态：77109e9；引用编号：31e5fba；详情重试：90f357a/9c324b5；模式切换：09d42cb。
- 样式集中变量及移动导航：09d42cb/a70b4b3/23e1a51。曾出现循环变量定义，已恢复色值并加入实际计算色值检查。
- 正式浏览器 35/35，含错误注入、引用 index=2、详情重试、模式切换、12 个长引用、手机导航、颜色和焦点；frontend-browser-results.json 为逐项证据。
- 统一检查 8/8 步骤通过，含后端 20 项/前端 12 项测试、OpenAPI 对齐、离线迁移与构建；local-checks.json 记录耗时。后续采集提交需重新运行。

原受审固定点不变；以上为原负责人修复与主审复验追踪，不冒充对后续所有新增代码的独立审查。

### 2026-09-12 02:22 定向关闭记录

独立 Evidence 读取路径已在0b5cbb9接入冻结段落校验；空摘录、段落缺失和文本不匹配被拒绝。初轮9项两轴发现均有对应代码修复和合成/静态复验，PG实际执行仍未验收。后续查询计划和采集新增代码不在原冻结审查范围内，另行验证。
