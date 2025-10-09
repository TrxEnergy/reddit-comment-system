"""
成本守护器
实时追踪L2 API调用成本并实施熔断机制
"""

import json
from pathlib import Path
from datetime import datetime, date
from typing import Optional

from src.core.logging import get_logger
from src.screening.models import CostGuardStatus

logger = get_logger(__name__)


class CostGuard:
    """成本守护器 - L2成本追踪和熔断"""

    def __init__(
        self,
        daily_limit: float = 0.50,
        monthly_limit: float = 15.0,
        storage_path: Optional[Path] = None
    ):
        """
        初始化成本守护器

        Args:
            daily_limit: 日成本上限（美元）
            monthly_limit: 月成本上限（美元）
            storage_path: 成本数据存储路径
        """
        self.daily_limit = daily_limit
        self.monthly_limit = monthly_limit

        if storage_path is None:
            storage_path = Path("data/cost_tracking.json")
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        self.daily_cost = 0.0
        self.monthly_cost = 0.0
        self.last_reset_date = date.today()

        self._load_state()

        logger.info(
            f"成本守护器初始化 - 日限:${daily_limit}, 月限:${monthly_limit}, "
            f"当前日成本:${self.daily_cost:.4f}"
        )

    def _load_state(self):
        """从存储加载成本状态"""
        if not self.storage_path.exists():
            logger.debug(f"成本追踪文件不存在，使用初始状态: {self.storage_path}")
            return

        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            saved_date = date.fromisoformat(data.get('last_reset_date', str(date.today())))
            current_date = date.today()

            if saved_date.month != current_date.month:
                logger.info("跨月检测，重置月成本")
                self.monthly_cost = 0.0
                self.daily_cost = 0.0
            elif saved_date != current_date:
                logger.info("跨日检测，重置日成本")
                self.monthly_cost = data.get('monthly_cost', 0.0)
                self.daily_cost = 0.0
            else:
                self.daily_cost = data.get('daily_cost', 0.0)
                self.monthly_cost = data.get('monthly_cost', 0.0)

            self.last_reset_date = current_date

            logger.info(f"成本状态加载成功 - 日:${self.daily_cost:.4f}, 月:${self.monthly_cost:.4f}")

        except Exception as e:
            logger.error(f"加载成本状态失败: {e}，使用初始状态")

    def _save_state(self):
        """保存成本状态到存储"""
        try:
            data = {
                'daily_cost': self.daily_cost,
                'monthly_cost': self.monthly_cost,
                'last_reset_date': str(self.last_reset_date),
                'updated_at': datetime.now().isoformat()
            }

            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"保存成本状态失败: {e}")

    def add_cost(self, amount: float):
        """
        添加成本记录

        Args:
            amount: 成本金额（美元）
        """
        current_date = date.today()

        if current_date.month != self.last_reset_date.month:
            logger.info("跨月检测，重置月成本")
            self.monthly_cost = 0.0
            self.daily_cost = 0.0
            self.last_reset_date = current_date
        elif current_date != self.last_reset_date:
            logger.info("跨日检测，重置日成本")
            self.daily_cost = 0.0
            self.last_reset_date = current_date

        self.daily_cost += amount
        self.monthly_cost += amount

        self._save_state()

        logger.debug(f"成本记录添加: +${amount:.4f}, 日总计:${self.daily_cost:.4f}, 月总计:${self.monthly_cost:.4f}")

        if self.is_daily_exceeded():
            logger.warning(f"⚠️ 日成本超限! ${self.daily_cost:.4f} > ${self.daily_limit}")
        if self.is_monthly_exceeded():
            logger.warning(f"⚠️ 月成本超限! ${self.monthly_cost:.4f} > ${self.monthly_limit}")

    def is_daily_exceeded(self) -> bool:
        """检查是否超过日成本限制"""
        return self.daily_cost >= self.daily_limit

    def is_monthly_exceeded(self) -> bool:
        """检查是否超过月成本限制"""
        return self.monthly_cost >= self.monthly_limit

    def can_proceed(self) -> bool:
        """检查是否可以继续调用L2 API"""
        return not (self.is_daily_exceeded() or self.is_monthly_exceeded())

    def get_status(self) -> CostGuardStatus:
        """
        获取当前成本守护状态

        Returns:
            成本守护状态对象
        """
        return CostGuardStatus(
            daily_cost=self.daily_cost,
            monthly_cost=self.monthly_cost,
            daily_limit=self.daily_limit,
            monthly_limit=self.monthly_limit,
            is_daily_exceeded=self.is_daily_exceeded(),
            is_monthly_exceeded=self.is_monthly_exceeded(),
            remaining_daily_budget=max(0.0, self.daily_limit - self.daily_cost),
            last_reset_date=datetime.combine(self.last_reset_date, datetime.min.time())
        )

    def reset_daily(self):
        """手动重置日成本（用于测试）"""
        self.daily_cost = 0.0
        self.last_reset_date = date.today()
        self._save_state()
        logger.info("日成本已手动重置")

    def reset_monthly(self):
        """手动重置月成本（用于测试）"""
        self.monthly_cost = 0.0
        self.daily_cost = 0.0
        self.last_reset_date = date.today()
        self._save_state()
        logger.info("月成本已手动重置")
