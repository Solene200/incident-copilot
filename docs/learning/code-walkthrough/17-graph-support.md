# 17 Graph 装配、Schema 与可视化

本篇覆盖 `graph/bootstrap.py`、`graph/schemas.py`、`graph/visualization.py` 和包导出。Graph Builder、Node、Routing、State、Model 已分别有独立核心精读。

## `graph/bootstrap.py`：组合根

源码：[src/incident_copilot/graph/bootstrap.py](../../../src/incident_copilot/graph/bootstrap.py)

### 离线 Graph

```python
fixture = fixture_provider or FixtureProvider.payment_service()
return build_mixed_investigation_graph(
    metrics_provider=fixture,
    model=model,
    fixture_provider=fixture,
    ...,
)
```

第一行允许测试注入自定义 Fixture，否则加载规范 payment-service 场景。第二步复用 mixed builder，并把同一 Fixture 同时作为指标和其他来源，避免离线/混合两套装配逻辑漂移。

### 混合 Graph

逐行数据流如下：

1. 准备 Fixture 作为日志、Trace、变更和拓扑来源。
2. `build_fixture_retriever(clock=clock)` 加载本地知识文档并建立离线混合索引。
3. `ProviderBundle` 把真实 `metrics_provider` 与其他本地 Provider 组合。
4. `RagKnowledgeProvider(retriever)` 把 RAG 命中转换为统一 Evidence。
5. `build_tool_registry(..., retry_backoff_seconds=0)` 注册七个只读工具；离线测试不真实等待重试退避。
6. `model or FakeModelProvider()` 保证默认无网络。
7. 最终调用 `build_investigation_graph` 编译节点、边和可选 Checkpointer/HITL。

本文件不更新 State，但它决定运行时有哪些数据源、模型和持久化能力。错误地让失败的真实 Prometheus 静默回退 Fixture 会让报告混淆真实与模拟证据，所以 mixed 模式只替换 metrics 端口。

## `graph/schemas.py`：节点交换契约

源码：[src/incident_copilot/graph/schemas.py](../../../src/incident_copilot/graph/schemas.py)

### 稳定查询键

`stable_query_key()` 把 tool name 和 arguments 用排序键、紧凑 JSON 序列化，再算 SHA-256。ID 由可信代码计算而非模型提供，所以同一查询能跨轮次去重。

### 枚举和预算

- `StepStatus`：完成、失败或跳过。
- `ErrorCategory`：Graph 可公开的归一化失败类型。
- `StopReason`：六种明确循环终止原因。
- `InvestigationOptions`：轮数、工具、并行度、模型、Token 和总时间上限。
- `ModelTask`：模型只允许执行计划、假设、判断、报告四类结构化任务。

这些字段进入初始 State 后由代码控制，模型输出不能改预算。

### 计划与步骤

`InvestigationStep` 是单个白名单工具意图；`InvestigationPlan` 是一轮计划。计划 validator 逐步检查所有 step 的 round 与 plan 一致、step ID 唯一、query key 唯一。重复查询因此在进入并行 `Send` 前就被拒绝。

`StepResult` 只记录参数、状态、Evidence ID、错误 ID、次数和时间，不复制完整 Evidence。它要求完成时间不早于开始；失败必须有 error ID；成功不得引用 error。

### 错误、模型用量和结构化输出

`InvestigationError` 是经过脱敏、可放入 State 的错误。`ModelUsage` 明确输入/输出 Token 和是否估算。`ModelResponse.payload` 仍是不可信 dict，Node 会根据 task 再用以下专属模型校验：

- `PlanOutput`：目标、步骤和理由。
- `HypothesesOutput`：至少一个有界 Hypothesis。
- `SufficiencyOutput`：是否充分、理由和下一步查询。
- `ReportDraftOutput`：只有叙事和建议，不允许模型直接创建 Citation。

`ModelContext` 是发送给 Provider 的裁剪输入包；它只包含摘要、假设和人工反馈，不包含原始大 Evidence。`RouteTarget` 限制判断后只能去 refine 或 report；最终实际选择仍在路由函数中完成。

| Schema | 谁写入 | 谁读取 | State 影响 |
| --- | --- | --- | --- |
| InvestigationPlan | plan/refine Node | dispatch | 替换当前计划 |
| StepResult | collect Node | aggregate/Event projector | reducer 追加 |
| InvestigationError | 模型/工具降级路径 | report/Service | reducer 追加 |
| ModelUsage | 每次模型调用 | budget/report | reducer 累加 |
| HumanFeedback | resume API | refine/human review | 受控写入 |

## `graph/visualization.py`

源码：[src/incident_copilot/graph/visualization.py](../../../src/incident_copilot/graph/visualization.py)

`extract_documented_mermaid(path)` 统一换行后定位唯一 Mermaid 围栏，返回其中内容。若文档缺少围栏会立即抛 `ValueError`，不会误判为通过。

`current_mermaid()` 使用内存 saver 和 HITL 构建真实 Graph，然后调用 LangGraph 自带 `draw_mermaid()`。所以 `docs/GRAPH_CURRENT.md` 描述的是编译源码，而非手动画的理想流程。

## `graph/__init__.py`

[`graph/__init__.py`](../../../src/incident_copilot/graph/__init__.py) 重新导出构建函数、Graph 类型、模型端口、核心 Schema、State 和初始状态函数。`__all__` 是稳定教学/API 表面；实际内部 helper 不在其中。导入包不会编译 Graph，只有调用 build 函数才装配依赖。

## 修改风险与测试

- 放宽 `ModelResponse` 并跳过 task Schema 会让 LLM 任意字段进入 State。
- 删除稳定 query key 会重复调用工具并浪费预算。
- 在 bootstrap 中直接读取远程系统会让测试默认访问网络。
- 手写 Mermaid 会与真实边漂移。

对照测试：`tests/unit/graph/`、`tests/integration/test_investigation_graph.py`、`tests/integration/test_graph_mermaid.py`。

下一篇：[RAG 加载与索引](18-rag-ingestion.md)。
