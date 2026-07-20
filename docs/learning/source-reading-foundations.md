# 源码阅读基础：先认识常量、类型和数据关系

这一篇不要急着追业务流程。目标是先认识源码反复使用的“积木”：常量、枚举、ID、领域模型、接口、State 字段和 Python 语法。后面看到业务函数时, 你就能把注意力放在控制流上。

## 1. 先区分五种定义

| 写法 | 例子 | 它解决什么问题 |
| --- | --- | --- |
| 模块常量 | `MAX_QUERY_WINDOW = timedelta(hours=24)` | 给整个模块一个统一且可搜索的限制 |
| 枚举 | `class SourceType(StrEnum)` | 把任意字符串缩成有限白名单 |
| 数据模型 | `class Evidence(DomainModel)` | 定义数据有哪些字段以及字段之间的约束 |
| Protocol | `class MetricsProvider(Protocol)` | 只规定组件必须提供哪些方法, 不绑定具体实现 |
| 业务函数/方法 | `collect_evidence_node(...)` | 读取已有对象, 执行流程并产生新结果 |

源码阅读时先判断当前看到的是哪一种。前三种主要回答“系统里有什么”；Protocol 回答“组件如何连接”；最后一种才回答“系统如何运行”。

## 2. 项目最外层常量

### 版本和 ASGI 对象

| 定义 | 位置 | 含义 |
| --- | --- | --- |
| `__version__ = "0.1.0"` | `incident_copilot/__init__.py` | 应用自身版本, health API 和 Settings 默认读取它 |
| `app = create_app()` | `main.py` | Uvicorn 导入的模块级 ASGI 应用对象 |
| `router = APIRouter(...)` | API route 文件 | 收集一组 HTTP 路由, 最后由 `main.py` 注册 |
| `logger = logging.getLogger(__name__)` | 多个模块 | 使用当前模块名创建日志记录器, 不立即写日志 |

`app`、`router` 和 `logger` 虽然名字不是全大写, 但它们也是模块加载后复用的单例对象。导入 `main.py` 会创建 FastAPI app；导入普通领域模块不会连接外部系统。

## 3. 配置枚举和默认值

位置：[src/incident_copilot/core/config.py](../../src/incident_copilot/core/config.py)

### 四组配置枚举

| 枚举 | 可选值 | 中文理解 |
| --- | --- | --- |
| `RuntimeEnvironment` | development/test/staging/production | 当前部署环境 |
| `LogLevel` | DEBUG/INFO/WARNING/ERROR/CRITICAL | 最低日志级别 |
| `CheckpointBackend` | memory/postgres | Graph 快照放内存还是 PostgreSQL |
| `MetricsBackend` | fixture/prometheus | 指标从本地样例还是真实 Prometheus 获取 |

### Settings 默认值

| 字段 | 默认值 | 为什么存在 |
| --- | ---: | --- |
| `api_prefix` | `/api` | 统一 API 路径前缀 |
| `sse_heartbeat_seconds` | `15.0` | SSE 没有新事件时多久发一次心跳 |
| `checkpoint_backend` | memory | 默认无需数据库即可运行 |
| `metrics_backend` | fixture | 默认无需真实可观测性系统 |
| `prometheus_base_url` | `http://127.0.0.1:9090` | 本地 Prometheus 默认地址 |
| `prometheus_timeout_seconds` | `2.0` | 单次 Prometheus 调用上限 |

环境变量统一添加 `INCIDENT_COPILOT_` 前缀。例如 `metrics_backend` 对应 `INCIDENT_COPILOT_METRICS_BACKEND`。`postgres_dsn` 和 `model_api_key` 使用 `SecretStr`, 打印 Settings 时不会显示明文。

## 4. 领域枚举：报告里反复出现的词

位置：[src/incident_copilot/domain/common.py](../../src/incident_copilot/domain/common.py)

### 事故与环境

| 枚举 | 值 | 含义 |
| --- | --- | --- |
| `Severity` | unknown、sev1..sev4 | 故障严重度, sev1 最严重 |
| `Environment` | production、staging、development、unknown | 故障发生环境 |

