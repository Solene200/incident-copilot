# IncidentCopilot 实施进度

## 当前状态

| 项目 | 值 |
| --- | --- |
| 当前已完成阶段 | Phase 3 |
| 下一阶段 | Phase 4（等待用户明确确认） |
| 最近更新 | 2026-07-18 |
| 仓库初始状态 | 空目录，无 `.git` 元数据 |
| 当前运行环境 | Windows / PowerShell；Python 3.13 可用 |

## Phase 0 — 需求、架构和项目规范

### 状态

`completed`

### 完成内容

- 将原始设想整理为产品目标、角色、场景、功能/非功能需求和明确范围边界。
- 定义离线 fixture、Docker 集成、外部数据源三种运行模式。
- 定义 API、Investigation Service、LangGraph、Model、Tool/Provider、RAG、Repository 和 Checkpointer 的职责边界。
- 设计动态并行取证、证据聚合、假设验证、研究循环、预算路由、报告与 HITL 主图。
- 明确 State 的覆盖/reducer 字段、原始证据外置、有界上下文和父图/子图策略。
- 定义 Incident、Evidence、Hypothesis、Report 及计划、引用、错误、知识 Chunk 的字段与不变量。
- 核验 2026-07-18 的主要依赖发布线，确定“兼容范围 + uv 锁文件 + Phase 1 实测”的版本策略。
- 为 Phase 1–7 定义输入条件、产出、关键测试和完成定义。

### 新增文件

- `AGENTS.md`
- `docs/PRD.md`
- `docs/ARCHITECTURE.md`
- `docs/GRAPH_DESIGN.md`
- `docs/DATA_MODEL.md`
- `docs/ROADMAP.md`
- `docs/PROGRESS.md`

### 实际检查结果

| 检查 | 结果 |
| --- | --- |
| 必需文件与非空检查 | PASS：7/7 文件存在且非空 |
| Markdown 标题/尾随空白/Tab 检查 | PASS：7 个 Markdown 文件，0 项失败 |
| 相对 Markdown 链接目标检查 | PASS：0 个断链 |
| Mermaid fence 配对与必需图检查 | PASS：架构图 1、Graph 图 1，0 个未闭合 fence |
| 必需主题与 Phase 状态一致性检查 | PASS：0 项失败 |
| 敏感信息模式扫描 | PASS：未发现疑似硬编码密钥 |
| Phase 1 文件越界检查 | PASS：未发现业务代码、依赖或容器文件 |
| Ruff / mypy / pytest | 不适用：Phase 0 没有 Python 项目或业务代码 |

检查由 PowerShell 只读脚本完成，脚本遍历全部 Markdown，检查 H1、空白、相对链接、Mermaid fence、必需主题、路线图状态、敏感模式和越界路径。两次检查的终端摘要分别为 `PHASE_0_DOC_CHECKS=PASS` 与 `PHASE_0_CONSISTENCY=PASS`。

### 环境事实

- 2026-07-18 已通过 winget 安装并验证 Git 2.55.0、uv 0.11.29、Docker Desktop 4.82.0 和 Microsoft WSL 2.7.10。
- 当前 Python 为 3.13.0；uv 能定位到 `D:\mysoftwares\python\python3.13\python.exe`。
- Docker CLI 29.6.1 与 Docker Compose 5.3.0 可执行，当前用户已加入 `docker-users`。
- Docker Desktop 服务尚未首次启动；首次运行可能要求完成界面初始化或重启 Windows，不能据此声称 Docker daemon 已就绪。
- 当前 Codex 进程在安装前启动，因此可能需要新开终端后才会通过短命令解析新 PATH。
- 环境完整性复检结果为 `ENVIRONMENT_SETUP_CHECK=PASS`；同时确认没有创建任何 Phase 1+ 文件。
- Mermaid 源码已做 fence 和人工结构检查，但未用 CLI 实际渲染；该环境没有渲染器。这是文档工具限制，不影响 Phase 0 其它门禁。

