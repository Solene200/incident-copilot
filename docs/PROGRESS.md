# IncidentCopilot 实施进度

## 当前状态

| 项目 | 值 |
| --- | --- |
| 当前已完成阶段 | Phase 1 |
| 下一阶段 | Phase 2（等待用户明确确认） |
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

## Phase 1 — 工程骨架和领域模型

### 状态

`completed`

### 完成内容

- 建立 Python `src` layout、Hatchling 构建配置、uv 依赖组和精确锁文件。
- 建立 FastAPI app factory 与默认 ASGI app；`/health` 是不依赖外部服务的进程存活检查。
- 使用 Pydantic Settings 管理 `INCIDENT_COPILOT_` 前缀配置，模型密钥保持可选且不出现在 repr。
- 使用标准库 logging 输出 JSON，并对消息及嵌套 extra 中的 token、密码、密钥和 Authorization 做脱敏。
- 定义框架无关的应用异常层次，以及 FastAPI 的应用异常、请求校验异常和未知异常安全映射。
- 实现 Incident、Evidence/Citation/EvidenceRef、Hypothesis/VerificationQuery、IncidentReport 及其子模型。
- 所有领域时间拒绝 naive datetime；ID、时间窗口、分数、证据关系、时间线和调查统计均有 Schema 不变量。
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
| `uv run pytest tests/unit tests/integration` | PASS：29 passed，最终复检 0.45s |
| `uv run pytest` | PASS：29 passed，最终复检 0.47s |
| 独立 Uvicorn + HTTP `/health` | PASS：返回 `status=ok`、版本 0.1.0、development 环境 |

上述耗时只是本机测试运行记录，不是性能基准或项目性能声明。

### 已知问题

- 仓库根目录存在空 `.git/` 目录，但不是有效 Git repository，缺少 `HEAD`/`config`；因此阶段开始与结束都无法提供 Git status/diff。未擅自初始化或删除它。
- Docker Desktop 因固件/Windows 虚拟化支持尚未启用而不能启动；Phase 1 不依赖 Docker，Phase 7 前需按系统说明修复。
- 当前 Codex 沙箱不能直接执行用户 winget 目录中的 uv，自动化检查使用了已验证的 uv 绝对路径；普通新终端应通过用户 PATH 运行 `uv`。
- `Makefile` 是跨平台命令速记；Windows 若没有 `make`，README 中的原始 uv 命令仍是受支持入口。

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
