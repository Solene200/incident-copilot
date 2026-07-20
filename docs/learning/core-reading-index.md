# 完整源码阅读索引

`src/incident_copilot/` 当前 64 个 Python 文件已经全部纳入源码精读。建议先读 A 级控制流，再按兴趣进入 B 级支撑模块；逐行阅读不等于从第一个文件机械读到最后一个文件。

## A 级：先理解主控制流

| 顺序 | 核心文件 | 先读专题 | Walkthrough |
| ---: | --- | --- | --- |
| 1 | `main.py` | 02、09 | [应用组合根](code-walkthrough/01-main.md) |
| 2 | `api/routes/investigations.py` | 03、09、10 | [调查 API 与 SSE](code-walkthrough/02-investigation-api.md) |
| 3 | `investigations/service.py` | 03、09、10 | [任务生命周期与 Graph 桥梁](code-walkthrough/03-investigation-service.md) |
| 4 | `investigations/checkpoint.py` | 10 | [Checkpoint](code-walkthrough/04-checkpoint.md) |
| 5 | `graph/state.py` | 04 | [State 与 Reducer](code-walkthrough/05-graph-state.md) |
| 6 | `graph/builder.py` | 05 | [Graph、边与并行分发](code-walkthrough/06-graph-builder.md) |
| 7 | `graph/nodes.py` | 05、08 | [十个核心 Node](code-walkthrough/07-graph-nodes.md) |
| 8 | `graph/routing.py` | 05、08 | [停止条件与路由](code-walkthrough/08-graph-routing.md) |
| 9 | `graph/model.py` | 08 | [ModelProvider 与 Fake](code-walkthrough/09-model-provider.md) |
| 10 | `tools/registry.py` | 06 | [工具执行安全边界](code-walkthrough/10-tool-registry.md) |
| 11 | `rag/retrieval.py` | 07 | [Hybrid Retriever](code-walkthrough/11-hybrid-retrieval.md) |
| 12 | `evaluation/runner.py` | 11 | [离线 Evaluation 编排](code-walkthrough/12-evaluation-runner.md) |

## B 级：补齐完整工程实现

| 顺序 | 模块范围 | 覆盖文件 | Walkthrough |
| ---: | --- | ---: | --- |
| 13 | 应用入口与 API 辅助 | 9 | [demo、server、错误、Schema、health](code-walkthrough/13-application-api-support.md) |
| 14 | 核心基础设施 | 5 | [配置、异常、日志、遥测](code-walkthrough/14-core-infrastructure.md) |
| 15 | 领域层 | 7 | [Incident、Evidence、Hypothesis、Report、Review](code-walkthrough/15-domain-models.md) |
| 16 | 任务存储与 Fixture | 5 | [任务模型、Repository、Fixture Schema](code-walkthrough/16-investigation-storage-fixtures.md) |
| 17 | Graph 辅助 | 4 | [装配、Schema、可视化、公共门面](code-walkthrough/17-graph-support.md) |
| 18 | RAG 摄取 | 7 | [加载、切分、嵌入、BM25、改写、Provider](code-walkthrough/18-rag-ingestion.md) |
| 19 | RAG 数据与存储 | 3 | [RAG Schema、内存向量库、pgvector](code-walkthrough/19-rag-schemas-vector-store.md) |
| 20 | Tool 契约 | 6 | [Protocol、参数、异常、内置工具](code-walkthrough/20-tool-contracts-builtin.md) |
| 21 | Tool Provider | 2 | [Fixture 与 Prometheus Adapter](code-walkthrough/21-tool-providers.md) |
| 22 | Evaluation 辅助 | 4 | [数据集、Schema、纯指标函数](code-walkthrough/22-evaluation-support.md) |

表中的覆盖文件数包含所属包的 `__init__.py`。单行初始化文件会解释导出和导入副作用，不重复粘贴没有业务逻辑的代码。

## 按问题选择源码

| 你想弄懂的问题 | 建议顺序 |
| --- | --- |
| HTTP 请求如何启动调查 | 01 → 02 → 03 → 06 |
| 并行证据如何合并 | 05 → 06 → 07 → 08 |
| 工具为什么不能任意调用 | 20 → 10 → 21 |
| Evidence/Citation 如何保留 | 15 → 20 → 10 → 07 |
| RAG 如何从文档变成 Evidence | 18 → 19 → 11 → 21 |
| 暂停恢复如何工作 | 04 → 03 → 02 |
| 评估数字如何计算 | 22 → 12 |
| 配置、日志和遥测如何装配 | 14 → 01 |

## 对照源码的阅读方法

1. 在 IDE 中打开 walkthrough 顶部的源码链接。
2. 同时打开文档和源码，按照文档小节从上向下移动光标。
3. 看到代码块时逐行对照；看到字段表时逐字段查看 Pydantic 约束。
4. 每读完一个函数，回答它的输入、输出、State 影响和失败路径。
5. 跳到文档末尾的测试，观察这些约束如何被断言。
6. 尝试只修改一个 Fixture 或配置值，不要先改业务逻辑。

## 文档解释约定

每份 walkthrough 都回答：

- 代码做什么、为什么这样写。
- 输入从哪里来、输出到哪里去。
- 是否改变 `InvestigationState`。
- 下一节点由谁决定。
- 相关 Python/Pydantic/异步语法。
- 后端工程类比。
- 删除或修改后的真实影响。

不涉及 State 的文件会明确写“不直接读写 State”。简单导出文件按每条导入/导出解释，不用重复内容制造虚假的复杂度。

## 覆盖门禁

`scripts/build_learning_guide.py` 在合并前会扫描全部源码链接。新增 `.py` 文件却没有加入 walkthrough 时，文档构建会直接失败并列出缺失路径。这个门禁保证“64/64”不是手工声明的数字。
