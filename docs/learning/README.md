# IncidentCopilot 中文学习中心

这套文档面向已经理解 LangGraph 基本概念、但还不熟悉完整 AI 后端工程的读者。文档解释的是当前仓库真实实现, 不是理想化架构。

<a id="english-terms"></a>

## 📘 阅读前先看懂这些英文

项目保留了一些 AI、后端和可观测性领域常用的英文名称。它们不是额外的复杂概念, 可以先通过下面的中文解释建立直觉。

| 英文 | 中文含义 | 在本项目中的作用 |
| --- | --- | --- |
| **Incident** | 故障事件 | 一次需要调查的线上异常, 包括服务名、症状、发生时间和环境等信息。 |
| **Evidence** | 证据 | 从日志、指标、链路、变更记录或知识库中查到的事实。每条证据都有来源、时间、服务和唯一 ID。 |
| **Citation** | 引用信息 / 证据出处 | 记录 Evidence 来自哪里以及如何再次定位, 类似论文的参考文献。最终报告通过它证明结论不是凭空生成的。 |
| **Provider** | 数据提供者 | 屏蔽具体数据源差异的统一接口。Graph 不关心数据来自本地样例还是远程系统, 只通过 Provider 获取证据。 |
| **KnowledgeProvider** | 知识库数据提供者 | Provider 的一种, 专门查询 Runbook 和历史故障。当前可由本地 RAG 实现, 也可由 Fixture 实现。 |
| **ModelProvider** | 模型提供者 | 屏蔽具体大模型厂商的统一接口。当前默认使用不访问网络的 Fake Model, 让测试和演示可以稳定复现。 |
| **Fixture** | 固定的本地样例数据 | 提前准备并脱敏的日志、指标、链路、变更和故障数据。没有外部服务和付费 API 时, 项目仍能完整运行。 |
| **Prometheus** | 指标监控与查询系统 | 保存并查询时间序列指标。本项目已经提供真实 HTTP Adapter, 可查询服务错误率、延迟等 Metric。 |
| **Metric** | 指标 | 随时间变化的数值, 例如错误率、请求耗时、CPU 使用率和数据库连接数。 |
| **Log** | 日志 | 服务在某个时刻记录的离散事件或文本, 例如错误消息、请求结果和异常堆栈。 |
| **Trace** | 分布式调用链路 | 描述一个请求经过哪些服务以及每一段耗时多久, 用于定位跨服务故障和慢调用。 |
| **Runbook** | 故障处理手册 | 运维人员总结的排查步骤、判断标准和安全操作建议, 是 RAG 检索的重要知识来源。 |
| **Tool** | 调查工具 | Graph 可以调用的受控只读操作, 例如 `search_logs`、`query_metrics` 和 `search_runbooks`。 |
| **ToolRegistry** | 工具注册中心 | 保存工具白名单, 统一执行参数校验、超时、重试、预算限制和 Evidence 校验。 |
| **State** | 工作流状态 | LangGraph 调查过程共享的数据, 包括计划、证据引用、假设、轮数、预算和最终报告等。 |
| **Reducer** | 状态合并规则 | 多个并行节点同时更新 State 时, 决定列表如何追加、计数如何累加, 避免结果互相覆盖。 |
| **RAG** | 检索增强生成 | 先从 Runbook、服务文档和历史故障中检索相关内容, 再把检索结果用于调查和报告生成。 |
| **Checkpoint** | 工作流快照 | 保存某个 `thread_id` 的 State 和执行位置, 让暂停后的调查可以从原位置恢复。 |
| **HITL** | 人在回路 / 人工审核 | `Human-in-the-loop` 的缩写。高风险修复建议在最终确认前暂停, 等待人类接受或要求追加调查。 |
| **SSE** | 服务器推送事件 | `Server-Sent Events` 的缩写。API 用它把调查进度持续推送给前端或调用方。 |

> [!TIP]
> 可以先记住一条主线: **Prometheus 或 Fixture（数据源）→ Provider（统一取数）→ Tool（受控查询）→ Evidence（证据）+ Citation（出处）→ State（调查状态）→ 最终报告**。

> [!NOTE]
> 英文类名通常直接表达职责。例如 `KnowledgeProvider` 可以拆成 **Knowledge（知识）+ Provider（提供者）**, 即“负责提供知识库数据的组件”。看到陌生名称时, 可以先按这种方式拆开理解。

建议直接阅读合并后的完整文档：[IncidentCopilot 中文教学版完整文档](INCIDENT_COPILOT_LEARNING_GUIDE.md)。

当前目录中的分章文件是完整文档的维护源。修改分章后执行：

```text
uv run python scripts/build_learning_guide.py
```

业务实现基线为 `26f6130`。后续只调整了教学注释和文档组织;Graph 结构、函数签名和业务逻辑没有变化。

## 推荐入口

1. [学习路线](00-learning-path.md)
2. [项目整体介绍](01-project-introduction.md)
3. [目录和模块关系](02-directory-and-modules.md)
4. [一次请求的完整生命周期](03-request-lifecycle.md)
5. [State 和 Reducer](04-state-and-reducers.md)
6. [Graph、Node、Edge 与调查循环](05-graph-and-nodes.md)
7. [Provider、Tool 和 Evidence](06-providers-and-tools.md)
8. [RAG 索引和检索](07-rag-pipeline.md)
9. [调查循环与假设](08-investigation-loop-and-hypotheses.md)
10. [FastAPI 与异步任务](09-fastapi-and-async.md)
11. [Checkpoint、Streaming 与 HITL](10-checkpoint-streaming-hitl.md)
12. [Evaluation 与测试](11-evaluation-and-tests.md)
13. [本地运行和演示](12-local-run-and-demo.md)
14. [常见问题和面试问答](13-faq-and-interview.md)
15. [术语表](14-glossary.md)

需要直接读代码时, 使用[核心源码阅读索引](core-reading-index.md)进入逐文件源码解读。

## 阅读约定

- “State 读取/写入”专指 LangGraph `InvestigationState`。
- “任务状态”专指 `InvestigationRecord.status`。
- “Checkpoint”保存 Graph 执行快照, 不等于业务 Repository。
- “真实 Prometheus”表示真实经过 HTTP API 的指标链路; 其他数据源仍可能来自 Fixture。
- 文档中的流程图只展示源码中存在的节点、函数和依赖。

## 当前生产化边界

当前实现没有真实 LLM、持久化 Investigation/Event Repository、外部 Evidence Store、Loki/Tempo Adapter、分布式 worker 或自动修复能力。教学文档会明确这些边界, 不把作品集实现描述成完整生产系统。
