"""日志系统单元测试"""
import pytest
import logging
from src.core.logging import setup_logging, get_logger


def test_logger_basic_output(caplog):
    """测试基础日志输出"""
    with caplog.at_level(logging.INFO):
        logger = setup_logging(level="INFO")
        logger.info("test_message", key1="value1", key2=123)

    assert "test_message" in caplog.text


def test_logger_levels(caplog):
    """测试不同日志级别"""
    with caplog.at_level(logging.WARNING):
        logger = setup_logging(level="WARNING")

        logger.debug("debug_msg")
        logger.info("info_msg")
        logger.warning("warning_msg")
        logger.error("error_msg")

    assert "debug_msg" not in caplog.text
    assert "info_msg" not in caplog.text
    assert "warning_msg" in caplog.text
    assert "error_msg" in caplog.text


def test_named_logger():
    """测试命名日志记录器"""
    logger = get_logger("test_module")
    assert logger is not None


def test_exception_logging(caplog):
    """测试异常日志"""
    with caplog.at_level(logging.ERROR):
        logger = setup_logging(level="ERROR")

        try:
            raise ValueError("Test error")
        except Exception:
            logger.exception("error_occurred", user="test_user")

    assert "error_occurred" in caplog.text
    assert "ValueError" in caplog.text