### 已知问题与后续决策

- 版本表是已核验的解析基线，不代表依赖组合已安装；Phase 1 必须用 uv 生成锁文件并跑导入/测试。
- Redis 是否为必需组件留到 Phase 5 以跨进程 SSE/任务需求实测决定。
- Checkpointer 的默认本地/集成后端留到 Phase 5 决定，但目标持久化后端为 PostgreSQL。
- 真实 Provider 类型留到 Phase 7 根据 OpenTelemetry Demo 的可复现性选择。
- 性能和准确率尚无数据；当前文档中的数字只标记为目标或建议默认值。

### 下一阶段输入条件

开始 Phase 1 前必须具备：

1. 用户明确确认进入 Phase 1。
2. 新开终端验证 `git --version` 与 `uv --version` 可通过 PATH 直接运行。
3. 重新核验核心依赖范围，用真实解析生成 `uv.lock`。
4. 只实施 Phase 1 的工程骨架、领域模型、`/health` 与基础测试，不提前实现 Provider/RAG/Graph。

## 变更日志

| 日期 | Phase | 摘要 |
| --- | --- | --- |
| 2026-07-18 | 0 | 从空目录建立需求、架构、Graph、数据模型、路线和仓库规范基线 |
| 2026-07-18 | 环境准备 | 安装并验证 Git、uv、WSL 2、Docker Desktop/CLI/Compose；未开始 Phase 1 |
| 2026-07-18 | 2 | 完成离线 Fixture Provider、七工具、Registry、基准 payment-service 数据与失败测试 |
| 2026-07-18 | 3 | 完成离线知识 ingest、Fake Embedding、BM25/向量/RRF、pgvector Adapter 与检索脚本 |

## Phase 1 — 工程骨架和领域模型

### 状态

`completed`

### 完成内容

- 建立 Python `src` layout、Hatchling 构建配置、uv 依赖组和精确锁文件。
- 建立 FastAPI app factory 与默认 ASGI app；`/health` 是不依赖外部服务的进程存活检查。
- 使用 Pydantic Settings 管理 `INCIDENT_COPILOT_` 前缀配置，模型密钥保持可选且不出现在 repr。
- 使用标准库 logging 输出 JSON，对消息及嵌套 extra 中的凭据做脱敏，同时保留 `input_tokens`、`token_usage` 等非秘密 AI 可观测字段。
- 定义框架无关的应用异常层次，以及 FastAPI 的应用异常、请求校验异常和未知异常安全映射；已知异常在 API 边界再次执行秘密脱敏。
- 实现 Incident、Evidence/Citation/EvidenceRef、Hypothesis/VerificationQuery、IncidentReport 及其子模型。
- 所有领域时间拒绝 naive datetime；ID、时间窗口、分数、证据关系、时间线和调查统计均有 Schema 不变量。领域值对象冻结，需要维持集合不变量的序列和统计映射不可原地修改。
- 定义版本化 `IncidentFixture` 与 evaluation-only ground truth，并提供一个脱敏 JSON 结构样例。
- 配置 Ruff、mypy strict、pytest 与 pytest-asyncio；测试全程不访问付费 API 或外部服务。

### 新增或修改文件

- 工程：`pyproject.toml`、`uv.lock`、`.gitignore`、`.env.example`、`Makefile`、`README.md`、`LICENSE`。
- 应用：`src/incident_copilot/main.py`、`api/`、`core/`。
- 领域：`src/incident_copilot/domain/`。
- Fixture：`src/incident_copilot/fixtures/`、`data/README.md`、`data/incidents/example.json`。
- 测试：`tests/unit/`、`tests/integration/test_api.py`。
- 文档：`AGENTS.md`、`docs/ROADMAP.md`、`docs/PROGRESS.md`。

### 依赖解析结果

