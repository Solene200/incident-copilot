# 09 `model.py`：模型端口与确定性 Fake

源码：[src/incident_copilot/graph/model.py](../../../src/incident_copilot/graph/model.py)

## `ModelProvider` Protocol

```python
class ModelProvider(Protocol):
    async def complete(self, context: ModelContext) -> ModelResponse:
        ...
```

`Protocol` 是结构化子类型：实现类不必继承它，只要提供同签名 `complete` 就能注入 Graph。输入是裁剪后的 `ModelContext`，输出是 JSON-like payload 和 usage；具体 SDK、模型名和 API Key 不进入 Node。

该模块不直接读写 `InvestigationState`。Node 从 State 构造 Context，调用 Provider，再用 Pydantic Schema 校验输出并把增量写回 State。下一节点也由 Builder/Routing 决定。

后端类比是六边形架构的 outbound port。删除 Protocol 会让 Graph 更容易耦合厂商 SDK；把 Schema 校验放进某一家 Provider 会使不同实现行为不一致。

## `FakeModelProvider.complete`

```python
if context.task is ModelTask.PLAN:
    output = self._plan(context)
elif context.task is ModelTask.HYPOTHESES:
    output = self._hypotheses(context)
elif context.task is ModelTask.JUDGE:
    output = self._judge(context)
else:
    output = self._report(context)
```

任务是枚举白名单，不是任意 prompt。Fake 按 task 生成 Pydantic 输出，随后序列化为不可信 payload，刻意走与真实 Provider 相同的 Node 校验路径。

```python
return ModelResponse(
    payload=payload,
    usage=ModelUsage(
        input_tokens=max(1, len(serialized_context) // 4),
        output_tokens=max(1, len(serialized_output) // 4),
        estimated=True,
    ),
)
```

Token 用字符数近似，必须标记 `estimated=True`。输入来自 Node 的 Context，输出回 `_call_structured`。若把 estimated 改为 false，Evaluation 会虚构精确 Token。

## Plan：只生成有界只读步骤

`_plan` 首轮产生七类工具计划；后续轮调用 `_follow_up_specs`，把 judge 或人工反馈的 `VerificationQuery` 映射为已有 Tool Schema。

```python
queries = (
    feedback.requested_queries
    if feedback is not None and feedback.requested_queries
    else context.next_investigation_queries
)
...
if len(specs) == 20:
    return tuple(specs)
```

人工反馈不能注入任意可执行代码，只能变成来源类型允许的查询，并有 20 步上限。Node 随后还会检查 Registry allow-list、重算 query key。修改这个映射会改变下一轮 pending steps，但不会直接选择下一节点。

## Hypothesis：只引用当前证据摘要

```python
for item in context.evidence_summaries:
    score = item.get("relevance_score", 0.0)
    if isinstance(score, (int, float)) and not isinstance(score, bool) and score >= 0.75:
        relevant.append(item)
supporting_ids = tuple(str(item["evidence_id"]) for item in relevant[:20])
```

Fake 只读取 Context 中高相关 Evidence 摘要，不读 Evaluation ground truth。`bool` 在 Python 是 `int` 子类，所以显式排除，防止 `True` 被当作分数。输出的 Evidence ID 仍由 verify Node 做外键检查。

## Judge 与 Report 草稿

`_judge` 根据来源种类、最小轮数和是否存在假设给出“建议充分性”；Node 还会与 verified hypothesis 条件相交。`_report` 只写叙事、根因草稿、动作和风险，不创建最终 Citation、risk level 或 disposition。

这相当于“模型负责建议，可信代码负责授权与完整性”。若让 `_report` 直接构造 `IncidentReport`，模型会越过 Citation 外键和停止原因规则。

## 九问总结

| 问题 | 答案 |
| --- | --- |
| 做什么 | 定义模型端口和零网络确定性实现 |
| 为什么 | 默认可运行、测试可复现、厂商可替换 |
| 输入 | Node 从 State 裁剪出的 ModelContext |
| 输出 | ModelResponse payload + usage |
| State | 不直接变化；Node 校验后写模型增量 |
| 下一节点 | Provider 不决定；judge 结果只是路由输入 |
| Python | Protocol、async、Enum dispatch、staticmethod、类型收窄 |
| 类比 | AI gateway port + deterministic test double |
| 修改风险 | 读取 ground truth 会造成评估泄漏；自由任务会扩大模型权限 |

下一篇：[ToolRegistry](10-tool-registry.md)。
