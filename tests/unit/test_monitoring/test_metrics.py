"""
测试 MetricsCollector - Prometheus指标收集器
"""

import pytest
from src.monitoring.metrics import MetricsCollector, metrics_collector


class TestMetricsCollector:
    """MetricsCollector测试"""

    def test_singleton(self):
        """测试单例模式"""
        collector1 = MetricsCollector()
        collector2 = MetricsCollector()

        assert collector1 is collector2
        assert collector1 is metrics_collector

    def test_record_post_discovered(self):
        """测试记录发现的帖子"""
        initial_value = metrics_collector._get_counter_value(metrics_collector.posts_discovered)

        metrics_collector.record_post_discovered("test_subreddit", "reddit_api")

        new_value = metrics_collector._get_counter_value(metrics_collector.posts_discovered)
        assert new_value >= initial_value

    def test_record_screening_result(self):
        """测试记录筛选结果"""
        metrics_collector.record_screening_result(approved=True)
        metrics_collector.record_screening_result(approved=False, rejection_reason="low_relevance")

        snapshot = metrics_collector.get_snapshot()
        assert snapshot['screening']['total_screened'] >= 2

    def test_record_publish_success(self):
        """测试记录发布成功"""
        initial_success = metrics_collector._get_counter_value(
            metrics_collector.comments_published,
            {'status': 'success'}
        )

        metrics_collector.record_publish_success()

        new_success = metrics_collector._get_counter_value(
            metrics_collector.comments_published,
            {'status': 'success'}
        )

        assert new_success >= initial_success

    def test_update_account_stats(self):
        """测试更新账号池统计"""
        metrics_collector.update_account_stats({
            'total_accounts': 100,
            'available_accounts': 80,
            'locked_accounts': 5,
            'no_quota_accounts': 15
        })

        snapshot = metrics_collector.get_snapshot()
        assert snapshot['accounts']['total'] == 100
        assert snapshot['accounts']['available'] == 80

    def test_get_snapshot(self):
        """测试获取指标快照"""
        snapshot = metrics_collector.get_snapshot()

        assert 'discovery' in snapshot
        assert 'screening' in snapshot
        assert 'generation' in snapshot
        assert 'publishing' in snapshot
        assert 'accounts' in snapshot