2026-07-18 使用 Python 3.13.0 与 uv 0.11.29 实际解析 37 个包。直接依赖的最终锁定版本包括：FastAPI 0.139.2、Pydantic 2.13.4、pydantic-settings 2.14.2、Uvicorn 0.51.0、Ruff 0.15.22、mypy 2.3.0、pytest 9.1.1、pytest-asyncio 1.4.0 和 httpx2 2.7.0。

初次测试使用旧 `httpx` 时出现 Starlette 弃用警告；已切换到当前 `httpx2` 并重新锁定，最终测试为 0 warning。

### 实际检查结果

| 命令/检查 | 真实结果 |
| --- | --- |
| `uv sync` | PASS：创建 `.venv`，解析 37 个包并安装项目 |
| `uv lock --check` | PASS：锁文件与项目元数据一致 |
| `uv run ruff format --check .` | PASS：27 个 Python 文件已格式化 |
| `uv run ruff check .` | PASS：All checks passed |
| `uv run mypy src` | PASS：19 个 source files，0 issues |
| `uv run mypy src tests` | PASS：27 个 source files，0 issues |
| `uv run pytest` | PASS：43 passed，0 warning，最终复检 0.46s |
| 独立 Uvicorn + HTTP `/health` | PASS：真实 TCP 请求返回 `status=ok`、版本 0.1.0、test 环境 |

上述耗时只是本机测试运行记录，不是性能基准或项目性能声明。

### 已知问题

- 当前仓库是有效 Git worktree；本次审查开始时 `git status --short` 为空，基线提交为 `f3d4055 feat: initialize IncidentCopilot phase 1`。
- Docker Desktop 因固件/Windows 虚拟化支持尚未启用而不能启动；Phase 1 不依赖 Docker，Phase 7 前需按系统说明修复。
- 当前 Codex 沙箱不能直接执行用户 winget 目录中的 uv，自动化检查使用了已验证的 uv 绝对路径；普通新终端应通过用户 PATH 运行 `uv`。
- `Makefile` 是跨平台命令速记；Windows 若没有 `make`，README 中的原始 uv 命令仍是受支持入口。
- P2：`X-Request-ID` 尚未限制长度/字符；`api_prefix` 在 Phase 1 尚无消费者；报告 timeline/evidence/citations 的跨集合引用完整性待 Phase 4 报告生成策略定稿。
- P2：Pydantic 冻结是浅层冻结，`Evidence.content` 与 `metadata` 的嵌套 JSON 仍可变；深层不可变或副本策略待 Evidence Store 实现时确定。

### 手动验证

```text
uv sync
uv run uvicorn incident_copilot.main:app --reload
```

浏览 `http://127.0.0.1:8000/health`，预期 HTTP 200；浏览 `/docs` 可查看 OpenAPI 页面。停止服务使用 `Ctrl+C`。

### 下一阶段输入条件

开始 Phase 2 前必须具备：

1. 用户明确确认进入 Phase 2。
2. 保持 Phase 1 的全部质量门禁通过。
3. 为 payment-service 场景设计脱敏且含噪声的日志、指标、Trace、变更和拓扑原始 fixture。
4. 只实现 Provider Protocol、Fixture Provider、七类工具、Registry、超时/错误与单元测试，不提前实现 RAG 或 LangGraph。

## Phase 1 变更日志

| 日期 | 摘要 |
| --- | --- |
| 2026-07-18 | 完成工程骨架、领域模型、Fixture Schema、health API 与 29 项离线测试 |
| 2026-07-18 | 独立审查 Phase 1，修复领域可变性、EvidenceRef/Citation/统计不变量及日志/API 脱敏边界；43 项离线测试通过 |

## Phase 2 — Fixture Provider 和工具层

### 状态

`completed`

### 开始前基线

