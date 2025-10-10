import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional

from .config import BudgetConfig


@dataclass
class BudgetStatus:
    """预算状态"""

    posts_fetched: int = 0
    api_calls_made: int = 0
    runtime_seconds: float = 0.0
    start_time: float = field(default_factory=time.time)

    posts_limit: int = 0
    api_calls_limit: int = 0
    runtime_limit_seconds: float = 0.0

    exceeded: bool = False
    exceeded_reason: str = ""

    @property
    def posts_remaining(self) -> int:
        return max(0, self.posts_limit - self.posts_fetched)

    @property
    def api_calls_remaining(self) -> int:
        return max(0, self.api_calls_limit - self.api_calls_made)

    @property
    def runtime_remaining_seconds(self) -> float:
        elapsed = time.time() - self.start_time
        return max(0.0, self.runtime_limit_seconds - elapsed)

    @property
    def posts_usage_percent(self) -> float:
        if self.posts_limit == 0:
            return 0.0
        return (self.posts_fetched / self.posts_limit) * 100

    @property
    def api_calls_usage_percent(self) -> float:
        if self.api_calls_limit == 0:
            return 0.0
        return (self.api_calls_made / self.api_calls_limit) * 100

    @property
    def runtime_usage_percent(self) -> float:
        if self.runtime_limit_seconds == 0:
            return 0.0
        elapsed = time.time() - self.start_time
        return (elapsed / self.runtime_limit_seconds) * 100

    def to_dict(self) -> Dict:
        return {
            "posts_fetched": self.posts_fetched,
            "posts_limit": self.posts_limit,
            "posts_remaining": self.posts_remaining,
            "posts_usage_percent": f"{self.posts_usage_percent:.1f}%",
            "api_calls_made": self.api_calls_made,
            "api_calls_limit": self.api_calls_limit,
            "api_calls_remaining": self.api_calls_remaining,
            "api_calls_usage_percent": f"{self.api_calls_usage_percent:.1f}%",
            "runtime_seconds": f"{self.runtime_seconds:.1f}s",
            "runtime_limit_seconds": f"{self.runtime_limit_seconds:.1f}s",
            "runtime_remaining_seconds": f"{self.runtime_remaining_seconds:.1f}s",
            "runtime_usage_percent": f"{self.runtime_usage_percent:.1f}%",
            "exceeded": self.exceeded,
            "exceeded_reason": self.exceeded_reason,
        }


class BudgetManager:
    """预算管理系统"""

    def __init__(self, config: BudgetConfig):
        self.config = config
        self.status = BudgetStatus(
            posts_limit=config.max_posts_per_run,
            api_calls_limit=config.max_api_calls,
            runtime_limit_seconds=config.max_runtime_minutes * 60,
        )

    def track_posts(self, count: int):
        """跟踪帖子数"""
        self.status.posts_fetched += count

        if self.config.enable_budget_tracking:
            self._check_budget()

    def track_api_call(self, count: int = 1):
        """跟踪API调用"""
        self.status.api_calls_made += count

        if self.config.enable_budget_tracking:
            self._check_budget()

    def update_runtime(self):
        """更新运行时间"""
        self.status.runtime_seconds = time.time() - self.status.start_time

        if self.config.enable_budget_tracking:
            self._check_budget()

    def _check_budget(self):
        """检查预算是否超标"""

        if self.status.posts_fetched >= self.status.posts_limit:
            self.status.exceeded = True
            self.status.exceeded_reason = (
                f"帖子数超标: {self.status.posts_fetched}/{self.status.posts_limit}"
            )
            return

        if self.status.api_calls_made >= self.status.api_calls_limit:
            self.status.exceeded = True
            self.status.exceeded_reason = f"API调用超标: {self.status.api_calls_made}/{self.status.api_calls_limit}"
            return

        elapsed = time.time() - self.status.start_time
        if elapsed >= self.status.runtime_limit_seconds:
            self.status.exceeded = True
            self.status.exceeded_reason = (
                f"运行时间超标: {elapsed:.1f}s/{self.status.runtime_limit_seconds:.1f}s"
            )
            return

    def is_budget_exceeded(self) -> bool:
        """检查预算是否已超"""
        self.update_runtime()
        return self.status.exceeded

    def should_stop(self) -> bool:
        """是否应该停止（基于配置）"""
        if not self.config.stop_on_budget_exceeded:
            return False

        return self.is_budget_exceeded()

    def get_status(self) -> BudgetStatus:
        """获取预算状态"""
        self.update_runtime()
        return self.status

    def get_stats(self) -> Dict:
        """获取统计信息"""
        self.update_runtime()
        return self.status.to_dict()

    def reset(self):
        """重置预算"""
        self.status = BudgetStatus(
            posts_limit=self.config.max_posts_per_run,
            api_calls_limit=self.config.max_api_calls,
            runtime_limit_seconds=self.config.max_runtime_minutes * 60,
        )

    def print_status(self):
        """打印预算状态"""
        self.update_runtime()

        print("\n=== 预算状态 ===")
        print(
            f"帖子: {self.status.posts_fetched}/{self.status.posts_limit} ({self.status.posts_usage_percent:.1f}%)"
        )
        print(
            f"API调用: {self.status.api_calls_made}/{self.status.api_calls_limit} ({self.status.api_calls_usage_percent:.1f}%)"
        )
        print(
            f"运行时间: {self.status.runtime_seconds:.1f}s/{self.status.runtime_limit_seconds:.1f}s ({self.status.runtime_usage_percent:.1f}%)"
        )

        if self.status.exceeded:
            print(f"[WARN] 预算超标: {self.status.exceeded_reason}")
        else:
            print("[OK] 预算正常")
        print("================\n")
