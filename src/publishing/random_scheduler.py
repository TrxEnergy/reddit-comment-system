"""
M5 Publishing - 完全随机时间调度器
负责为0-200个账号分配完全随机的发布时间（6:00-02:00窗口）
"""

import random
from datetime import datetime, timedelta, time
from typing import List, Dict, Tuple
from collections import defaultdict

from src.core.logging import get_logger

logger = get_logger(__name__)


class UniformRandomScheduler:
    """
    完全随机时间调度器
    确保每个账号在活跃窗口内随机发布1条评论，无时间模式
    """

    # 活跃窗口：6:00-02:00（跨日，共20小时）
    WINDOW_START_HOUR = 6
    WINDOW_END_HOUR = 2  # 次日2点

    # 微扰动范围（±5分钟）
    MICRO_PERTURBATION_MINUTES = 5

    def __init__(self, seed: int = None):
        """
        初始化随机调度器

        Args:
            seed: 随机种子（可选，用于测试）
        """
        if seed is not None:
            random.seed(seed)

    def schedule_accounts(
        self,
        account_ids: List[str],
        base_date: datetime = None
    ) -> Dict[str, datetime]:
        """
        为所有账号分配随机发布时间

        Args:
            account_ids: 账号ID列表
            base_date: 基准日期（默认今天）

        Returns:
            {account_id: scheduled_time}
        """
        if base_date is None:
            base_date = datetime.now()

        # 确保base_date是当天0点
        base_date = base_date.replace(hour=0, minute=0, second=0, microsecond=0)

        schedule = {}

        for account_id in account_ids:
            scheduled_time = self._generate_random_time(base_date)
            schedule[account_id] = scheduled_time

        logger.info(
            "随机调度完成",
            total_accounts=len(account_ids),
            date=base_date.date().isoformat()
        )

        return schedule

    def _generate_random_time(self, base_date: datetime) -> datetime:
        """
        在活跃窗口内生成完全随机的时间点

        Args:
            base_date: 基准日期（当天0点）

        Returns:
            随机时间点
        """
        # 6:00-23:59（今天）
        if random.random() < 0.85:  # 85%概率在今天
            start_hour = self.WINDOW_START_HOUR
            end_hour = 24

            random_hour = random.randint(start_hour, end_hour - 1)
            random_minute = random.randint(0, 59)
            random_second = random.randint(0, 59)

            scheduled_time = base_date.replace(
                hour=random_hour,
                minute=random_minute,
                second=random_second
            )

        # 00:00-02:00（次日）
        else:  # 15%概率在次日凌晨
            next_day = base_date + timedelta(days=1)

            random_hour = random.randint(0, self.WINDOW_END_HOUR)
            random_minute = random.randint(0, 59)
            random_second = random.randint(0, 59)

            scheduled_time = next_day.replace(
                hour=random_hour,
                minute=random_minute,
                second=random_second
            )

        # 添加微扰动（±5分钟）
        perturbation_seconds = random.randint(
            -self.MICRO_PERTURBATION_MINUTES * 60,
            self.MICRO_PERTURBATION_MINUTES * 60
        )
        scheduled_time += timedelta(seconds=perturbation_seconds)

        return scheduled_time

    def get_pending_tasks(
        self,
        schedule: Dict[str, datetime],
        now: datetime = None
    ) -> List[str]:
        """
        获取当前应该执行的任务列表

        Args:
            schedule: 调度表
            now: 当前时间（默认datetime.now()）

        Returns:
            应该执行的账号ID列表
        """
        if now is None:
            now = datetime.now()

        pending = []

        for account_id, scheduled_time in schedule.items():
            if scheduled_time <= now:
                pending.append(account_id)

        return pending

    def validate_schedule_distribution(
        self,
        schedule: Dict[str, datetime]
    ) -> Dict[str, any]:
        """
        统计验证调度分布（用于测试和监控）

        Args:
            schedule: 调度表

        Returns:
            统计信息字典
        """
        if not schedule:
            return {"error": "空调度表"}

        times = list(schedule.values())

        # 按小时分组统计
        hour_distribution = defaultdict(int)
        for t in times:
            hour_distribution[t.hour] += 1

        # 计算分布均匀性（标准差）
        counts = list(hour_distribution.values())
        mean_count = sum(counts) / len(counts)
        variance = sum((x - mean_count) ** 2 for x in counts) / len(counts)
        std_dev = variance ** 0.5

        # 计算熵（信息熵，越高越随机）
        total = len(times)
        entropy = 0
        for count in counts:
            if count > 0:
                p = count / total
                entropy -= p * (p ** 0.5)  # 简化熵计算

        return {
            "total_accounts": len(schedule),
            "hour_distribution": dict(sorted(hour_distribution.items())),
            "std_dev": round(std_dev, 2),
            "entropy": round(entropy, 4),
            "uniformity_score": round(1 / (1 + std_dev), 4)  # 0-1分数，越接近1越均匀
        }

    def reschedule_failed_account(
        self,
        account_id: str,
        current_schedule: Dict[str, datetime],
        retry_after_minutes: int = 30
    ) -> datetime:
        """
        为失败的账号重新安排时间

        Args:
            account_id: 账号ID
            current_schedule: 当前调度表
            retry_after_minutes: 重试延迟（分钟）

        Returns:
            新的调度时间
        """
        now = datetime.now()
        new_time = now + timedelta(minutes=retry_after_minutes)

        # 确保新时间在活跃窗口内
        if not self._is_in_active_window(new_time):
            # 如果不在窗口内，推迟到次日早上6点
            next_day = (now + timedelta(days=1)).replace(
                hour=self.WINDOW_START_HOUR,
                minute=0,
                second=0,
                microsecond=0
            )
            new_time = next_day

        current_schedule[account_id] = new_time

        logger.info(
            "账号重新调度",
            account_id=account_id,
            new_time=new_time.isoformat(),
            retry_after_minutes=retry_after_minutes
        )

        return new_time

    def _is_in_active_window(self, dt: datetime) -> bool:
        """
        检查时间是否在活跃窗口内

        Args:
            dt: 待检查时间

        Returns:
            是否在窗口内
        """
        hour = dt.hour

        # 6:00-23:59 或 00:00-02:00
        return hour >= self.WINDOW_START_HOUR or hour <= self.WINDOW_END_HOUR

    def get_next_batch(
        self,
        schedule: Dict[str, datetime],
        batch_size: int = 10,
        now: datetime = None
    ) -> List[Tuple[str, datetime]]:
        """
        获取下一批待执行任务（按时间排序）

        Args:
            schedule: 调度表
            batch_size: 批次大小
            now: 当前时间

        Returns:
            [(account_id, scheduled_time), ...]
        """
        if now is None:
            now = datetime.now()

        # 筛选已到期的任务
        pending = [
            (account_id, scheduled_time)
            for account_id, scheduled_time in schedule.items()
            if scheduled_time <= now
        ]

        # 按时间排序
        pending.sort(key=lambda x: x[1])

        # 返回前N个
        return pending[:batch_size]