- 完整重读 `AGENTS.md`、PRD、架构、Graph、数据模型、路线图和进度文档。
- 当前 `main` 跟踪 `origin/main`；工作区已有 17 个未提交的 Phase 1 加固文件（309 行新增、73 行删除），无未跟踪文件。本阶段保留并兼容这些既有修改，没有回退或覆盖。
- 基线真实门禁：`uv lock --check`、Ruff format/check、`mypy src tests` 全部通过，Phase 1 全量测试 `43 passed`。

### 完成内容

- 定义 Log、Metrics、Trace、Change、Topology、Knowledge 六个异步 Provider Protocol；知识端口分别支持 Runbook 与历史事故。
- 定义七个严格 Pydantic 输入 Schema：服务名、timezone-aware 时间、24 小时窗口、limit、拓扑深度、指标/Trace/变更过滤和历史回看均有边界。
- 实现 allow-list Tool Registry，提供重名/未知工具保护、参数校验、per-call deadline、单次 timeout、最多有限重试、指数退避、调用预算、输出来源校验、错误归一化和结构化遥测。
- 实现单一版本化 IncidentFixture 驱动的 FixtureProvider；所有过滤、排序和 limit 都是确定性的，空结果不会伪造证据。
- 注册 `search_logs`、`query_metrics`、`query_traces`、`get_service_topology`、`get_recent_changes`、`search_runbooks`、`search_similar_incidents` 七个只读工具。
- 建立 payment-service 连接池耗尽场景：12 条证据覆盖日志、指标、Trace、变更、拓扑和知识，并包含网关健康反证、健康检查/业务拒绝噪声。
- 每条 fixture Evidence 包含来源名称/类型、时间点或窗口、服务、可解析 Citation，以及由规范化 content 实际计算的 SHA-256；ground truth 不经 Provider 工具返回。
- 测试全程使用 fixture 或受控内存 handler，不调用网络、数据库、真实可观测平台或付费 API。

### 新增或修改文件

- 工具契约与实现：`src/incident_copilot/tools/`。
- Fixture 数据：`data/incidents/payment-service-pool-exhaustion.json`、`data/README.md`。
- 测试：`tests/unit/tools/`、`tests/integration/test_fixture_tools.py`。
- 文档：`AGENTS.md`、`README.md`、`docs/ROADMAP.md`、`docs/PROGRESS.md`。

### 实际检查结果

| 命令/检查 | 真实结果 |
| --- | --- |
| `uv lock --check` | PASS：锁文件与项目元数据一致；Phase 2 未新增依赖 |
| `uv run ruff format --check .` | PASS |
| `uv run ruff check .` | PASS |
| `uv run mypy src tests` | PASS：38 个 source files，0 issues |
| `uv run pytest tests/unit/tools tests/integration/test_fixture_tools.py` | PASS：23 passed |
| `uv run pytest` | PASS：66 passed |

测试耗时只作为本机命令记录，不作为性能基准或 P95 声明。

### 已知问题

- `search_runbooks` 和 `search_similar_incidents` 当前只是确定性 fixture 文本/metadata 过滤；BM25、向量检索、RRF、Chunk 和检索评估属于 Phase 3。
- Registry 当前校验单次调用的 `remaining_tool_calls` 和 deadline，不维护调查级共享计数；Phase 4 的 Graph State/reducer 才负责全局预算原子更新。
- FixtureProvider 适合小型离线演示，启动时整体加载 JSON；未实现 Evidence Store、持久化或真实 Provider。
- Docker Desktop 的虚拟化问题仍未解决，但 Phase 2 不依赖 Docker。
- 本阶段没有测量或声明调查性能、诊断准确率、Recall 或 MRR。

### 手动验证

```text
uv sync
uv run pytest tests/unit/tools tests/integration/test_fixture_tools.py
uv run pytest
```

检查 `data/incidents/payment-service-pool-exhaustion.json` 可审阅固定时间线、反证/噪声和 evaluation-only ground truth。工具还没有 HTTP API；Phase 2 的受支持调用入口是 `ToolRegistry.execute(...)`，其端到端用法由 `tests/integration/test_fixture_tools.py` 覆盖。

