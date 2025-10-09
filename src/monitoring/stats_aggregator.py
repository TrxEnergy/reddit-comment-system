"""
M6 Monitoring - 业务统计聚合器
从各模块收集统计数据并计算派生指标
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from src.monitoring.metrics import metrics_collector
from src.core.logging import get_logger

logger = get_logger(__name__)


class StatsAggregator:
    """
    业务统计聚合器
    计算成功率、错误率、趋势等派生指标
    """

    def __init__(self):
        """初始化统计聚合器"""
        self.metrics = metrics_collector

    def get_discovery_stats(self) -> Dict[str, Any]:
        """
        获取M2发现模块统计

        Returns:
            发现统计字典
        """
        total_discovered = self.metrics._get_counter_value(self.metrics.posts_discovered)
        total_duplicate = self.metrics._get_counter_value(self.metrics.posts_duplicate)

        unique_posts = total_discovered - total_duplicate
        duplicate_rate = total_duplicate / total_discovered if total_discovered > 0 else 0.0

        return {
            "total_discovered": total_discovered,
            "unique_posts": unique_posts,
            "duplicate_posts": total_duplicate,
            "duplicate_rate": round(duplicate_rate, 4)
        }

    def get_screening_stats(self) -> Dict[str, Any]:
        """
        获取M3筛选模块统计

        Returns:
            筛选统计字典
        """
        total_screened = self.metrics._get_counter_value(self.metrics.posts_screened)
        approved = self.metrics._get_counter_value(
            self.metrics.posts_screened,
            {'decision': 'approved'}
        )
        rejected = self.metrics._get_counter_value(
            self.metrics.posts_screened,
            {'decision': 'rejected'}
        )

        approval_rate = approved / total_screened if total_screened > 0 else 0.0

        # 获取拒绝原因分布（需要从Prometheus samples中提取）
        rejection_reasons = self._get_rejection_reasons_distribution()

        return {
            "total_screened": total_screened,
            "approved": approved,
            "rejected": rejected,
            "approval_rate": round(approval_rate, 4),
            "rejection_rate": round(1 - approval_rate, 4),
            "rejection_reasons": rejection_reasons
        }

    def get_generation_stats(self) -> Dict[str, Any]:
        """
        获取M4生成模块统计

        Returns:
            生成统计字典
        """
        total_generated = self.metrics._get_counter_value(self.metrics.comments_generated)
        total_failures = self.metrics._get_counter_value(self.metrics.generation_failures)

        total_attempts = total_generated + total_failures
        success_rate = total_generated / total_attempts if total_attempts > 0 else 0.0

        return {
            "total_generated": total_generated,
            "total_failures": total_failures,
            "success_rate": round(success_rate, 4),
            "failure_rate": round(1 - success_rate, 4)
        }

    def get_publishing_stats(self) -> Dict[str, Any]:
        """
        获取M5发布模块统计

        Returns:
            发布统计字典
        """
        total_published = self.metrics._get_counter_value(self.metrics.comments_published)
        success = self.metrics._get_counter_value(
            self.metrics.comments_published,
            {'status': 'success'}
        )
        failed = self.metrics._get_counter_value(
            self.metrics.comments_published,
            {'status': 'failed'}
        )
        deleted = self.metrics._get_counter_value(self.metrics.comments_deleted)

        success_rate = success / total_published if total_published > 0 else 0.0
        delete_rate = deleted / success if success > 0 else 0.0

        # 获取失败原因分布
        failure_reasons = self._get_publish_failure_reasons()

        return {
            "total_published": total_published,
            "success": success,
            "failed": failed,
            "deleted": deleted,
            "success_rate": round(success_rate, 4),
            "failure_rate": round(1 - success_rate, 4),
            "delete_rate": round(delete_rate, 4),
            "failure_reasons": failure_reasons
        }

    def get_account_pool_stats(self) -> Dict[str, Any]:
        """
        获取账号池统计

        Returns:
            账号池统计字典
        """
        total = self.metrics._get_gauge_value(self.metrics.total_accounts)
        available = self.metrics._get_gauge_value(self.metrics.available_accounts)
        locked = self.metrics._get_gauge_value(self.metrics.locked_accounts)
        quota_exhausted = self.metrics._get_gauge_value(self.metrics.quota_exhausted_accounts)

        availability_rate = available / total if total > 0 else 0.0
        utilization_rate = (locked + quota_exhausted) / total if total > 0 else 0.0

        return {
            "total_accounts": total,
            "available_accounts": available,
            "locked_accounts": locked,
            "quota_exhausted_accounts": quota_exhausted,
            "availability_rate": round(availability_rate, 4),
            "utilization_rate": round(utilization_rate, 4)
        }

    def get_performance_stats(self) -> Dict[str, Any]:
        """
        获取性能统计（基于Histogram）

        Returns:
            性能统计字典
        """
        # Histogram的统计值需要从samples中提取
        screening_stats = self._get_histogram_stats(self.metrics.screening_duration)
        generation_stats = self._get_histogram_stats(self.metrics.generation_duration)
        publishing_stats = self._get_histogram_stats(self.metrics.publishing_duration)

        return {
            "screening": screening_stats,
            "generation": generation_stats,
            "publishing": publishing_stats
        }

    def get_health_summary(self) -> Dict[str, Any]:
        """
        获取系统健康摘要

        Returns:
            健康摘要字典
        """
        account_stats = self.get_account_pool_stats()
        publishing_stats = self.get_publishing_stats()

        # 健康评分逻辑
        health_score = 100.0

        # 账号池健康度（权重40%）
        if account_stats['availability_rate'] < 0.3:
            health_score -= 40
        elif account_stats['availability_rate'] < 0.5:
            health_score -= 20

        # 发布成功率（权重40%）
        if publishing_stats['success_rate'] < 0.8:
            health_score -= 40
        elif publishing_stats['success_rate'] < 0.9:
            health_score -= 20

        # 删除率（权重20%）
        if publishing_stats['delete_rate'] > 0.1:
            health_score -= 20
        elif publishing_stats['delete_rate'] > 0.05:
            health_score -= 10

        health_status = "healthy" if health_score >= 80 else "degraded" if health_score >= 60 else "unhealthy"

        return {
            "status": health_status,
            "score": health_score,
            "account_availability": account_stats['availability_rate'],
            "publish_success_rate": publishing_stats['success_rate'],
            "delete_rate": publishing_stats['delete_rate'],
            "timestamp": datetime.now().isoformat()
        }

    def get_full_stats(self) -> Dict[str, Any]:
        """
        获取完整统计数据

        Returns:
            完整统计字典
        """
        return {
            "health": self.get_health_summary(),
            "discovery": self.get_discovery_stats(),
            "screening": self.get_screening_stats(),
            "generation": self.get_generation_stats(),
            "publishing": self.get_publishing_stats(),
            "accounts": self.get_account_pool_stats(),
            "performance": self.get_performance_stats(),
            "timestamp": datetime.now().isoformat()
        }

    # 辅助方法

    def _get_rejection_reasons_distribution(self) -> Dict[str, int]:
        """获取拒绝原因分布"""
        try:
            reasons = {}
            for sample in self.metrics.screening_rejection_reasons.collect()[0].samples:
                if sample.name.endswith('_total'):
                    reason = sample.labels.get('reason', 'unknown')
                    reasons[reason] = int(sample.value)
            return reasons
        except:
            return {}

    def _get_publish_failure_reasons(self) -> Dict[str, int]:
        """获取发布失败原因分布"""
        try:
            reasons = {}
            for sample in self.metrics.publish_failures.collect()[0].samples:
                if sample.name.endswith('_total'):
                    error_type = sample.labels.get('error_type', 'unknown')
                    reasons[error_type] = int(sample.value)
            return reasons
        except:
            return {}

    def _get_histogram_stats(self, histogram) -> Dict[str, float]:
        """
        从Histogram中提取统计信息

        Args:
            histogram: Prometheus Histogram对象

        Returns:
            统计字典 {count, sum, avg}
        """
        try:
            samples = list(histogram.collect()[0].samples)

            count = 0
            total = 0.0

            for sample in samples:
                if sample.name.endswith('_count'):
                    count = int(sample.value)
                elif sample.name.endswith('_sum'):
                    total = sample.value

            avg = total / count if count > 0 else 0.0

            return {
                "count": count,
                "total_seconds": round(total, 2),
                "average_seconds": round(avg, 2)
            }
        except:
            return {"count": 0, "total_seconds": 0.0, "average_seconds": 0.0}


# 全局单例
stats_aggregator = StatsAggregator()
