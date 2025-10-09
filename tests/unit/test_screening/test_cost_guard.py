"""
测试成本守护器
"""

import pytest
from pathlib import Path
from datetime import date
from src.screening.cost_guard import CostGuard


class TestCostGuard:
    """成本守护器测试"""

    @pytest.fixture
    def temp_storage(self, tmp_path):
        """临时存储路径"""
        return tmp_path / "cost_tracking.json"

    def test_init(self, temp_storage):
        """测试初始化"""
        guard = CostGuard(
            daily_limit=0.50,
            monthly_limit=15.0,
            storage_path=temp_storage
        )
        assert guard.daily_limit == 0.50
        assert guard.monthly_limit == 15.0
        assert guard.daily_cost == 0.0
        assert guard.monthly_cost == 0.0

    def test_add_cost(self, temp_storage):
        """测试添加成本"""
        guard = CostGuard(daily_limit=1.0, storage_path=temp_storage)

        guard.add_cost(0.10)
        assert abs(guard.daily_cost - 0.10) < 0.0001
        assert abs(guard.monthly_cost - 0.10) < 0.0001

        guard.add_cost(0.20)
        assert abs(guard.daily_cost - 0.30) < 0.0001
        assert abs(guard.monthly_cost - 0.30) < 0.0001

    def test_is_daily_exceeded(self, temp_storage):
        """测试日成本超限检测"""
        guard = CostGuard(daily_limit=0.50, storage_path=temp_storage)

        guard.add_cost(0.30)
        assert not guard.is_daily_exceeded()

        guard.add_cost(0.25)
        assert guard.is_daily_exceeded()  # 0.55 >= 0.50

    def test_is_monthly_exceeded(self, temp_storage):
        """测试月成本超限检测"""
        guard = CostGuard(monthly_limit=5.0, storage_path=temp_storage)

        guard.add_cost(3.0)
        assert not guard.is_monthly_exceeded()

        guard.add_cost(2.5)
        assert guard.is_monthly_exceeded()  # 5.5 >= 5.0

    def test_can_proceed(self, temp_storage):
        """测试是否可继续"""
        guard = CostGuard(daily_limit=0.50, monthly_limit=5.0, storage_path=temp_storage)

        assert guard.can_proceed()

        guard.add_cost(0.60)
        assert not guard.can_proceed()  # 日超限

    def test_get_status(self, temp_storage):
        """测试获取状态"""
        guard = CostGuard(daily_limit=1.0, monthly_limit=10.0, storage_path=temp_storage)
        guard.add_cost(0.30)

        status = guard.get_status()
        assert abs(status.daily_cost - 0.30) < 0.0001
        assert abs(status.monthly_cost - 0.30) < 0.0001
        assert status.daily_limit == 1.0
        assert status.monthly_limit == 10.0
        assert not status.is_daily_exceeded
        assert not status.is_monthly_exceeded
        assert abs(status.remaining_daily_budget - 0.70) < 0.0001
        assert status.can_proceed()

    def test_reset_daily(self, temp_storage):
        """测试重置日成本"""
        guard = CostGuard(storage_path=temp_storage)
        guard.add_cost(0.50)

        guard.reset_daily()
        assert guard.daily_cost == 0.0
        assert guard.last_reset_date == date.today()

    def test_reset_monthly(self, temp_storage):
        """测试重置月成本"""
        guard = CostGuard(storage_path=temp_storage)
        guard.add_cost(5.0)

        guard.reset_monthly()
        assert guard.daily_cost == 0.0
        assert guard.monthly_cost == 0.0

    def test_persistence(self, temp_storage):
        """测试成本持久化"""
        guard1 = CostGuard(storage_path=temp_storage)
        guard1.add_cost(0.50)

        guard2 = CostGuard(storage_path=temp_storage)
        assert abs(guard2.daily_cost - 0.50) < 0.0001
        assert abs(guard2.monthly_cost - 0.50) < 0.0001

    def test_daily_reset_on_date_change(self, temp_storage):
        """测试跨日自动重置（模拟）"""
        guard = CostGuard(storage_path=temp_storage)
        guard.add_cost(0.50)

        # 设置为昨天（同一个月，只跨日不跨月）
        from datetime import timedelta
        guard.last_reset_date = date.today() - timedelta(days=1)

        guard.add_cost(0.10)
        assert abs(guard.daily_cost - 0.10) < 0.0001  # 应该重置
        assert abs(guard.monthly_cost - 0.60) < 0.0001  # 月成本累加