### 下一阶段输入条件

开始 Phase 3 前必须具备：

1. 用户明确确认进入 Phase 3。
2. 保持 Phase 2 的 Provider/Registry 契约与全部质量门禁通过。
3. 只实现知识文档加载、切分、确定性 Fake Embedding、BM25/向量/RRF、过滤去重和 citation 保留。
4. 不提前实现 LangGraph 调查流程、API 生命周期或真实模型调用。

## Phase 3 — RAG Indexing 和 Retrieval

### 状态

`completed`

### 开始前基线

- 完整重读 `AGENTS.md`、PRD、架构、Graph、数据模型、路线图和进度文档。
- `main` 与 `origin/main` 一致，工作区无 diff；基线提交为 `121148c feat: complete phase 2 provider tool layer`。
- 基线 `uv lock --check`、Ruff format/check、`mypy src tests` 全部通过，全量测试 `66 passed`。

### 完成内容

- 定义 `KnowledgeDocument`、`KnowledgeChunk`、`EmbeddedChunk`、metadata filter、查询、候选、命中和 ingest/result Schema；时间、URI、服务、环境、hash 和引用均严格校验。
- 使用标准库 `tomllib` 加载 UTF-8 Markdown frontmatter，限制文件位于配置根目录内，拒绝坏 TOML、缺失 metadata 和重复 document ID。
- 实现按 Markdown 标题边界切分的 Splitter；只在超长小节内使用有界 overlap，每个 Chunk 继承文档 metadata 并生成可解析 citation。
- 实现固定 64 维 signed-hash Fake Embedding，明确只用于确定性数据链路，不声明真实语义质量。
- 实现 BM25、内存 cosine VectorStore、统一 metadata filter、稳定 tie-break、RRF 融合、content-hash 去重、top_k 和 citation 保留。
- 实现透明规则 Query Rewrite，覆盖 `db/postgresql/timeout/pool/checkout` 和 payment-service 场景中的中文别名，不调用 LLM。
- 实现 `RagKnowledgeProvider`，保持 Phase 2 `KnowledgeProvider` 与两个工具的调用契约。
- 实现 `PgVectorStore`：安全表名、维度校验、显式 `ensure_schema()`、参数化 SQL、JSONB payload 和 pgvector cosine 查询；默认无驱动/数据库依赖。
- 准备 2 个 Runbook、1 个服务说明和 1 个历史事故，共加载为 12 个 Chunk。
- 提供 `scripts/ingest_knowledge.py` 和 `scripts/search_knowledge.py`；实际运行输出可审计 JSON，不写入伪造索引/评估文件。
- 将 pytest `basetemp` 固定到仓库内已忽略的 `.pytest-tmp/`，避免 Windows 用户临时目录 ACL 导致 Loader 的真实临时文件测试无法运行；未跳过测试。
- 测试默认仅使用本地 Markdown、Fake Embedding、内存索引或 recording SQL session，不调用网络、在线模型、在线 embedding 或付费 API。

### 分步 Git 记录

- `048e5e3`：知识 Schema、Loader、Splitter、metadata/hash/citation 和 4 个样例文档；相关 8 tests、全量 74 tests 通过后推送。
- `bc4bb9d`：Fake Embedding、BM25、内存/pgvector、Query Rewrite、RRF Hybrid Retrieval、RAG Provider；相关 21 tests、全量 87 tests 通过后推送。
- 最终脚本与阶段文档在完整门禁通过后单独提交推送。

### 新增或修改文件

- RAG：`src/incident_copilot/rag/`。
- 知识数据：`data/knowledge/runbooks/`、`data/knowledge/services/`、`data/knowledge/incidents/`。
- 脚本：`scripts/ingest_knowledge.py`、`scripts/search_knowledge.py`。
- 测试：`tests/unit/rag/`、`tests/integration/test_rag_pipeline.py`。
- 文档/入口：`README.md`、`data/README.md`、`Makefile`、`.gitignore`、`pyproject.toml`、`AGENTS.md`、`docs/ROADMAP.md`、`docs/PROGRESS.md`。

