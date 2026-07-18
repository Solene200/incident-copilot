# Phase 4 当前源码 Graph

下图由 `build_offline_investigation_graph().get_graph().draw_mermaid()` 直接生成，
对应当前提交中的实际节点与边。虚线为条件边；从计划/细化节点到 `collect_evidence`
的条件边在运行时返回多个 `Send`，并行分支在 `aggregate_evidence` 汇合。

Phase 5 才会实现的 checkpoint、interrupt、`human_review`、SSE 和调查 API 不在图中。

```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>__start__</p>]):::first
	parse_incident(parse_incident)
	build_investigation_plan(build_investigation_plan)
	collect_evidence(collect_evidence)
	aggregate_evidence(aggregate_evidence)
	generate_hypotheses(generate_hypotheses)
	verify_hypotheses(verify_hypotheses)
	judge_evidence(judge_evidence)
	refine_investigation(refine_investigation)
	generate_report(generate_report)
	__end__([<p>__end__</p>]):::last
	__start__ --> parse_incident;
	aggregate_evidence --> generate_hypotheses;
	build_investigation_plan -.-> aggregate_evidence;
	build_investigation_plan -.-> collect_evidence;
	collect_evidence --> aggregate_evidence;
	generate_hypotheses --> verify_hypotheses;
	judge_evidence -.-> generate_report;
	judge_evidence -.-> refine_investigation;
	parse_incident --> build_investigation_plan;
	refine_investigation -.-> aggregate_evidence;
	refine_investigation -.-> collect_evidence;
	verify_hypotheses --> judge_evidence;
	generate_report --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```

一致性检查：

```text
uv run python scripts/render_graph.py --check docs/GRAPH_CURRENT.md
```
