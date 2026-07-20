# 13 应用入口与 API 辅助源码

本篇补齐 `demo.py`、`server.py`、API 错误处理、请求/响应 Schema、健康检查以及对应的 `__init__.py`。调查主路由已经在 [02 调查 API](02-investigation-api.md) 中讲解。

## `demo.py`：真实指标演示辅助

源码：[src/incident_copilot/demo.py](../../../src/incident_copilot/demo.py)

### `wait_for_metric`

```python
loop = asyncio.get_running_loop()
deadline = loop.time() + timeout_seconds
consecutive_successes = 0
while loop.time() < deadline:
    now = datetime.now(UTC)
    query = QueryMetricsInput(...)
    context = QueryContext(...)
    evidence = await provider.query(query, context)
```

逐行理解：

1. `get_running_loop()` 取得当前事件循环；`loop.time()` 是单调时钟，不会因系统时间校准而倒退。
2. `deadline` 是整个等待过程的上限，而 `QueryContext.deadline` 是单次 Provider 调用的上限。
3. 每轮都用当前 UTC 时间重新构造最近 20 分钟窗口。
4. `QueryMetricsInput` 在发出 HTTP 前完成服务名、时间和指标白名单校验。
5. `await provider.query(...)` 只调用 Prometheus Adapter，不启动 Graph。
6. 只有连续两次取得非空 Evidence 才返回，避免把刚启动时的一次偶然数据当成稳定就绪。
7. 异常会保存到 `last_error` 并清零连续成功数；循环尾部 `sleep(2)` 避免忙轮询。
8. 最终 `raise ... from last_error` 保留底层失败原因链。

### `shift_fixture_to_now`

`delta = reference_end - fixture.incident.end_time` 先算统一偏移量。内部 `shifted()` 对可选时间做同样平移；随后用 Pydantic `model_copy(update=...)` 复制 Evidence、Citation 和 Incident，而不是修改冻结领域对象。最终得到新 Fixture，其证据陈述、ID 和内容哈希不变，时间窗口移动到真实 Prometheus 数据附近。

| 阅读问题 | 答案 |
| --- | --- |
| 输入 | `PrometheusMetricsProvider` 或已校验 `IncidentFixture` |
| 输出 | 指标 Evidence，或时间平移后的新 Fixture |
| State | 不直接读写；演示脚本随后才把 Fixture 交给 Graph |
| Python 重点 | 单调时钟、异常链、闭包、不可变模型复制 |
| 工程类比 | 集成测试的 readiness probe 与测试数据时间重定位 |
| 修改风险 | 只成功一次就返回会使演示抖动；只移动 Incident 而不移动 Evidence 会造成时间过滤为空 |

## `server.py`：跨平台 Uvicorn 启动器

源码：[src/incident_copilot/server.py](../../../src/incident_copilot/server.py)

```python
parser = argparse.ArgumentParser()
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", default=8000, type=int)
arguments = parser.parse_args()
config = uvicorn.Config("incident_copilot.main:app", ...)
server = uvicorn.Server(config)
with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
    runner.run(server.serve())
```

- 前三行声明并解析命令行参数，`type=int` 在进入应用前拒绝非法端口。
- 字符串 `incident_copilot.main:app` 表示导入模块并寻找模块级 ASGI 对象。
- 显式创建 `uvicorn.Server`，使事件循环由本项目控制。
- Windows 下使用 `SelectorEventLoop`，兼容异步 psycopg；`Runner` 退出时负责关闭循环资源。
- `if __name__ == "__main__"` 只在直接执行模块时调用 `main()`，被导入时不会启动服务器。

本文件不接触 State。删除自定义 Runner 后，纯内存模式可能仍可运行，但 Windows PostgreSQL Checkpointer 兼容性会退化。

## `api/investigation_schemas.py`：HTTP 与领域对象转换

源码：[src/incident_copilot/api/investigation_schemas.py](../../../src/incident_copilot/api/investigation_schemas.py)

### 请求字段和校验顺序

