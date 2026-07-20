# IncidentCopilot Repository Guide

本文件约束所有在本仓库内工作的开发者与 AI Agent。若任务说明与本文件冲突，以用户在当前任务中的明确要求为准。

## 项目目标

IncidentCopilot 是一个面向学习、面试和作品集展示的智能故障诊断项目。它使用 LangGraph 把多源证据收集、假设生成、证据验证、研究循环、报告生成和人工审核建模为可恢复工作流。

核心质量目标按优先级排序：

1. 无付费 API Key 也能本地运行、测试和演示。
2. 控制流、状态生命周期、证据来源和安全边界清晰可讲解。
3. Fixture 与真实数据源通过同一 Protocol/Adapter 契约替换。
4. 结果可复现；性能、准确率和评估结果不得虚构。
5. 保持必要的生产式边界，但避免与当前阶段无关的抽象。

## 变更门禁

- 一次只实施用户明确指定的一个变更批次或目标，不从历史 Phase 编号推断授权。
- 开始前先扫描现有实现，并说明问题编号、修改文件、设计决策、测试计划和风险。
- 当前能力以源码、`README.md` 的能力矩阵和可执行质量门禁为准；`ROADMAP` 与
  `PROGRESS` 中的历史 Phase 记录不是后续工作的授权条件。
- 结束时运行适用的锁文件、格式、静态检查、全量测试、Graph 文档、Learning Guide、
  Demo 和 Evaluation 门禁，记录真实结果，然后停止等待下一项明确指令。
- 不得提前创建下一批次占位业务代码，也不得把 Experimental 或 Target 能力写成 Current。

## 架构边界

- `domain/` 不依赖 FastAPI、LangGraph、SQLAlchemy 或具体供应商 SDK。
- `graph/` 编排用例，不直接读取文件、数据库或远端观测系统。
- `tools/interfaces.py` 定义端口，`tools/providers/` 提供适配器；业务代码只依赖端口。
- 模型通过统一 `ModelProvider` 注入；禁止硬编码模型名、API Key 或厂商客户端。
- RAG 的加载、切分、嵌入、索引和检索保持可替换；测试默认使用确定性假嵌入。
- API 只负责协议转换、鉴权/限流边界和依赖装配，不承载调查逻辑。
- 当前 Investigation/Event Repository 为内存实现；未来持久化模型必须与领域模型分离，
  Repository 负责映射。

## 编码规则

- 支持 Python 3.11+；所有时间使用带时区的 `datetime`，持久化统一为 UTC。
- 外部输入、工具参数和 LLM 结构化输出必须经 Pydantic v2 校验。
- LLM 输出视为不可信输入；校验失败应有限重试或进入明确降级路径。
- 不吞异常，不使用空 `except`；跨层异常转换必须保留原因链和可观测上下文。
- 工具必须限制服务名、时间范围、结果数、超时、重试次数、工具总调用数与预算。
- Graph State 只保存 ID、截断摘要和有界集合；当前没有外部 Evidence Store，文档不得
  暗示已经持久化原始大对象。
- 核心公共接口要有类型标注和说明契约的 docstring；注释解释原因，不复述代码。
- 不把秘密写入仓库；只提交脱敏 fixture 和 `.env.example`。
- 不为了通过测试而削弱断言、删除测试或绕过真实路径。

## 测试与质量门禁

默认命令以 `uv` 管理的锁定环境为准：

```text
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests scripts
uv run pytest
uv run python scripts/render_graph.py --check docs/GRAPH_CURRENT.md
uv run python scripts/build_learning_guide.py --check
```

只运行相关测试可以用于开发反馈，但批次验收必须运行用户协议要求的完整测试集。
涉及外部系统的测试使用 fixture、fake 或受控容器；默认测试不得访问真实付费 API。

## 变更纪律

- 先读后改，保留用户已有的正确实现和无关改动。
- 修改保持在当前批次范围内；目录规划不等于提前创建空目录。
- 新增依赖前说明用途、许可证/运维影响和可替代方案。
- `uv.lock` 由 `uv` 生成并提交，禁止手工编辑。
- 数据库结构变化使用 Alembic；禁止在启动路径中隐式改表。
- 不自动推送远程仓库，不执行破坏性 Git 或文件操作。
- 每次交付列出新增/修改文件、真实检查结果、遗留问题和下一阶段输入条件。

## 文档索引

- 产品范围：[`docs/PRD.md`](docs/PRD.md)
- 总体架构：[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- Graph 设计：[`docs/GRAPH_DESIGN.md`](docs/GRAPH_DESIGN.md)
- 当前源码 Graph：[`docs/GRAPH_CURRENT.md`](docs/GRAPH_CURRENT.md)
- 数据模型：[`docs/DATA_MODEL.md`](docs/DATA_MODEL.md)
- 路线与验收：[`docs/ROADMAP.md`](docs/ROADMAP.md)
- 实际进度：[`docs/PROGRESS.md`](docs/PROGRESS.md)
