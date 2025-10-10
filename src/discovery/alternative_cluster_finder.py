"""
替代Subreddit簇发现器
自动发现和推荐替代的活跃subreddit
"""
import asyncio
import httpx
from typing import List, Dict, Optional
from dataclasses import dataclass

from .cluster_builder import SubredditCluster
from .cluster_health_checker import SubredditHealthChecker, HealthStatus
from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SubredditCandidate:
    """Subreddit候选"""
    name: str
    subscribers: int
    active_users: int
    description: str
    relevance_score: float  # 相关度评分（0-1）


class AlternativeClusterFinder:
    """替代Subreddit簇发现器"""

    def __init__(self, credential_manager=None):
        """
        初始化替代簇发现器

        Args:
            credential_manager: 凭据管理器（用于API认证）
        """
        self.credential_manager = credential_manager
        self.health_checker = SubredditHealthChecker(credential_manager)

        # 预设的高质量备用簇池（手动精选，确保可用）
        self.backup_clusters = self._get_backup_clusters()

    def _get_backup_clusters(self) -> Dict[str, List[SubredditCluster]]:
        """
        获取预设的高质量备用簇池

        Returns:
            Dict[str, List[SubredditCluster]]: 按类别分组的备用簇
        """
        return {
            "crypto_general": [
                SubredditCluster("crypto", "crypto_general", "General crypto (500K+ subs)"),
                SubredditCluster("cryptomarkets", "crypto_general", "Crypto markets (600K+)"),
                SubredditCluster("cryptocurrencies", "crypto_general", "Various cryptocurrencies (100K+)"),
            ],
            "trading": [
                SubredditCluster("cryptotrading", "trading", "Crypto trading (100K+)"),
                SubredditCluster("wallstreetbetscrypto", "trading", "WSB Crypto (50K+)"),
                SubredditCluster("daytrading", "trading", "Day trading (400K+, includes crypto)"),
            ],
            "tron_ecosystem": [
                # TRON生态的替代方案较少，主要依赖r/Tronix
                # 可以从大社区中搜索TRX相关帖子作为补充
            ],
            "development": [
                SubredditCluster("ethfinance", "development", "Ethereum finance (100K+)"),
                SubredditCluster("web3_community", "development", "Web3 community"),
            ],
            "meme_culture": [
                SubredditCluster("cryptocurrencymemes", "meme_culture", "Crypto memes"),
                SubredditCluster("cryptomemes", "meme_culture", "Crypto memes"),
            ]
        }

    async def search_subreddits(
        self,
        query: str,
        limit: int = 10
    ) -> List[SubredditCandidate]:
        """
        使用Reddit API搜索相关subreddit

        Args:
            query: 搜索关键词
            limit: 返回结果数量

        Returns:
            List[SubredditCandidate]: 候选subreddit列表
        """
        # 获取凭据
        credential = None
        if self.credential_manager:
            credential = self.credential_manager.get_credential()

        if not credential:
            logger.warning("无可用凭据，无法搜索subreddit")
            return []

        url = "https://oauth.reddit.com/api/search_subreddits"
        headers = {
            "Authorization": f"Bearer {credential.access_token}",
            "User-Agent": "python:discovery:v1.0"
        }
        params = {
            "query": query,
            "limit": limit,
            "include_over_18": False  # 排除成人内容
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, headers=headers, json=params)

                if response.status_code == 200:
                    data = response.json()
                    subreddits = data.get("subreddits", [])

                    candidates = []
                    for sub_data in subreddits:
                        candidate = SubredditCandidate(
                            name=sub_data.get("name", ""),
                            subscribers=sub_data.get("subscriber_count", 0),
                            active_users=sub_data.get("active_user_count", 0),
                            description=sub_data.get("description", "")[:100],
                            relevance_score=0.0  # 需要后续计算
                        )
                        candidates.append(candidate)

                    logger.info(f"搜索'{query}'找到{len(candidates)}个subreddit")
                    return candidates

                else:
                    logger.error(f"搜索失败: HTTP {response.status_code}")
                    return []

        except Exception as e:
            logger.error(f"搜索subreddit异常: {e}")
            return []

    async def validate_subreddit_quality(
        self,
        subreddit: str,
        min_subscribers: int = 1000,
        check_health: bool = True
    ) -> bool:
        """
        验证subreddit质量

        Args:
            subreddit: subreddit名称
            min_subscribers: 最小订阅者数
            check_health: 是否检查健康状态

        Returns:
            bool: 是否合格
        """
        # 健康检查
        if check_health:
            result = await self.health_checker.check_subreddit(subreddit)

            # 必须是active状态
            if result.status != HealthStatus.ACTIVE:
                logger.info(f"r/{subreddit} 不可访问: {result.status.value}")
                return False

            # 检查订阅者数
            if result.subscribers and result.subscribers < min_subscribers:
                logger.info(f"r/{subreddit} 订阅者不足: {result.subscribers} < {min_subscribers}")
                return False

        return True

    async def get_replacement_suggestions(
        self,
        category: str,
        limit: int = 5,
        use_search: bool = False
    ) -> List[SubredditCluster]:
        """
        获取指定类别的替代簇建议

        Args:
            category: 类别（crypto_general, trading, tron_ecosystem等）
            limit: 返回数量
            use_search: 是否使用搜索API（否则仅使用备用池）

        Returns:
            List[SubredditCluster]: 替代簇列表
        """
        suggestions = []

        # 1. 从备用池获取
        backup = self.backup_clusters.get(category, [])
        suggestions.extend(backup[:limit])

        logger.info(f"类别'{category}'的备用簇: {len(backup)}个")

        # 2. 如果启用搜索且数量不足，使用API搜索
        if use_search and len(suggestions) < limit:
            # 根据类别构建搜索关键词
            search_queries = {
                "crypto_general": ["cryptocurrency", "crypto", "blockchain"],
                "trading": ["crypto trading", "cryptocurrency trading"],
                "tron_ecosystem": ["tron", "trx", "trc20"],
                "development": ["crypto development", "blockchain dev"],
                "meme_culture": ["crypto meme", "cryptocurrency meme"]
            }

            queries = search_queries.get(category, ["cryptocurrency"])

            for query in queries:
                if len(suggestions) >= limit:
                    break

                # 搜索候选
                candidates = await self.search_subreddits(query, limit=5)

                # 验证质量并添加
                for candidate in candidates:
                    if len(suggestions) >= limit:
                        break

                    # 检查是否已在建议列表中
                    if any(s.subreddit_name == candidate.name for s in suggestions):
                        continue

                    # 质量验证
                    is_valid = await self.validate_subreddit_quality(
                        candidate.name,
                        min_subscribers=1000
                    )

                    if is_valid:
                        cluster = SubredditCluster(
                            subreddit_name=candidate.name,
                            category=category,
                            description=candidate.description
                        )
                        suggestions.append(cluster)

                # 添加延迟避免速率限制
                await asyncio.sleep(1.0)

        logger.info(f"类别'{category}'最终建议: {len(suggestions)}个")
        return suggestions[:limit]

    async def find_all_replacements(
        self,
        required_categories: List[str],
        per_category_limit: int = 3
    ) -> Dict[str, List[SubredditCluster]]:
        """
        为所有类别查找替代簇

        Args:
            required_categories: 需要替代的类别列表
            per_category_limit: 每个类别的替代数量

        Returns:
            Dict[str, List[SubredditCluster]]: 类别 -> 替代簇列表
        """
        results = {}

        for category in required_categories:
            suggestions = await self.get_replacement_suggestions(
                category,
                limit=per_category_limit,
                use_search=False  # 默认只使用备用池，避免API限流
            )
            results[category] = suggestions

        return results

    async def get_verified_backup_pool(self) -> List[SubredditCluster]:
        """
        获取经过验证的备用簇池（所有类别）

        Returns:
            List[SubredditCluster]: 已验证的备用簇列表
        """
        all_backup = []
        for category_clusters in self.backup_clusters.values():
            all_backup.extend(category_clusters)

        verified = []

        # 批量健康检查
        subreddit_names = [c.subreddit_name for c in all_backup]
        health_results = await self.health_checker.batch_check(subreddit_names, use_auth=True)

        # 过滤出active状态的簇
        for cluster in all_backup:
            result = health_results.get(cluster.subreddit_name)
            if result and result.status == HealthStatus.ACTIVE:
                verified.append(cluster)

        logger.info(f"备用池验证完成: {len(verified)}/{len(all_backup)} 可用")
        return verified
