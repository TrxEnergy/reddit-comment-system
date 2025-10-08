"""
配置管理系统
使用Pydantic Settings实现类型安全的配置管理
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class YanghaoAPIConfig(BaseSettings):
    """养号系统API配置"""
    base_url: str = Field(
        default="http://localhost:8000",
        description="养号API基础URL"
    )
    timeout: int = Field(default=30, description="请求超时（秒）")
    max_retries: int = Field(default=3, description="最大重试次数")


class AIConfig(BaseSettings):
    """AI服务配置"""
    provider: str = Field(
        default="openai",
        description="AI提供商 (openai|anthropic)"
    )
    model: str = Field(default="gpt-4o-mini", description="模型名称")
    api_key: str = Field(default="", description="API密钥")
    temperature: float = Field(default=0.9, description="生成温度")
    max_tokens: int = Field(default=500, description="最大token数")


class RedditConfig(BaseSettings):
    """Reddit配置"""
    max_comments_per_day: int = Field(
        default=5,
        description="每账号每日最大评论数"
    )
    max_comments_per_hour: int = Field(
        default=2,
        description="每账号每小时最大评论数"
    )
    client_id: str = Field(default="", env="REDDIT_CLIENT_ID")
    client_secret: str = Field(default="", env="REDDIT_CLIENT_SECRET")


class LogConfig(BaseSettings):
    """日志配置"""
    level: str = Field(default="INFO", description="日志级别")
    format: str = Field(default="json", description="日志格式 (json|console)")


class Settings(BaseSettings):
    """全局配置"""
    yanghao: YanghaoAPIConfig = Field(default_factory=YanghaoAPIConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    reddit: RedditConfig = Field(default_factory=RedditConfig)
    log: LogConfig = Field(default_factory=LogConfig)

    app_name: str = "reddit-comment-system"
    version: str = "0.1.0"
    debug: bool = Field(default=False, env="DEBUG")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_nested_delimiter = "__"
        case_sensitive = False


# 全局单例
settings = Settings()