### 证据来源 `SourceType`

| 值 | 中文含义 | 对应工具 |
| --- | --- | --- |
| `log` | 日志 | `search_logs` |
| `metric` | 数值指标 | `query_metrics` |
| `trace` | 分布式调用链 | `query_traces` |
| `change` | 发布或配置变更 | `get_recent_changes` |
| `topology` | 服务依赖拓扑 | `get_service_topology` |
| `knowledge` | Runbook 或历史故障 | 两个知识搜索工具 |

### 推理与报告状态

| 枚举 | 主要值 | 判断对象 |
| --- | --- | --- |
| `HypothesisStatus` | proposed/investigating/supported/rejected/inconclusive | 一条根因假设目前处于什么阶段 |
| `ReportDisposition` | confirmed/probable/inconclusive | 最终报告对根因有多确定 |
| `RiskLevel` | low/medium/high/critical | 修复建议的操作风险 |

不要把 `HypothesisStatus.SUPPORTED` 理解成已确认事故根因。它只表示某条假设有支持证据；最终报告还要结合反证、充分性和停止原因。

## 5. ID 前缀：看到 ID 就知道对象类型

项目使用正则限制 ID。下面这张表可以当作源码阅读图例。

| 前缀 | 对象 | 示例 |
| --- | --- | --- |
| `inc_` | `IncidentContext` 故障 | `inc_payment_...` |
| `inv_` | API 调查任务 | `inv_` + 32 位十六进制 |
| `thread_` | LangGraph Checkpoint 线程 | 恢复执行时保持不变 |
| `run_` | 一次任务运行 | 新一轮运行的关联 ID |
| `plan_` | 一轮调查计划 | 由计划 Node 产生 |
| `step_` | 单次工具步骤 | 每个 `InvestigationStep` 一个 |
| `ev_` | Evidence | Provider 返回的完整证据 |
| `cit_` | Citation | 证据出处和定位信息 |
| `hyp_` | Hypothesis | 一条可证伪根因假设 |
| `err_` | InvestigationError | Graph State 中的安全错误 |
| `rpt_` | IncidentReport | 最终报告 |
| `evt_` | InvestigationEvent | SSE 可重放事件 |
| `doc_` | KnowledgeDocument | RAG 原始知识文档 |
| `chunk_` | KnowledgeChunk | 文档切分后的小块 |
| `eval_` / `evalrun_` | 评估样例 / 评估运行 | 离线 Evaluation 使用 |

这些前缀不是装饰。Pydantic 会拒绝错误类型的 ID；日志、报告和事件也能仅凭前缀快速识别对象。

## 6. 调查预算与停止常量

位置：[src/incident_copilot/graph/schemas.py](../../src/incident_copilot/graph/schemas.py)

### `InvestigationOptions` 默认预算

| 字段 | 默认值 | 上限作用 |
| --- | ---: | --- |
| `max_research_rounds` | 2 | 最多进行几轮“证据不足 → 再调查” |
| `max_tool_calls` | 14 | 全部逻辑工具步骤总数 |
| `max_tool_attempts` | 28 | 包含 retry 的物理 Provider 尝试总数 |
| `max_parallel_tools` | 7 | 一个批次最多并行多少工具 |
| `max_model_calls` | 20 | 结构化模型调用总数 |
| `max_estimated_tokens` | 20000 | 输入和输出 Token 总预算 |
| `timeout_seconds` | 30 | 整次 Graph 调查 deadline |

### `StopReason`

| 值 | 为什么停止 |
| --- | --- |
| `evidence_sufficient` | 证据已经足够 |
| `max_research_rounds` | 达到调查轮数上限 |
| `tool_budget_exhausted` | 工具预算耗尽 |
| `model_budget_exhausted` | 模型调用预算耗尽 |
| `token_budget_exhausted` | Token 预算耗尽 |
| `deadline_exceeded` | 总时间截止 |

