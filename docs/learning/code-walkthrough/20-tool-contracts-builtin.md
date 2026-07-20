# 20 Tool 接口、Schema、异常与内置工具

本篇覆盖 Tool Registry 周围的全部辅助源码。Registry 自身见 [10 ToolRegistry](10-tool-registry.md)。

## `tools/interfaces.py`：Provider 端口

源码：[src/incident_copilot/tools/interfaces.py](../../../src/incident_copilot/tools/interfaces.py)

六个 `@runtime_checkable Protocol` 分别描述日志、指标、Trace、变更、拓扑和知识查询。每个方法都接收“特定查询 Schema + QueryContext”，异步返回 `Sequence[Evidence]`。

逐个映射：

| Protocol | 方法 | Tool |
| --- | --- | --- |
| `LogProvider` | `search` | `search_logs` |
| `MetricsProvider` | `query` | `query_metrics` |
| `TraceProvider` | `query` | `query_traces` |
| `ChangeProvider` | `recent` | `get_recent_changes` |
| `TopologyProvider` | `get` | `get_service_topology` |
| `KnowledgeProvider` | 两个 search | runbook / similar incident |

Protocol 使用结构类型：实现类无需继承，只要签名兼容。`runtime_checkable` 允许必要时 `isinstance(provider, MetricsProvider)`，但主要价值仍是 mypy 静态约束。

## `tools/schemas.py`：调用边界

源码：[src/incident_copilot/tools/schemas.py](../../../src/incident_copilot/tools/schemas.py)

`QueryContext` 由 Graph 创建，提供 correlation ID、绝对 deadline 和剩余调用数，不暴露完整 State。

`ToolInput` 统一规范化必填 service；注释中的 pragma 分支理论上被 Pydantic 必填约束挡住，仍保留防御。`TimeRangeToolInput` 在此基础上加入起止时间和 limit，最终 validator 要求正向窗口且不超过 24 小时。

七类参数再添加各自白名单：

- logs：可选文本 query。
- metrics：受正则限制的指标名和五种 aggregation。
- traces：可选 operation 与三种 status。
- topology：时间点、深度 1..3、结果上限。
- changes：四种 change type。
- runbooks：查询文本与较小 limit。
- similar incidents：截止时间、1..365 天回溯。

`ToolExecutionResult` 是 Registry 的统一成功返回，包含工具名、最多 50 条完整 Evidence、真实 attempts 和 duration。

## `tools/exceptions.py`：双层失败

源码：[src/incident_copilot/tools/exceptions.py](../../../src/incident_copilot/tools/exceptions.py)

Provider 层的 `ProviderErrorCategory` 区分非法查询、超时、不可用、限流、错误响应和内部错误。每个 ProviderError 保存安全 message、provider name 和 operation；timeout/unavailable/rate-limited 子类把 `retryable=True`。

Tool 层再定义注册冲突、未知工具、参数错误、预算耗尽和执行失败。`ToolExecutionError` 把具体 Provider 异常规范成 tool name、category、attempts 和 retryable，Graph 不需要依赖具体 Adapter 异常类。

不要把所有失败都设为可重试：非法参数和 malformed response 重试不会改变结果，只会浪费预算。

## `tools/builtin.py`：七个工具的装配

源码：[src/incident_copilot/tools/builtin.py](../../../src/incident_copilot/tools/builtin.py)

`ProviderBundle` 是冻结 slots dataclass，六个字段显式列出全部依赖。与 `dict[str, Any]` 相比，缺少 Provider 会在构造阶段暴露。

`build_tool_registry()` 先创建 Registry，再定义七个薄异步函数。例如：

```python
async def query_metrics(query, context):
    return await providers.metrics.query(query, context)
```

这层没有业务逻辑，只把统一工具名称桥接到各 Provider 方法。随后每次 `register(ToolDefinition(...))` 按固定顺序提供：工具名、参数 Pydantic 模型、handler、允许的 Evidence source type、timeout、max retries。

来源白名单很重要：即使 MetricsProvider 错误返回 LOG Evidence，Registry 也会拒绝。七个工具共享 Registry 的参数校验、预算、超时、重试、日志和 Evidence 校验，不在每个 wrapper 重复实现。

## `tools/__init__.py` 与 providers 包

[`tools/__init__.py`](../../../src/incident_copilot/tools/__init__.py) 只重新导出 `ProviderBundle`、Registry 相关类型和 `build_tool_registry`。[`tools/providers/__init__.py`](../../../src/incident_copilot/tools/providers/__init__.py) 重新导出 Fixture 与 Prometheus Provider。两者都不实例化远程客户端，实际选择发生在组合根。

## State、下一节点和类比

Provider/Tool Schema 本身不写 State。collect Node 从计划取 arguments，Registry 成功后才把 EvidenceRef 和 StepResult 作为增量返回；下一节点由 Graph barrier/edge 决定，不由 Provider 决定。

后端类比是 Ports and Adapters + Command Bus：Protocol 是端口，Provider 是 Adapter，ToolDefinition 是受控 command handler 描述，Registry 是总线和策略边界。

## 对照测试

- `tests/unit/tools/test_registry.py`
- `tests/integration/test_fixture_tools.py`
- `tests/integration/test_investigation_graph.py`

下一篇：[真实与 Fixture Provider](21-tool-providers.md)。
