# 14 术语表

| 术语 | 本项目中的含义 |
| --- | --- |
| Adapter | 把统一端口翻译为 Fixture、Prometheus 或数据库操作的实现 |
| Aggregate | 并行 collect 分支汇合并检查预算的节点 |
| BM25 | 基于词频和文档频率的词法检索算法 |
| Checkpoint | LangGraph 某个 thread 的 State 和执行位置快照 |
| Checkpointer | 保存和读取 checkpoint 的组件 |
| Citation | 可解析来源, 包含 URI、locator、hash 和获取时间 |
| Conditional Edge | 通过路由函数选择预声明目标的边 |
| Correlation ID | 关联一次工具步骤及其日志/Telemetry 的标识 |
| Deadline | 整次调查允许执行到的绝对时间 |
| Domain Model | 与 FastAPI/LangGraph 解耦的领域值对象 |
| Edge | Graph 中从一个节点到下一个节点的连接 |
| Embedding | 把文本映射为向量; 当前默认是确定性 Fake |
| Evidence | Provider 返回的完整、带来源证据对象 |
| EvidenceRef | 写入 Graph State 的轻量 Evidence 投影 |
| Fake Model | 无网络确定性 ModelProvider, 用于测试控制流 |
| Fixture | 版本化、脱敏、可复现的本地事故数据 |
| Ground truth | Evaluation 使用的已知根因和相关证据标签 |
| HITL | Human-in-the-loop, 在高风险建议前暂停等待人审 |
| Idempotency | 重复请求或重放不会产生重复副作用 |
| IncidentContext | 规范化事故服务、时间、症状和环境 |
| InvestigationRecord | API 任务元数据和任务状态 |
| InvestigationState | LangGraph 节点共享的有界状态通道 |
| Interrupt | LangGraph 暂停当前 thread 并等待 resume 的机制 |
| ModelContext | 发送给 ModelProvider 的裁剪、结构化上下文 |
| ModelProvider | 隔离具体模型厂商的协议端口 |
| Node | 读取 State 并返回最小更新的 Graph 函数 |
| Port / Protocol | 业务层依赖的窄接口, 与具体 Adapter 解耦 |
| Provider | 从某一数据源查询并返回 Evidence 的实现 |
| Pydantic Schema | 外部输入、模型输出和领域不变量的运行时校验 |
| Query Rewrite | 保留原词并增加受审别名的查询扩展 |
| Reducer | 合并同一 State 通道多个更新的函数 |
| Repository | 读写任务记录和事件的持久化端口 |
| Rerank | 对候选重新排序; 当前没有额外模型 reranker |
| RRF | Reciprocal Rank Fusion, 按各检索器排名融合 |
| Run ID | 一次初始或恢复执行的标识 |
| Send | LangGraph 根据运行时步骤动态分发节点任务的机制 |
| SSE | Server-Sent Events, 服务端单向事件流 |
| StepResult | 一次真实工具步骤的状态、参数和 Evidence ID |
| StopReason | evidence sufficient 或预算停止的可审计原因 |
| Structured Output | 必须通过任务 Pydantic Schema 的模型 JSON 输出 |
| Superstep | LangGraph 中可并行运行并在结束后合并更新的一轮 |
| Thread ID | LangGraph checkpoint 的稳定工作流实例标识 |
| Tool | 暴露给调查计划的只读、强 Schema 操作 |
| ToolRegistry | 工具白名单、执行策略和 Evidence 校验边界 |
| Usage | 模型输入/输出 Token; Fake Model 标记为估算 |
| VectorStore | 存储和搜索版本化 embedding 的端口 |

返回[学习中心](README.md)或进入[核心源码阅读索引](core-reading-index.md)。
