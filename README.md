# IncidentCopilot

IncidentCopilot 是一个面向 AI 应用开发岗位面试与作品集展示的多源可观测性故障诊断项目。当前仓库已完成 Phase 2：在 Phase 1 工程和领域模型之上，提供离线 Fixture Provider、Provider Protocol、七个只读调查工具和统一 Tool Registry。

当前阶段不包含 LangGraph 调查流程、RAG、数据库、真实可观测平台或模型调用。

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

工具输入使用严格 Pydantic Schema；Registry 统一处理 allow-list、deadline、timeout、有限重试、调用预算、错误归一化和结构化日志。所有 fixture 工具测试均离线运行。Phase 3 才会把知识工具接到 Hybrid Search/RAG。

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
