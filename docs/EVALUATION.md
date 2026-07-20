# IncidentCopilot 离线评估

## 运行方式

默认命令不访问网络，不需要模型 API Key，使用 Fixture Provider、确定性 Fake Embedding 和 Fake Model：

```text
uv run python -m scripts.evaluate_offline --output-dir artifacts/evaluation/latest
```

输出包括：

- `raw-results.jsonl`：每个样例的预测、检索排序、工具名与参数、Evidence/Citation 指标、完整报告、轮数、调用数、实测时延和 Token 来源。
- `summary.json`：机器可读汇总。
- `summary.md`：人工可读汇总。

Runner 会捕获单个样例异常并写入原始结果，失败样例仍计入 `sample_count` 和
`failed_sample_count`，不会静默丢弃。除完成率/失败数外，质量、检索、用量和时延聚合
只使用状态为 `completed` 且对应指标已定义的样例；failed 样例不会隐式按 0 进入这些均值。

## 数据集

当前数据集为 `dataset_incident_copilot_offline` 版本 `1.0.0`，定义在 `data/evaluation/incidents-v1.json`，包含 3 个脱敏故障：

1. payment-service 数据库连接池上限被错误下调。
2. checkout-service DNS resolver 配置错误。
3. inventory-service cache TTL 被设为零。

每个样例引用独立 Fixture，并标注受影响服务、故障类型、根因关键词、相关 Evidence/知识文档、理想工具和关键参数。Ground truth 只在 Graph 完成后交给 evaluator；检索过滤使用 Fixture 中的 `IncidentContext.services`，而不是标签服务。Runner 传给 Graph 的只有 `IncidentContext`、Fixture Provider 和固定预算。

这只是小型 fixture 回归集，不是独立同分布的生产数据集，也不能用来证明模型泛化能力。

## 指标定义

| 指标 | 单样例定义 | 聚合分母 |
| --- | --- | --- |
| 样例完成/失败数 | 按 Runner 最终状态计数 | 数据集全部样例，`completed_count + failed_count = sample_count` |
| 服务定位 | 预测与标签服务集合 exact match；原始结果另存 precision/recall/F1 | 已完成且该指标已定义的样例数 |
| 故障类型 | 透明、样例无关的词法 taxonomy 与标签 exact match | 已完成且该指标已定义的样例数 |
| Recall@K | 前 K 个去重 document ID 覆盖相关文档的比例；无相关标签时定义为 1 | 已完成且 retrieval 已定义的样例数 |
| MRR | 前 K 个结果中第一个相关 document ID 的倒数排名；未命中为 0 | 已完成且 retrieval 已定义的样例数 |
| 工具选择 | 期望与实际工具名集合的 F1 | 已完成且 tool-selection 已定义的样例数 |
| 工具参数 | 只比较 ground truth 标注字段；同名工具取字段匹配度最高的真实调用 | 已完成且 tool-argument 已定义的样例数；单样例内分母为标注字段数 |
| Evidence relevance | 报告 supporting Evidence ID 与相关 Evidence ID 集合的 F1 | 已完成且该集合指标已定义的样例数 |
| Citation reference consistency | Citation ID、URI、locator、hash algorithm/content hash 与报告 Citation 一致 | 单样例分母为报告全部 EvidenceRef；聚合分母为该 score 非 `null` 的 completed 样例数 |
| Citation locator resolvability | Repository resolver 能按 URI/locator 找回 fixture Evidence 或 knowledge Chunk | 单样例分母为报告全部 EvidenceRef；聚合分母为该 score 非 `null` 的 completed 样例数 |
| Citation content integrity | 对成功解析内容按 `sha256-canonical-content-v1` 复算并匹配 hash | 单样例分母仅为成功解析的 Citation；聚合分母为该 score 非 `null` 的 completed 样例数 |
| 根因准确率 | 报告覆盖至少 75% 版本化根因关键词记为正确；另存 term recall | 已完成且根因指标已定义的样例数 |
| 平均轮数/工具次数 | 读取最终报告统计；工具次数指 logical tool steps | 已完成且 usage 已定义的样例数 |
| 平均/P95 时延 | `perf_counter` 单进程 Graph wall-clock；P95 线性插值 | 已完成且 usage 已定义的样例数 |
| Token 总数/均值 | ModelProvider usage；Fake 字符估算标记 `estimated=true` | 总数对 completed usage 求和；均值除以 completed usage 数 |
| Token estimated | 是否所有 completed usage 都标记 estimated | 已完成且 usage 已定义的样例集合；空集合为 `null` |
| 成本 | 未配置模型与定价时为 `unavailable_no_pricing` | 无分母，不推算或伪造 |

集合 evaluator 的两个空集合定义为 perfect exact match；期望非空而实际为空时
precision/recall/F1 均为 0。任一 Citation 层没有可检查引用时返回 `null`，聚合时跳过
该未定义值，而不是记为满分或零分。离线 resolver 只覆盖仓库内不可变 fixture 和
knowledge 来源，不把 live HTTP citation 计为已验证。

## Batch A 可信引用基线

schema 2.0 新产物位于 `artifacts/evaluation/batch-a-citation-integrity/`。本次运行 ID 为 `evalrun_20260720T083338Z_b7eaa5a9`，3/3 样例完成、0 个失败。Phase 6 的 `citation_correctness` 只代表旧对象自洽口径，保留为历史产物但不复用为当前结论：