### 依赖与运行影响

- Phase 3 未新增第三方依赖，`uv.lock` 仍解析 37 个包。
- Fake Embedding、BM25 与内存向量索引使用 Python 标准库，默认启动/测试不需要 API Key、数据库或网络。
- pgvector Adapter 面向窄 `PgVectorSession` Protocol；真实部署可由 psycopg/SQLAlchemy 包装器注入，避免把数据库驱动变成离线必需依赖。

### 实际检查结果

| 命令/检查 | 真实结果 |
| --- | --- |
| `uv lock --check` | PASS：锁文件一致，37 packages |
| `uv run ruff format --check .` | PASS：56 个 Python 文件已格式化 |
| `uv run ruff check .` | PASS |
| `uv run mypy src tests` | PASS：54 个 source files，0 issues |
| `uv run pytest tests/unit/rag tests/integration/test_rag_pipeline.py` | PASS：21 passed |
| `uv run pytest` | PASS：87 passed |
| `uv run python scripts/ingest_knowledge.py` | PASS：4 documents、12 chunks、重复 ingest 计数一致 |
| `uv run python scripts/search_knowledge.py --query "database connection pool timeout" --service payment-service --document-type runbook --top-k 2` | PASS：返回 2 条 Runbook Chunk，citation 可解析到源 Markdown |

测试耗时只作为本机运行记录，不作为性能/P95 声明。

### 固定检索回归结果

3 条手写查询分别期望数据库连接池 Runbook、payment-service 服务文档和历史连接池事故。最终离线结果：

- Recall@3：`1.0`（3/3 目标文档进入前三）；
- MRR：`7/9 ≈ 0.7778`（目标文档排名分别为 3、1、1）。

该结果只描述当前 4 文档、3 查询的确定性回归 fixture，不是模型准确率、生产检索质量或统计显著评估。完整 Evaluation 仍属于 Phase 6。

### 已知问题

- Fake Embedding 是 signed-hash 词袋，不能代表真实语义 embedding；中文能力来自有限规则 rewrite。
- 默认索引在内存中，每个进程重新 ingest；未实现持久化快照、增量文件监控或并发写协调。
- `PgVectorStore` 的参数化 SQL contract 已用 recording session 验证，但当前机器没有可用 PostgreSQL/pgvector，因此未运行真实数据库集成测试。
- Splitter 使用确定性近似 token 计数，不等同于未来模型 tokenizer；reranker 尚未实现且在 Phase 3 为可选项。
- Hybrid `score` 是归一化 RRF 排序分数，不是概率或诊断置信度。
- 未实现 LangGraph、模型推理、调查预算/循环或最终报告；这些属于 Phase 4。

### 手动验证

```text
uv sync
uv run python scripts/ingest_knowledge.py
uv run python scripts/search_knowledge.py --query "database connection pool timeout" --service payment-service --document-type runbook --top-k 2
uv run pytest tests/unit/rag tests/integration/test_rag_pipeline.py
```

预期初始化脚本报告 4 documents、12 chunks 和 `repeated_ingest_same_counts=true`；检索脚本输出 rewritten query、RRF 匹配来源、section、原文及 `internal://knowledge/...` citation。

### 下一阶段输入条件

开始 Phase 4 前必须具备：

1. 用户明确确认进入 Phase 4。
2. 保持 Phase 2 工具和 Phase 3 RAG 契约及全部质量门禁通过。
3. 先使用 Fixture Provider、RagKnowledgeProvider 和可复现 Fake Model 实现有界 LangGraph 调查循环。
4. 不提前实现 Phase 5 的 HTTP 调查生命周期、SSE、checkpoint 后端或 HITL API。
