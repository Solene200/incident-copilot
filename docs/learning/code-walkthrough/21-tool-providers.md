# 21 Fixture 与 Prometheus Provider

本篇解释两个真正取数的 Tool Adapter：一个从版本化本地事故数据过滤，另一个通过 HTTP
查询 Prometheus。后者的 Current live 范围只验证 payment/database-pool synthetic demo；
DNS/cache 场景没有等价 live mapping。

## `tools/providers/fixture.py`

源码：[src/incident_copilot/tools/providers/fixture.py](../../../src/incident_copilot/tools/providers/fixture.py)

### 构造与加载

`__init__` 保存已经校验的不可变 Fixture 和 Evidence tuple。`from_path()` 用 UTF-8 读取 JSON 后直接交给 `IncidentFixture.model_validate_json`；`payment_service()` 从源码文件向上定位仓库，加载规范故障文件。

### 七种查询的共同模式

每个异步方法都 `del context`，说明 Fixture 无 I/O、无需 deadline，但签名仍兼容 Protocol。查询按“来源/服务 → 时间 → 专属字段 → 稳定排序 → limit”执行。

- `search`：LOG + 时间重叠 + 可选全文词项。
- `query(QueryMetricsInput)`：METRIC + 窗口 + metadata 中 metric/aggregation。
- `query(QueryTracesInput)`：TRACE + 窗口 + operation/status。
- `recent`：CHANGE + 窗口 + change type，最新优先。
- `get`：TOPOLOGY + timestamp 不晚于 at_time + depth。
- `search_runbooks`：KNOWLEDGE + kind=runbook + 文本。
- `search_similar_incidents`：KNOWLEDGE + kind=incident + 有界历史窗口。

同名 `query` 通过 `isinstance` 对两个 Pydantic 输入类型分发，这是为了让一个 FixtureProvider 同时满足 MetricsProvider 和 TraceProvider。

### 过滤 helper 逐句理解

`_by_source_service` 返回 generator，直到最终排序才实际遍历。`_within_window` 调 `_overlaps`：单点证据使用闭区间；区间证据判断两个区间相交。`_within_depth` 显式排除 bool，因为 Python 中 `True` 也是 int。

`_text_matches` 用正则提取英文词项，把标题、摘要、content JSON 和 metadata JSON 合并为 haystack，要求所有 term 都出现。它是确定性 Fixture 搜索，不宣称语义能力。

`_ordered` 以 timestamp、start_time 或 UTC 最小值排序，再用 evidence ID 破同分；`newest_first` 反转整个复合键。稳定顺序使测试可复现。

## `tools/providers/prometheus.py`

源码：[src/incident_copilot/tools/providers/prometheus.py](../../../src/incident_copilot/tools/providers/prometheus.py)

### 传输边界

`HttpResponse` 只含 status/body。`PrometheusTransport` Protocol 让单测注入 fake transport。`UrllibPrometheusTransport.get()` 用 `asyncio.to_thread` 把阻塞 urllib 移出事件循环。

`_get_sync()` 设置 Accept/User-Agent，正常响应与 HTTPError 都读取有界 body；`_read_bounded()` 只多读一个字节，超限立即抛内部异常。网络库细节不会泄漏到 Provider 调用方。

### 响应 Schema 与指标白名单

三个私有 Pydantic 模型只接受 Prometheus matrix success 结构，额外字段忽略。`_MetricMapping` 把领域指标映射到真实 metric、单位和允许 aggregation。`METRIC_MAPPINGS` 是安全白名单，用户不能提交任意 PromQL。

### `query` 完整顺序

1. 从 mapping 查领域 metric 和 aggregation，不支持则抛 invalid query。
2. `_build_promql` 只拼接白名单 metric/aggregation，service 已由 ToolInput 正则规范化。
3. `_build_request_url` 根据窗口计算 step，最多约 240 点，并 urlencode 所有参数。
4. 用 `context.deadline - now` 算剩余时间，取 Adapter timeout 与剩余时间较小值。
5. 调 transport，把 timeout、响应过大、OS/URL 错误分别归一化。
6. `_raise_for_status` 把 400/422、429、其他非 2xx 分类。
7. `_parse_response` 做 Pydantic matrix 校验。
8. 拒绝超过 query.limit 的 series。
9. 每个 series 进入 `_series_to_evidence`。

### `_series_to_evidence` 逐点校验

函数先限制点数和 service label。随后逐点把字符串值转 float，并依次拒绝：非数字、NaN/Infinity、窗口外 timestamp、非严格递增时间。空序列也拒绝。

通过后构造 canonical content：领域 metric、真实 Prometheus metric、aggregation、unit、排序 labels 和 points。紧凑排序 JSON 计算内容哈希；查询身份与 hash 再产生稳定 Evidence/Citation ID。

Citation 的 URI 是实际 query_range URL，locator 指向 matrix 下标；Evidence 保存完整点、最大值/最新值摘要、窗口、服务、0.9 相关性/可靠性和采样数 metadata。

### 安全边界

- base URL 只允许绝对 HTTP(S)，拒绝凭据、query 和 fragment。
- timeout 最大 30 秒，响应最大 1 MB，每序列最大 240 点。
- 不接受任意 PromQL，不跟随模型生成查询语句。
- 不信任远端 service、顺序、数值和结果数量。

## State 与降级

两个 Provider 只返回 Evidence，不决定 Graph 路由。Registry 转成统一结果，collect Node 投影为 EvidenceRef。真实 Prometheus 失败时 Graph 记录 coverage gap；它不会暗中用 Fixture 指标冒充真实结果。

## 对照测试

- `tests/unit/tools/test_fixture_provider.py`
- `tests/unit/tools/test_prometheus_provider.py`
- `tests/integration/test_fixture_tools.py`
- `tests/integration/test_prometheus_graph.py`

下一篇：[Evaluation 辅助源码](22-evaluation-support.md)。
