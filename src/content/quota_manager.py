"""
M4内容工厂 - 配额管理器
负责管理账户日配额、Persona冷却、子版冷却
"""

from datetime import datetime, timedelta
from typing import Dict, Optional
from collections import defaultdict

from src.content.models import QuotaStatus
from src.core.logging import get_logger

logger = get_logger(__name__)


class QuotaManager:
    """
    配额管理器
    管理三层配额：账户级（1条/天）、Persona级、子版级
    """

    def __init__(
        self,
        account_daily_limit: int = 1,
        window_type: str = "rolling"
    ):
        """
        初始化配额管理器

        Args:
            account_daily_limit: 账户日配额限制
            window_type: 窗口类型（rolling滚动24h/calendar自然日）
        """
        self.account_daily_limit = account_daily_limit
        self.window_type = window_type

        # 账户使用记录 {account_id: [timestamp, ...]}
        self.account_usage: Dict[str, list] = defaultdict(list)

    def check_account_quota(self, account_id: str) -> bool:
        """
        检查账户是否还有配额

        Args:
            account_id: 账户ID

        Returns:
            是否有配额可用
        """
        status = self.get_account_status(account_id)
        return status.remaining > 0

    def get_account_status(self, account_id: str) -> QuotaStatus:
        """
        获取账户配额状态

        Args:
            account_id: 账户ID

        Returns:
            QuotaStatus对象
        """
        now = datetime.now()

        if self.window_type == "rolling":
            # 滚动24小时窗口
            window_start = now - timedelta(hours=24)
        else:
            # 自然日窗口（今天0点）
            window_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # 统计窗口内使用次数
        usage_timestamps = self.account_usage.get(account_id, [])
        daily_used = sum(1 for ts in usage_timestamps if ts >= window_start)

        return QuotaStatus(
            account_id=account_id,
            daily_used=daily_used,
            daily_limit=self.account_daily_limit,
            window_start=window_start,
            remaining=0  # 会自动计算
        )

    def mark_account_used(self, account_id: str):
        """
        记录账户使用（发布成功后调用）

        Args:
            account_id: 账户ID
        """
        self.account_usage[account_id].append(datetime.now())

        logger.info(
            "Marked account used",
            account_id=account_id,
            total_usage=len(self.account_usage[account_id])
        )

    def reset_account_quota(self, account_id: str):
        """重置账户配额（测试/调试用）"""
        if account_id in self.account_usage:
            del self.account_usage[account_id]
            logger.info(f"Reset quota for account: {account_id}")

    def get_all_statuses(self) -> Dict[str, QuotaStatus]:
        """
        获取所有账户的配额状态

        Returns:
            {account_id: QuotaStatus}
        """
        return {
            account_id: self.get_account_status(account_id)
            for account_id in self.account_usage.keys()
        }

    def cleanup_old_records(self, days: int = 7):
        """
        清理旧记录

        Args:
            days: 保留天数
        """
        cutoff = datetime.now() - timedelta(days=days)

        for account_id in list(self.account_usage.keys()):
            timestamps = self.account_usage[account_id]
            # 保留cutoff之后的记录
            self.account_usage[account_id] = [
                ts for ts in timestamps if ts >= cutoff
            ]

            # 如果无记录，删除key
            if not self.account_usage[account_id]:
                del self.account_usage[account_id]

        logger.info(f"Cleaned up records older than {days} days")
