"""
M4内容工厂 - ComplianceChecker单元测试
验证合规审查的硬禁止和软约束
"""

import pytest
from pathlib import Path

from src.content.compliance_checker import ComplianceChecker
from src.content.models import ComplianceCheck


@pytest.fixture
def checker():
    """创建ComplianceChecker实例"""
    config_path = Path(__file__).parent.parent.parent / "config" / "content_policies.yaml"
    return ComplianceChecker(config_path)


class TestHardBans:
    """硬禁止规则测试"""

    def test_hard_ban_phrases(self, checker):
        """测试硬禁词拦截"""
        test_cases = [
            ("This is guaranteed profit, trust me!", False, "guaranteed profit"),
            ("It's a sure thing, buy now!", False, "sure thing"),
            ("Join the pump and dump group!", False, "pump"),
            ("Free money opportunity here!", False, "free money"),
            ("DM me for insider info!", False, "DM me"),
            ("Act fast, limited time offer!", False, "act fast"),
            ("This can't lose, risk-free investment!", False, "risk-free"),
        ]

        for text, should_pass, expected_reason in test_cases:
            result = checker.check(text)
            assert result.passed == should_pass, f"Failed for: {text}"
            if not should_pass:
                assert expected_reason in result.block_reason.lower()

    def test_hard_ban_patterns_external_links(self, checker):
        """测试外链正则拦截"""
        test_cases = [
            ("Check out https://scam-site.com for details", False),
            ("Visit http://suspicious-link.io now", False),
            ("More info at https://reddit.com/r/crypto", True),  # 白名单
            ("See https://github.com/project/repo", True),  # 白名单
            ("Details on https://ethereum.org", True),  # 白名单
        ]

        for text, should_pass in test_cases:
            result = checker.check(text)
            assert result.passed == should_pass, f"Failed for: {text}"

    def test_hard_ban_patterns_private_contact(self, checker):
        """测试私信渠道拦截"""
        test_cases = [
            ("Join our telegram group for signals", False),
            ("Add me on discord for tips", False),
            ("Message me on whatsapp", False),
            ("Use my referral code REF123", False),
            ("Here's my ref code for bonus", False),
        ]

        for text, should_pass in test_cases:
            result = checker.check(text)
            assert result.passed == should_pass, f"Failed for: {text}"
            if not should_pass:
                assert "private contact" in result.block_reason.lower() or "referral" in result.block_reason.lower()

    def test_clean_text_passes(self, checker):
        """测试干净文本通过检查"""
        clean_texts = [
            "TRC20 has lower fees than ERC20 for USDT transfers.",
            "From my experience, withdrawals take 10-30 minutes.",
            "Check your exchange's withdrawal policy first.",
            "Not financial advice, but I prefer TRC20 for cost savings.",
        ]

        for text in clean_texts:
            result = checker.check(text)
            assert result.passed is True, f"Clean text failed: {text}"
            assert result.compliance_score >= 0.95


class TestSoftRules:
    """软约束规则测试"""

    def test_emotional_intensity(self, checker):
        """测试情绪强度检查"""
        high_emotion = "This is AMAZING and INSANE! Absolutely UNBELIEVABLE returns! TERRIBLE decision not to buy!"
        result = checker.check(high_emotion)

        # 软约束应该降低合规分数但不完全拦截
        assert result.compliance_score < 1.0

    def test_absolutism_ratio(self, checker):
        """测试绝对化措辞检查"""
        absolutist = "You must always use TRC20. Never use ERC20. Everyone knows this is certain. Nobody uses alternatives."
        result = checker.check(absolutist)

        # 应该检测到高绝对化比例
        assert result.compliance_score < 1.0

    def test_length_constraints(self, checker):
        """测试长度约束"""
        # 过短
        too_short = "Yes"
        result_short = checker.check(too_short)
        assert result_short.compliance_score < 1.0

        # 过长（>600字符）
        too_long = "A" * 650
        result_long = checker.check(too_long)
        assert result_long.compliance_score < 1.0

        # 合理长度
        optimal = "This is a well-balanced comment with appropriate length for Reddit."
        result_optimal = checker.check(optimal)
        assert result_optimal.compliance_score >= 0.95


class TestFinanceDisclaimer:
    """金融免责声明测试"""

    def test_auto_append_disclaimer_intent_a(self, checker):
        """测试A组意图自动附加免责声明"""
        assert checker.should_auto_append_disclaimer("A") is True

    def test_auto_append_disclaimer_intent_b(self, checker):
        """测试B组意图自动附加免责声明"""
        assert checker.should_auto_append_disclaimer("B") is True

    def test_no_auto_append_disclaimer_intent_c(self, checker):
        """测试C组意图不自动附加"""
        assert checker.should_auto_append_disclaimer("C") is False

    def test_get_disclaimer_text(self, checker):
        """测试获取免责声明文本"""
        disclaimer = checker.get_disclaimer_text()
        assert isinstance(disclaimer, str)
        assert len(disclaimer) > 0
        assert "not financial advice" in disclaimer.lower()


