"""
测试L1快速筛选器
"""

import pytest
from src.screening.l1_fast_filter import L1FastFilter
from src.discovery.models import RawPost
from src.screening.models import FilterDecision


@pytest.fixture
def sample_posts():
    """示例帖子列表"""
    return [
        RawPost(
            post_id="post1",
            cluster_id="r/python",
            title="How to learn Python? Any tips?",
            author="user1",
            score=150,
            num_comments=25,
            created_utc=1704067200.0,  # 2024-01-01
            selftext="I'm a beginner looking for advice on learning Python programming."
        ),
        RawPost(
            post_id="post2",
            cluster_id="r/python",
            title="Fuck Python, it's terrible!",
            author="user2",
            score=5,
            num_comments=2,
            created_utc=1704067200.0,
            selftext="Hate this language, worst ever."
        ),
        RawPost(
            post_id="post3",
            cluster_id="r/machinelearning",
            title="Best practices for ML model training",
            author="user3",
            score=300,
            num_comments=50,
            created_utc=1704067200.0,
            selftext="Looking for recommendations on optimizing ML training pipelines."
        )
    ]


class TestL1FastFilter:
    """L1快速筛选器测试"""

    def test_init(self):
        """测试初始化"""
        filter = L1FastFilter(
            direct_pass_threshold=0.75,
            review_threshold=0.45
        )
        assert filter.direct_pass_threshold == 0.75
        assert filter.review_threshold == 0.45

    def test_make_decision_direct_pass(self):
        """测试直通决策"""
        filter = L1FastFilter(direct_pass_threshold=0.75)
        decision = filter._make_decision(0.85)
        assert decision == FilterDecision.DIRECT_PASS

    def test_make_decision_send_to_l2(self):
        """测试送L2决策"""
        filter = L1FastFilter(direct_pass_threshold=0.75, review_threshold=0.45)
        decision = filter._make_decision(0.60)
        assert decision == FilterDecision.SEND_TO_L2

    def test_make_decision_direct_reject(self):
        """测试直接拒绝决策"""
        filter = L1FastFilter(review_threshold=0.45)
        decision = filter._make_decision(0.30)
        assert decision == FilterDecision.DIRECT_REJECT

    def test_calculate_sentiment_score_positive(self, sample_posts):
        """测试正面情感评分"""
        filter = L1FastFilter()
        post = sample_posts[0]  # "How to learn Python? Any tips?"
        score = filter._calculate_sentiment_score(post)
        assert score >= 0.6  # 包含question, help等正面词

    def test_calculate_sentiment_score_negative(self, sample_posts):
        """测试负面情感评分"""
        filter = L1FastFilter()
        post = sample_posts[1]  # "Fuck Python, it's terrible!"
        score = filter._calculate_sentiment_score(post)
        assert score <= 0.5  # 包含hate, fuck等负面词

    def test_calculate_title_quality_with_question(self):
        """测试标题质量 - 带问号"""
        filter = L1FastFilter()
        post = RawPost(
            post_id="test",
            cluster_id="test",
            title="How to do this?",
            author="test",
            score=0,
            num_comments=0,
            created_utc=0.0
        )
        score = filter._calculate_title_quality(post)
        assert score >= 0.7  # 有问号加分

    def test_calculate_interaction_potential(self, sample_posts):
        """测试互动潜力评分"""
        filter = L1FastFilter()

        high_interaction_post = sample_posts[2]  # 300赞, 50评论
        score_high = filter._calculate_interaction_potential(high_interaction_post)

        low_interaction_post = sample_posts[1]  # 5赞, 2评论
        score_low = filter._calculate_interaction_potential(low_interaction_post)

        assert score_high > score_low

    def test_filter_posts(self, sample_posts):
        """测试批量筛选"""
        filter = L1FastFilter(
            direct_pass_threshold=0.75,
            review_threshold=0.45
        )

        results = filter.filter_posts(sample_posts)

        assert len(results) == 3
        assert all(hasattr(r, 'post_id') for r in results)
        assert all(hasattr(r, 'score') for r in results)
        assert all(hasattr(r, 'decision') for r in results)

        # 检查决策分布
        decisions = [r.decision for r in results]
        assert FilterDecision.DIRECT_PASS in decisions or \
               FilterDecision.SEND_TO_L2 in decisions or \
               FilterDecision.DIRECT_REJECT in decisions

    def test_filter_posts_empty_list(self):
        """测试空列表"""
        filter = L1FastFilter()
        results = filter.filter_posts([])
        assert len(results) == 0

    def test_composite_score_calculation(self):
        """测试综合评分计算"""
        filter = L1FastFilter(
            topic_weight=0.40,
            interaction_weight=0.30,
            sentiment_weight=0.20,
            title_quality_weight=0.10
        )

        score = filter._calculate_composite_score(
            topic_score=0.8,
            interaction_score=0.7,
            sentiment_score=0.9,
            title_score=0.6
        )

        expected = 0.8*0.40 + 0.7*0.30 + 0.9*0.20 + 0.6*0.10
        assert abs(score - expected) < 0.01

    def test_processing_time_recorded(self, sample_posts):
        """测试处理时间记录"""
        filter = L1FastFilter()
        results = filter.filter_posts(sample_posts)

        assert all(r.processing_time_ms >= 0 for r in results)
