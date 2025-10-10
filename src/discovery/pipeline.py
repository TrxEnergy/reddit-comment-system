import asyncio
import random
from typing import List, Optional
from datetime import datetime
from pathlib import Path
import json

from .config import DiscoveryConfig, CapacityRecipeConfig
from .cluster_builder import ClusterBuilder
from .capacity_executor import CapacityExecutor
from .models import RawPost
from .cluster_blacklist import ClusterBlacklist
from .alternative_cluster_finder import AlternativeClusterFinder

from src.core.logging import get_logger

logger = get_logger(__name__)


class DiscoveryPipeline:
    """Module 2 发现引擎核心管道"""

    def __init__(self, config: Optional[DiscoveryConfig] = None):
        self.config = config or DiscoveryConfig()
        self.cluster_builder = ClusterBuilder()
        self.executor = CapacityExecutor(self.config)

        # [2025-10-10] 黑名单管理器
        self.blacklist = ClusterBlacklist()

        # [2025-10-10] 替代簇发现器（延迟初始化，避免不必要的开销）
        self._alternative_finder = None

        self.config.storage_path.mkdir(parents=True, exist_ok=True)

    async def run(
        self,
        recipe_name: str = "standard",
        target_posts: Optional[int] = None
    ) -> List[RawPost]:
        """
        运行发现管道

        Args:
            recipe_name: 配方名称
            target_posts: 目标帖子数（覆盖配方设置，用于动态调整）

        Returns:
            发现的帖子列表
        """

        recipe = self._get_recipe(recipe_name)
        if not recipe:
            raise ValueError(f"配方不存在: {recipe_name}")

        # [2025-10-10] 动态调整目标帖子数（基于账号数量）
        if target_posts is not None:
            original_max = recipe.max_posts
            recipe.max_posts = target_posts
            print(f"动态调整搜索配额: {original_max} -> {target_posts}个帖子\n")

        print(f"\n{'#'*60}")
        print(f"# Module 2 发现引擎启动")
        print(f"# 配方: {recipe.name}")
        print(f"# 时间: {datetime.now().isoformat()}")
        print(f"{'#'*60}\n")

        # [2025-10-10] 加载所有簇
        all_clusters = self.cluster_builder.get_all_clusters()

        # [2025-10-10] 清理过期的黑名单条目
        expired = self.blacklist.remove_expired()
        if expired:
            logger.info(f"清理过期黑名单: {len(expired)}个 - {expired}")

        # [2025-10-10] 过滤掉黑名单中的簇
        valid_clusters = [
            c for c in all_clusters
            if not self.blacklist.is_blacklisted(c.subreddit_name)
        ]

        blacklisted_count = len(all_clusters) - len(valid_clusters)
        if blacklisted_count > 0:
            logger.info(f"过滤黑名单簇: {blacklisted_count}个")

        # [2025-10-10] 如果有效簇不足，尝试补充替代簇
        min_cluster_count = 20
        if len(valid_clusters) < min_cluster_count:
            logger.warning(f"有效簇数量不足({len(valid_clusters)}<{min_cluster_count})，尝试添加替代簇")
            valid_clusters = await self._add_replacement_clusters(valid_clusters)

        # [2025-10-10] 加权随机打乱簇顺序,优先访问业务相关度高的簇
        clusters = self._shuffle_clusters_weighted(valid_clusters)
        cluster_ids = [c.subreddit_name for c in clusters]

        print(f"已加载 {len(cluster_ids)} 个有效簇 (加权随机排序，已过滤{blacklisted_count}个黑名单):")
        for cluster in clusters[:5]:
            print(f"  - {cluster.subreddit_name} ({cluster.category})")
        if len(clusters) > 5:
            print(f"  ... 以及其他 {len(clusters) - 5} 个簇")

        posts = await self.executor.execute_recipe(recipe, cluster_ids)

        self._save_results(posts, recipe_name)

        return posts

    def _shuffle_clusters_weighted(self, clusters):
        """
        加权随机打乱簇顺序

        业务背景: TRX能量租赁,帮助用户省USDT转账手续费
        优先访问高相关度的簇(TRON生态、交易所用户、USDT讨论)
        """
        # [2025-10-10] 基于TRX能量租赁业务的权重配置
        weights_map = {
            # Tier 1: 核心业务相关 (权重 8-10)
            "Tronix": 10,              # TRON官方社区,核心目标
            "TronTRX": 10,             # TRON TRX讨论,核心目标
            "CryptoCurrency": 9,       # 通用加密货币,大流量
            "binance": 9,              # 币安用户,高频提现USDT
            "CryptoMarkets": 8,        # 交易用户,有USDT转账需求

            # Tier 2: 高相关度 (权重 5-7)
            "SunSwap": 7,              # TRON DeFi,需要能量
            "TronLink": 7,             # TRON钱包用户,懂TRC20
            "JustStable": 6,           # USDD稳定币,TRON生态
            "defi": 6,                 # DeFi用户,有转账需求
            "CoinBase": 6,             # Coinbase用户,提现需求
            "ethereum": 5,             # ETH用户抱怨ERC20贵,可引导到TRC20
            "Tronscan": 5,             # TRON浏览器用户

            # Tier 3: 中等相关 (权重 3-4)
            "Bitcoin": 4,              # BTC社区,加密用户
            "BlockChain": 4,           # 区块链技术讨论
            "CoinMarketCap": 4,        # CMC社区,市场用户
            "CryptoCurrencyTrading": 5, # 交易讨论,可能有转账需求
            "SatoshiStreetBets": 3,    # 交易赌徒,可能需要频繁转账
            "CryptoTechnology": 3,     # 技术讨论
            "altcoin": 3,              # 山寨币讨论

            # Tier 4: 低相关 (权重 1-2)
            "dogecoin": 2,             # Meme币,用户可能不懂USDT
            "Shibainucoin": 2,         # Meme币
            "CryptoMoonShots": 2,      # Moonshot讨论
            "SatoshiStreetDegens": 2,  # Degen文化
            "CryptoMeme": 1,           # 纯娱乐
            "CryptoHumor": 1,          # 纯娱乐

            # Tier 5: 开发者社区 (权重 2,技术含量高但转化低)
            "ethdev": 2,
            "CryptoDev": 2,
            "bitcoindev": 2,
            "solidity": 2,
            "web3": 2,
        }

        # 提取权重列表(未定义的簇默认权重3)
        weights = [weights_map.get(c.subreddit_name, 3) for c in clusters]

        # 使用加权随机采样打乱顺序(不重复)
        # 高权重簇有更大概率排在前面
        shuffled = []
        remaining_clusters = clusters.copy()
        remaining_weights = weights.copy()

        while remaining_clusters:
            # 加权随机选择一个
            chosen = random.choices(
                remaining_clusters,
                weights=remaining_weights,
                k=1
            )[0]

            # 添加到结果并从候选中移除
            shuffled.append(chosen)
            idx = remaining_clusters.index(chosen)
            remaining_clusters.pop(idx)
            remaining_weights.pop(idx)

        return shuffled

    async def _add_replacement_clusters(self, current_clusters: List) -> List:
        """
        添加替代簇以补充有效簇数量

        Args:
            current_clusters: 当前有效簇列表

        Returns:
            补充后的簇列表
        """
        # 延迟初始化替代簇发现器
        if not self._alternative_finder:
            self._alternative_finder = AlternativeClusterFinder(
                credential_manager=self.executor.credential_manager
            )

        # 获取已验证的备用簇池
        backup_clusters = await self._alternative_finder.get_verified_backup_pool()

        # 过滤掉已存在的簇
        current_names = {c.subreddit_name for c in current_clusters}
        new_clusters = [
            c for c in backup_clusters
            if c.subreddit_name not in current_names
            and not self.blacklist.is_blacklisted(c.subreddit_name)
        ]

        # 添加新簇到当前列表
        current_clusters.extend(new_clusters)

        logger.info(f"添加替代簇: {len(new_clusters)}个")

        return current_clusters

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

        print(f"\n[SAVE] 结果已保存: {filepath}")
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
            status = "[ON]" if channel.enabled else "[OFF]"
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
