# 核心源码阅读索引

## 推荐阅读顺序

| 顺序 | A 级文件 | 先读专题 | 重点入口 |
| ---: | --- | --- | --- |
| 1 | `main.py` | 02、09 | `create_app`, `_build_runtime_graph` |
| 2 | `api/routes/investigations.py` | 03、09、10 | 四个 API endpoint, `_event_stream` |
| 3 | `investigations/service.py` | 03、09、10 | `create`, `resume`, `_execute` |
| 4 | `investigations/checkpoint.py` | 10 | `open_checkpointer` |
| 5 | `graph/state.py` | 04 | reducers, `InvestigationState` |
| 6 | `graph/builder.py` | 05 | `_dispatch_batch`, `build_investigation_graph` |
| 7 | `graph/nodes.py` | 05、08 | 十个核心 Node, `_call_structured` |
| 8 | `graph/routing.py` | 05、08 | `budget_stop_reason`, `decide_after_judge` |
| 9 | `graph/model.py` | 08 | `ModelProvider`, `FakeModelProvider` |
| 10 | `tools/registry.py` | 06 | `execute`, `_validate_evidence` |
| 11 | `rag/retrieval.py` | 07 | `ingest`, `search` |
| 12 | `evaluation/runner.py` | 11 | `run`, `_run_sample` |

## 对应 walkthrough

- [main.py](code-walkthrough/01-main.md)
- [调查 API](code-walkthrough/02-investigation-api.md)
- [InvestigationService](code-walkthrough/03-investigation-service.md)
- [Checkpoint](code-walkthrough/04-checkpoint.md)
- [Graph State](code-walkthrough/05-graph-state.md)
- [Graph Builder](code-walkthrough/06-graph-builder.md)
- [Graph Nodes](code-walkthrough/07-graph-nodes.md)
- [Graph Routing](code-walkthrough/08-graph-routing.md)
- [ModelProvider](code-walkthrough/09-model-provider.md)
- [ToolRegistry](code-walkthrough/10-tool-registry.md)
- [HybridRetriever](code-walkthrough/11-hybrid-retrieval.md)
- [OfflineEvaluationRunner](code-walkthrough/12-evaluation-runner.md)

## 阅读方法

每个 walkthrough 都按同一问题集解释关键代码:

1. 做什么。
2. 为什么这样写。
3. 输入从哪里来。
4. 输出到哪里去。
5. State 如何变化。
6. 下一节点如何确定。
7. 相关 Python 语法。
8. 后端工程类比。
9. 删除或修改的影响。

不涉及 Graph State 的文件会明确标记“State 不直接变化”, 而不会强行编造状态更新。
