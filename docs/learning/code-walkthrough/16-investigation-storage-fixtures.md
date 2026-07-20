# 16 任务模型、Repository 与 Fixture

本篇解释 Graph State 之外的任务元数据、SSE 事件存储和离线事故样例。Checkpoint 已在 [04 Checkpoint](04-checkpoint.md) 中讲解。

## `investigations/models.py`

源码：[src/incident_copilot/investigations/models.py](../../../src/incident_copilot/investigations/models.py)

### 两组状态不要混淆

`InvestigationStatus` 是 API 任务生命周期：`PENDING → RUNNING → WAITING_REVIEW/COMPLETED/FAILED`。它不是 Graph 节点，也不保存在 `InvestigationState` 中。

`EventType` 是公开 SSE 事件白名单。它从排队、启动、节点/工具完成、证据/假设/预算更新，一直到审核、报告或失败。使用枚举让前端可以按稳定机器值分支。

### `InvestigationRecord`

字段按源码顺序理解：

| 字段组 | 来源与用途 |
| --- | --- |
| `investigation_id` | API 任务 ID，由 Service 生成 |
| `incident_id`, `thread_id`, `run_id` | 分别关联事故、Checkpoint 线程和一次运行 |
| `status` | 当前公开生命周期状态 |
| `incident`, `options` | 重新执行所需的规范输入和预算 |
| `request_fingerprint`, `idempotency_key` | 幂等创建判断 |
| `report`, `review_request`, `error_message` | 三种终态/暂停投影 |
| `created_at`, `updated_at`, `version` | 审计时间和乐观锁版本 |

它刻意不包含完整 State。把 State 再复制到 Record 会制造两个真相来源，并可能让大证据对象进入业务表。

### `InvestigationEvent`

`event_id` 同时编码随机任务前缀和 sequence；`sequence >= 1` 保证客户端能用 `Last-Event-ID` 重放。事件携带四个关联 ID 和小型 `data`，不携带 checkpoint 原始值。

## `investigations/repository.py`

源码：[src/incident_copilot/investigations/repository.py](../../../src/incident_copilot/investigations/repository.py)

### Protocol 端口

`InvestigationRepository` 只规定 create/get/update、追加/列出/等待事件。所有方法异步，因此当前内存实现可以替换为数据库而不修改 Service 调用方式。`...` 表示 Protocol 只声明签名。

### 内存 Adapter 的四张表

```python
self._records: dict[str, InvestigationRecord] = {}
self._idempotency: dict[str, str] = {}
self._events: dict[str, list[InvestigationEvent]] = {}
self._condition = asyncio.Condition()
```

前三项分别保存任务、幂等键到任务 ID 的映射、仅追加事件；Condition 同时充当互斥锁和新事件通知机制。

### `create` 逐步执行

1. `async with self._condition` 保证检查和写入是同一临界区。
2. 有幂等键时查 `_idempotency`。
3. 找到旧任务后比较 request fingerprint；不同请求复用同一键返回 409。
4. 相同请求返回旧 Record 和 `False`，Service 不会重复启动 Graph。
5. 新请求写入 record、空事件列表和可选幂等映射。
6. `notify_all()` 唤醒可能等待资源的协程。
7. 返回 `(record, True)`。

### 乐观更新与事件单调性

`update()` 同时要求数据库当前版本等于 `expected_version`，新对象版本等于 `expected_version + 1`。两个条件缺一不可：前者发现并发写，后者发现调用方忘记递增。

`append_event()` 计算 `len(events) + 1`，拒绝跳号或重复 sequence。`list_events()` 返回 tuple 快照，防止调用方修改内部 list。

### 长轮询 `wait_for_events`

内部 `available()` 闭包读取目标事件长度。`Condition.wait_for` 会释放锁等待，收到通知后重新获取锁并再次检查谓词；`asyncio.wait_for` 再加超时上限。超时返回空 tuple，不当作系统错误。SSE 层据此发送 heartbeat。

| 阅读问题 | 答案 |
| --- | --- |
| State | Repository 不保存 Graph State；State 由 Checkpointer 负责 |
| 输入/输出 | Service 提交 Record/Event，API 获取稳定快照 |
| Python 重点 | Protocol、Condition、闭包、乐观锁 |
| 类比 | 任务表 + append-only outbox/event log |
| 修改风险 | 去掉 Condition 会产生重复 sequence；把超时当异常会频繁断开 SSE |

## `fixtures/schemas.py`

源码：[src/incident_copilot/fixtures/schemas.py](../../../src/incident_copilot/fixtures/schemas.py)

`FixtureGroundTruth` 保存已知根因、服务和证据 ID，只供 Evaluation 使用。字段 validator 复用领域服务与 Evidence ID 规则。

`IncidentFixture` 固定 `schema_version="1.0"` 和 `contains_sensitive_data=False`，后者使用 `Literal[False]`，意味着包含敏感数据的文件根本无法通过模型校验。它组合 Incident、最多 1000 条 Evidence、可选 ground truth 和标签。

最终校验先检查 Evidence ID 全局唯一，再验证 ground truth 引用的 Evidence 全部存在。这样评估标签不会指向不存在的数据。

## 初始化文件

[`investigations/__init__.py`](../../../src/incident_copilot/investigations/__init__.py) 只有包说明；[`fixtures/__init__.py`](../../../src/incident_copilot/fixtures/__init__.py) 重新导出 `FixtureGroundTruth` 和 `IncidentFixture`，`__all__` 明确公共集合。它们都不创建 Repository 或加载文件，导入包没有 I/O 副作用。

## 对照测试

- `tests/unit/investigations/test_checkpoint.py`
- `tests/integration/test_investigation_service.py`
- `tests/unit/fixtures/test_schemas.py`
- `tests/integration/test_investigation_api_phase5.py`

下一篇：[Graph 辅助模块](17-graph-support.md)。
