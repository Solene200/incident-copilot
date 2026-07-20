# IncidentCopilot 总体架构

## 0. 能力状态

| 状态 | 架构边界 |
| --- | --- |
| **Current** | 单 primary service 的结构化 IncidentContext + 自然语言描述；Fixture/Fake 默认链路；内存 RAG；内存 Investigation/Event Repository；Memory 或 PostgreSQL LangGraph checkpointer |
| **Current（窄场景）** | Prometheus metrics Adapter 与 Compose 只验证 payment/database-pool synthetic demo |
| **Experimental** | `PgVectorStore` 参数化 SQL Adapter；未装配到默认 RAG/Compose，未做 live pgvector 集成验收 |
| **Target** | raw-query parser、真实 LLM/Embedding、完整多服务 fan-out、外部 Evidence Store、持久 Investigation/Event Repository、reranker、语义 Context Compression、鉴权与分布式 worker |

后文未特别标注时描述 Current；Experimental/Target 不能作为当前交付声明。

## 1. 架构原则

1. **离线优先**：fixture 模式是完整产品路径，不是绕过业务逻辑的测试捷径。
2. **端口隔离**：Graph 只面向 Provider、Retriever、Model 和 Repository 契约。
3. **证据优先**：LLM 提出与解释假设，事实由带来源的结构化证据承载。
4. **有界自治**：任何循环、工具和模型调用都受显式预算限制。
5. **可恢复**：节点尽量幂等，外部副作用与 checkpoint 边界清晰。
6. **渐进复杂度**：当前只引入能支持验收、测试或替换点的抽象。

## 2. 系统上下文与组件

```mermaid
flowchart LR
    User["用户 / 演示 UI"] --> API["FastAPI API"]
    API --> Service["Investigation Service"]
    Service --> Graph["LangGraph 调查工作流"]
    Graph --> Model["ModelProvider\n当前：Fake"]
    Graph --> Registry["Tool Registry"]
    Registry --> MetricPort["MetricsProvider"]
    Registry --> OtherPorts["Log / Trace / Change / Topology Ports"]
    MetricPort --> PromAdapter["Prometheus HTTP Adapter"]
    OtherPorts --> Fixture["Sanitized Fixture Providers"]
    Graph --> Retriever["Knowledge Retriever"]
    Retriever --> BM25["BM25 Index"]
    Retriever --> Vector["Vector Store Port"]
    Vector --> InMemory["当前：In-memory Fake Vector"]
    Vector -. "Experimental；非默认链路" .-> PGV["PostgreSQL + pgvector"]
    Graph --> Checkpoint["LangGraph Checkpointer"]
    Service --> Repo["Investigation Repository"]
    Repo --> MemoryRepo["当前：In-memory"]
    Checkpoint --> Saver["Memory / PostgreSQL Saver"]
    API --> Stream["SSE Event Stream"]
    Emitter["OTel Demo Metric Emitter"] -->|"OTLP/HTTP"| Collector["OpenTelemetry Collector"]
    Collector -->|"Prometheus exporter"| Prometheus["Prometheus"]
    Prometheus --> PromAdapter
```

### 2.1 组件职责

| 组件 | 职责 | 禁止承担 |
| --- | --- | --- |
| API | HTTP/SSE 协议、校验、错误映射、依赖装配 | 根因推理、直接查询数据源 |
| Investigation Service | 启动/恢复图、管理 thread、读取状态/报告 | Provider 细节、Prompt 拼装 |
| LangGraph | 控制流、State、循环、并行、HITL | 存放无界原始证据 |
| ModelProvider | 结构化模型调用、用量返回、厂商隔离 | 业务路由决定 |
| Tool Registry | 工具发现、策略、超时、统计、错误归一化 | 具体厂商查询语法泄漏到图中 |
| Providers | 把统一查询翻译为数据源操作 | 生成根因结论 |
| Retriever | Query rewrite、混合检索、去重、过滤、引用 | Graph 路由 |
| Repository | 当前进程内保存任务投影和 SSE 事件 | API Schema 或 Prompt 逻辑 |
| Checkpointer | 保存可恢复的执行状态 | 代替业务报告存储 |

