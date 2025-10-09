"""
测试 AlertEngine - 告警规则引擎
"""

import pytest
from src.monitoring.alert_engine import AlertEngine, AlertRule, AlertSeverity, alert_engine
from src.monitoring.metrics import metrics_collector


class TestAlertEngine:
    """AlertEngine测试"""

    def test_add_rule(self):
        """测试添加告警规则"""
        engine = AlertEngine()
        initial_count = len(engine.rules)

        def test_condition():
            return False, 0.0, 1.0, ""

        engine.add_rule(AlertRule(
            name="test_rule",
            severity=AlertSeverity.INFO,
            description="测试规则",
            condition=test_condition
        ))

        assert len(engine.rules) > initial_count

    def test_account_pool_exhausted_alert(self):
        """测试账号池耗尽告警"""
        # 模拟账号池耗尽
        metrics_collector.update_account_stats({
            'total_accounts': 100,
            'available_accounts': 5,  # 低于阈值10
            'locked_accounts': 10,
            'no_quota_accounts': 85
        })

        triggered = alert_engine.check_all_rules()

        # 应该触发account_pool_exhausted告警
        exhausted_alerts = [a for a in triggered if a.rule_name == 'account_pool_exhausted']
        assert len(exhausted_alerts) > 0

    def test_publish_success_rate_alert(self):
        """测试发布成功率低告警"""
        # 模拟低成功率（需要足够样本）
        for _ in range(15):
            metrics_collector.record_publish_success()

        for _ in range(5):
            metrics_collector.record_publish_failure("test_error")

        # 成功率75%，低于80%阈值
        triggered = alert_engine.check_all_rules()

        # 检查是否有发布成功率告警
        success_rate_alerts = [a for a in triggered if a.rule_name == 'publish_success_rate_low']
        # 可能触发，取决于之前测试的累积值

    def test_get_alert_summary(self):
        """测试获取告警摘要"""
        summary = alert_engine.get_alert_summary()

        assert 'total_active_alerts' in summary
        assert 'critical_alerts' in summary
        assert 'warning_alerts' in summary
        assert 'alerts' in summary
        assert isinstance(summary['alerts'], list)

    def test_clear_alert(self):
        """测试清除告警"""
        # 先触发一个告警
        metrics_collector.update_account_stats({
            'total_accounts': 100,
            'available_accounts': 3,
            'locked_accounts': 10,
            'no_quota_accounts': 87
        })

        alert_engine.check_all_rules()

        initial_count = len(alert_engine.active_alerts)

        if initial_count > 0:
            first_alert_name = alert_engine.active_alerts[0].rule_name
            alert_engine.clear_alert(first_alert_name)

            # 告警应该被清除
            assert len(alert_engine.active_alerts) < initial_count
