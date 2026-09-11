# 双轴审查：0b5cbb9 摄取阶段

冻结范围 git diff 407e5b0...0b5cbb9。两个独立 Astra 审查代理只读固定提交；不把之后的 WIP 当修复，不执行真实 HTTP 或 PostgreSQL。

## Standards

| 级别 | 发现 | 固定位置 |
| --- | --- | --- |
| P1 | 仅处理前20条且吞正文失败后确认ETag，304使尾部与失败URL持续遗漏 | worker_service.py:45/64 |
| P2 | claim/finish/最终租约超时不汇总run状态、结束时间和失败信息 | ingest_repository.py:146 |
| P2 | response模型未声明found/kept/candidates/versions，model_copy增加的字段序列化丢失 | schemas.py:128、main.py:366 |
| P2 | 多source job更新同run使用无锁Python +=，并发丢增量 | worker_service.py:69 |
| P2 | 业务提交与job完成分为两事务，崩溃导致重复计数或结果与终态不一致 | worker_service.py:51、app/worker.py:31 |
| P2 | updated_articles用整run.new_articles==0判断，混合新增/更新少报 | worker_service.py:108 |
| P2 | 摄取仓储SQL异常未转统一503，端点逃出错误协议 | main.py:365/390 |

序列化丢字段已实际执行冻结 Pydantic 模型复现，其余为明确静态路径/事务语义证据；不声称 PG 并发实测。

## Spec

| 级别 | 发现 | 规格 |
| --- | --- | --- |
| P1 | 两篇正文全失败仍保存feed-v1 ETag，零候选且正常返回 | 第14节恢复点与部分失败 |
| P1 | Article URL全局唯一，但worker按source+URL查，跨源同URL必撞唯一约束 | 第16节报道身份 |
| P1 | 运行终态永远queued | 第15节run状态聚合 |
| P2 | 一篇新增+一篇更新插入2版本，却只计new=1/updated=0 | 第14节分项计数 |

全失败确认ETag、混合版本计数均以冻结模块和模拟会话/抓取替身实际复现；跨源URL唯一约束由固定SQLAlchemy表元数据确认，未运行PG。

## 主审补充与修复追踪

两轴重叠问题保持各自原分级，不相加当成独立缺陷总数。主审另确认：默认60秒租约与最长20篇抓取不匹配；业务fencing缺少lease_until；独立scheduler首次调度延后；来源注册缺闭环；公开地址验证与实际DNS连接之间存在重绑定窗口。

15e6561 阶段修复加入heartbeat、启动即调度、trigger_type、finally释放、业务与job原子完成、run/source锁、304原子完成及正式响应字段。它不等于全部缺陷关闭。其余持久article子任务、失败/超时run汇总、统一503、来源注册、固定IP连接仍由Sol继续实施。

后续提交必须逐项复验后关闭。没有PG实例的锁、事务、恢复与迁移执行继续保留未验收。

## 定向复验 1a6a078（固定提交）

复验确认：25 条条目全部形成持久正文任务，304 不删除待办；文章按全局 canonical_url upsert，等待本 run 全部 feed 发现结束后抓正文；新 run 的成功、最终失败与租约耗尽均汇总终态。正式响应字段、run 锁和业务/job 原子提交已落码。4 项冻结模拟检查通过，不等于 PG 事务实测。

新增 P2：0002 遗留的 queued run 若所有 jobs 已终态，0003 未回填 run，后续 claim 不会再触发汇总。已交后端负责人补迁移。统一503、来源注册与失败健康统计继续收尾。

0be49e0 加入固定 IP transport 并保留 Host/TLS 主机名及证书验证，46 项单测通过。主审发现共享地址 100.64.0.0/10 不属于 private 却非公网，要求统一 is_global 判定并补禁止 connect 的检查；该补丁未集成前不能关闭网络边界问题。

### 526bd793 固定提交复验

独立规格审查执行18项模拟网络/地址检查及1项迁移SQL断言，全部通过。旧run回填只处理queued/running且无活动jobs的记录；公网候选全部校验后才按IP连接，TLS主机名/Host及证书验证保留。上述两项代码问题关闭；真实PG回填及真实TLS握手未执行。

7492716加入来源注册、source健康、DocumentParseError计数与SQLAlchemy错误503。根目录通过关闭的本机端口独立复现连接拒绝仍返回500，原因在于底层连接异常未必属于SQLAlchemyError；该项再次退回Sol。HTTPX生产依赖此前仅在dev组，也要求移至运行依赖。
