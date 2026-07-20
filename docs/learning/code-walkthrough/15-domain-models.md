# 15 全部领域模型源码

本篇覆盖 `domain/` 的公共类型、Incident、Evidence、Hypothesis、Report、人工审核和包导出。领域层不导入 FastAPI、LangGraph、数据库或具体 Provider。

## `domain/common.py`：共同不变量

源码：[src/incident_copilot/domain/common.py](../../../src/incident_copilot/domain/common.py)

### 时区与严格基类

```python
def require_timezone(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(...)
    return value

AwareDatetime = Annotated[datetime, AfterValidator(require_timezone)]
```

第一行检查是否声明时区，第二个条件还防止无有效 UTC offset 的伪时区对象。`Annotated` 把校验器绑定到类型，之后所有模型复用 `AwareDatetime` 就自动执行同一规则。

`DomainModel` 的三个配置逐行含义：`extra="forbid"` 拒绝未知字段；`frozen=True` 防止创建后原地修改；`str_strip_whitespace=True` 自动清理字段首尾空格。冻结值对象使并行 Graph 分支不会共享可变领域实体。

六组 `StrEnum` 统一严重度、环境、来源、假设状态、报告确定度和修复风险。它们是跨 Graph、Tool、API 的领域词汇表。

### 三个规范化函数

- `normalize_services`：逐项 `strip().lower()`；检查长度和允许字符；用 `seen` 去重但保留输入顺序；返回不可变 tuple。
- `normalize_optional_service`：把 `None` 原样返回，否则复用单元素服务校验。
- `unique_non_empty`：用于普通字符串集合，只去首尾空格、拒绝空值、稳定去重。
- `unique_evidence_ids`：先复用普通集合规则，再用完整正则验证 `ev_...` 格式。

如果直接用 `set(values)`，顺序会丢失，报告和测试输出将不稳定。

## `domain/incident.py`：调查边界

源码：[src/incident_copilot/domain/incident.py](../../../src/incident_copilot/domain/incident.py)

`IncidentContext` 的字段按职责分为：唯一 ID；原始用户问题；服务和时间范围；症状/严重度/环境；创建时间和时区假设。字段校验先规范化 services/symptoms，模型校验最后保证 `start_time < end_time`。

它是 Graph State 的只读输入之一。修改时间窗口会改变所有工具查询；删除 `raw_query` 会让计划和模型上下文失去原始意图。

## `domain/evidence.py`：Evidence 与 Citation

源码：[src/incident_copilot/domain/evidence.py](../../../src/incident_copilot/domain/evidence.py)

### `Citation`

字段从“身份”到“定位”依次是 citation ID、URI、locator、展示名、抓取时间和内容哈希。`validate_uri()` 逐层防御：只允许四种 scheme；拒绝 URL 用户名/密码；HTTP 必须有 host；内部 URI 也必须有实际位置。

### `Evidence`

完整 Evidence 包含原始 `content`、摘要、单点或区间时间、服务、相关性/可靠性、metadata、Citation 和哈希。`validate_time_range()` 按顺序确保：

1. 起止时间必须成对出现。
2. 起点严格早于终点。
3. Citation 的内容哈希必须与 Evidence 相同。

第三条把“证据内容”和“证据出处”绑定起来，防止报告引用另一份内容。

### `EvidenceRef`

它删除了完整 content 和任意 metadata，只保留 State/报告真正需要的摘要和引用。`from_evidence()` 显式逐字段复制，而不是 `model_dump` 后全量透传，因此 Evidence 新增大字段时不会自动膨胀 State。

| 对比 | Evidence | EvidenceRef |
| --- | --- | --- |
| 位置 | Provider/工具边界 | Graph State 与报告 |
| 原始 content | 有 | 无 |
| metadata | 有 | 无 |
| Citation | 有 | 有 |

## `domain/hypothesis.py`：可证伪假设

源码：[src/incident_copilot/domain/hypothesis.py](../../../src/incident_copilot/domain/hypothesis.py)