## 3. 数据流与控制流

### 3.1 数据流

1. API 校验调用方提供的自然语言描述、单 primary service 和带时区时间窗，生成
   `IncidentContext`、`incident_id` 与 `thread_id`；不从 raw query 推断必填范围。
2. Graph 的 `parse_incident` 校验领域边界并载入可信工具 attempt policy；计划节点产生
   有界 `InvestigationStep`。
3. 调度节点用 `Send` 为本轮查询建立并行任务；各 Tool 只返回结构化 `Evidence`。
4. Provider/Fixture 在工具返回边界持有完整 Evidence，State 仅累积 `EvidenceRef`。当前没有
   外部 Evidence Store 或 object storage 持久化原始 payload。
5. reducer 按稳定 Evidence ID 去重、排序并限制集合大小；模型只接收短摘要。
6. 模型输出经 Pydantic 校验后成为 `Hypothesis`；验证器将双向证据附到假设。
7. 路由器依据充分性与预算进入下一轮或报告节点。
8. 报告、统计和引用写入当前进程内 Repository 投影；checkpoint 可写内存或 PostgreSQL。
   API 返回快照并通过 SSE 发送进度事件，但任务/事件不具备跨进程持久性。

### 3.2 控制流

控制流由 Graph 决定，不由模型自由选择任意代码路径。LLM 可以提出调查步骤和查询意图，但路由器会执行白名单、参数边界和预算校验。完整图见 [`GRAPH_DESIGN.md`](GRAPH_DESIGN.md)。

## 4. 端口与适配器

概念端口保持窄接口；具体签名在实现 Phase 定稿：

| 端口 | 输入 | 输出 |
| --- | --- | --- |
| `LogProvider.search` | 服务、时间范围、模式、limit | 日志类 Evidence 列表 |
| `MetricsProvider.query` | 服务、时间范围、指标/聚合 | 指标类 Evidence 列表 |
| `TraceProvider.query` | 服务、时间范围、过滤条件 | Trace 类 Evidence 列表 |
| `ChangeProvider.recent` | 服务集合、时间范围 | 变更类 Evidence 列表 |
| `TopologyProvider.get` | 服务集合、深度限制 | 拓扑类 Evidence 列表 |
| `HybridRetriever.search` | 查询、top_k、metadata filter | 带 Citation 的检索结果 |
| `ModelProvider.complete` | 白名单任务与受限 `ModelContext` | 不可信 payload + usage；Graph 再校验 |
| `InvestigationRepository` | 任务/Event 对象或 ID | 当前进程内对象 |

所有 Provider 统一接受 `QueryContext`，包含 correlation ID、调用 deadline 和剩余预算；统一抛出可分类异常：`InvalidQuery`、`Unavailable`、`Timeout`、`RateLimited`、`MalformedResponse`。

### 4.1 Current（payment-only）的真实 Metrics 路径

```text
OTel SDK demo emitter
  → OTLP/HTTP receiver
  → OpenTelemetry Collector prometheus exporter
  → Prometheus scrape + /api/v1/query_range
  → PrometheusMetricsProvider
  → query_metrics
  → EvidenceRef / IncidentReport citation
```

`PrometheusMetricsProvider` 只接受现有 `QueryMetricsInput`。领域指标经固定 mapping 生成 PromQL，调用方不能传入任意表达式；Adapter 限制 HTTP timeout、响应字节、序列数量和每序列样本数，并拒绝非有限数值。HTTP 400/422、429、超时、不可用和畸形响应被转换为统一 Provider 异常。

当前混合运行模式只替换 metrics 端口，而且受控 mapping 只为 payment 演示验证
`db.pool.utilization` 与 `http.server.error_rate`。checkout DNS 和 inventory cache 没有等价
live mapping/Compose 证据。日志、Trace、变更和拓扑继续使用 Fixture，知识查询继续使用
本地 RAG。显式选择 Prometheus 后发生失败时，Graph 记录 coverage gap 并继续其他分支，
不会暗中返回 Fixture metrics。

## 5. RAG 架构

### 5.1 写入链路

