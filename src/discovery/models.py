"""
发现引擎数据模型
定义Reddit帖子和发现结果的数据结构
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class RawPost:
    """原始Reddit帖子（用于发现引擎）"""

    post_id: str
    cluster_id: str
    title: str
    author: str
    score: int
    num_comments: int
    created_utc: float
    url: str = ""
    permalink: str = ""
    selftext: str = ""
    is_self: bool = False
    over_18: bool = False
    spoiler: bool = False
    stickied: bool = False
    raw_json: Dict = field(default_factory=dict)
    discovered_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "post_id": self.post_id,
            "cluster_id": self.cluster_id,
            "title": self.title,
            "author": self.author,
            "score": self.score,
            "num_comments": self.num_comments,
            "created_utc": self.created_utc,
            "url": self.url,
            "permalink": self.permalink,
            "selftext": self.selftext,
            "is_self": self.is_self,
            "over_18": self.over_18,
            "spoiler": self.spoiler,
            "stickied": self.stickied,
            "discovered_at": self.discovered_at.isoformat(),
        }


class RedditPost(BaseModel):
    """Reddit帖子数据模型"""

    post_id: str = Field(description="帖子ID")
    title: str = Field(description="标题")
    selftext: str = Field(default="", description="正文")
    subreddit: str = Field(description="所属subreddit")
    author: str = Field(description="作者")
    score: int = Field(description="分数")
    num_comments: int = Field(description="评论数")
    created_utc: datetime = Field(description="创建时间UTC")
    url: str = Field(description="帖子URL")
    permalink: str = Field(description="永久链接")
    is_nsfw: bool = Field(default=False, description="是否NSFW")

    # 扩展字段
    matched_cluster_id: Optional[str] = Field(
        default=None,
        description="匹配的簇ID"
    )
    matched_keyword: Optional[str] = Field(
        default=None,
        description="匹配的关键词"
    )

    def get_text_length(self) -> int:
        """获取文本总长度"""
        return len(self.title) + len(self.selftext)

    def get_full_text(self) -> str:
        """获取完整文本（标题+正文）"""
        return f"{self.title} {self.selftext}"


class DiscoveryResult(BaseModel):
    """发现结果汇总"""

    tier: Optional[int] = Field(default=None, description="层级（如果按层级发现）")
    keywords_used: List[str] = Field(description="使用的关键词列表")
    clusters_used: List[str] = Field(
        default_factory=list,
        description="使用的簇ID列表"
    )

    # 流程统计
    total_crawled: int = Field(description="总爬取数")
    after_dedup: int = Field(description="去重后数量")
    after_filter: int = Field(description="过滤后数量")

    # 最终结果
    final_posts: List[RedditPost] = Field(description="最终帖子列表")

    # 性能指标
    duration_seconds: float = Field(description="总耗时（秒）")
    avg_hit_rate: float = Field(
        default=0.0,
        description="平均命中率"
    )

    # 通道统计
    channel_stats: dict = Field(
        default_factory=dict,
        description="各通道统计 {channel: hits}"
    )

    def get_summary(self) -> str:
        """获取结果摘要"""
        return (
            f"发现帖子: {len(self.final_posts)}条 | "
            f"爬取: {self.total_crawled} → 去重: {self.after_dedup} → "
            f"过滤: {self.after_filter} | "
            f"耗时: {self.duration_seconds:.1f}秒 | "
            f"命中率: {self.avg_hit_rate:.1%}"
        )
