import asyncio
from typing import List, Optional
from datetime import datetime
from pathlib import Path
import json

from .config import DiscoveryConfig, CapacityRecipeConfig
from .cluster_builder import ClusterBuilder
from .capacity_executor import CapacityExecutor
from .models import RawPost


class DiscoveryPipeline:
    """Module 2 发现引擎核心管道"""

    def __init__(self, config: Optional[DiscoveryConfig] = None):
        self.config = config or DiscoveryConfig()
        self.cluster_builder = ClusterBuilder()
        self.executor = CapacityExecutor(self.config)

        self.config.storage_path.mkdir(parents=True, exist_ok=True)

    async def run(self, recipe_name: str = "standard") -> List[RawPost]:
        """运行发现管道"""

        recipe = self._get_recipe(recipe_name)
        if not recipe:
            raise ValueError(f"配方不存在: {recipe_name}")

        print(f"\n{'#'*60}")
        print(f"# Module 2 发现引擎启动")
        print(f"# 配方: {recipe.name}")
        print(f"# 时间: {datetime.now().isoformat()}")
        print(f"{'#'*60}\n")

        clusters = self.cluster_builder.get_all_clusters()
        cluster_ids = [c.subreddit_name for c in clusters]

        print(f"已加载 {len(cluster_ids)} 个簇:")
        for cluster in clusters[:5]:
            print(f"  - {cluster.subreddit_name} ({cluster.category})")
        if len(clusters) > 5:
            print(f"  ... 以及其他 {len(clusters) - 5} 个簇")

        posts = await self.executor.execute_recipe(recipe, cluster_ids)

        self._save_results(posts, recipe_name)

        return posts

    def _get_recipe(self, recipe_name: str) -> Optional[CapacityRecipeConfig]:
        """获取配方"""
        for recipe in self.config.capacity_recipes:
            if recipe.name == recipe_name:
                return recipe
        return None

    def _save_results(self, posts: List[RawPost], recipe_name: str):
        """保存结果到文件"""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"discovery_{recipe_name}_{timestamp}.jsonl"
        filepath = self.config.storage_path / filename

        with open(filepath, "w", encoding="utf-8") as f:
            for post in posts:
                f.write(json.dumps(post.to_dict(), ensure_ascii=False) + "\n")

        print(f"\n✅ 结果已保存: {filepath}")
        print(f"   共 {len(posts)} 个帖子\n")

    def get_available_recipes(self) -> List[str]:
        """获取可用配方列表"""
        return [r.name for r in self.config.capacity_recipes]

    def print_config_summary(self):
        """打印配置摘要"""

        print(f"\n{'='*60}")
        print("配置摘要")
        print(f"{'='*60}")

        print(f"\n【凭据配置】")
        print(f"  文件: {self.config.credential.credential_file}")
        print(f"  轮换策略: {self.config.credential.rotation_strategy}")
        print(f"  最大请求数: {self.config.credential.max_requests_per_credential}")

        print(f"\n【预算配置】")
        print(f"  最大帖子数: {self.config.budget.max_posts_per_run}")
        print(f"  最大运行时间: {self.config.budget.max_runtime_minutes} 分钟")
        print(f"  最大API调用: {self.config.budget.max_api_calls}")

        print(f"\n【质量控制】")
        print(f"  最小分数: {self.config.quality_control.min_post_score}")
        print(f"  最小评论数: {self.config.quality_control.min_comment_count}")
        print(f"  最大年龄: {self.config.quality_control.max_post_age_hours} 小时")
        print(f"  去重策略: {self.config.deduplication.strategy}")

        print(f"\n【搜索通道】")
        for channel in self.config.search_channels:
            status = "✅" if channel.enabled else "❌"
            print(f"  {status} {channel.channel_name} (优先级: {channel.priority})")

        print(f"\n【产能配方】")
        for recipe in self.config.capacity_recipes:
            print(f"  - {recipe.name}: {recipe.max_posts} 帖子 / {recipe.max_runtime_minutes} 分钟")

        print(f"\n{'='*60}\n")


async def main():
    """命令行入口"""

    pipeline = DiscoveryPipeline()

    pipeline.print_config_summary()

    print("可用配方:")
    for recipe_name in pipeline.get_available_recipes():
        print(f"  - {recipe_name}")

    print("\n选择配方（默认: standard）:")
    recipe_choice = input("> ").strip() or "standard"

    posts = await pipeline.run(recipe_choice)

    print(f"\n最终收集: {len(posts)} 个帖子")

    if posts:
        print("\n示例帖子（前3个）:")
        for i, post in enumerate(posts[:3], 1):
            print(f"\n{i}. [{post.cluster_id}] {post.title}")
            print(f"   分数: {post.score} | 评论: {post.num_comments}")


if __name__ == "__main__":
    asyncio.run(main())
