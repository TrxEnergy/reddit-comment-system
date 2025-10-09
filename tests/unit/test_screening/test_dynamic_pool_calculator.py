"""
测试动态池子计算器
"""

import pytest
from unittest.mock import AsyncMock, patch
from src.screening.dynamic_pool_calculator import DynamicPoolCalculator
from src.screening.models import AccountScale


class TestDynamicPoolCalculator:
    """动态池子计算器测试"""

    def test_init(self):
        """测试初始化"""
        calc = DynamicPoolCalculator(
            yanghao_api_base_url="http://test:8000",
            max_account_limit=200,
            buffer_ratio=3.0
        )
        assert calc.yanghao_api_base_url == "http://test:8000"
        assert calc.max_account_limit == 200
        assert calc.buffer_ratio == 3.0

    def test_determine_account_scale_small(self):
        """测试账号规模判断 - 小规模"""
        calc = DynamicPoolCalculator()
        assert calc._determine_account_scale(10) == AccountScale.SMALL
        assert calc._determine_account_scale(50) == AccountScale.SMALL

    def test_determine_account_scale_medium(self):
        """测试账号规模判断 - 中规模"""
        calc = DynamicPoolCalculator()
        assert calc._determine_account_scale(51) == AccountScale.MEDIUM
        assert calc._determine_account_scale(100) == AccountScale.MEDIUM

    def test_determine_account_scale_large(self):
        """测试账号规模判断 - 大规模"""
        calc = DynamicPoolCalculator()
        assert calc._determine_account_scale(101) == AccountScale.LARGE
        assert calc._determine_account_scale(200) == AccountScale.LARGE

    def test_get_thresholds_small(self):
        """测试小规模阈值"""
        calc = DynamicPoolCalculator()
        l1_direct, l1_review, l2_pass = calc._get_thresholds_by_scale(AccountScale.SMALL)
        assert l1_direct == 0.75
        assert l1_review == 0.45
        assert l2_pass == 0.70

    def test_get_thresholds_medium(self):
        """测试中规模阈值"""
        calc = DynamicPoolCalculator()
        l1_direct, l1_review, l2_pass = calc._get_thresholds_by_scale(AccountScale.MEDIUM)
        assert l1_direct == 0.77
        assert l1_review == 0.45
        assert l2_pass == 0.65

    def test_get_thresholds_large(self):
        """测试大规模阈值"""
        calc = DynamicPoolCalculator()
        l1_direct, l1_review, l2_pass = calc._get_thresholds_by_scale(AccountScale.LARGE)
        assert l1_direct == 0.80
        assert l1_review == 0.45
        assert l2_pass == 0.60

    def test_calculate_pool_config_20_accounts(self):
        """测试20账号场景"""
        calc = DynamicPoolCalculator(buffer_ratio=3.0, daily_comment_limit_per_account=1)
        config = calc.calculate_pool_config(active_account_count=20)

        assert config.active_accounts == 20
        assert config.pool_size == 60  # 20 * 1 * 3
        assert config.account_scale == AccountScale.SMALL
        assert config.l1_direct_pass_threshold == 0.75
        assert config.l2_pass_threshold == 0.70
        assert config.estimated_l2_calls == 30  # 60 * 0.5
        assert abs(config.estimated_daily_cost - 0.045) < 0.0001  # 30 * 0.0015

    def test_calculate_pool_config_100_accounts(self):
        """测试100账号场景"""
        calc = DynamicPoolCalculator(buffer_ratio=3.0)
        config = calc.calculate_pool_config(active_account_count=100)

        assert config.active_accounts == 100
        assert config.pool_size == 300  # 100 * 1 * 3
        assert config.account_scale == AccountScale.MEDIUM
        assert config.l1_direct_pass_threshold == 0.77
        assert config.l2_pass_threshold == 0.65

    def test_calculate_pool_config_200_accounts(self):
        """测试200账号场景（极限）"""
        calc = DynamicPoolCalculator(buffer_ratio=3.0)
        config = calc.calculate_pool_config(active_account_count=200)

        assert config.active_accounts == 200
        assert config.pool_size == 600  # 200 * 1 * 3
        assert config.account_scale == AccountScale.LARGE
        assert config.l1_direct_pass_threshold == 0.80
        assert config.l2_pass_threshold == 0.60

    def test_fallback_account_count(self):
        """测试降级策略"""
        calc = DynamicPoolCalculator()
        fallback_count = calc._get_fallback_account_count()
        assert fallback_count == 100

    @pytest.mark.asyncio
    async def test_get_active_account_count_success(self):
        """测试成功获取账号数"""
        calc = DynamicPoolCalculator(yanghao_api_base_url="http://test:8000")

        mock_accounts = [{"username": f"user{i}"} for i in range(20)]

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.json.return_value = mock_accounts
            mock_response.raise_for_status = AsyncMock()

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            count = await calc.get_active_account_count()
            assert count == 20

    @pytest.mark.asyncio
    async def test_get_active_account_count_failure(self):
        """测试API失败时的降级"""
        calc = DynamicPoolCalculator()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=Exception("API Error")
            )

            count = await calc.get_active_account_count()
            assert count == 100  # 降级值

    @pytest.mark.asyncio
    async def test_calculate_pool_config_async(self):
        """测试异步计算池子配置"""
        calc = DynamicPoolCalculator()

        with patch.object(calc, 'get_active_account_count', return_value=50):
            config = await calc.calculate_pool_config_async()
            assert config.active_accounts == 50
            assert config.pool_size == 150
