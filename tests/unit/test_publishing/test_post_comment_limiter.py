"""
测试 PostCommentLimiter - 单帖子评论限制器
"""

import pytest
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import json

from src.publishing.post_comment_limiter import PostCommentLimiter


@pytest.fixture
def temp_history_file():
    """临时历史记录文件"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = Path(f.name)

    yield temp_path

    # 清理
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def limiter(temp_history_file):
    """PostCommentLimiter实例"""
    return PostCommentLimiter(
        history_file=temp_history_file,
        ttl_hours=24,
        auto_save=True
    )


class TestPostCommentLimiter:
    """PostCommentLimiter测试"""

    def test_init(self, limiter):
        """测试初始化"""
        assert limiter.post_comment_history == {}
        assert limiter.ttl_hours == 24
        assert limiter.auto_save is True

    def test_can_comment_on_new_post(self, limiter):
        """测试新帖子可以评论"""
        assert limiter.can_comment_on_post("post1", "account1") is True

    def test_cannot_comment_after_commented(self, limiter):
        """测试已评论的帖子不能再评论"""
        # 记录评论
        limiter.record_comment("post1", "account1")

        # 检查（同账号）
        assert limiter.can_comment_on_post("post1", "account1") is False

        # 检查（不同账号）
        assert limiter.can_comment_on_post("post1", "account2") is False

    def test_cannot_comment_after_attempted_failed(self, limiter):
        """测试已尝试失败的帖子不能再评论"""
        # 标记为已尝试失败
        limiter.mark_post_as_attempted(
            "post1",
            "account1",
            failure_reason="all_top3_unavailable"
        )

        # 检查（同账号）
        assert limiter.can_comment_on_post("post1", "account1") is False

        # 检查（不同账号）
        assert limiter.can_comment_on_post("post1", "account2") is False

    def test_record_comment_structure(self, limiter):
        """测试记录评论的数据结构"""
        limiter.record_comment("post1", "account1")

        record = limiter.post_comment_history["post1"]

        assert record["status"] == "commented"
        assert "account1" in record["account_ids"]
        assert record["comment_count"] == 1
        assert record["failure_reason"] is None
        assert "first_comment_at" in record

    def test_mark_post_as_attempted_structure(self, limiter):
        """测试标记失败的数据结构"""
        limiter.mark_post_as_attempted(
            "post1",
            "account1",
            failure_reason="all_top3_locked"
        )

        record = limiter.post_comment_history["post1"]

        assert record["status"] == "attempted_failed"
        assert "account1" in record["account_ids"]
        assert record["comment_count"] == 0
        assert record["failure_reason"] == "all_top3_locked"
        assert "first_comment_at" in record

    def test_get_post_comment_count(self, limiter):
        """测试获取帖子评论数"""
        assert limiter.get_post_comment_count("post1") == 0

        limiter.record_comment("post1", "account1")
        assert limiter.get_post_comment_count("post1") == 1

        # attempted_failed状态应返回0
        limiter.mark_post_as_attempted("post2", "account2")
        assert limiter.get_post_comment_count("post2") == 0

    def test_get_commented_accounts(self, limiter):
        """测试获取评论过的账号列表"""
        assert limiter.get_commented_accounts("post1") == []

        limiter.record_comment("post1", "account1")
        assert limiter.get_commented_accounts("post1") == ["account1"]

        limiter.record_comment("post1", "account2")
        assert "account1" in limiter.get_commented_accounts("post1")
        assert "account2" in limiter.get_commented_accounts("post1")

    def test_cleanup_old_records(self, limiter):
        """测试清理过期记录"""
        # 创建旧记录（25小时前）
        old_time = datetime.now() - timedelta(hours=25)
        limiter.post_comment_history["post_old"] = {
            "status": "commented",
            "account_ids": ["account1"],
            "first_comment_at": old_time.isoformat(),
            "comment_count": 1,
            "failure_reason": None
        }

        # 创建新记录
        limiter.record_comment("post_new", "account2")

        # 触发清理（通过调用can_comment_on_post）
        limiter.can_comment_on_post("post_test", "account_test")

        # 验证旧记录被删除，新记录保留
        assert "post_old" not in limiter.post_comment_history
        assert "post_new" in limiter.post_comment_history

    def test_save_and_load_from_file(self, temp_history_file):
        """测试保存和加载历史记录"""
        # 创建第一个实例并记录数据
        limiter1 = PostCommentLimiter(
            history_file=temp_history_file,
            auto_save=True
        )
        limiter1.record_comment("post1", "account1")
        limiter1.mark_post_as_attempted("post2", "account2", "all_top3_failed")

        # 创建第二个实例（应该加载文件）
        limiter2 = PostCommentLimiter(
            history_file=temp_history_file,
            auto_save=False
        )

        # 验证数据加载成功
        assert "post1" in limiter2.post_comment_history
        assert "post2" in limiter2.post_comment_history
        assert limiter2.post_comment_history["post1"]["status"] == "commented"
        assert limiter2.post_comment_history["post2"]["status"] == "attempted_failed"

    def test_reset_all(self, limiter):
        """测试重置所有记录"""
        limiter.record_comment("post1", "account1")
        limiter.mark_post_as_attempted("post2", "account2")

        assert len(limiter.post_comment_history) == 2

        limiter.reset_all()

        assert len(limiter.post_comment_history) == 0

    def test_get_stats(self, limiter):
        """测试统计信息"""
        limiter.record_comment("post1", "account1")
        limiter.record_comment("post2", "account2")
        limiter.mark_post_as_attempted("post3", "account3")

        stats = limiter.get_stats()

        assert stats["total_posts_tracked"] == 3
        assert stats["total_comments_published"] == 2  # 只计算commented状态
        assert stats["unique_accounts_used"] == 3
        assert stats["ttl_hours"] == 24

    def test_multiple_accounts_same_post(self, limiter):
        """测试多个账号对同一帖子的操作（边界情况）"""
        # 第一个账号评论成功
        limiter.record_comment("post1", "account1")

        # 第二个账号不应该能评论（单帖子单评论约束）
        assert limiter.can_comment_on_post("post1", "account2") is False

    def test_same_account_multiple_posts(self, limiter):
        """测试同一账号对多个帖子的操作"""
        limiter.record_comment("post1", "account1")
        limiter.record_comment("post2", "account1")

        # 应该允许同一账号在不同帖子评论
        assert limiter.get_post_comment_count("post1") == 1
        assert limiter.get_post_comment_count("post2") == 1

        # 但不能重复评论同一帖子
        assert limiter.can_comment_on_post("post1", "account1") is False
