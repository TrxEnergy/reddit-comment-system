"""配置系统单元测试"""
import pytest
import os
from src.core.config import Settings, YanghaoAPIConfig, AIConfig
from src.core.exceptions import CommentSystemError


def test_default_config():
    """测试默认配置（考虑Docker环境变量覆盖）"""
    settings = Settings()
    # Docker环境下YANGHAO__BASE_URL会被设置为host.docker.internal
    assert "8000" in settings.yanghao.base_url
    assert settings.ai.provider == "openai"
    assert settings.reddit.max_comments_per_day == 5


def test_env_override():
    """测试环境变量覆盖"""
    os.environ['YANGHAO__BASE_URL'] = 'http://test:9000'
    os.environ['AI__MODEL'] = 'gpt-4o'

    settings = Settings()
    assert settings.yanghao.base_url == 'http://test:9000'
    assert settings.ai.model == 'gpt-4o'

    del os.environ['YANGHAO__BASE_URL']
    del os.environ['AI__MODEL']


def test_nested_config():
    """测试嵌套配置"""
    settings = Settings()
    assert isinstance(settings.yanghao, YanghaoAPIConfig)
    assert isinstance(settings.ai, AIConfig)
    assert settings.yanghao.timeout == 30


def test_required_fields():
    """测试必填字段"""
    settings = Settings()
    assert isinstance(settings.ai.api_key, str)


def test_exceptions():
    """测试异常定义"""
    err = CommentSystemError("Test error", {"code": 123})
    assert str(err) == "Test error | Details: {'code': 123}"
