"""
M3→M4集成测试
验证M3筛选结果能正确流入M4内容工厂
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

from src.content.content_pipeline import ContentPipeline
from src.content.models import GeneratedComment, QualityScores


@pytest.fixture
def pipeline():
    """创建ContentPipeline实例"""
    config_base = Path(__file__).parent.parent.parent
    return ContentPipeline(config_base)


@pytest.fixture
def m3_result_intent_a():
    """M3筛选结果 - 意图组A（费用转账）"""
    return {
        "post_id": "post_a_001",
        "title": "What's the cheapest way to send USDT from Binance to TronLink?",
        "subreddit": "Tronix",
        "score": 85,
        "age_hours": 3.2,
        "lang": "en",
        "screening_metadata": {
            "l1_score": 0.82,
            "l2_intent_prob": 0.91,
            "l2_topic_prob": 0.87,
            "suggestion": "Compare TRC20 vs ERC20 withdrawal fees",
            "intent_group": "A",
            "risk_level": "low"
        },
        "priority": 0.88,
        "account_id": "acc_a_001",
        "account_username": "user_a_001"
    }


@pytest.fixture
def m3_result_intent_b():
    """M3筛选结果 - 意图组B（钱包问题）"""
    return {
        "post_id": "post_b_001",
        "title": "USDT withdrawal stuck for 2 hours, is this normal?",
        "subreddit": "CryptoCurrency",
        "score": 120,
        "age_hours": 1.5,
        "lang": "en",
        "screening_metadata": {
            "l1_score": 0.78,
            "l2_intent_prob": 0.89,
            "l2_topic_prob": 0.85,
            "suggestion": "Provide troubleshooting steps for stuck withdrawals",
            "intent_group": "B",
            "risk_level": "medium"
        },
        "priority": 0.92,
        "account_id": "acc_b_001",
        "account_username": "user_b_001"
    }


@pytest.fixture
def m3_result_intent_c():
    """M3筛选结果 - 意图组C（新手学习）"""
    return {
        "post_id": "post_c_001",
        "title": "Can someone explain what TRC20 means? I'm new to crypto",
        "subreddit": "CryptoCurrency",
        "score": 65,
        "age_hours": 4.8,
        "lang": "en",
        "screening_metadata": {
            "l1_score": 0.75,
            "l2_intent_prob": 0.86,
            "l2_topic_prob": 0.82,
            "suggestion": "Explain TRC20 in beginner-friendly terms",
            "intent_group": "C",
            "risk_level": "low"
        },
        "priority": 0.81,
        "account_id": "acc_c_001",
        "account_username": "user_c_001"
    }


@pytest.fixture
def m3_result_multilingual():
    """M3筛选结果 - 多语言混写场景"""
    return {
        "post_id": "post_multi_001",
        "title": "¿Cómo transferir USDT con fees bajos?",
        "subreddit": "CryptoCurrency",
        "score": 45,
        "age_hours": 2.0,
        "lang": "es",
        "screening_metadata": {
            "l1_score": 0.80,
            "l2_intent_prob": 0.88,
            "l2_topic_prob": 0.84,
            "suggestion": "Suggest TRC20 for low-fee transfers",
            "intent_group": "A",
            "risk_level": "low"
        },
        "priority": 0.85,
        "account_id": "acc_multi_001",
        "account_username": "user_multi_001"
    }


class TestM3ToM4DataFlow:
    """M3→M4数据流测试"""

    def test_m3_result_parsing(self, pipeline, m3_result_intent_a):
        """测试M3结果正确解析为CommentRequest"""
        request = pipeline._parse_request(m3_result_intent_a)

        # 验证基本字段映射
        assert request.post_id == "post_a_001"
        assert request.title == "What's the cheapest way to send USDT from Binance to TronLink?"
        assert request.subreddit == "Tronix"
        assert request.account_id == "acc_a_001"

        # 验证screening_metadata完整传递
        assert request.screening_metadata["l1_score"] == 0.82
        assert request.screening_metadata["l2_intent_prob"] == 0.91
        assert request.screening_metadata["suggestion"] == "Compare TRC20 vs ERC20 withdrawal fees"
        assert request.screening_metadata["intent_group"] == "A"

    def test_intent_group_routing_a(self, pipeline, m3_result_intent_a):
        """测试意图组A正确路由"""
        request = pipeline._parse_request(m3_result_intent_a)
        intent_group = pipeline.intent_router.route(
            post_title=request.title,
            post_metadata=request.screening_metadata
        )

        assert intent_group.name == "A"
        assert "gas_optimizer" in intent_group.preferred_personas
        assert "crypto_expert" in intent_group.preferred_personas

    def test_intent_group_routing_b(self, pipeline, m3_result_intent_b):
        """测试意图组B正确路由"""
        request = pipeline._parse_request(m3_result_intent_b)
        intent_group = pipeline.intent_router.route(
            post_title=request.title,
            post_metadata=request.screening_metadata
        )

        assert intent_group.name == "B"
        assert "wallet_helper" in intent_group.preferred_personas
        assert "exchange_user" in intent_group.preferred_personas

    def test_intent_group_routing_c(self, pipeline, m3_result_intent_c):
        """测试意图组C正确路由"""
        request = pipeline._parse_request(m3_result_intent_c)
        intent_group = pipeline.intent_router.route(
            post_title=request.title,
            post_metadata=request.screening_metadata
        )

        assert intent_group.name == "C"
        assert "beginner_mentor" in intent_group.preferred_personas


class TestPersonaSelection:
    """Persona选择测试"""

    def test_persona_selection_for_intent_a(self, pipeline, m3_result_intent_a):
        """测试A组意图的Persona选择"""
        request = pipeline._parse_request(m3_result_intent_a)
        intent_group = pipeline.intent_router.route(
            post_title=request.title,
            post_metadata=request.screening_metadata
        )

        # 选择Persona
        persona = pipeline.persona_manager.select_persona(
            intent_group=intent_group.name,
            subreddit=request.subreddit,
            post_metadata=request.screening_metadata
        )

        # 验证Persona属于A组
        assert "A" in persona.intent_groups
        assert persona.id in ["gas_optimizer", "crypto_expert", "multilingual_user"]

    def test_persona_subreddit_compatibility(self, pipeline, m3_result_intent_a):
        """测试Persona与子版兼容性"""
        request = pipeline._parse_request(m3_result_intent_a)
        intent_group = pipeline.intent_router.route(
            post_title=request.title,
            post_metadata=request.screening_metadata
        )

        persona = pipeline.persona_manager.select_persona(
            intent_group=intent_group.name,
            subreddit=request.subreddit,
            post_metadata=request.screening_metadata
        )

        # Tronix子版应该选择支持TRON的Persona
        if hasattr(persona, 'compatible_subreddits'):
            assert "Tronix" in persona.compatible_subreddits or persona.compatible_subreddits == []


class TestStyleGuideApplication:
    """风格卡应用测试"""

    def test_style_guide_loading_cryptocurrency(self, pipeline, m3_result_intent_b):
        """测试CryptoCurrency子版风格卡"""
        style_guide = pipeline.style_guide_loader.load("CryptoCurrency")

        assert style_guide.subreddit == "CryptoCurrency"
        assert style_guide.tone == "neutral_sober"
        assert style_guide.must_end_with_question is True
        assert style_guide.compliance.financial_disclaimer is True

    def test_style_guide_loading_tronix(self, pipeline, m3_result_intent_a):
        """测试Tronix子版风格卡"""
        style_guide = pipeline.style_guide_loader.load("Tronix")

        assert style_guide.subreddit == "Tronix"
        assert style_guide.tone == "friendly_practical"
        assert style_guide.jargon_level == "medium_high"


class TestMultilingualHandling:
    """多语言处理测试"""

    def test_multilingual_m3_result_parsing(self, pipeline, m3_result_multilingual):
        """测试多语言M3结果解析"""
        request = pipeline._parse_request(m3_result_multilingual)

        assert request.lang == "es"
        assert request.title.startswith("¿Cómo")

    def test_multilingual_persona_selection(self, pipeline, m3_result_multilingual):
        """测试多语言场景Persona选择"""
        request = pipeline._parse_request(m3_result_multilingual)
        intent_group = pipeline.intent_router.route(
            post_title=request.title,
            post_metadata=request.screening_metadata
        )

        persona = pipeline.persona_manager.select_persona(
            intent_group=intent_group.name,
            subreddit=request.subreddit,
            post_metadata=request.screening_metadata
        )

        # 应该优先选择支持多语言的Persona（如multilingual_user）
        # 或至少是A组的Persona
        assert "A" in persona.intent_groups


class TestEndToEndIntegration:
    """端到端集成测试"""

    @pytest.mark.asyncio
    async def test_e2e_intent_a_to_generated_comment(
        self,
        pipeline,
        m3_result_intent_a
    ):
        """测试A组意图从M3到生成评论的完整流程"""
        # Mock AI生成
        mock_comment = GeneratedComment(
            text="honestly, TRC20 is way cheaper than ERC20 for USDT transfers. I've saved tons on fees. Just make sure your exchange supports TRC20. What's been your experience?",
            persona_used="gas_optimizer",
            intent_group="A",
            style_guide_id="Tronix",
            quality_scores=QualityScores(
                relevance=0.92,
                natural=0.88,
                compliance=0.98,
                overall=0.93
            ),
            audit={},
            timestamps={},
            variants=[],
            request_id="post_a_001"
        )

        with patch.object(pipeline.comment_generator, 'generate', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_comment

            results = await pipeline.process_batch([m3_result_intent_a])

            # 验证生成成功
            assert len(results) == 1
            assert results[0].intent_group == "A"
            assert results[0].persona_used == "gas_optimizer"
            assert results[0].request_id == "post_a_001"

    @pytest.mark.asyncio
    async def test_e2e_batch_mixed_intents(
        self,
        pipeline,
        m3_result_intent_a,
        m3_result_intent_b,
        m3_result_intent_c
    ):
        """测试混合意图组的批量处理"""
        mock_comment_a = GeneratedComment(
            text="Test A comment", persona_used="gas_optimizer", intent_group="A",
            style_guide_id="Tronix", quality_scores=QualityScores(relevance=0.9, natural=0.88, compliance=0.98, overall=0.92),
            audit={}, timestamps={}, variants=[], request_id="post_a_001"
        )
        mock_comment_b = GeneratedComment(
            text="Test B comment", persona_used="wallet_helper", intent_group="B",
            style_guide_id="CryptoCurrency", quality_scores=QualityScores(relevance=0.91, natural=0.87, compliance=0.97, overall=0.92),
            audit={}, timestamps={}, variants=[], request_id="post_b_001"
        )
        mock_comment_c = GeneratedComment(
            text="Test C comment", persona_used="beginner_mentor", intent_group="C",
            style_guide_id="CryptoCurrency", quality_scores=QualityScores(relevance=0.89, natural=0.90, compliance=0.98, overall=0.92),
            audit={}, timestamps={}, variants=[], request_id="post_c_001"
        )

        with patch.object(pipeline.comment_generator, 'generate', new_callable=AsyncMock) as mock_gen:
            mock_gen.side_effect = [mock_comment_a, mock_comment_b, mock_comment_c]

            results = await pipeline.process_batch([
                m3_result_intent_a,
                m3_result_intent_b,
                m3_result_intent_c
            ])

            # 验证三个不同意图组都成功处理
            assert len(results) == 3
            intent_groups = [r.intent_group for r in results]
            assert "A" in intent_groups
            assert "B" in intent_groups
            assert "C" in intent_groups


class TestM3MetadataUtilization:
    """M3元数据利用测试"""

    def test_m3_suggestion_passed_to_prompt(self, pipeline, m3_result_intent_a):
        """测试M3的suggestion传递到Prompt构建"""
        request = pipeline._parse_request(m3_result_intent_a)

        # 验证suggestion在metadata中
        assert "suggestion" in request.screening_metadata
        assert request.screening_metadata["suggestion"] == "Compare TRC20 vs ERC20 withdrawal fees"

    def test_m3_scores_preserved(self, pipeline, m3_result_intent_a):
        """测试M3的评分信息保留"""
        request = pipeline._parse_request(m3_result_intent_a)

        # 验证L1/L2评分保留
        assert request.screening_metadata["l1_score"] == 0.82
        assert request.screening_metadata["l2_intent_prob"] == 0.91
        assert request.screening_metadata["l2_topic_prob"] == 0.87

    def test_m3_risk_level_preserved(self, pipeline, m3_result_intent_b):
        """测试M3的风险等级保留"""
        request = pipeline._parse_request(m3_result_intent_b)

        assert request.screening_metadata["risk_level"] == "medium"


class TestQuotaIntegration:
    """配额集成测试"""

    @pytest.mark.asyncio
    async def test_account_daily_quota_enforcement(
        self,
        pipeline,
        m3_result_intent_a
    ):
        """测试账户日配额强制执行"""
        # 预先标记账号已用额
        pipeline.quota_manager.mark_account_used("acc_a_001")

        # 相同账号的第二次请求应被拒绝
        results = await pipeline.process_batch([m3_result_intent_a])

        assert len(results) == 0
        assert pipeline.stats["quota_denied"] >= 1

    @pytest.mark.asyncio
    async def test_different_accounts_quota_independent(
        self,
        pipeline,
        m3_result_intent_a,
        m3_result_intent_b
    ):
        """测试不同账号配额独立"""
        # 标记账号A已用额
        pipeline.quota_manager.mark_account_used("acc_a_001")

        mock_comment = GeneratedComment(
            text="Test", persona_used="wallet_helper", intent_group="B",
            style_guide_id="CryptoCurrency", quality_scores=QualityScores(relevance=0.9, natural=0.88, compliance=0.98, overall=0.92),
            audit={}, timestamps={}, variants=[], request_id="post_b_001"
        )

        with patch.object(pipeline.comment_generator, 'generate', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_comment

            # 账号B应该仍能生成
            results = await pipeline.process_batch([m3_result_intent_b])

            assert len(results) == 1
            assert results[0].request_id == "post_b_001"
