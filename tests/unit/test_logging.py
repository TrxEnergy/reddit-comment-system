"""日志系统单元测试"""
import pytest
from src.core.logging import setup_logging, get_logger


def test_logger_basic_output(capsys):
    """测试基础日志输出"""
    logger = setup_logging(level="INFO")
    logger.info("test_message", key1="value1", key2=123)

    captured = capsys.readouterr()
    assert "test_message" in captured.out


def test_logger_levels(capsys):
    """测试不同日志级别"""
    logger = setup_logging(level="WARNING")

    logger.debug("debug_msg")
    logger.info("info_msg")
    logger.warning("warning_msg")
    logger.error("error_msg")

    captured = capsys.readouterr()
    assert "debug_msg" not in captured.out
    assert "info_msg" not in captured.out
    assert "warning_msg" in captured.out
    assert "error_msg" in captured.out


def test_named_logger():
    """测试命名日志记录器"""
    logger = get_logger("test_module")
    assert logger is not None


def test_exception_logging(capsys):
    """测试异常日志"""
    logger = setup_logging(level="ERROR")

    try:
        raise ValueError("Test error")
    except Exception:
        logger.exception("error_occurred", user="test_user")

    captured = capsys.readouterr()
    assert "error_occurred" in captured.out
    assert "ValueError" in captured.out
