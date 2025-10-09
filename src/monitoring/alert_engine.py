"""
M6 Monitoring - 告警规则引擎
定义告警规则、检查条件、触发告警
"""

from typing import List, Dict, Any, Callable, Optional
from enum import Enum
from datetime import datetime
from dataclasses import dataclass

from src.monitoring.stats_aggregator import stats_aggregator
from src.core.logging import get_logger

logger = get_logger(__name__)


class AlertSeverity(str, Enum):
    """告警严重程度"""
    CRITICAL = "critical"  # 严重：系统无法正常工作
    WARNING = "warning"    # 警告：性能下降但仍可用
    INFO = "info"          # 信息：需要关注但不紧急


@dataclass
class Alert:
    """告警实例"""
    rule_name: str
    severity: AlertSeverity
    message: str
    value: float
    threshold: float
    timestamp: datetime
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "rule_name": self.rule_name,
            "severity": self.severity.value,
            "message": self.message,
            "value": self.value,
            "threshold": self.threshold,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class AlertRule:
    """告警规则"""
    name: str
    severity: AlertSeverity
    description: str
    condition: Callable[[], tuple[bool, float, float, str]]  # (is_triggered, value, threshold, message)
    cooldown_minutes: int = 5  # 冷却时间，避免重复告警


class AlertEngine:
    """
    告警规则引擎
    定义规则、检查条件、生成告警
    """

    def __init__(self):
        """初始化告警引擎"""
        self.stats = stats_aggregator
        self.rules: List[AlertRule] = []
        self.active_alerts: List[Alert] = []
        self.alert_history: List[Alert] = []
        self._last_alert_time: Dict[str, datetime] = {}

        # 注册默认规则
        self._register_default_rules()

    def _register_default_rules(self):
        """注册默认告警规则"""

        # 严重告警：账号池耗尽
        self.add_rule(AlertRule(
            name="account_pool_exhausted",
            severity=AlertSeverity.CRITICAL,
            description="可用账号数低于10个",
            condition=self._check_account_pool_exhausted,
            cooldown_minutes=10
        ))

        # 严重告警：发布成功率过低
        self.add_rule(AlertRule(
            name="publish_success_rate_low",
            severity=AlertSeverity.CRITICAL,
            description="发布成功率低于80%",
            condition=self._check_publish_success_rate,
            cooldown_minutes=10
        ))

        # 警告：账号可用性低
        self.add_rule(AlertRule(
            name="account_availability_low",
            severity=AlertSeverity.WARNING,
            description="账号可用性低于50%",
            condition=self._check_account_availability,
            cooldown_minutes=15
        ))

        # 警告：评论删除率高
        self.add_rule(AlertRule(
            name="comment_delete_rate_high",
            severity=AlertSeverity.WARNING,
            description="评论删除率高于5%",
            condition=self._check_comment_delete_rate,
            cooldown_minutes=30
        ))

        # 警告：筛选通过率异常低
        self.add_rule(AlertRule(
            name="screening_approval_rate_low",
            severity=AlertSeverity.WARNING,
            description="筛选通过率低于30%",
            condition=self._check_screening_approval_rate,
            cooldown_minutes=30
        ))

        # 信息：系统健康度下降
        self.add_rule(AlertRule(
            name="system_health_degraded",
            severity=AlertSeverity.INFO,
            description="系统健康评分低于80分",
            condition=self._check_system_health,
            cooldown_minutes=20
        ))

    def add_rule(self, rule: AlertRule):
        """添加告警规则"""
        self.rules.append(rule)
        logger.info(f"告警规则已注册: {rule.name} ({rule.severity.value})")

    def check_all_rules(self) -> List[Alert]:
        """
        检查所有告警规则

        Returns:
            触发的告警列表
        """
        triggered_alerts = []

        for rule in self.rules:
            try:
                # 检查冷却时间
                if not self._is_cooldown_expired(rule.name, rule.cooldown_minutes):
                    continue

                # 执行条件检查
                is_triggered, value, threshold, message = rule.condition()

                if is_triggered:
                    alert = Alert(
                        rule_name=rule.name,
                        severity=rule.severity,
                        message=message,
                        value=value,
                        threshold=threshold,
                        timestamp=datetime.now(),
                        metadata={"description": rule.description}
                    )

                    triggered_alerts.append(alert)
                    self._record_alert(alert)

                    logger.warning(
                        f"告警触发: {rule.name}",
                        severity=rule.severity.value,
                        message=message,
                        value=value,
                        threshold=threshold
                    )

            except Exception as e:
                logger.error(f"告警规则检查失败: {rule.name}", error=str(e))

        return triggered_alerts

    def get_active_alerts(self) -> List[Alert]:
        """获取当前活跃告警"""
        return self.active_alerts.copy()

    def get_alert_summary(self) -> Dict[str, Any]:
        """获取告警摘要"""
        critical_count = sum(1 for a in self.active_alerts if a.severity == AlertSeverity.CRITICAL)
        warning_count = sum(1 for a in self.active_alerts if a.severity == AlertSeverity.WARNING)
        info_count = sum(1 for a in self.active_alerts if a.severity == AlertSeverity.INFO)

        return {
            "total_active_alerts": len(self.active_alerts),
            "critical_alerts": critical_count,
            "warning_alerts": warning_count,
            "info_alerts": info_count,
            "alerts": [alert.to_dict() for alert in self.active_alerts]
        }

    # 告警条件检查方法

    def _check_account_pool_exhausted(self) -> tuple[bool, float, float, str]:
        """检查账号池是否耗尽"""
        account_stats = self.stats.get_account_pool_stats()
        available = account_stats['available_accounts']
        threshold = 10

        is_triggered = available < threshold
        message = f"可用账号仅剩{available}个，低于阈值{threshold}个" if is_triggered else ""

        return is_triggered, available, threshold, message

    def _check_publish_success_rate(self) -> tuple[bool, float, float, str]:
        """检查发布成功率"""
        publish_stats = self.stats.get_publishing_stats()
        success_rate = publish_stats['success_rate']
        threshold = 0.80

        is_triggered = success_rate < threshold and publish_stats['total_published'] > 10
        message = f"发布成功率{success_rate:.2%}低于阈值{threshold:.2%}" if is_triggered else ""

        return is_triggered, success_rate, threshold, message

    def _check_account_availability(self) -> tuple[bool, float, float, str]:
        """检查账号可用性"""
        account_stats = self.stats.get_account_pool_stats()
        availability = account_stats['availability_rate']
        threshold = 0.50

        is_triggered = availability < threshold and account_stats['total_accounts'] > 0
        message = f"账号可用性{availability:.2%}低于阈值{threshold:.2%}" if is_triggered else ""

        return is_triggered, availability, threshold, message

    def _check_comment_delete_rate(self) -> tuple[bool, float, float, str]:
        """检查评论删除率"""
        publish_stats = self.stats.get_publishing_stats()
        delete_rate = publish_stats['delete_rate']
        threshold = 0.05

        is_triggered = delete_rate > threshold and publish_stats['success'] > 20
        message = f"评论删除率{delete_rate:.2%}高于阈值{threshold:.2%}" if is_triggered else ""

        return is_triggered, delete_rate, threshold, message

    def _check_screening_approval_rate(self) -> tuple[bool, float, float, str]:
        """检查筛选通过率"""
        screening_stats = self.stats.get_screening_stats()
        approval_rate = screening_stats['approval_rate']
        threshold = 0.30

        is_triggered = approval_rate < threshold and screening_stats['total_screened'] > 20
        message = f"筛选通过率{approval_rate:.2%}低于阈值{threshold:.2%}" if is_triggered else ""

        return is_triggered, approval_rate, threshold, message

    def _check_system_health(self) -> tuple[bool, float, float, str]:
        """检查系统健康度"""
        health = self.stats.get_health_summary()
        health_score = health['score']
        threshold = 80.0

        is_triggered = health_score < threshold
        message = f"系统健康评分{health_score:.1f}分，低于阈值{threshold:.1f}分 ({health['status']})" if is_triggered else ""

        return is_triggered, health_score, threshold, message

    # 辅助方法

    def _is_cooldown_expired(self, rule_name: str, cooldown_minutes: int) -> bool:
        """检查冷却时间是否过期"""
        if rule_name not in self._last_alert_time:
            return True

        last_time = self._last_alert_time[rule_name]
        elapsed = (datetime.now() - last_time).total_seconds() / 60

        return elapsed >= cooldown_minutes

    def _record_alert(self, alert: Alert):
        """记录告警"""
        # 更新最后告警时间
        self._last_alert_time[alert.rule_name] = alert.timestamp

        # 添加到活跃告警
        # 移除同名旧告警
        self.active_alerts = [a for a in self.active_alerts if a.rule_name != alert.rule_name]
        self.active_alerts.append(alert)

        # 添加到历史记录（最多保留100条）
        self.alert_history.append(alert)
        if len(self.alert_history) > 100:
            self.alert_history.pop(0)

    def clear_alert(self, rule_name: str):
        """清除指定告警"""
        self.active_alerts = [a for a in self.active_alerts if a.rule_name != rule_name]
        logger.info(f"告警已清除: {rule_name}")


# 全局单例
alert_engine = AlertEngine()