模型不能自由发明停止原因。`routing.py` 只会从这组六个枚举中选择。

### 工具步骤相关枚举

- `StepStatus`：completed、failed、skipped。
- `ErrorCategory`：validation、timeout、unavailable、malformed_response、budget、internal。
- `ModelTask`：plan、hypotheses、judge、report。
- `RouteTarget`：只允许 `refine_investigation` 或 `generate_report`。

`ModelTask` 表示“要求模型返回哪一种结构”；`RouteTarget` 才是 Graph 下一节点。两者不要混在一起。

## 7. 工具和 Provider 的固定限制

位置：[src/incident_copilot/tools/schemas.py](../../src/incident_copilot/tools/schemas.py) · [src/incident_copilot/tools/providers/prometheus.py](../../src/incident_copilot/tools/providers/prometheus.py)

| 常量 | 值 | 作用 |
| --- | ---: | --- |
| `MAX_QUERY_WINDOW` | 24 小时 | 单次日志/指标/Trace/变更查询最大窗口 |
| Tool `limit` | 通常最多 50 | 防止 Provider 返回无界 Evidence |
| `PROVIDER_NAME` | `prometheus-http` | Prometheus Evidence 和错误的稳定来源名 |
| `MAX_RESPONSE_BYTES` | 1,000,000 | Prometheus HTTP body 最大 1 MB |
| `MAX_POINTS_PER_SERIES` | 240 | 单条指标序列最多采样点 |

### Prometheus 指标白名单

| 领域指标名 | Prometheus 指标 | 单位 | 聚合 |
| --- | --- | --- | --- |
| `db.pool.utilization` | `incident_demo_db_pool_utilization_ratio` | ratio | avg/max/min/p95 |
| `http.server.error_rate` | `incident_demo_http_server_error_rate_ratio` | ratio | avg/max/rate |

Graph 和模型只能请求左侧领域指标名，Adapter 再转换成右侧 Prometheus 指标。这样模型不能直接生成任意 PromQL。

### Provider 错误类别

`ProviderErrorCategory` 包含 invalid_query、timeout、unavailable、rate_limited、malformed_response 和 internal。只有 timeout、unavailable、rate_limited 默认可重试；参数错误和错误响应重复执行通常不会变好。

## 8. RAG 常量和检索参数

位置：`rag/loader.py`、`rag/splitter.py`、`rag/retrieval.py`

| 定义 | 默认值 | 含义 |
| --- | ---: | --- |
| `FRONTMATTER_DELIMITER` | `+++` | 知识 Markdown 的 TOML metadata 边界 |
| `MAX_KNOWLEDGE_FILE_BYTES` | 1,000,000 | 单份知识文件最大尺寸 |
| `MarkdownSplitter.max_tokens` | 120 | 离线组合根中的 Chunk 最大近似 Token 数 |
| `MarkdownSplitter.overlap_tokens` | 20 | 相邻 Chunk 重叠大小 |
| `FakeEmbedding.dimension` | 64 | 离线假向量维度 |
| `BM25Index.k1` | 1.5 | 词频饱和参数 |
| `BM25Index.b` | 0.75 | 文档长度归一化参数 |
| `HybridRetriever.rrf_k` | 60 | RRF 排名融合平滑常数 |
| `candidate_multiplier` | 4 | 融合前每路候选池放大倍数 |

`SEARCH_TOKEN_PATTERN` 同时识别英文技术标识和单个中文字符；`HEADING_PATTERN` 识别一到六级 Markdown 标题。它们决定“如何切分和检索文本”，不是业务故障规则。

QueryRewriter 的别名表是经过审核的确定性等价映射。例如“连接池”只扩展为 `connection pool`。原始词始终保留，不使用在线模型改写，也不追加 payment、database acquisition 等未经原查询表达的场景词。

## 9. 其他模块级常量和类型别名