`VerificationQuery` 描述“查什么来源、针对哪个服务”，不包含厂商查询语言。来源 tuple 通过 `dict.fromkeys` 稳定去重。

`Hypothesis` 把陈述、影响服务、支持/反对 Evidence ID、置信度、状态、下一步查询、推理摘要和版本放在一起。最终模型校验先求支持与反对集合交集，再要求 `SUPPORTED` 状态至少有一条支持证据。这样模型不能只输出高置信文字而不给证据。

Graph 的 `generate_hypotheses`/`verify_hypotheses` 会更新这些对象；路由代码只读取验证后的结果。

## `domain/report.py`：可审计输出

源码：[src/incident_copilot/domain/report.py](../../../src/incident_copilot/domain/report.py)

辅助值对象按报告顺序排列：

- `TimelineEvent`：时间、描述和 Evidence ID。
- `RejectedHypothesis`：被排除的假设、原因和证据。
- `RemediationStep`：建议、优先级、风险、验证和回滚；它只是数据，不是可执行命令。
- `InvestigationStats`：真实轮数、调用数、Token、时间、来源计数和停止原因。

`InvestigationStats.evidence_count_by_source` 使用 `MappingProxyType` 防止字典被原地修改；自定义 serializer 在输出 JSON 时再转回普通 dict。`validate_totals()` 检查 Token 加法、工具结果不超过调用数、完成时间顺序以及完成时间/耗时必须同时出现。

`IncidentReport` 的模型级校验逐条执行：

1. 非 `INCONCLUSIVE` 报告必须有 root cause。
2. Timeline 必须已经按时间排序，模型不会在校验器里偷偷重排。
3. 支持与反对 EvidenceRef 合并后 ID 不得重复。
4. Citation ID 不得重复。

报告由 Graph `generate_report` 写入 State；最终节点只能引用已收集 EvidenceRef。删掉一致性校验会允许“确认根因但无根因文本”或重复引用进入 API。

## `domain/review.py`：HITL 白名单

源码：[src/incident_copilot/domain/review.py](../../../src/incident_copilot/domain/review.py)

`ReviewAction` 只允许接受或追加研究。`HumanFeedback.validate_action_payload()` 把 action 与 payload 绑定：接受时禁止查询；追加研究时至少需要一条查询。调用方不能提交任意 Graph 节点名或 Command。

`HumanReviewRequest` 是暂停时公开的小载荷：报告 ID、原因、高风险动作和允许决策。`high_risk_actions` 至少一项，说明系统不会对无风险报告无故中断。

## `domain/__init__.py`：公共门面

[`domain/__init__.py`](../../../src/incident_copilot/domain/__init__.py) 从各子模块导入稳定类型，再用 `__all__` 声明 `from incident_copilot.domain import *` 的公开集合。它没有包含 HumanFeedback/ReviewAction，因此审核模块当前要求显式导入。删除 `__all__` 不会破坏显式导入，但会让包的公共边界不清晰。

## 阅读卡片

| 问题 | 答案 |
| --- | --- |
| 输入 | API、Provider、模型结构化输出和代码生成值 |
| 输出 | 冻结、已校验的领域对象 |
| State | Incident、EvidenceRef、Hypothesis、Report 等会进入 State；模型本身不知道 Reducer |
| 下一节点 | 领域模型不路由；`routing.py` 读取其状态后决定 |
| Python 重点 | `Annotated`、`StrEnum`、Pydantic validator、冻结模型、`MappingProxyType` |
| 后端类比 | DDD Value Object 与 Aggregate 内部不变量 |
| 修改风险 | 放宽字段或删除交叉校验会把不一致数据传播到 Graph、API 和 Evaluation |

## 对照测试

- `tests/unit/domain/`
- `tests/unit/fixtures/test_schemas.py`
- `tests/integration/test_investigation_graph.py`

下一篇：[任务、Repository 与 Fixture](16-investigation-storage-fixtures.md)。