`DocumentLoader → normalizer → semantic splitter → metadata validator → deterministic/real embedding → vector store + BM25 index`

文档以内容 hash 保证幂等。Chunk 保留 `document_id`、标题、类型、服务、版本、时间、路径/URL、段落定位和父文档引用。

### 5.2 查询链路与状态

- **Current**：`query rewrite → metadata filter → BM25 + in-memory Fake Vector parallel
  search → reciprocal rank fusion → content-hash dedupe → citation-preserving result`。
- **Experimental**：`PgVectorStore` 实现同一 `VectorStore` 端口的参数化 SQL Adapter，但仅有
  recording fake 合同测试，不在默认运行链路。
- **Target**：真实在线 Embedding、Reranker 与语义 Context Compression；当前源码未实现。

Fake Embedding 只验证数据链路与确定性，不代表语义质量。

## 6. 持久化与运行模式

| 模式 | Provider | Model | Vector/DB | 用途 |
| --- | --- | --- | --- | --- |
| `fixture`（默认） | 本地 JSON/JSONL | Fake Model | 内存/本地测试实现 | 单测、演示、CI |
| `docker` | Prometheus metrics + 其余 Fixture | Fake Model | PostgreSQL checkpoint + 内存 RAG | 集成演示、HITL |
| `external` | 可配置 Prometheus endpoint | Fake Model | 外部 PostgreSQL saver | 受限 Adapter 示例 |

当前 PostgreSQL 只由 LangGraph checkpointer 使用。事故任务元数据、幂等键和 SSE 历史仍由 `InMemoryInvestigationRepository` 保存；pgvector Adapter 存在但默认 RAG 没有切到 PostgreSQL。Redis、持久化 Investigation/Event Repository 和外部 Evidence Store 尚未实现。

## 7. 可靠性、预算与降级

### 7.1 预算层级

- 每调查最大研究轮数，当前默认 2。
- 每调查最多 14 个逻辑工具步骤、28 次物理 Provider 尝试；retry 消耗 attempt，
  不重复计算 logical step。
- 每调查最大模型 Token 预算，由 Provider 统一计量。
- 调查总 deadline 与单节点/单工具 timeout。
- 每查询最大时间窗口、服务数、top_k 与返回字节数。

预算值在 Phase 4 用设置项配置并测试，不写死在节点内。路由顺序是：取消/总 deadline → 工具/Token 预算 → 充分性 → 研究轮数。

### 7.2 失败策略

- 参数错误：不重试，记录错误并请求修正计划。
- 超时/限流/临时不可用：确定性指数退避，最多有限重试，且不得越过 deadline；当前没有 jitter。
- 数据格式错误：保留脱敏响应摘要，转换为错误，不把脏数据传给模型。
- 单 Provider 失败：其它并行分支继续；聚合器记录 coverage gap。
- 模型结构输出失败：有限修复重试，失败后使用规则降级或产生“不充分”报告。
- checkpoint 后重放：节点使用确定性 ID 或幂等写，避免重复证据和重复计费统计。

## 8. 安全与隐私边界

- MVP 所有诊断工具只读；不提供命令执行或自动修复工具。
- 服务、环境、时间范围、查询表达式模板、结果量均校验；真实 Adapter 使用最小权限凭据。
- Prompt 不直接拼接未转义工具指令；知识内容视为不可信数据并与系统指令隔离。
- 结构化日志默认脱敏 token、密码、支付字段、个人信息；fixture 不含真实客户数据。
- 原始证据与报告设独立保留策略；API 不默认回传完整原始 payload。
- 人工审核意见同样进行 Schema、长度和命令边界校验。

## 9. 可观测性

每次调查携带 `incident_id`、`thread_id`、`run_id`；每次节点/工具携带 `span_id`。记录：

- 节点开始/结束/路由、时延、重试和错误类别；
- 工具名、经过脱敏的参数摘要、结果数和数据时间范围；
- 模型任务类型、模型 Provider、输入/输出 Token 和校验重试；
- 当前轮次、证据覆盖、预算余额、checkpoint 与 interrupt；
- 不记录 API Key、完整 Prompt、未脱敏原始日志。

