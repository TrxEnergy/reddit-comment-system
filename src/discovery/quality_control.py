import re
import hashlib
from typing import List, Set, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from .config import QualityControlConfig, DeduplicationConfig
from .models import RawPost


class DeduplicationEngine:
    """去重引擎"""

    def __init__(self, config: DeduplicationConfig):
        self.config = config
        self.seen_ids: Set[str] = set()
        self.seen_titles: Set[str] = set()
        self.seen_urls: Set[str] = set()
        self.seen_hashes: Set[str] = set()

    def is_duplicate(self, post: RawPost) -> bool:
        """检查是否重复"""

        if post.post_id in self.seen_ids:
            return True

        if self.config.strategy == "exact_title":
            return self._check_exact_title(post)
        elif self.config.strategy == "fuzzy_title":
            return self._check_fuzzy_title(post)
        elif self.config.strategy == "url":
            return self._check_url(post)
        elif self.config.strategy == "content_hash":
            return self._check_content_hash(post)
        else:
            return self._check_exact_title(post)

    def _check_exact_title(self, post: RawPost) -> bool:
        """精确标题匹配"""
        normalized = self._normalize_title(post.title)

        if normalized in self.seen_titles:
            return True

        self.seen_titles.add(normalized)
        self.seen_ids.add(post.post_id)
        return False

    def _check_fuzzy_title(self, post: RawPost) -> bool:
        """模糊标题匹配（基于编辑距离）"""
        normalized = self._normalize_title(post.title)

        for seen_title in self.seen_titles:
            similarity = self._calculate_similarity(normalized, seen_title)
            if similarity >= self.config.similarity_threshold:
                return True

        self.seen_titles.add(normalized)
        self.seen_ids.add(post.post_id)
        return False

    def _check_url(self, post: RawPost) -> bool:
        """URL匹配"""
        if not post.url:
            return False

        if post.url in self.seen_urls:
            return True

        self.seen_urls.add(post.url)
        self.seen_ids.add(post.post_id)
        return False

    def _check_content_hash(self, post: RawPost) -> bool:
        """内容哈希匹配"""
        content = f"{post.title}|{post.selftext}"
        content_hash = hashlib.md5(content.encode()).hexdigest()

        if content_hash in self.seen_hashes:
            return True

        self.seen_hashes.add(content_hash)
        self.seen_ids.add(post.post_id)
        return False

    def _normalize_title(self, title: str) -> str:
        """标准化标题"""
        title = title.lower().strip()
        title = re.sub(r"\s+", " ", title)
        title = re.sub(r"[^\w\s]", "", title)
        return title

    def _calculate_similarity(self, s1: str, s2: str) -> float:
        """计算相似度（Jaccard相似度）"""
        set1 = set(s1.split())
        set2 = set(s2.split())

        if not set1 or not set2:
            return 0.0

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0

    def reset(self):
        """重置去重缓存"""
        self.seen_ids.clear()
        self.seen_titles.clear()
        self.seen_urls.clear()
        self.seen_hashes.clear()

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "total_seen": len(self.seen_ids),
            "strategy": self.config.strategy,
            "similarity_threshold": self.config.similarity_threshold,
        }


class QualityControl:
    """质量控制系统"""

    def __init__(
        self,
        quality_config: QualityControlConfig,
        dedup_config: DeduplicationConfig,
    ):
        self.quality_config = quality_config
        self.dedup_engine = DeduplicationEngine(dedup_config)
        self.rejection_stats = defaultdict(int)

    def filter_posts(self, posts: List[RawPost]) -> List[RawPost]:
        """过滤帖子列表"""
        filtered = []

        for post in posts:
            if self.is_valid(post):
                filtered.append(post)

        return filtered

    def is_valid(self, post: RawPost) -> bool:
        """检查帖子是否有效"""

        if self.quality_config.enable_duplicate_filter:
            if self.dedup_engine.is_duplicate(post):
                self.rejection_stats["duplicate"] += 1
                return False

        if post.score < self.quality_config.min_post_score:
            self.rejection_stats["low_score"] += 1
            return False

        if post.num_comments < self.quality_config.min_comment_count:
            self.rejection_stats["low_comments"] += 1
            return False

        post_age_hours = (datetime.now().timestamp() - post.created_utc) / 3600
        if post_age_hours > self.quality_config.max_post_age_hours:
            self.rejection_stats["too_old"] += 1
            return False

        title_len = len(post.title)
        if title_len < self.quality_config.min_title_length:
            self.rejection_stats["title_too_short"] += 1
            return False

        if title_len > self.quality_config.max_title_length:
            self.rejection_stats["title_too_long"] += 1
            return False

        if self.quality_config.enable_nsfw_filter and post.over_18:
            self.rejection_stats["nsfw"] += 1
            return False

        if self.quality_config.enable_spam_filter and post.stickied:
            self.rejection_stats["stickied"] += 1
            return False

        if self.quality_config.banned_keywords:
            if self._contains_banned_keywords(post):
                self.rejection_stats["banned_keywords"] += 1
                return False

        if self.quality_config.required_keywords:
            if not self._contains_required_keywords(post):
                self.rejection_stats["missing_required_keywords"] += 1
                return False

        return True

    def _contains_banned_keywords(self, post: RawPost) -> bool:
        """检查是否包含禁止关键词"""
        text = f"{post.title} {post.selftext}".lower()

        for keyword in self.quality_config.banned_keywords:
            if keyword.lower() in text:
                return True

        return False

    def _contains_required_keywords(self, post: RawPost) -> bool:
        """检查是否包含必需关键词"""
        text = f"{post.title} {post.selftext}".lower()

        for keyword in self.quality_config.required_keywords:
            if keyword.lower() in text:
                return True

        return False

    def get_stats(self) -> dict:
        """获取统计信息"""
        total_rejected = sum(self.rejection_stats.values())

        return {
            "total_rejected": total_rejected,
            "rejection_breakdown": dict(self.rejection_stats),
            "deduplication": self.dedup_engine.get_stats(),
        }

    def reset(self):
        """重置统计"""
        self.rejection_stats.clear()
        self.dedup_engine.reset()