| 定义 | 位置 | 含义 |
| --- | --- | --- |
| `REDACTED = "***REDACTED***"` | `core/logging.py` | 日志发现密钥或 Token 后使用的统一替换文本 |
| `_SENSITIVE_KEYS` | `core/logging.py` | api_key、password、secret、token 等敏感键白名单 |
| `OTEL_ENABLED_ENV` | `core/telemetry.py` | 控制可选 OpenTelemetry 的环境变量名 |
| `FENCE_START` / `FENCE_END` | `graph/visualization.py` | 从 Markdown 中定位 Mermaid 代码块的边界 |
| `FAILURE_TYPE_PATTERNS` | `evaluation/evaluators.py` | 离线故障类型分类使用的透明关键词表 |
| `ROOT_CAUSE_ACCURACY_THRESHOLD` | `evaluation/runner.py` | 根因关键词召回率达到 `0.75` 才记为准确 |
| `ReportStatus` | `graph/schemas.py` | 只允许 complete 或 limited 的类型别名 |

以下写法看起来像常量, 实际主要服务静态类型检查：

- `InvestigationGraph`：编译后 Graph 的复杂泛型类型别名。
- `Clock`：返回 `datetime` 的可注入时钟函数类型。
- `ToolHandler`：工具异步处理器的统一 Callable 类型。
- `ParamT`、`ReturnT`、`ItemT`、`OutputT`：让装饰器、Reducer 和结构化模型 helper 保留输入输出类型的 `TypeVar/ParamSpec`。

名字以下划线开头, 例如 `_SENSITIVE_KEYS`，表示模块内部实现细节；普通调用方不应把它当稳定公共 API。

## 10. 任务状态和事件名称

位置：[src/incident_copilot/investigations/models.py](../../src/incident_copilot/investigations/models.py)

### `InvestigationStatus`

```text
pending → running → waiting_review → completed
                  └──────────────→ failed
```

- `pending`：任务已创建, 后台 Graph 尚未开始。
- `running`：Graph 正在执行。
- `waiting_review`：Graph 在 HITL interrupt 暂停。
- `completed`：报告已完成并通过需要的人工确认。
- `failed`：任务执行失败。

这是 API 任务状态；Graph 内部是否到某个 Node 由 Checkpoint 的执行位置描述。

### `EventType`

SSE 事件分为四组：任务级 queued/started/failed；节点和工具级 completed/failed；数据级 evidence/hypothesis/budget updated；终点级 review required/report completed。每条事件有严格递增 `sequence`，客户端才能从 `Last-Event-ID` 继续读取。

## 11. 先认识核心数据模型

### 调查主链路

```text
CreateInvestigationRequest
    ↓ to_incident
IncidentContext
    ↓ plan Node
InvestigationPlan → InvestigationStep
    ↓ collect Node + ToolRegistry
Evidence → EvidenceRef + StepResult
    ↓ hypothesis / verify Node
Hypothesis + VerificationQuery
    ↓ judge / route
StopReason 或下一轮计划
    ↓ report Node
IncidentReport
    ↓ Service 投影
InvestigationRecord + InvestigationEvent
```

### 为什么 Evidence 有两个版本

| 类型 | 保存什么 | 放在哪里 |
| --- | --- | --- |
| `Evidence` | 原始 content、metadata、摘要、Citation | Provider/Tool 边界 |
| `EvidenceRef` | ID、摘要、评分、时间和 Citation | Graph State 与报告 |

State 不存原始大对象，避免 Checkpoint 不断膨胀。Citation 始终保留，因此最终报告仍能定位来源。

### 为什么模型输出还有一层 Schema

`ModelResponse.payload` 只是未可信 dict。Node 会按 `ModelTask` 再校验为 `PlanOutput`、`HypothesesOutput`、`SufficiencyOutput` 或 `ReportDraftOutput`。模型报告草稿不能直接提供 Citation；引用由代码从已验证 EvidenceRef 附加。

## 12. Protocol、Adapter、Provider、Tool 的关系

```text
Protocol（规定方法签名）
    ↑
Provider / Adapter（真正读取 Fixture、Prometheus 或 RAG）
    ↑
ToolDefinition（绑定工具名、参数 Schema、来源白名单、超时重试）
    ↑
ToolRegistry（统一执行安全策略）
    ↑
Graph collect Node（只按计划调用工具）
```

