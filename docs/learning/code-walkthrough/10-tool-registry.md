# 10 `registry.py`：工具白名单与执行边界

源码：[src/incident_copilot/tools/registry.py](../../../src/incident_copilot/tools/registry.py)

## `ToolDefinition`

```python
@dataclass(frozen=True, slots=True)
class ToolDefinition(Generic[InputT]):
    name: str
    input_model: type[InputT]
    handler: ToolHandler[InputT]
    expected_sources: frozenset[SourceType]
    timeout_seconds: float = 2.0
    max_retries: int = 1
```

一个定义把名称、Pydantic 输入、异步 handler、允许证据来源和执行策略绑定在一起。`frozen` 防止注册后被改写，`Generic` 保持 input model 与 handler 参数类型一致，`slots` 限制实例字段。

`__post_init__` 校验名称、来源、timeout 和重试上限。删除这些边界可能注册无限超时或无限重试工具。

## 注册与发现

```python
if definition.name in self._tools:
    raise ToolRegistrationError(f"tool already registered: {definition.name}")
self._tools[definition.name] = cast(ToolDefinition[ToolInput], definition)
```

禁止静默覆盖同名工具，避免装配顺序改变真实 Provider。`tool_names` 返回排序 tuple，供 plan Node 建立 allow-list。Registry 本身不直接改变 Graph State；collect Node 将执行结果转为 EvidenceRef/StepResult 增量。

## `execute` 的真实顺序

```text
allow-list
  → 当前调用预算
  → Pydantic 参数
  → 全局 deadline / 单次 timeout
  → Provider handler
  → Evidence 边界校验
  → ToolExecutionResult
```

### 1. 白名单、预算、参数

```python
definition = self._tools.get(name)
if definition is None:
    raise ToolNotFoundError(f"unknown tool: {name}")
if context.remaining_tool_calls < 1:
    raise ToolBudgetExceededError("tool call budget exhausted")
tool_input = definition.input_model.model_validate(arguments)
```

输入来自模型计划但不能被信任。Pydantic 把字典收敛到具体 ToolInput。调查级总计数由 Graph State 管理，Registry 只看当前调用剩余预算。

### 2. deadline、timeout 和 retry

```python
max_attempts = min(definition.max_retries + 1, context.remaining_tool_calls)
while attempts < max_attempts:
    remaining_seconds = (context.deadline - datetime.now(UTC)).total_seconds()
    attempt_timeout = min(definition.timeout_seconds, remaining_seconds)
    evidence = await asyncio.wait_for(
        definition.handler(tool_input, context),
        timeout=attempt_timeout,
    )
```

重试次数也占调用余额；单次 timeout 不能超过全局剩余时间。`asyncio.wait_for` 超时会取消等待。只有 `failure.retryable` 才指数退避，退避也必须装得进 deadline。

若固定等待完整 backoff，调查可能在明知过期时继续睡眠；若所有异常都重试，参数/格式错误会浪费预算。

### 3. 统一错误

Provider timeout、ProviderError 和未知异常分别归一化，最终抛 `ToolExecutionError ... from failure`，保留原因链。collect Node 把它转成失败 Step 和 InvestigationError；兄弟 Send 分支仍可成功。下一节点固定 aggregate。

## `_validate_evidence`

```python
if len(evidence) > result_limit:
    raise ProviderMalformedResponseError(...)
for item in evidence:
    if item.source_type not in definition.expected_sources:
        raise ProviderMalformedResponseError(...)
    if item.service != tool_input.service:
        raise ProviderMalformedResponseError(...)
```

即使对象已是 `Evidence` 也不能默认业务范围正确。后续还检查：

- 必须有时间点或时间窗；
- TimeRange 证据必须与请求窗口相交；
- topology 证据不能晚于 `at_time`；
- similar incident 必须位于 lookback 内；
- 结果数不能超过请求 limit。

输入来自 Provider，输出 tuple 回 collect Node。State 只接收通过检查的 EvidenceRef。删除服务/时间检查会把别的事故证据混入当前报告和 Citation。

## 九问总结

| 问题 | 答案 |
| --- | --- |
| 做什么 | 注册、校验、限时、重试并验证工具结果 |
| 为什么 | Provider 和模型参数都是不可信边界 |
| 输入 | tool name、arguments、QueryContext |
| 输出 | ToolExecutionResult 或归一化 ToolError |
| State | 不直接变；collect Node 写 evidence/step/count/error |
| 下一节点 | Registry 不决定；collect 固定进入 aggregate |
| Python | frozen generic dataclass、Awaitable、cast、异常链 |
| 类比 | API gateway + circuit policy + response contract validator |
| 修改风险 | 取消白名单/范围校验会越权；不受限重试会消耗 deadline |

下一篇：[HybridRetriever](11-hybrid-retrieval.md)。