OpenTelemetry 与 LangSmith 都是可选 exporter；关闭时核心功能不受影响。

## 10. 技术选型与版本策略

### 10.1 Historical：2026-07-18 规划时版本基线

| 技术 | 规划范围 | 理由 |
| --- | --- | --- |
| Python | `>=3.11,<3.14` | 满足需求并覆盖本机 3.13；先避开生态对 3.14 的潜在滞后 |
| LangGraph | `>=1.2,<1.3` | Graph API 提供 reducer、`Send`、`Command`、interrupt 和 persistence |
| LangChain | `>=1.3,<1.4` | 模型/消息集成；领域与图不依赖其高层 Agent 封装 |
| FastAPI | `>=0.139,<0.140` | Pydantic v2 API 与异步 HTTP/SSE 基础 |
| Pydantic | `>=2.13,<2.14` | 统一领域边界和不可信结构输出校验 |
| SQLAlchemy | `>=2.0,<2.1` | 选择稳定 2.0 线，避开 2.1 预发布线 |
| Psycopg | `>=3.3,<3.4` | PostgreSQL 异步/连接池驱动 |
| PostgreSQL | 18.x | 当前稳定主版本；同时承载关系数据和向量 |
| pgvector | 0.8.x | 支持 PostgreSQL 18 与 HNSW/过滤检索 |

核验依据：PyPI 的 [LangGraph](https://pypi.org/project/langgraph/)、[LangChain](https://pypi.org/project/langchain/)、[FastAPI](https://pypi.org/project/fastapi/)、[Pydantic](https://pypi.org/project/pydantic/)、[SQLAlchemy](https://pypi.org/project/SQLAlchemy/) 与 [Psycopg](https://pypi.org/project/psycopg/) 发布页，以及 PostgreSQL [当前文档](https://www.postgresql.org/docs/) 和 pgvector [changelog](https://github.com/pgvector/pgvector/blob/master/CHANGELOG.md)。

该表是 2026-07-18 的历史选型依据，不代表读者当前环境已验证。Current Python 依赖以
`pyproject.toml` 的兼容范围和 `uv.lock` 的精确解析为准；每次交付通过 `uv lock --check`
重新验证一致性。uv 官方说明见 [项目布局](https://docs.astral.sh/uv/concepts/projects/layout/)
与 [锁定和同步](https://docs.astral.sh/uv/concepts/projects/sync/)。

### 10.2 主要取舍

- 选择 LangGraph Graph API 而非自由工具调用 Agent：调查循环、并行和停止条件更易测试与讲解。
- 选择 Pydantic 领域模型 + TypedDict State：领域不变量与图更新语义分别清晰。
- PostgreSQL Current 只用于可选 LangGraph checkpoint；pgvector 是 Experimental Adapter，
  默认 RAG 仍为内存实现。
- Redis 不是 Current 依赖；只有未来持久事件流或多 worker 协调有实测需要时才评估。
- 不在第一版引入消息队列/Celery：LangGraph persistence 与应用任务层足够支持作品集规模。
- SSE 优于 WebSocket：进度主要是服务端单向发送，协议和演示更简单。

## 11. Current 源码结构

下列目录均存在于当前仓库；未实现的 `migrations/`、reranker、外部 Evidence Store 等不
列入 Current 树：

```text
incident-copilot/
├── AGENTS.md
├── README.md
├── pyproject.toml
├── uv.lock
├── .env.example
├── compose.yaml
├── Makefile
├── src/incident_copilot/
│   ├── main.py
│   ├── api/
│   ├── core/
│   ├── domain/
│   ├── fixtures/
│   ├── graph/
│   ├── investigations/
│   ├── tools/{schemas.py,registry.py,interfaces.py,providers/}
│   ├── rag/
│   └── evaluation/
├── data/{incidents,evaluation,knowledge}/
├── tests/{unit,integration}/
├── scripts/
└── docs/
```

## 12. 架构决策记录候选

后续遇到以下变化时应新增轻量 ADR，而不是悄悄改设计：Graph State/子图共享策略、checkpointer 后端、Redis 是否成为必需、真实 Provider 首选、默认模型策略、向量维度或融合算法变更。