以指标为例：

- `MetricsProvider`：只规定 `query(...) -> Sequence[Evidence]`。
- `FixtureProvider`：离线实现。
- `PrometheusMetricsProvider`：真实 HTTP 实现。
- `query_metrics`：Graph 看到的稳定工具名。
- `ToolRegistry`：验证参数、预算、超时、重试和 Evidence 来源。

替换数据源时改 Adapter 装配，不改 Graph Node。

## 13. State 字段先分组再记

位置：[src/incident_copilot/graph/state.py](../../src/incident_copilot/graph/state.py)

| 分组 | 字段 |
| --- | --- |
| 输入 | `incident` |
| 当前计划 | `investigation_plan`, `pending_steps`, `current_step` |
| 并行产物 | `completed_steps`, `evidence`, `errors` |
| 推理 | `hypotheses`, `evidence_sufficient`, `sufficiency_reason`, `next_investigation_queries` |
| 轮数和预算 | `research_round`, 各种 max 字段、调用计数、`model_usage` |
| 时间 | `started_at`, `deadline_at`, `deadline_exceeded` |
| 终点 | `stop_reason`, `final_report` |
| HITL | `human_feedback`, `review_completed` |

### 哪些字段有 Reducer

- `completed_steps` → `merge_step_results`
- `evidence` → `merge_evidence`
- `errors` → `merge_errors`
- 调用计数 → `add_count`
- `model_usage` → `add_usage`

有 Reducer 的并行节点应返回“本分支增量”；没有 Reducer 的字段采用覆盖语义。理解这一点后再读 `collect_evidence_node`，就不会疑惑为什么计数返回 `1` 而不是总数。

## 14. 常见 Python/Pydantic 写法

| 写法 | 先这样理解 |
| --- | --- |
| `tuple[str, ...]` | 任意长度、元素都是 str 的不可变序列 |
| `X | None` | 这个值可以不存在 |
| `Annotated[T, reducer]` | T 类型 State 通道额外绑定合并函数 |
| `Protocol` | 只要方法签名相同就算实现该接口 |
| `@dataclass(frozen=True, slots=True)` | 小型、不可变、字段固定的数据对象 |
| `Field(ge=1, le=50)` | Pydantic 运行时数值边界 |
| `@field_validator` | 校验或规范一个字段 |
| `@model_validator(mode="after")` | 字段解析后检查多个字段关系 |
| `model_copy(update={...})` | 从冻结模型复制一个修改后的新对象 |
| `async def` / `await` | 协程在 I/O 等待时把控制权交还事件循环 |
| `asyncio.to_thread` | 把阻塞同步函数移出事件循环线程 |
| `asynccontextmanager` | `yield` 前启动资源, `yield` 后释放资源 |
| `raise NewError(...) from exc` | 转换异常类型但保留原始原因链 |

## 15. 推荐的“定义优先”源码顺序

第一轮只读定义：

```text
domain/common.py
→ domain/evidence.py、incident.py、hypothesis.py、report.py
→ graph/schemas.py、state.py
→ tools/interfaces.py、schemas.py、exceptions.py
→ rag/schemas.py
→ investigations/models.py
```

第二轮读数据如何被取得和处理：

```text
rag loader/splitter/vector/retrieval
→ Fixture/Prometheus Provider
→ builtin tools
→ ToolRegistry
```

第三轮才读主业务控制流：

```text
ModelProvider
→ Graph Nodes
→ Routing
→ Builder
→ Checkpoint
→ InvestigationService
→ API routes
→ main.py
```

第四轮读验证系统：

```text
evaluation schemas/evaluators
→ OfflineEvaluationRunner
```

完成本篇后, 继续阅读后面的源码精读时先查看每章“职责”和“输入输出”，再进入代码块。遇到陌生类型可以回到本篇对应表格，而不需要在业务函数中猜它的含义。
