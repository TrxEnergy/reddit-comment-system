from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict
from pathlib import Path
from datetime import timedelta


class CredentialConfig(BaseModel):
    """爬虫账号凭据配置"""

    credential_file: Path = Field(
        default=Path(r"C:\Users\beima\Desktop\BaiduSyncdisk\Trx相关\reddit账号\爬虫账号.jsonl"),
        description="爬虫账号JSONL文件路径"
    )
    rotation_strategy: str = Field(
        default="round_robin",
        description="轮换策略: round_robin, random, least_used"
    )
    max_requests_per_credential: int = Field(
        default=6000,
        description="单个凭据的最大请求数（触发轮换）- Reddit允许100QPM=6000/小时"
    )
    credential_cooldown_minutes: int = Field(
        default=60,
        description="凭据冷却时间（分钟）- 对应Reddit的1小时限制"
    )
    enable_auto_refresh: bool = Field(
        default=True,
        description="自动刷新token"
    )


class BudgetConfig(BaseModel):
    """预算管理配置"""

    max_posts_per_run: int = Field(
        default=1000,
        description="单次运行最大帖子数"
    )
    max_runtime_minutes: int = Field(
        default=60,
        description="最大运行时间（分钟）"
    )
    max_api_calls: int = Field(
        default=3000,
        description="最大API调用次数"
    )
    enable_budget_tracking: bool = Field(
        default=True,
        description="启用预算跟踪"
    )
    stop_on_budget_exceeded: bool = Field(
        default=True,
        description="超预算时停止"
    )


class CapacityRecipeConfig(BaseModel):
    """产能配方配置"""

    name: str = Field(..., description="配方名称")
    max_posts: int = Field(..., description="目标帖子数")
    max_runtime_minutes: int = Field(..., description="最大运行时间")
    search_channels: List[str] = Field(
        default_factory=lambda: ["hot", "top_day"],
        description="搜索通道列表"
    )
    min_score: int = Field(default=10, description="最小评分")
    min_comments: int = Field(default=5, description="最小评论数")
    max_age_hours: int = Field(default=72, description="最大帖子年龄（小时）")


class SearchChannelConfig(BaseModel):
    """搜索通道配置"""

    channel_name: str = Field(..., description="通道名称")
    endpoint: str = Field(..., description="Reddit API端点")
    time_filter: Optional[str] = Field(None, description="时间过滤器")
    limit: int = Field(default=100, description="每次请求限制")
    enabled: bool = Field(default=True, description="是否启用")
    priority: int = Field(default=1, description="优先级（1-10）")

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: int) -> int:
        if not 1 <= v <= 10:
            raise ValueError("优先级必须在1-10之间")
        return v


class QualityControlConfig(BaseModel):
    """质量控制配置"""

    # [2025-10-10] 极度宽松阈值,最大化帖子获取量
    min_post_score: int = Field(default=0, description="最小帖子分数 - 允许0分甚至负分")
    min_comment_count: int = Field(default=0, description="最小评论数 - 允许0评论")
    max_post_age_hours: int = Field(default=720, description="最大帖子年龄（小时）- 30天")
    min_title_length: int = Field(default=10, description="最小标题长度")
    max_title_length: int = Field(default=300, description="最大标题长度")

    banned_keywords: List[str] = Field(
        default_factory=list,
        description="禁止关键词"
    )
    required_keywords: List[str] = Field(
        default_factory=list,
        description="必需关键词"
    )

    enable_nsfw_filter: bool = Field(default=True, description="过滤NSFW内容")
    enable_spam_filter: bool = Field(default=True, description="过滤垃圾内容")
    enable_duplicate_filter: bool = Field(default=True, description="去重过滤")


class DeduplicationConfig(BaseModel):
    """去重配置"""

    strategy: str = Field(
        default="exact_title",
        description="去重策略: exact_title, fuzzy_title, url, content_hash"
    )
    similarity_threshold: float = Field(
        default=0.85,
        description="相似度阈值（0-1）"
    )
    lookback_days: int = Field(
        default=7,
        description="回溯天数"
    )
    cache_size: int = Field(
        default=10000,
        description="缓存大小"
    )
    enable_persistent_cache: bool = Field(
        default=True,
        description="启用持久化缓存"
    )


class RateLimitConfig(BaseModel):
    """速率限制配置"""

    requests_per_minute: int = Field(default=100, description="每分钟请求数（Reddit OAuth限制）")
    requests_per_hour: int = Field(default=6000, description="每小时请求数（理论值100×60）")
    retry_attempts: int = Field(default=3, description="重试次数")
    retry_backoff_seconds: int = Field(default=5, description="重试退避时间（秒）")

    respect_reddit_ratelimit: bool = Field(
        default=True,
        description="遵守Reddit速率限制头"
    )


class DiscoveryConfig(BaseModel):
    """Module 2 发现引擎完整配置"""

    credential: CredentialConfig = Field(
        default_factory=CredentialConfig,
        description="凭据配置"
    )
    budget: BudgetConfig = Field(
        default_factory=BudgetConfig,
        description="预算配置"
    )
    quality_control: QualityControlConfig = Field(
        default_factory=QualityControlConfig,
        description="质量控制配置"
    )
    deduplication: DeduplicationConfig = Field(
        default_factory=DeduplicationConfig,
        description="去重配置"
    )
    rate_limit: RateLimitConfig = Field(
        default_factory=RateLimitConfig,
        description="速率限制配置"
    )

    search_channels: List[SearchChannelConfig] = Field(
        default_factory=lambda: [
            SearchChannelConfig(
                channel_name="hot",
                endpoint="/hot",
                priority=10
            ),
            SearchChannelConfig(
                channel_name="top_day",
                endpoint="/top",
                time_filter="day",
                priority=9
            ),
            SearchChannelConfig(
                channel_name="top_week",
                endpoint="/top",
                time_filter="week",
                priority=8
            ),
            SearchChannelConfig(
                channel_name="rising",
                endpoint="/rising",
                priority=7
            ),
            SearchChannelConfig(
                channel_name="new",
                endpoint="/new",
                priority=5
            ),
        ],
        description="搜索通道配置列表"
    )

    capacity_recipes: List[CapacityRecipeConfig] = Field(
        default_factory=lambda: [
            CapacityRecipeConfig(
                name="quick_scan",
                max_posts=100,
                max_runtime_minutes=10,
                search_channels=["hot", "rising"],
                min_score=20,
                max_age_hours=24
            ),
            CapacityRecipeConfig(
                name="standard",
                max_posts=500,
                max_runtime_minutes=30,
                search_channels=["hot", "top_day", "rising"],
                min_score=10,
                max_age_hours=48
            ),
            CapacityRecipeConfig(
                name="deep_dive",
                max_posts=1000,
                max_runtime_minutes=60,
                search_channels=["hot", "top_day", "top_week", "rising", "new"],
                min_score=5,
                max_age_hours=72
            ),
        ],
        description="产能配方列表"
    )

    storage_path: Path = Field(
        default=Path("data/discovery"),
        description="数据存储路径"
    )
    enable_metrics: bool = Field(
        default=True,
        description="启用指标收集"
    )
    log_level: str = Field(
        default="INFO",
        description="日志级别"
    )

    class Config:
        env_prefix = "DISCOVERY_"
        case_sensitive = False
