"""
智能筛选流程主编排器
协调L1快速筛选、L2深度筛选和成本守护的完整流程
"""

import time
from typing import List, Optional

from src.core.logging import get_logger
from src.discovery.models import RawPost
from src.screening.models import (
    PoolConfig,
    ScreeningResult,
    ScreeningStats,
    FilterDecision
)
from src.screening.dynamic_pool_calculator import DynamicPoolCalculator
from src.screening.l1_fast_filter import L1FastFilter
from src.screening.l2_deep_filter import L2DeepFilter
from src.screening.cost_guard import CostGuard

logger = get_logger(__name__)


class ScreeningPipeline:
    """智能筛选流程主编排器"""

    def __init__(
        self,
        pool_calculator: DynamicPoolCalculator,
        l1_filter: L1FastFilter,
        l2_filter: L2DeepFilter,
        cost_guard: CostGuard
    ):
        """
        初始化筛选流程

        Args:
            pool_calculator: 动态池子计算器
            l1_filter: L1快速筛选器
            l2_filter: L2深度筛选器
            cost_guard: 成本守护器
        """
        self.pool_calculator = pool_calculator
        self.l1_filter = l1_filter
        self.l2_filter = l2_filter
        self.cost_guard = cost_guard

        logger.info("筛选流程初始化完成")

    async def run(
        self,
        raw_posts: List[RawPost],
        pool_config: Optional[PoolConfig] = None
    ) -> ScreeningResult:
        """
        执行完整筛选流程

        Args:
            raw_posts: 原始帖子列表（来自M2发现引擎）
            pool_config: 池子配置（如果为None则自动计算）

        Returns:
            筛选结果对象
        """
        overall_start_time = time.time()

        if pool_config is None:
            logger.info("自动计算池子配置...")
            pool_config = await self.pool_calculator.calculate_pool_config_async()

        logger.info(
            f"开始筛选流程 - 输入:{len(raw_posts)}帖, "
            f"活跃账号:{pool_config.active_accounts}, "
            f"池子规模:{pool_config.pool_size}"
        )

        l1_start_time = time.time()
        l1_results_list = self.l1_filter.filter_posts(raw_posts)
        l1_processing_time = time.time() - l1_start_time

        l1_results_map = {r.post_id: r for r in l1_results_list}

        direct_pass_posts = [
            post for post in raw_posts
            if l1_results_map.get(post.post_id, None) and
            l1_results_map[post.post_id].decision == FilterDecision.DIRECT_PASS
        ]

        l2_candidate_posts = [
            post for post in raw_posts
            if l1_results_map.get(post.post_id, None) and
            l1_results_map[post.post_id].decision == FilterDecision.SEND_TO_L2
        ]

        l2_results_list = []
        l2_processing_time = 0.0
        l2_total_cost = 0.0

        if l2_candidate_posts:
            if not self.cost_guard.can_proceed():
                logger.warning(
                    "⚠️ 成本守护熔断！跳过L2筛选 - "
                    f"日成本:${self.cost_guard.daily_cost:.4f}/{self.cost_guard.daily_limit}, "
                    f"月成本:${self.cost_guard.monthly_cost:.4f}/{self.cost_guard.monthly_limit}"
                )
            else:
                logger.info(f"开始L2深度筛选 - 候选:{len(l2_candidate_posts)}帖")

                l2_start_time = time.time()
                l2_results_list = await self.l2_filter.filter_posts(
                    l2_candidate_posts,
                    l1_results_map,
                    pool_config.active_accounts
                )
                l2_processing_time = time.time() - l2_start_time

                l2_total_cost = sum(r.api_cost for r in l2_results_list)
                self.cost_guard.add_cost(l2_total_cost)

                logger.info(f"L2成本已记录: ${l2_total_cost:.4f}")

        l2_results_map = {r.post_id: r for r in l2_results_list}

        l2_pass_posts = [
            post for post in l2_candidate_posts
            if l2_results_map.get(post.post_id, None) and
            l2_results_map[post.post_id].decision == FilterDecision.L2_PASS
        ]

        final_posts = direct_pass_posts + l2_pass_posts
        final_post_ids = [p.post_id for p in final_posts]

        total_processing_time = time.time() - overall_start_time

        stats = ScreeningStats(
            total_input=len(raw_posts),
            l1_direct_pass=len(direct_pass_posts),
            l1_sent_to_l2=len(l2_candidate_posts),
            l1_direct_reject=len(raw_posts) - len(direct_pass_posts) - len(l2_candidate_posts),
            l1_processing_time_s=l1_processing_time,
            l2_pass=len(l2_pass_posts),
            l2_reject=len(l2_candidate_posts) - len(l2_pass_posts),
            l2_processing_time_s=l2_processing_time,
            l2_total_cost=l2_total_cost,
            final_output=len(final_posts),
            total_processing_time_s=total_processing_time,
            pool_utilization_rate=len(final_posts) / pool_config.pool_size if pool_config.pool_size > 0 else 0.0
        )

        result = ScreeningResult(
            pool_config=pool_config,
            stats=stats,
            passed_post_ids=final_post_ids,
            l1_results=l1_results_map,
            l2_results=l2_results_map
        )

        logger.info(f"筛选流程完成 - {stats.get_summary()}")

        return result
