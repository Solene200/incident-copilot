"""应用各层共享的可注入 UTC 时钟。"""

from collections.abc import Callable
from datetime import UTC, datetime

# 返回带时区当前时间的函数类型; 测试可以注入固定或可推进时钟。
Clock = Callable[[], datetime]


def utc_now() -> datetime:
    """返回生产环境使用的实时 UTC 时间。"""
    return datetime.now(UTC)