| 指标 | 实际值 |
| --- | ---: |
| 服务定位准确率 | 1.0000 |
| 故障类型准确率 | 1.0000 |
| Retrieval Recall@K | 1.0000 |
| Retrieval MRR | 1.0000 |
| 工具选择 F1 | 0.9487 |
| 工具参数准确率 | 0.7857 |
| Evidence relevance F1 | 0.7852 |
| Citation reference consistency | 1.0000 |
| Citation locator resolvability | 1.0000 |
| Citation content integrity | 1.0000 |
| 根因准确率 | 1.0000 |
| 平均调查轮数 | 1.0000 |
| 平均工具调用数 | 7.0000 |
| 平均时延 | 12.5324 ms |
| P95 时延 | 15.7717 ms |
| 总 Token | 12,512（estimated） |
| 平均 Token | 4,170.6667（estimated） |
| 估算成本 | N/A（未配置定价） |

这些数值只描述 2026-07-20 在当前 Windows/Python 3.13 机器上的一次固定 fixture 运行。三个 Citation 指标证明本次报告能回到仓库内不可变来源并复算内容，不覆盖 live HTTP 来源。样例少且与 Fake Model/知识库同仓，其他 1.0 指标不能解释为生产准确率；时延也不是稳定 benchmark。工具参数与 Evidence relevance 的非满分结果被原样保留。

## Batch B 核心调查正确性

Batch B 使用独立目录 `artifacts/evaluation/batch-b-core-correctness/` 在最终代码上重新运行，run ID 为 `evalrun_20260720T090453Z_3b34b1ee`，3/3 样例完成、0 个失败。本次 Planner 只读取 raw query、symptoms、primary service 和已收集 Evidence 摘要；不接收 ground truth、fixture 文件名或 evaluator sample ID。

| 指标 | 实际值 |
| --- | ---: |
| 服务定位准确率 | 1.0000 |
| 故障类型准确率 | 1.0000 |
| Retrieval Recall@K / MRR | 1.0000 / 1.0000 |
| 工具选择 F1 | 1.0000 |
| 工具参数准确率 | 1.0000 |
| Evidence relevance F1 | 0.5167 |
| Citation reference / locator / integrity | 1.0000 / 1.0000 / 1.0000 |
| 根因准确率 | 1.0000 |
| 平均轮数 / 工具调用 | 1.0000 / 6.3333 |
| 总 Token / 平均 Token | 15,193 / 5,064.3333（estimated） |

Evidence relevance 的 0.5167 原样保留：当前报告把 request trace 用作竞争假设的反证，而该指标只以 leading hypothesis 的 `supporting_evidence` 为预测集合，不把 `contradicting_evidence` 或 rejected hypothesis 的 supporting IDs 计入预测。该口径没有为本批修改；此结果也不应外推为生产诊断质量。

## Batch D 产品边界复验

Batch D 使用独立目录 `artifacts/evaluation/batch-d-product-boundaries/` 在最终代码上重新运行，run ID 为
`evalrun_20260720T095024Z_5a059ee4`：3/3 样例完成、0 个失败。该次运行没有改变模型、检索或
evaluator 逻辑，目的只是确认文档与 API 边界校准没有破坏现有离线调查路径。

| 指标 | 实际值 | 聚合分母 |
| --- | ---: | --- |
| 服务定位 / 故障类型准确率 | 1.0000 / 1.0000 | 3 个 completed 且指标已定义的样例 |
| Retrieval Recall@K / MRR | 1.0000 / 1.0000 | 3 个 completed 且 retrieval 已定义的样例 |
| 工具选择 F1 / 参数准确率 | 1.0000 / 1.0000 | 3 个 completed 且对应指标已定义的样例 |
| Evidence relevance F1 | 0.5167 | 3 个 completed 且集合指标已定义的样例 |
| Citation reference / locator / integrity | 1.0000 / 1.0000 / 1.0000 | 3 个对应 score 非 `null` 的 completed 样例；单样例分母见上表 |
| 根因准确率 | 1.0000 | 3 个 completed 且根因指标已定义的样例 |
| 平均轮数 / logical tool steps | 1.0000 / 6.3333 | 3 个 completed 且 usage 已定义的样例 |
| 平均 / P95 wall-clock 时延 | 12.5956 / 16.0956 ms | 3 个 completed 且 usage 已定义的样例 |
| 总 / 平均 Token | 15,193 / 5,064.3333（estimated） | 3 个 completed 且 usage 已定义的样例 |

这仍是与 Fake Model 和知识库同代的 3 条 fixture 回归，不是生产泛化或性能 benchmark。离线 resolver
只验证仓库内不可变 fixture/knowledge citation；Live Prometheus 当前只验证 payment 场景，未进入本离线
数据集的 citation 完整性结论。

## 可观测性

OpenTelemetry 默认关闭且不会导入可选包。节点、工具和结构化模型调用分别使用 `incident_copilot.node.*`、`incident_copilot.tool.execute`、`incident_copilot.model.structured_complete` span 名称。启用方式：

```text
uv sync --extra observability
$env:INCIDENT_COPILOT_OTEL_ENABLED="true"
```

应用宿主仍需配置自己的 TracerProvider/SpanProcessor/exporter；项目默认不选择外部后端，也不会自动发送数据。

LangSmith 使用 LangGraph 原生 tracing，必须显式传入 `--langsmith`；默认 Runner 会通过 tracing context 覆盖外部环境变量并关闭 tracing：

```text
$env:LANGSMITH_API_KEY="<your-key>"
uv run python -m scripts.evaluate_offline --langsmith --langsmith-project incident-copilot-eval
```

LangSmith 是可选外部服务，不属于默认测试或本次离线基线。以上命令没有在线模型调用，但会把 Graph trace 发送到配置的 LangSmith workspace。
