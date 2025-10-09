import asyncio
from typing import List, Dict
from datetime import datetime

from .config import CapacityRecipeConfig, DiscoveryConfig
from .credential_manager import CredentialManager
from .budget_manager import BudgetManager
from .quality_control import QualityControl
from .multi_channel_search import MultiChannelSearch, SearchResult
from .models import RawPost


class CapacityExecutor:
    """产能配方执行器"""

    def __init__(self, config: DiscoveryConfig):
        self.config = config
        self.credential_manager = CredentialManager(config.credential)
        self.budget_manager = BudgetManager(config.budget)
        self.quality_control = QualityControl(
            config.quality_control, config.deduplication
        )

        enabled_channels = [c for c in config.search_channels if c.enabled]
        self.multi_channel_search = MultiChannelSearch(
            channels=enabled_channels,
            credential_manager=self.credential_manager,
            rate_limit_config=config.rate_limit,
        )

    async def execute_recipe(
        self, recipe: CapacityRecipeConfig, cluster_ids: List[str]
    ) -> List[RawPost]:
        """执行产能配方"""

        print(f"\n{'='*60}")
        print(f"执行配方: {recipe.name}")
        print(f"目标: {recipe.max_posts} 帖子 / {recipe.max_runtime_minutes} 分钟")
        print(f"簇数量: {len(cluster_ids)}")
        print(f"搜索通道: {', '.join(recipe.search_channels)}")
        print(f"{'='*60}\n")

        self.budget_manager.reset()
        self.quality_control.reset()

        self.budget_manager.status.posts_limit = recipe.max_posts
        self.budget_manager.status.runtime_limit_seconds = recipe.max_runtime_minutes * 60

        all_posts = []

        for cluster_id in cluster_ids:
            if self.budget_manager.should_stop():
                print(f"\n⚠️ 预算已用尽，停止执行")
                break

            print(f"\n处理簇: {cluster_id}")

            cluster_posts = await self._fetch_cluster_posts(cluster_id, recipe)

            filtered_posts = self.quality_control.filter_posts(cluster_posts)

            all_posts.extend(filtered_posts)
            self.budget_manager.track_posts(len(filtered_posts))

            print(f"  原始: {len(cluster_posts)} | 过滤后: {len(filtered_posts)} | 累计: {len(all_posts)}")

        self._print_summary(recipe, all_posts)

        return all_posts

    async def _fetch_cluster_posts(
        self, cluster_id: str, recipe: CapacityRecipeConfig
    ) -> List[RawPost]:
        """获取单个簇的帖子"""

        posts_per_cluster = recipe.max_posts // 30

        all_posts = []

        async for search_result in self.multi_channel_search.search_all_channels(
            cluster_id, posts_per_cluster
        ):
            if search_result.channel not in recipe.search_channels:
                continue

            self.budget_manager.track_api_call(search_result.api_calls)
            all_posts.extend(search_result.posts)

            if self.budget_manager.should_stop():
                break

        return all_posts

    def _print_summary(self, recipe: CapacityRecipeConfig, posts: List[RawPost]):
        """打印执行摘要"""

        budget_stats = self.budget_manager.get_stats()
        quality_stats = self.quality_control.get_stats()
        credential_stats = self.credential_manager.get_stats()

        print(f"\n{'='*60}")
        print(f"配方执行完成: {recipe.name}")
        print(f"{'='*60}")

        print(f"\n【帖子统计】")
        print(f"  收集帖子: {len(posts)} 个")
        print(f"  目标帖子: {recipe.max_posts} 个")
        print(f"  完成率: {(len(posts) / recipe.max_posts * 100):.1f}%")

        print(f"\n【预算使用】")
        print(f"  帖子: {budget_stats['posts_fetched']}/{budget_stats['posts_limit']} ({budget_stats['posts_usage_percent']})")
        print(f"  API调用: {budget_stats['api_calls_made']}/{budget_stats['api_calls_limit']} ({budget_stats['api_calls_usage_percent']})")
        print(f"  运行时间: {budget_stats['runtime_seconds']}/{budget_stats['runtime_limit_seconds']} ({budget_stats['runtime_usage_percent']})")

        if budget_stats["exceeded"]:
            print(f"  ⚠️ {budget_stats['exceeded_reason']}")

        print(f"\n【质量控制】")
        print(f"  总拒绝: {quality_stats['total_rejected']} 个")
        for reason, count in quality_stats["rejection_breakdown"].items():
            print(f"    - {reason}: {count}")

        print(f"\n【凭据使用】")
        print(f"  总凭据: {credential_stats['total_credentials']} 个")
        print(f"  总请求: {credential_stats['total_requests']} 次")
        print(f"  冷却触发: {credential_stats['cooldowns_triggered']} 次")

        print(f"\n{'='*60}\n")

    def get_all_stats(self) -> Dict:
        """获取所有统计信息"""
        return {
            "budget": self.budget_manager.get_stats(),
            "quality": self.quality_control.get_stats(),
            "credentials": self.credential_manager.get_stats(),
        }
