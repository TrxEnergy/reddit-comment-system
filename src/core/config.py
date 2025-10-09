"""
配置管理系统
使用Pydantic Settings实现类型安全的配置管理
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AliasChoices
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
    client_id: str = Field(
        default="",
        validation_alias=AliasChoices("REDDIT_CLIENT_ID", "reddit_client_id")
    )
    client_secret: str = Field(
        default="",
        validation_alias=AliasChoices("REDDIT_CLIENT_SECRET", "reddit_client_secret")
    )


class LogConfig(BaseSettings):
    """日志配置"""
    level: str = Field(default="INFO", description="日志级别")
    format: str = Field(default="json", description="日志格式 (json|console)")


class M3ScreeningConfig(BaseSettings):
    """M3智能筛选配置（≤200账号专用）"""

    max_account_limit: int = Field(
        default=200,
        description="账号总数硬上限"
    )
    daily_comment_limit_per_account: int = Field(
        default=1,
        description="每账号日评论上限"
    )
    pool_buffer_ratio: float = Field(
        default=3.0,
        description="池子安全系数（倍数）"
    )

    l1_threshold_small: float = Field(
        default=0.75,
        description="L1直通阈值（1-50账号）"
    )
    l1_threshold_medium: float = Field(
        default=0.77,
        description="L1直通阈值（51-100账号）"
    )
    l1_threshold_large: float = Field(
        default=0.80,
        description="L1直通阈值（101-200账号）"
    )
    l1_review_threshold: float = Field(
        default=0.45,
        description="L1送审阈值（通用，送L2）"
    )

    l2_model: str = Field(
        default="gpt-4o-mini",
        description="L2使用的AI模型"
    )
    l2_threshold_small: float = Field(
        default=0.70,
        description="L2通过阈值（1-50账号）"
    )
    l2_threshold_medium: float = Field(
        default=0.65,
        description="L2通过阈值（51-100账号）"
    )
    l2_threshold_large: float = Field(
        default=0.60,
        description="L2通过阈值（101-200账号）"
    )
    l2_max_concurrency: int = Field(
        default=10,
        description="L2最大并发调用数"
    )
    l2_cost_per_call: float = Field(
        default=0.0015,
        description="L2单次调用成本（美元）"
    )
    l2_temperature: float = Field(
        default=0.3,
        description="L2生成温度"
    )
    l2_max_tokens: int = Field(
        default=150,
        description="L2最大token数"
    )

    daily_cost_limit: float = Field(
        default=0.50,
        description="日成本上限（美元）"
    )
    monthly_cost_limit: float = Field(
        default=15.0,
        description="月成本上限（美元）"
    )

    account_change_alert_threshold: int = Field(
        default=15,
        description="账号数量波动告警阈值（账号数/小时）"
    )


class Settings(BaseSettings):
    """全局配置"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False
    )

    yanghao: YanghaoAPIConfig = Field(default_factory=YanghaoAPIConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    reddit: RedditConfig = Field(default_factory=RedditConfig)
    log: LogConfig = Field(default_factory=LogConfig)
    m3_screening: M3ScreeningConfig = Field(default_factory=M3ScreeningConfig)

    app_name: str = "reddit-comment-system"
    version: str = "0.3.0"
    debug: bool = Field(
        default=False,
        validation_alias=AliasChoices("DEBUG", "debug")
    )


# 全局单例
settings = Settings()
