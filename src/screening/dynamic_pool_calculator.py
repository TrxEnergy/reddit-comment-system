"""
动态池子计算器
根据实时活跃账号数动态计算池子规模和筛选阈值
"""

import httpx
from typing import Optional
from datetime import datetime

from src.core.logging import get_logger
from src.screening.models import PoolConfig, AccountScale

logger = get_logger(__name__)


class DynamicPoolCalculator:
    """动态池子规模和阈值计算器"""

    def __init__(
        self,
        yanghao_api_base_url: str = "http://localhost:8000",
        max_account_limit: int = 200,
        daily_comment_limit_per_account: int = 1,
        buffer_ratio: float = 3.0,
        l2_cost_per_call: float = 0.0015
    ):
        """
        初始化计算器

        Args:
            yanghao_api_base_url: 养号系统API基础URL
            max_account_limit: 账号总数上限
            daily_comment_limit_per_account: 每账号日评论上限
            buffer_ratio: 默认安全系数
            l2_cost_per_call: L2单次调用成本
        """
        self.yanghao_api_base_url = yanghao_api_base_url
        self.max_account_limit = max_account_limit
        self.daily_comment_limit = daily_comment_limit_per_account
        self.buffer_ratio = buffer_ratio
        self.l2_cost_per_call = l2_cost_per_call

        logger.info(f"动态池子计算器初始化 - 养号API: {yanghao_api_base_url}, 账号上限: {max_account_limit}")

    async def get_active_account_count(self, min_health_score: float = 70.0) -> int:
        """
        通过养号API获取活跃账号数

        Args:
            min_health_score: 最低健康分数

        Returns:
            活跃账号数量
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.yanghao_api_base_url}/api/v1/accounts/available",
                    params={"min_health_score": min_health_score}
                )
                response.raise_for_status()
                accounts = response.json()
                count = len(accounts)

                logger.info(f"获取活跃账号数: {count}个（健康分≥{min_health_score}）")
                return count

        except httpx.HTTPError as e:
            logger.warning(f"养号API调用失败: {e}，使用降级策略")
            return self._get_fallback_account_count()
        except Exception as e:
            logger.error(f"获取账号数异常: {e}")
            return self._get_fallback_account_count()

    def _get_fallback_account_count(self) -> int:
        """降级策略：返回默认账号数"""
        default_count = 100
        logger.warning(f"降级策略：假设活跃账号数为 {default_count}")
        return default_count

    def _determine_account_scale(self, account_count: int) -> AccountScale:
        """
        判断账号规模档位

        Args:
            account_count: 账号数量

        Returns:
            账号规模枚举
        """
        if account_count <= 50:
            return AccountScale.SMALL
        elif account_count <= 100:
            return AccountScale.MEDIUM
        else:
            return AccountScale.LARGE

    def _get_thresholds_by_scale(self, scale: AccountScale) -> tuple[float, float, float]:
        """
        根据账号规模获取阈值配置

        Args:
            scale: 账号规模

        Returns:
            (L1直通阈值, L1送审阈值, L2通过阈值)
        """
        thresholds_map = {
            AccountScale.SMALL: (0.75, 0.45, 0.70),   # 1-50账号：高质量
            AccountScale.MEDIUM: (0.77, 0.45, 0.65),  # 51-100账号：均衡
            AccountScale.LARGE: (0.80, 0.45, 0.60),   # 101-200账号：效率
        }
        return thresholds_map.get(scale, (0.75, 0.45, 0.65))

    def calculate_pool_config(
        self,
        active_account_count: Optional[int] = None
    ) -> PoolConfig:
        """
        计算池子配置

        Args:
            active_account_count: 活跃账号数（如果为None则自动查询）

        Returns:
            池子配置对象
        """
        if active_account_count is None:
            logger.warning("未提供账号数，使用同步降级策略")
            active_account_count = self._get_fallback_account_count()

        account_scale = self._determine_account_scale(active_account_count)

        pool_size = int(active_account_count * self.daily_comment_limit * self.buffer_ratio)

        l1_direct_threshold, l1_review_threshold, l2_pass_threshold = self._get_thresholds_by_scale(account_scale)

        estimated_l2_calls = int(pool_size * 0.5)

        estimated_daily_cost = estimated_l2_calls * self.l2_cost_per_call

        config = PoolConfig(
            active_accounts=active_account_count,
            pool_size=pool_size,
            buffer_ratio=self.buffer_ratio,
            account_scale=account_scale,
            l1_direct_pass_threshold=l1_direct_threshold,
            l1_review_threshold=l1_review_threshold,
            l2_pass_threshold=l2_pass_threshold,
            estimated_l2_calls=estimated_l2_calls,
            estimated_daily_cost=estimated_daily_cost,
            calculated_at=datetime.now()
        )

        logger.info(
            f"池子配置计算完成 - 账号数:{active_account_count} ({account_scale.value}), "
            f"池子规模:{pool_size}, 预估L2调用:{estimated_l2_calls}, "
            f"预估成本:${estimated_daily_cost:.4f}/日"
        )

        return config

    async def calculate_pool_config_async(self) -> PoolConfig:
        """
        异步计算池子配置（自动查询账号数）

        Returns:
            池子配置对象
        """
        active_count = await self.get_active_account_count()
        return self.calculate_pool_config(active_count)
