"""
M4内容工厂 - ContentPipeline单元测试
验证完整的9步评论生成流程
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from src.content.content_pipeline import ContentPipeline
from src.content.models import (
    CommentRequest,
    GeneratedComment,
    QualityScores,
    Persona,
    IntentGroup,
    StyleGuide
)


@pytest.fixture
def pipeline():
    """创建ContentPipeline实例"""
    config_base = Path(__file__).parent.parent.parent
    return ContentPipeline(config_base)


@pytest.fixture
def mock_m3_screening_result():
    """模拟M3筛选结果"""
    return {
        "post_id": "test_post_001",
        "title": "What's the cheapest way to transfer USDT?",
        "subreddit": "CryptoCurrency",
        "score": 120,
        "age_hours": 2.5,
        "lang": "en",
        "screening_metadata": {
            "intent_prob": 0.92,
            "topic_prob": 0.88,
            "suggestion": "Suggest TRC20 vs ERC20 comparison"
        },
        "priority": 0.9,
        "account_id": "acc_001",
        "account_username": "test_user_001"
    }


@pytest.fixture
def mock_generated_comment():
    """模拟生成的评论"""
    return GeneratedComment(
        text="honestly, TRC20 is way cheaper than ERC20 for USDT transfers. I've saved tons on fees switching to TRC20. Just make sure your exchange supports it. What's been your experience?",
        persona_used="gas_optimizer",
        intent_group="A",
        style_guide_id="CryptoCurrency",
        quality_scores=QualityScores(
            relevance=0.92,
            natural=0.88,
            compliance=0.98,
            overall=0.93
        ),
        audit={
            "policy_version": "1.0.0",
            "style_version": "1.0.0",
            "persona_version": "1.0.0",
            "rule_hits": []
        },
        timestamps={
            "generated_at": "2025-10-09T10:00:00",
            "passed_checks_at": "2025-10-09T10:00:01"
        },
        variants=[],
        request_id="test_post_001"
    )


class TestContentPipeline:
    """ContentPipeline测试套件"""

    def test_pipeline_initialization(self, pipeline):
        """测试管道初始化"""
        assert pipeline.persona_manager is not None
        assert pipeline.intent_router is not None
        assert pipeline.style_guide_loader is not None
        assert pipeline.comment_generator is not None
        assert pipeline.quota_manager is not None
        assert pipeline.ai_client is not None

        # 验证统计初始化
        assert pipeline.stats["processed"] == 0
        assert pipeline.stats["generated"] == 0

    def test_parse_request(self, pipeline, mock_m3_screening_result):
        """测试M3结果解析为CommentRequest"""
        request = pipeline._parse_request(mock_m3_screening_result)

        assert isinstance(request, CommentRequest)
        assert request.post_id == "test_post_001"
        assert request.title == "What's the cheapest way to transfer USDT?"
        assert request.subreddit == "CryptoCurrency"
        assert request.account_id == "acc_001"
        assert request.screening_metadata["intent_prob"] == 0.92

    def test_meets_thresholds_pass(self, pipeline):
        """测试质量阈值检查 - 通过"""
        scores = {
            "relevance": 0.90,
            "natural": 0.88,
            "compliance": 0.98,
            "overall": 0.92
        }

        assert pipeline._meets_thresholds(scores) is True

    def test_meets_thresholds_fail_relevance(self, pipeline):
        """测试质量阈值检查 - 相关性不足"""
        scores = {
            "relevance": 0.80,  # < 0.85
            "natural": 0.88,
            "compliance": 0.98
        }

        assert pipeline._meets_thresholds(scores) is False

    def test_meets_thresholds_fail_natural(self, pipeline):
        """测试质量阈值检查 - 自然度不足"""
        scores = {
            "relevance": 0.90,
            "natural": 0.80,  # < 0.85
            "compliance": 0.98
        }

        assert pipeline._meets_thresholds(scores) is False

    def test_meets_thresholds_fail_compliance(self, pipeline):
        """测试质量阈值检查 - 合规性不足"""
        scores = {
            "relevance": 0.90,
            "natural": 0.88,
            "compliance": 0.90  # < 0.95
        }

        assert pipeline._meets_thresholds(scores) is False

    @pytest.mark.asyncio
    async def test_process_batch_success(
        self,
        pipeline,
        mock_m3_screening_result,
        mock_generated_comment
    ):
        """测试批量处理 - 成功场景"""
        # Mock各模块
        with patch.object(pipeline.comment_generator, 'generate', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_generated_comment

            # 执行批量处理
            results = await pipeline.process_batch([mock_m3_screening_result])

            # 验证结果
            assert len(results) == 1
            assert results[0].text == mock_generated_comment.text
            assert results[0].persona_used == "gas_optimizer"
            assert results[0].intent_group == "A"

            # 验证统计
            assert pipeline.stats["processed"] == 1
            assert pipeline.stats["generated"] == 1
            assert pipeline.stats["errors"] == 0

    @pytest.mark.asyncio
    async def test_process_batch_quota_denied(
        self,
        pipeline,
        mock_m3_screening_result
    ):
        """测试批量处理 - 配额拒绝"""
        # 预先标记账号已用额
        pipeline.quota_manager.mark_account_used("acc_001")

        # 执行批量处理
        results = await pipeline.process_batch([mock_m3_screening_result])

        # 验证结果
        assert len(results) == 0
        assert pipeline.stats["quota_denied"] == 1
        assert pipeline.stats["generated"] == 0

    @pytest.mark.asyncio
    async def test_process_batch_quality_failed(
        self,
        pipeline,
        mock_m3_screening_result,
        mock_generated_comment
    ):
        """测试批量处理 - 质量不达标"""
        # Mock生成低质量评论
        low_quality_comment = mock_generated_comment
        low_quality_comment.quality_scores.relevance = 0.70  # < 0.85

        with patch.object(pipeline.comment_generator, 'generate', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = low_quality_comment

            results = await pipeline.process_batch([mock_m3_screening_result])

            # 验证结果
            assert len(results) == 0
            assert pipeline.stats["quality_failed"] == 1
            assert pipeline.stats["generated"] == 0

    @pytest.mark.asyncio
    async def test_process_batch_generation_error(
        self,
        pipeline,
        mock_m3_screening_result
    ):
        """测试批量处理 - 生成异常"""
        with patch.object(pipeline.comment_generator, 'generate', new_callable=AsyncMock) as mock_gen:
            mock_gen.side_effect = Exception("AI generation failed")

            results = await pipeline.process_batch([mock_m3_screening_result])

            # 验证结果
            assert len(results) == 0
            assert pipeline.stats["errors"] == 1
            assert pipeline.stats["generated"] == 0

    @pytest.mark.asyncio
    async def test_process_batch_multiple_posts(
        self,
        pipeline,
        mock_m3_screening_result,
        mock_generated_comment
    ):
        """测试批量处理 - 多个帖子"""
        # 准备3个不同的M3结果
        posts = [
            mock_m3_screening_result,
            {**mock_m3_screening_result, "post_id": "test_002", "account_id": "acc_002"},
            {**mock_m3_screening_result, "post_id": "test_003", "account_id": "acc_003"}
        ]

        with patch.object(pipeline.comment_generator, 'generate', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_generated_comment

            results = await pipeline.process_batch(posts)

            # 验证结果
            assert len(results) == 3
            assert pipeline.stats["processed"] == 3
            assert pipeline.stats["generated"] == 3

    def test_get_stats(self, pipeline):
        """测试统计信息获取"""
        pipeline.stats["processed"] = 10
        pipeline.stats["generated"] = 8
        pipeline.stats["quota_denied"] = 1

        stats = pipeline.get_stats()

        assert stats["processed"] == 10
        assert stats["generated"] == 8
        assert stats["quota_denied"] == 1
        assert "persona_stats" in stats
        assert "quota_statuses" in stats

    def test_reset_stats(self, pipeline):
        """测试统计重置"""
        pipeline.stats["processed"] = 10
        pipeline.stats["generated"] = 8

        pipeline.reset_stats()

        assert pipeline.stats["processed"] == 0
        assert pipeline.stats["generated"] == 0
        assert pipeline.stats["errors"] == 0


class TestIntegrationScenarios:
    """集成场景测试"""

    @pytest.mark.asyncio
    async def test_intent_group_a_routing(self, pipeline, mock_m3_screening_result):
        """测试意图组A的路由和Persona选择"""
        # A组（费用转账）应该路由到gas_optimizer等
        result = pipeline._parse_request(mock_m3_screening_result)
        intent_group = pipeline.intent_router.route(
            post_title=result.title,
            post_metadata=result.screening_metadata
        )

        assert intent_group.name == "A"
        assert "gas_optimizer" in intent_group.preferred_personas

    @pytest.mark.asyncio
    async def test_subreddit_style_guide_loading(self, pipeline):
        """测试子版风格卡加载"""
        style_guide = pipeline.style_guide_loader.load("CryptoCurrency")

        assert style_guide.subreddit == "CryptoCurrency"
        assert style_guide.tone == "neutral_sober"
        assert style_guide.must_end_with_question is True
        assert style_guide.compliance.financial_disclaimer is True

    @pytest.mark.asyncio
    async def test_default_style_guide_fallback(self, pipeline):
        """测试未知子版回退到默认风格"""
        style_guide = pipeline.style_guide_loader.load("UnknownSubreddit")

        assert style_guide.subreddit == "default"
        assert style_guide.tone == "neutral_helpful"