| 代码 | 含义 |
| --- | --- |
| `query`, `services`, `start_time`, `end_time` | 调查必填范围，长度和集合大小都有上限 |
| `symptoms`, `severity`, `environment` | 可选上下文，使用领域枚举而非任意字符串 |
| `options` | 服务端允许的有界预算配置 |
| `@field_validator("services")` | 复用领域层服务名规范化规则 |
| `@field_validator("symptoms")` | 去空、去重并保留输入顺序 |
| `@model_validator(mode="after")` | 字段都解析后再比较起止时间 |

`fingerprint()` 的代码按以下顺序执行：`model_dump(mode="json")` 把日期和枚举转成 JSON 值；`sort_keys=True` 固定字典顺序；紧凑分隔符避免空白差异；SHA-256 最终产生幂等请求指纹。它在生成服务器 ID 之前计算，因此同一语义请求可被识别。

`to_incident(incident_id)` 把传输层模型转换为 `IncidentContext`，并由服务器填入 ID 和 `created_at`。这条边界阻止 HTTP 专属字段混入领域模型。

`ResumeInvestigationRequest(HumanFeedback)` 没有新字段，作用是让 OpenAPI 显示独立的恢复请求名称，同时完全复用领域审核约束。

`InvestigationResponse.from_record()` 逐步完成：

1. 若有报告或审核请求，先 `model_dump(mode="python")`。
2. `redact_value` 递归脱敏。
3. 再次 `model_validate`，保证脱敏后仍满足公开 Schema。
4. `review_required` 由状态计算，不信任外部输入。
5. 不暴露 Graph 原始 checkpoint，只返回稳定任务投影。

## `api/errors.py`：异常到安全 JSON 的映射

源码：[src/incident_copilot/api/errors.py](../../../src/incident_copilot/api/errors.py)

```python
def _request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID") or f"req_{uuid4().hex}"
```

优先沿用调用方关联 ID，没有时生成新 ID。三个异步处理器分别负责：

- `handle_application_error`：把已知 `IncidentCopilotError` 的 code、status 和安全 details 映射出去。
- `handle_request_validation_error`：只保留错误类型、字段位置和消息，刻意不回显用户原始输入。
- `handle_unexpected_error`：用 `exc_info` 记录内部堆栈，对外固定返回 500 和通用消息。

`register_exception_handlers()` 的注册顺序从具体异常到通用 `Exception`。已知处理器先做 `isinstance` 防御，是因为 FastAPI 的回调签名统一为 `Exception`。

本文件不改变 Graph State；它相当于后端的全局异常中间层。若把 `exc.message` 或 Pydantic 的 `input` 原样返回，可能泄漏 API Key、查询内容或内部结构。

## `api/schemas.py` 与健康检查

源码：[src/incident_copilot/api/schemas.py](../../../src/incident_copilot/api/schemas.py) · [src/incident_copilot/api/routes/health.py](../../../src/incident_copilot/api/routes/health.py)

- `ApiModel.model_config = ConfigDict(extra="forbid")` 让公开响应拒绝未声明字段，避免协议悄悄漂移。
- `HealthResponse.status` 使用 `Literal["ok"]`，调用方不必猜测任意状态文本。
- `ErrorDetail.details` 用 `default_factory=dict`，避免共享可变默认值。
- `health()` 从 `request.app.state.settings` 读取启动时配置；`cast` 只帮助静态类型检查，不执行运行时转换。
- 健康接口只报告进程存活，不探测 PostgreSQL 或 Prometheus，所以外部可选组件故障不会让 Kubernetes 一直重启应用。

## 包初始化文件

[根包 `__init__.py`](../../../src/incident_copilot/__init__.py) 只定义 `__version__`；发布版本和 `Settings.app_version` 从这里取得。[`api/__init__.py`](../../../src/incident_copilot/api/__init__.py) 与 [`api/routes/__init__.py`](../../../src/incident_copilot/api/routes/__init__.py) 目前只有模块说明，不执行注册。路由由 `main.py` 显式导入，避免“导入包就产生副作用”。

## 对照测试

- `tests/integration/test_api.py`
- `tests/integration/test_investigation_api_phase5.py`
- `tests/unit/test_demo_scripts.py`
- `tests/unit/core/test_config.py`

下一篇：[核心基础设施](14-core-infrastructure.md)。
