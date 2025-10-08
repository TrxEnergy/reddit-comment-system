"""
结构化日志系统
使用structlog实现结构化、可解析的日志输出
"""
import structlog
import logging
import sys
from typing import Optional
from src.core.config import settings


def setup_logging(level: Optional[str] = None) -> structlog.BoundLogger:
    """
    配置并返回日志记录器

    Args:
        level: 日志级别（DEBUG/INFO/WARNING/ERROR/CRITICAL）

    Returns:
        配置好的structlog记录器
    """
    log_level = level or settings.log.level

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper())
    )

    if settings.log.format == "json":
        processors = [
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ]
    else:
        processors = [
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.stdlib.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer()
        ]

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger()


logger = setup_logging()


def get_logger(name: Optional[str] = None) -> structlog.BoundLogger:
    """获取命名日志记录器"""
    if name:
        return structlog.get_logger().bind(module=name)
    return structlog.get_logger()
