# 22 Evaluation 数据集、Schema 与指标计算

本篇解释 Evaluation Runner 周围的输入加载、纯指标函数和全部结果 Schema。运行编排见 [12 OfflineEvaluationRunner](12-evaluation-runner.md)。

## `evaluation/dataset.py`

源码：[src/incident_copilot/evaluation/dataset.py](../../../src/incident_copilot/evaluation/dataset.py)

`repository_root()` 从当前文件向上三级定位项目根，不依赖 shell 当前目录。`default_dataset_path()` 在根下拼出版本化 JSON。

`load_evaluation_dataset()` 选择传入或默认路径，resolve 后按 UTF-8 读取，并在执行任何 Graph 前通过 `EvaluationDataset.model_validate_json` 完整校验。

`resolve_fixture_path()` 先解析仓库根和候选路径，再要求 root 出现在 candidate.parents。即使数据集绕过前面的 `..` 校验，也不能读取仓库外文件。

`RepositoryEvidenceResolver` 实现领域 `EvidenceResolver` 端口，只解析仓库内两类不可变来源：fixture locator 支持 `evidence[index]` 及受控 JSON 子路径，knowledge locator 使用与运行时相同的 splitter 重建 section/chunk。路径逃逸、越界、未知 locator 和无法重建的来源统一转为 `EvidenceResolutionError`。

## `evaluation/schemas.py`：标签和产物契约

源码：[src/incident_copilot/evaluation/schemas.py](../../../src/incident_copilot/evaluation/schemas.py)

### 输入侧

- `SampleStatus`：样例完成或失败。
- `ExpectedToolCall`：只标注与评价有关的工具参数子集。
- `EvaluationGroundTruth`：服务、故障类型、根因关键词、相关证据/文档和预期工具。
- `EvaluationSample`：Fixture 路径、检索问题、top_k、标签和 tags。
- `EvaluationDataset`：版本化样例集合。

GroundTruth 的 validator 规范化服务和集合，并拒绝同一样例重复预期 tool name。`EvaluationSample.validate_relative_fixture_path()` 使用 `Path` 拒绝绝对路径和任意 `..` path part，再统一成 POSIX 字符串。Dataset 最后检查 sample ID 唯一。

这些标签只传给评估器，不进入 Graph。若把 ground truth 拼进 ModelContext，得到的准确率就是数据泄漏。

### 单样例指标模型

| 模型 | 表示什么 |
| --- | --- |
| `SetMetrics` | 集合 precision/recall/F1/exact match 与原始计数 |
| `ToolArgumentMetrics` | 标签指定字段中匹配多少 |
| `RetrievalMetrics` | 排名列表、Recall@K 和 reciprocal rank |
| `CitationCheckMetrics` | 单个验证层明确的 checked/passed/score |
| `CitationMetrics` | reference consistency、locator resolvability、content integrity 三层结果 |
| `ActualToolCall` | 从真实 StepResult 重建的工具调用 |
| `SampleUsage` | Graph 轮数、调用、延迟和 Token |

`SampleUsage.estimated_cost_usd` 的类型固定为 `None`，`cost_status` 固定为无定价。项目不会在没有真实模型价格时伪造成本。

`EvaluationSampleResult.validate_status()` 要求 completed 必须有 report 且无 error，failed 必须有 error。失败样例仍保留在原始输出，而不是被统计代码丢弃。

### 汇总模型

`AggregateMetrics` 的每个质量指标都可选，因为某些样例的分母可能未定义；计数/延迟/Token 也保留真实值。`EvaluationSummary.validate_counts()` 检查完成数 + 失败数 = 总数，以及完成时间不早于开始时间。

## `evaluation/evaluators.py`：纯函数指标

源码：[src/incident_copilot/evaluation/evaluators.py](../../../src/incident_copilot/evaluation/evaluators.py)

### 文本规则

`FAILURE_TYPE_PATTERNS` 是透明、与 sample ID 无关的故障类型词表。`_normalized_text()` 统一大小写并只保留可比较 token。

`classify_failure_type()` 对每类统计命中 pattern 数，最高分为零返回 None；并列时按 label 排序选第一个，保证确定性。`root_cause_term_recall()` 统计标签关键词在 root cause 中的覆盖比例，不调用在线 LLM 裁判。

### `set_metrics`

1. expected/actual 转 set 去重。
2. 交集是真阳性。
3. actual 为空时，若 expected 也空则 precision=1，否则 0。
4. expected 为空时 recall=1。
5. precision+recall 为零时 F1=0，否则用调和平均。
6. 同时返回计数和 exact match，结果可手算审计。

### `retrieval_metrics`

先用 `dict.fromkeys` 对排名稳定去重，只看 top_k。Recall@K 是相关文档在窗口内的覆盖率；MRR 找到第一个相关文档后返回 `1/rank`，没有则 0。

### `tool_argument_metrics`

actual calls 先按 tool name 分组。每个 expected call 只比较标签列出的字段，并在所有同名真实调用中取匹配字段数最大者；运行时额外的时间范围、limit 等未标注字段不扣分。最终 score 是匹配字段总数/预期字段总数。

### `citation_metrics`

报告 Citation 先按 ID 建索引，再依次计算三层独立结果：

1. `reference_consistency` 比较 EvidenceRef 与报告 Citation 的 ID、URI、locator、算法版本和 hash，分母为全部 EvidenceRef。
2. `locator_resolvability` 调 resolver 重新取得来源内容，分母同样为全部 EvidenceRef。
3. `content_integrity` 对成功解析的内容复算版本化 hash，分母只包含成功解析项。

因此 locator 失败不会被一个“内部对象相同”的高分掩盖，无法解析时也不会把 content integrity 虚构为满分。

### 聚合 helper

`_defined_mean()` 排除 None 后用 `fmean`，全未定义则 None。`_percentile()` 排序后计算位置，落在两个索引之间时线性插值。

`aggregate_metrics()` 只对 completed 样例计算质量均值，但总结果仍另有 failed count。每个字段都从对应单样例指标映射；Token 先求和再算均值；只有所有 usage 都标为估算时，汇总 estimated 才为真。

`json_argument_value()` 递归把通过 Pydantic 的对象收窄为 JsonValue。先接受 None/标量，再处理 list/dict，其他类型明确抛错，避免 `cast` 掩盖运行时非法值。

## `evaluation/__init__.py`

[`evaluation/__init__.py`](../../../src/incident_copilot/evaluation/__init__.py) 导出 Dataset loader、Runner、artifacts 和核心 Schema。它不会在 import 时运行评估或写 artifacts。

## State、类比和修改风险

Evaluation 读取最终 State/Report/StepResult 并产生外部结果，不反向更新调查 State，也不决定下一节点。工程类比是离线 benchmark harness 与纯统计库。

- 把失败样例从分母和计数中完全删除会掩盖可靠性问题。
- 用 sample ID 硬编码故障类型会变成答案泄漏。
- Citation 只比较对象会漏掉内容、hash 或 locator 被替换的错误。
- 把 None 当 0 或 1 会改变未定义指标语义。

## 对照测试

- `tests/unit/evaluation/test_dataset.py`
- `tests/unit/evaluation/test_evaluators.py`
- `tests/integration/test_offline_evaluation.py`

下一步：返回[完整源码阅读索引](../core-reading-index.md)，按模块选择真实源码对照阅读。