class TestComplianceScoring:
    """合规评分测试"""

    def test_perfect_compliance_score(self, checker):
        """测试完美合规评论"""
        perfect_text = "TRC20 offers lower transfer fees compared to ERC20. From my experience, it's worth checking if your exchange supports it. What's been your approach?"

        result = checker.check(perfect_text)

        assert result.passed is True
        assert result.compliance_score >= 0.95
        assert result.block_reason == ""

    def test_multiple_soft_violations(self, checker):
        """测试多个软约束违规累积"""
        # 同时违反：情绪强度 + 绝对化 + 过长
        problematic = "This is ABSOLUTELY AMAZING! Everyone MUST always use TRC20, NEVER EVER use ERC20! " * 20

        result = checker.check(problematic)

        # 多个软约束应该累积降低分数
        assert result.compliance_score < 0.90

    def test_edge_case_whitelist_links(self, checker):
        """测试白名单链接边界情况"""
        test_cases = [
            ("Visit https://reddit.com/r/CryptoCurrency", True),
            ("Check https://etherscan.io/tx/0x123", True),
            ("See https://tronscan.org/#/", True),
            ("More at https://bitcoin.org/en/", True),
            ("Details at https://not-whitelisted.com", False),
        ]

        for text, should_pass in test_cases:
            result = checker.check(text)
            assert result.passed == should_pass, f"Failed for: {text}"


class TestPoliciesConfiguration:
    """配置加载测试"""

    def test_policies_loaded(self, checker):
        """测试政策配置正确加载"""
        assert checker.policies is not None
        assert "hard_bans" in checker.policies
        assert "soft_rules" in checker.policies
        assert "enforcement" in checker.policies

    def test_hard_bans_phrases_loaded(self, checker):
        """测试硬禁词列表加载"""
        hard_bans = checker.policies["hard_bans"]
        assert "phrases" in hard_bans
        assert len(hard_bans["phrases"]) > 0
        assert "guaranteed profit" in hard_bans["phrases"]

    def test_soft_rules_loaded(self, checker):
        """测试软约束配置加载"""
        soft_rules = checker.policies["soft_rules"]
        assert "emotional_intensity" in soft_rules
        assert "absolutism" in soft_rules
        assert "length" in soft_rules

    def test_enforcement_policy_loaded(self, checker):
        """测试执行策略加载"""
        enforcement = checker.policies["enforcement"]
        assert "rewrite_on_soft_violation" in enforcement
        assert "block_on_hard_violation" in enforcement
        assert enforcement["block_on_hard_violation"] is True


class TestComplianceCheckModel:
    """ComplianceCheck模型测试"""

    def test_passed_result_structure(self, checker):
        """测试通过结果的数据结构"""
        result = checker.check("This is a clean, compliant comment.")

        assert isinstance(result, ComplianceCheck)
        assert result.passed is True
        assert 0.0 <= result.compliance_score <= 1.0
        assert result.block_reason == ""
        assert isinstance(result.soft_violations, list)

    def test_failed_result_structure(self, checker):
        """测试失败结果的数据结构"""
        result = checker.check("Guaranteed profit! Buy now!")

        assert isinstance(result, ComplianceCheck)
        assert result.passed is False
        assert result.compliance_score < 1.0
        assert len(result.block_reason) > 0
        assert isinstance(result.soft_violations, list)


class TestRealWorldScenarios:
    """真实场景测试"""

    def test_typical_a_group_comment(self, checker):
        """测试典型A组评论（费用转账）"""
        comment = "honestly, TRC20 is way cheaper for USDT transfers. I've been using it for months and saved a lot on fees. Just make sure your exchange supports it. What's been your experience?"

        result = checker.check(comment)
        assert result.passed is True
        assert result.compliance_score >= 0.95

    def test_typical_b_group_comment(self, checker):
        """测试典型B组评论（钱包问题）"""
        comment = "first things first, check if you copied the address correctly. Then verify the network (TRC20 vs ERC20). Withdrawals can take 10-30 minutes depending on the exchange. Let me know if it works."

        result = checker.check(comment)
        assert result.passed is True
        assert result.compliance_score >= 0.95

    def test_typical_c_group_comment(self, checker):
        """测试典型C组评论（新手指导）"""
        comment = "when I started, I was confused too. TRC20 is a network standard on TRON blockchain, similar to ERC20 on Ethereum. The main difference is fees - TRC20 is much cheaper. Hope that helps!"

        result = checker.check(comment)
        assert result.passed is True
        assert result.compliance_score >= 0.95

    def test_borderline_promotional(self, checker):
        """测试边界情况：接近营销的评论"""
        comment = "TRC20 is the best option! Everyone should switch immediately! You'll save so much money, it's incredible!"

        result = checker.check(comment)
        # 应该因情绪强度和绝对化降低分数
        assert result.compliance_score < 0.95

    def test_spam_like_pattern(self, checker):
        """测试垃圾信息模式"""
        spam = "Click here for free crypto! Limited time! Act now! Guaranteed returns!"

        result = checker.check(spam)
        assert result.passed is False
        assert "guaranteed" in result.block_reason.lower() or "free money" in result.block_reason.lower()
