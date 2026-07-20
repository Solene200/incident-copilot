# 14 配置、异常、日志与遥测

本篇按源码顺序解释 `core/` 下全部文件。它们为其他模块提供横切能力，但不承载调查业务。

## `core/config.py`

源码：[src/incident_copilot/core/config.py](../../../src/incident_copilot/core/config.py)

### 枚举为什么不直接用字符串

`RuntimeEnvironment`、`LogLevel`、`CheckpointBackend` 和 `MetricsBackend` 都继承 `StrEnum`。它们既能像字符串一样进入 JSON/环境配置，又把允许值限制为白名单。调用处可以写 `backend is MetricsBackend.PROMETHEUS`，避免拼写错误散落在业务代码中。

### `Settings` 逐项阅读

```python
model_config = SettingsConfigDict(
    env_prefix="INCIDENT_COPILOT_",
    env_file=".env",
    env_file_encoding="utf-8",
    case_sensitive=False,
    extra="ignore",
)
```

1. 所有环境变量加统一前缀，防止与系统变量冲突。
2. 本地可从 `.env` 读取，但生产仍可直接注入环境变量。
3. 键名不区分大小写；未知配置被忽略，便于同一 `.env` 放置其他组件变量。

字段分三类：应用元数据与日志；SSE 和 Checkpoint；指标 Provider 与可选凭据。数值字段用 `gt/le` 限制，`SecretStr` 的 `repr` 不显示明文，且字段额外声明 `repr=False`。

`validate_api_prefix()` 依次执行 `strip`、检查前导 `/`、拒绝根路径和尾随 `/`。因此路由拼接只有一种规范形式。`@cache` 让 `get_settings()` 每进程只解析一次；测试若改变环境变量，需要调用 `get_settings.cache_clear()`。

| 项目 | 说明 |
| --- | --- |
| 输入 | 环境变量、`.env` 和安全默认值 |
| 输出 | 冻结前的强类型 `Settings` 实例 |
| State | 不影响 Graph State，只决定组合根选择哪个 Adapter |
| 类比 | Spring `@ConfigurationProperties` |
| 修改风险 | 缓存前读取环境会导致测试不稳定；把密钥改为普通 `str` 容易在日志中泄漏 |

## `core/exceptions.py`

源码：[src/incident_copilot/core/exceptions.py](../../../src/incident_copilot/core/exceptions.py)

`ErrorCode` 是对外稳定机器码；异常类名可以重构，但客户端依赖的 code 不应随意改变。`IncidentCopilotError` 把三类信息分开：

```python
code: ClassVar[ErrorCode] = ErrorCode.INTERNAL
status_code: ClassVar[int] = 500

def __init__(self, message: str, *, details: dict[str, JsonValue] | None = None):
    super().__init__(message)
    self.message = message
    self.details = details or {}
```

- `ClassVar` 表示 code/status 属于异常类型，不是每个实例的 Pydantic 字段。
- `super().__init__` 保留标准异常行为；额外属性供 API Adapter 映射。
- `details or {}` 给每个实例独立字典。
- 四个子类只覆盖 code 和 HTTP status，实现领域校验 400、配置 500、资源不存在 404、状态冲突 409。

这些异常不导入 FastAPI，使 Service 和 Repository 可在 CLI、测试或其他协议中复用。

## `core/logging.py`

源码：[src/incident_copilot/core/logging.py](../../../src/incident_copilot/core/logging.py)

### 脱敏的三层防线

1. `_SENSITIVE_KEYS` 识别结构化字典中的敏感键。
2. `_KEY_VALUE_PATTERN` 识别嵌在自由文本里的 `password=...`、`token:...` 等格式。
3. `_AUTHORIZATION_PATTERN` 和 `_BEARER_PATTERN` 专门覆盖认证头与 Bearer Token。

`redact_text()` 按认证头、Bearer、普通键值的顺序替换。`redact_value()` 再递归处理 Mapping 和 Sequence：若当前 key 敏感，整项直接替换；字符串进入正则；集合递归复制；数字和布尔值原样返回。先判断字符串再判断 Sequence 很重要，因为 `str` 本身也是字符序列。

### `JsonFormatter.format`

```python
payload = {
    "timestamp": datetime.now(UTC).isoformat(),
    "level": record.levelname,
    "logger": record.name,
    "message": redact_text(record.getMessage()),
}
```

基础字段先固定为 UTC JSON。随后遍历 `record.__dict__`，只加入不属于标准 `LogRecord` 的 `extra` 字段，并再次按 key 脱敏。存在异常时，`formatException` 的堆栈也进入文本脱敏。最后 `json.dumps(..., default=str)` 确保时间等扩展对象可序列化。

`configure_logging()` 把枚举或字符串统一成级别文本，通过 `dictConfig` 幂等安装 JSON formatter、console handler 和 root logger；`disable_existing_loggers=False` 保留 Uvicorn 等库日志。

删除递归脱敏会让结构化 extra 泄密；只脱敏 message 远远不够。反过来把所有值都替换会失去排障上下文。

## `core/telemetry.py`

源码：[src/incident_copilot/core/telemetry.py](../../../src/incident_copilot/core/telemetry.py)

`telemetry_enabled()` 只有在环境变量显式属于 `1/true/yes/on` 时返回真，默认导入应用不会启动 exporter。

`trace_async(name, component=...)` 是“返回装饰器的函数”：

1. 外层接收 span 名和组件名。
2. `decorator(function)` 接收被装饰的异步函数。
3. `@wraps(function)` 保留原函数名、docstring 和签名元数据。
4. 每次调用先用 `nullcontext()`，关闭遥测时几乎只多一个普通上下文。
5. 启用时才 `import_module("opentelemetry.trace")`，因此默认依赖不必安装 OTel。
6. 缺少可选依赖时明确抛错，不静默假装已经追踪。
7. `start_as_current_span` 写入组件和真实函数限定名。
8. `with context: return await function(...)` 保证异常也会由 span 记录并正确结束。

`ParamSpec` 保留原异步函数的参数类型，`TypeVar` 保留返回类型；否则装饰后 mypy 只能看到 `Callable[..., Any]`。

## `core/__init__.py`

[`core/__init__.py`](../../../src/incident_copilot/core/__init__.py) 只有包说明，没有重新导出或启动逻辑。调用方显式从 `core.config`、`core.logging` 等子模块导入，依赖方向更容易搜索。

## State、路由和工程影响

四个模块都不直接读写 `InvestigationState`，也不决定下一节点。它们分别类似配置中心、统一异常基类、结构化日志中间件和 AOP tracing。错误地让 `core/` 导入 Graph 或 FastAPI 会形成反向依赖，破坏其跨协议复用能力。

## 对照测试

- `tests/unit/core/test_config.py`
- `tests/unit/core/test_logging.py`
- `tests/unit/core/test_telemetry.py`
- `tests/integration/test_api.py`

下一篇：[领域模型](15-domain-models.md)。
