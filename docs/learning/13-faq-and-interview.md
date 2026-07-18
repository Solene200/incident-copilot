# 13 常见问题和面试问答

## 为什么不是普通 ReAct Agent

事故调查需要可预测循环、工具白名单、预算、恢复和人工审批。这里让模型提供结构化内容建议, Graph 和 Registry 掌握执行权。开放式 ReAct 更灵活, 但更难证明不会无限调用或执行高风险动作。

## 并行工具调用是真的并行吗

是。`dispatch_evidence_collection` 返回多个 `Send("collect_evidence", scoped_state)`, 测试中的 barrier 要求七个初始分支全部开始后才能释放。串行实现会超时。

## 为什么还需要 aggregate 节点

它是并行汇合屏障, 也是分批并发的循环点。Reducer 在进入 aggregate 前合并证据、步骤和计数; aggregate 再检查 deadline/预算, 并决定是否发送下一批。

## 为什么 State 用 TypedDict 而不是全 Pydantic

Pydantic 用于边界和领域不变量, TypedDict + `Annotated` 更直接表达 LangGraph 通道和 reducer。两者职责不同, 不是二选一。

## 如何防止模型伪造 Citation

模型只返回假设中的 Evidence ID 和报告叙事草稿。`verify_hypotheses` 删除不存在的 ID, `generate_report` 从 State 中的 EvidenceRef 收集 Citation。模型不能直接写最终 Citation 对象。

## Provider 返回 Evidence 后为什么还要校验

Provider 可能是外部系统 Adapter, 可能返回错服务、越界时间、错误来源或超量结果。Registry 是第二道边界, 不因对象已经通过一次构造就默认其业务范围正确。

## 为什么 RAG 用 RRF

BM25 和 cosine 原始分数不在同一量纲。RRF 只依赖排名, 小型基线更容易解释和稳定复现。真实生产数据仍需调参或 reranker。

## Fake Model 是否硬编码根因

它使用当前 Evidence 摘要生成规则化输出, 不读取 Evaluation ground truth。它确实是面向演示的确定性规则实现, 因而不能代表真实 LLM 泛化能力。

## Checkpoint 是否等于任务不会丢

不是。Checkpoint 保存 Graph State。当前任务元数据、幂等键、SSE 历史和后台 Task 仍在内存。完整高可用需要持久化业务 Repository 和分布式 worker。

## request_more_research 如何生效

人工反馈先通过 Schema, Service 检查剩余预算, `Command(resume=...)` 恢复 human_review。反馈写入 State 后跳到 refine, Fake Model 把 requested queries 映射为允许的工具步骤。

## 为什么 waiting_review 会关闭 SSE

此时 Graph 已暂停, 在人工操作前不会产生新事件。关闭连接能避免客户端无限等待。恢复后用 `Last-Event-ID` 重新连接即可。

## Evaluation 的 1.0 指标说明什么

只说明当前确定性管线在三个同仓版本化 Fixture 上与词法标签一致, 不说明生产准确率。数据量、模型类型、标签方法和时延环境都限制了结论。

## 如果要接真实 LLM, 最先改哪里

实现 `ModelProvider.complete()`, 返回 `ModelResponse(payload, usage)`, 然后通过现有注入点传给 Graph。不要先改节点签名或绕过 Pydantic 结构输出。

## 如果要接 Loki 或 Tempo

分别实现 `LogProvider` 或 `TraceProvider`, 复用现有 Tool Schema 和 Registry。新增 Adapter contract tests, 再在 bootstrap 选择性注入。

## 下一步生产化优先级

1. 持久化 Investigation/Event Repository 和 Evidence Store。
2. 真实 LLM/embedding 与更大的人工评审集。
3. Loki/Tempo Adapter。
4. 鉴权、租户、审计和 secret manager。
5. 分布式 worker、lease 和取消。

下一步: [术语表](14-glossary.md)。
