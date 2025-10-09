import pytest
import asyncio
from pathlib import Path

from src.discovery import (
    DiscoveryConfig,
    ClusterBuilder,
    CredentialManager,
    BudgetManager,
    QualityControl,
    CapacityExecutor,
    DiscoveryPipeline,
)
from src.discovery.config import (
    CredentialConfig,
    BudgetConfig,
    QualityControlConfig,
    DeduplicationConfig,
    CapacityRecipeConfig,
)


class TestClusterBuilder:
    """簇构建器测试"""

    def test_load_clusters(self):
        builder = ClusterBuilder()
        clusters = builder.get_all_clusters()

        assert len(clusters) == 30
        assert all(c.subreddit_name for c in clusters)

    def test_cluster_categories(self):
        builder = ClusterBuilder()
        clusters = builder.get_all_clusters()

        categories = {c.category for c in clusters}
        expected_categories = {
            "crypto_general",
            "tron_ecosystem",
            "trading",
            "development",
            "meme_culture",
        }

        assert expected_categories.issubset(categories)


class TestCredentialManager:
    """凭据管理器测试"""

    def test_load_credentials(self):
        config = CredentialConfig()
        manager = CredentialManager(config)

        assert len(manager.credentials) == 3

    def test_round_robin_rotation(self):
        config = CredentialConfig(rotation_strategy="round_robin")
        manager = CredentialManager(config)

        cred1 = manager.get_credential()
        cred2 = manager.get_credential()
        cred3 = manager.get_credential()
        cred4 = manager.get_credential()

        assert cred1.profile_id != cred2.profile_id
        assert cred1.profile_id == cred4.profile_id

    def test_request_count_tracking(self):
        config = CredentialConfig()
        manager = CredentialManager(config)

        cred1 = manager.get_credential()
        assert cred1.request_count == 1

        cred2 = manager.get_credential()
        cred3 = manager.get_credential()

        # 验证轮询返回第一个凭据
        cred4 = manager.get_credential()
        assert cred4.profile_id == cred1.profile_id
        assert cred4.request_count == 2  # 第二次使用

    def test_cooldown_trigger(self):
        config = CredentialConfig(
            max_requests_per_credential=2, credential_cooldown_minutes=1
        )
        manager = CredentialManager(config)

        # 使用第1个凭据2次
        cred1 = manager.get_credential()  # 第1次
        cred1_id = cred1.profile_id

        cred2 = manager.get_credential()  # 第2个凭据
        cred3 = manager.get_credential()  # 第3个凭据

        cred4 = manager.get_credential()  # 轮回到第1个，第2次使用
        assert cred4.profile_id == cred1_id
        assert cred4.request_count == 2

        # 尝试再次使用第1个凭据，应该触发冷却并重置计数
        cred5 = manager.get_credential()  # 第2个凭据
        cred6 = manager.get_credential()  # 第3个凭据
        cred7 = manager.get_credential()  # 尝试第1个凭据，触发冷却

        # 验证第1个凭据进入冷却期
        assert cred1.is_in_cooldown or cred1.request_count == 0


class TestBudgetManager:
    """预算管理器测试"""

    def test_initialization(self):
        config = BudgetConfig(max_posts_per_run=100, max_api_calls=500)
        manager = BudgetManager(config)

        assert manager.status.posts_limit == 100
        assert manager.status.api_calls_limit == 500

    def test_track_posts(self):
        config = BudgetConfig(max_posts_per_run=10)
        manager = BudgetManager(config)

        manager.track_posts(5)
        assert manager.status.posts_fetched == 5
        assert manager.status.posts_remaining == 5

        manager.track_posts(6)
        assert manager.status.exceeded is True

    def test_should_stop(self):
        config = BudgetConfig(
            max_posts_per_run=5, stop_on_budget_exceeded=True
        )
        manager = BudgetManager(config)

        assert manager.should_stop() is False

        manager.track_posts(6)
        assert manager.should_stop() is True


class TestQualityControl:
    """质量控制测试"""

    def test_basic_filtering(self):
        from src.discovery.models import RawPost
        import time

        quality_config = QualityControlConfig(
            min_post_score=10,
            min_comment_count=5,
            min_title_length=5  # 降低最小长度要求
        )
        dedup_config = DeduplicationConfig(strategy="exact_title")

        qc = QualityControl(quality_config, dedup_config)

        good_post = RawPost(
            post_id="test1",
            cluster_id="tron",
            title="Good Test Post Title",  # 更长的标题
            author="user1",
            score=20,
            num_comments=10,
            created_utc=time.time(),
        )

        low_score_post = RawPost(
            post_id="test2",
            cluster_id="tron",
            title="Low Score",
            author="user2",
            score=5,
            num_comments=10,
            created_utc=time.time(),
        )

        assert qc.is_valid(good_post) is True
        assert qc.is_valid(low_score_post) is False

    def test_duplicate_detection(self):
        from src.discovery.models import RawPost
        import time

        quality_config = QualityControlConfig()
        dedup_config = DeduplicationConfig(strategy="exact_title")

        qc = QualityControl(quality_config, dedup_config)

        post1 = RawPost(
            post_id="test1",
            cluster_id="tron",
            title="Duplicate Test",
            author="user1",
            score=20,
            num_comments=10,
            created_utc=time.time(),
        )

        post2 = RawPost(
            post_id="test2",
            cluster_id="tron",
            title="Duplicate Test",
            author="user2",
            score=20,
            num_comments=10,
            created_utc=time.time(),
        )

        assert qc.is_valid(post1) is True
        assert qc.is_valid(post2) is False


class TestDiscoveryPipeline:
    """发现管道集成测试"""

    def test_initialization(self):
        pipeline = DiscoveryPipeline()

        assert pipeline.config is not None
        assert pipeline.cluster_builder is not None
        assert pipeline.executor is not None

    def test_get_recipe(self):
        pipeline = DiscoveryPipeline()

        recipe = pipeline._get_recipe("quick_scan")
        assert recipe is not None
        assert recipe.name == "quick_scan"

        invalid_recipe = pipeline._get_recipe("nonexistent")
        assert invalid_recipe is None

    def test_available_recipes(self):
        pipeline = DiscoveryPipeline()
        recipes = pipeline.get_available_recipes()

        assert "quick_scan" in recipes
        assert "standard" in recipes
        assert "deep_dive" in recipes


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
