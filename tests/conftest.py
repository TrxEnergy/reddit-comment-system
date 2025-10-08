"""Pytest配置和通用fixture"""
import pytest
import os
from src.core.config import Settings


@pytest.fixture(scope="session")
def test_settings():
    """测试环境配置"""
    os.environ['YANGHAO__BASE_URL'] = 'http://test-yanghao:8000'
    os.environ['AI__API_KEY'] = 'test-key'
    os.environ['LOG__LEVEL'] = 'DEBUG'

    settings = Settings()
    yield settings

    for key in ['YANGHAO__BASE_URL', 'AI__API_KEY', 'LOG__LEVEL']:
        os.environ.pop(key, None)


@pytest.fixture
def mock_logger(monkeypatch):
    """Mock日志记录器"""
    from src.core.logging import logger

    logs = []

    def mock_log(event, **kwargs):
        logs.append({"event": event, **kwargs})

    monkeypatch.setattr(logger, "info", mock_log)
    monkeypatch.setattr(logger, "warning", mock_log)
    monkeypatch.setattr(logger, "error", mock_log)

    return logs
