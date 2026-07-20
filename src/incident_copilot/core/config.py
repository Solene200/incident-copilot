"""从环境变量加载的强类型应用配置。"""

from enum import StrEnum
from functools import cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from incident_copilot import __version__


class RuntimeEnvironment(StrEnum):
    """应用配置支持的运行环境。"""

    DEVELOPMENT = "development"  # 本地开发环境。
    TEST = "test"  # 自动化测试环境。
    STAGING = "staging"  # 上线前的预发布环境。
    PRODUCTION = "production"  # 面向真实用户的生产环境。


class LogLevel(StrEnum):
    """标准库日志系统接受的日志级别。"""

    DEBUG = "DEBUG"  # 最详细的开发调试信息。
    INFO = "INFO"  # 正常运行过程中的关键事件。
    WARNING = "WARNING"  # 可继续运行但值得关注的问题。
    ERROR = "ERROR"  # 当前操作失败, 但进程未必退出。
    CRITICAL = "CRITICAL"  # 可能导致服务不可用的严重故障。


class CheckpointBackend(StrEnum):
    """支持的 LangGraph 持久化 Adapter。"""

    MEMORY = "memory"  # 只在当前进程保存 Graph 快照。
    POSTGRES = "postgres"  # 在 PostgreSQL 中持久化 Graph 快照。


class MetricsBackend(StrEnum):
    """支持的指标 Provider Adapter。"""

    FIXTURE = "fixture"  # 使用仓库内可复现的本地指标样例。
    PROMETHEUS = "prometheus"  # 通过 HTTP 查询真实 Prometheus。


class Settings(BaseSettings):
    """带有安全离线默认值的应用配置。"""

    # 统一读取 INCIDENT_COPILOT_ 前缀环境变量和本地 .env, 字段名不区分大小写。
    model_config = SettingsConfigDict(
        env_prefix="INCIDENT_COPILOT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 应用在 health 响应和日志中展示的名称。
    app_name: str = Field(default="IncidentCopilot", min_length=1, max_length=100)
    # 当前应用版本, 默认读取包级 __version__。
    app_version: str = Field(default=__version__, min_length=1, max_length=50)
    # 当前部署环境, 用于区分开发、测试和生产。
    environment: RuntimeEnvironment = RuntimeEnvironment.DEVELOPMENT
    # 是否启用开发调试模式。
    debug: bool = False
    # 根日志记录器允许输出的最低级别。
    log_level: LogLevel = LogLevel.INFO
    # 所有业务 API 共用的 URL 前缀。
    api_prefix: str = "/api"
    # SSE 没有新事件时发送心跳的间隔秒数。
    sse_heartbeat_seconds: float = Field(default=15.0, gt=0, le=60)
    # Graph Checkpoint 选择内存还是 PostgreSQL Adapter。
    checkpoint_backend: CheckpointBackend = CheckpointBackend.MEMORY
    # PostgreSQL 连接字符串, 使用 SecretStr 避免意外打印。
    postgres_dsn: SecretStr | None = Field(default=None, repr=False)
    # 指标查询选择 Fixture 还是真实 Prometheus。
    metrics_backend: MetricsBackend = MetricsBackend.FIXTURE
    # Prometheus HTTP API 的基础地址。
    prometheus_base_url: str = "http://127.0.0.1:9090"
    # 单次 Prometheus 请求允许等待的最大秒数。
    prometheus_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    # 预留给真实模型 Provider 的密钥, 默认离线模式不需要。
    model_api_key: SecretStr | None = Field(default=None, repr=False)

    @field_validator("api_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        """要求后续路由使用规范化且非根路径的 API 前缀。"""
        value = value.strip()
        if not value.startswith("/"):
            raise ValueError("api_prefix must start with '/'")
        if value == "/" or value.endswith("/"):
            raise ValueError("api_prefix must not be '/' or end with '/'")
        return value


@cache
def get_settings() -> Settings:
    """为每个进程返回一个配置实例。"""
    return Settings()
