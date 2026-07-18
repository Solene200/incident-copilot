# IncidentCopilot

IncidentCopilot 是一个面向 AI 应用开发岗位面试与作品集展示的多源可观测性故障诊断项目。当前仓库已完成 Phase 3：在 Provider/工具层之上，提供离线知识加载、切分、确定性 Fake Embedding、BM25、内存向量检索、pgvector Adapter 和 RRF Hybrid Search。

当前阶段不包含 LangGraph 调查流程、数据库部署、真实可观测平台或模型调用。

## 环境要求

- Python 3.11–3.13
- [uv](https://docs.astral.sh/uv/)

Docker 不是 Phase 1 的运行前提。

## 快速开始

```text
uv sync
uv run uvicorn incident_copilot.main:app --reload
```

服务启动后访问：

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/docs
```

`/health` 不访问数据库、网络或任何付费 API。

## Phase 2 工具

默认 payment-service fixture 位于 `data/incidents/payment-service-pool-exhaustion.json`，包含内部一致的日志、指标、Trace、变更、拓扑、Runbook、历史事故以及 evaluation-only ground truth。可用工具为：

- `search_logs`
- `query_metrics`
- `query_traces`
- `get_service_topology`
- `get_recent_changes`
- `search_runbooks`
- `search_similar_incidents`

工具输入使用严格 Pydantic Schema；Registry 统一处理 allow-list、deadline、timeout、有限重试、调用预算、错误归一化和结构化日志。所有 fixture 工具测试均离线运行；Phase 3 的 `RagKnowledgeProvider` 在不修改工具名的前提下把两个知识工具接到 Hybrid Search。

## Phase 3 RAG

知识库使用带 TOML frontmatter 的 Markdown，当前包含 Runbook、payment-service 服务说明和历史事故。默认链路完全离线：

```text
DocumentLoader → heading-aware splitter → Fake Embedding + BM25
               → in-memory vector search → RRF → content-hash dedupe
```

初始化并验证重复 ingest 的稳定计数：

```text
uv run python scripts/ingest_knowledge.py
```

执行带 query rewrite、metadata filter 和 citation 的检索演示：

```text
uv run python scripts/search_knowledge.py --query "database connection pool timeout" --service payment-service --top-k 3
```

限制到 Runbook：

```text
uv run python scripts/search_knowledge.py --query "连接池超时" --service payment-service --document-type runbook
```

Fake Embedding 只用于验证确定性管线，不代表在线 embedding 的语义质量。`PgVectorStore` 使用参数化 SQL 和显式 `ensure_schema()`，默认测试通过 recording session 验证契约；项目不会在启动时隐式建表，当前机器也未运行真实 PostgreSQL/pgvector 集成测试。

检索结果中的 `score` 是归一化 RRF 排序分数，不是根因概率或置信度。

## 质量检查

```text
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run mypy src tests
uv run pytest
```

## 配置

复制 `.env.example` 为 `.env` 后按需修改。所有环境变量使用 `INCIDENT_COPILOT_` 前缀。模型密钥是可选项，默认运行和测试不需要设置。

## 文档

- [产品需求](docs/PRD.md)
- [总体架构](docs/ARCHITECTURE.md)
- [Graph 设计](docs/GRAPH_DESIGN.md)
- [数据模型](docs/DATA_MODEL.md)
- [路线图](docs/ROADMAP.md)
- [进度](docs/PROGRESS.md)
