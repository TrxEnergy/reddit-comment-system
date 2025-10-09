"""
M5 Publishing - 数据模型
定义发布系统的所有数据结构
"""

from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any


class PublishState(str, Enum):
    """发布状态机"""
    PENDING = "pending"
    ACQUIRING_ACCOUNT = "acquiring"
    ACQUIRED = "acquired"
    PUBLISHING = "publishing"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLBACK = "rollback"


class RedditAccount(BaseModel):
    """
    Reddit账号模型
    对应tokens.jsonl中的一行数据
    """
    profile_id: str = Field(description="AdsPower Profile ID（唯一标识）")
    client_id: str = Field(description="Reddit App Client ID")
    client_secret: str = Field(description="Reddit App Secret")
    access_token: str = Field(description="OAuth Access Token")
    refresh_token: str = Field(description="OAuth Refresh Token")
    token_expires_at: datetime = Field(description="Token过期时间")

    # 运行时状态（内存管理，不持久化）
    is_locked: bool = Field(default=False, description="是否被锁定")
    locked_at: Optional[datetime] = Field(default=None, description="锁定时间")
    locked_by: Optional[str] = Field(default=None, description="锁定任务ID")

    # 配额管理
    daily_comment_count: int = Field(default=0, description="今日已发布数")
    last_comment_at: Optional[datetime] = Field(default=None, description="最后发布时间")

    @property
    def is_token_expired(self) -> bool:
        """检查Token是否过期"""
        return datetime.now() >= self.token_expires_at

    @property
    def can_publish_today(self) -> bool:
        """检查今日配额（每天1条）"""
        return self.daily_comment_count < 1


class PublishRequest(BaseModel):
    """
    发布请求（来自M4内容工厂）
    """
    comment_id: str = Field(description="评论ID")
    post_id: str = Field(description="Reddit帖子ID（如t3_xxxxx）")
    subreddit: str = Field(description="目标子版")
    comment_text: str = Field(description="评论内容")
    persona_id: str = Field(description="使用的Persona")
    parent_comment_id: Optional[str] = Field(
        default=None,
        description="父评论ID（回复评论时使用，None则为顶级评论）"
    )
    account_profile_id: Optional[str] = Field(
        default=None,
        description="指定账号Profile ID（可选，为None则自动分配）"
    )
    priority: int = Field(default=0, description="优先级")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="M4元数据"
    )


class PublishResult(BaseModel):
    """发布结果"""
    comment_id: str = Field(description="评论ID")
    success: bool = Field(description="是否成功")
    state: PublishState = Field(description="最终状态")
    permalink: Optional[str] = Field(default=None, description="Reddit评论链接")
    reddit_id: Optional[str] = Field(default=None, description="Reddit评论ID")
    error_type: Optional[str] = Field(default=None, description="错误类型")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    latency_seconds: float = Field(default=0.0, description="发布延迟（秒）")
    account_used: Optional[str] = Field(default=None, description="使用的账号Profile ID")
    published_at: Optional[datetime] = Field(default=None, description="发布时间")


class PublishingStats(BaseModel):
    """批量发布统计"""
    total_requests: int = Field(default=0, description="总请求数")
    successful_publishes: int = Field(default=0, description="成功发布数")
    failed_publishes: int = Field(default=0, description="失败发布数")
    account_acquisition_failures: int = Field(default=0, description="账号获取失败数")
    reddit_api_failures: int = Field(default=0, description="Reddit API失败数")
    total_latency_seconds: float = Field(default=0.0, description="总延迟（秒）")

    @property
    def average_latency_seconds(self) -> float:
        """平均延迟"""
        if self.total_requests == 0:
            return 0.0
        return self.total_latency_seconds / self.total_requests

    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_requests == 0:
            return 0.0
        return self.successful_publishes / self.total_requests
