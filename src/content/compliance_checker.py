"""
M4内容工厂 - 合规检查器
负责检查评论是否符合平台规则和内容政策
"""

import re
import yaml
from pathlib import Path
from typing import List, Dict, Any

from src.content.models import ComplianceCheck
from src.core.logging import get_logger

logger = get_logger(__name__)


class ComplianceChecker:
    """
    合规检查器
    检查评论内容是否违反硬禁止规则和软约束
    """

    def __init__(self, policies_path: Path):
        """
        初始化合规检查器

        Args:
            policies_path: content_policies.yaml配置文件路径
        """
        self.policies_path = policies_path
        self.policies: Dict = {}

        self._load_policies()

    def _load_policies(self):
        """从YAML文件加载内容政策"""
        try:
            with open(self.policies_path, 'r', encoding='utf-8') as f:
                self.policies = yaml.safe_load(f)

            logger.info("Loaded content policies")

        except Exception as e:
            logger.error(f"Failed to load content policies: {e}")
            raise

    def check(self, comment_text: str) -> ComplianceCheck:
        """
        检查评论合规性

        Args:
            comment_text: 评论文本

        Returns:
            ComplianceCheck对象
        """
        hard_violations = self._check_hard_bans(comment_text)
        soft_violations = self._check_soft_rules(comment_text)

        # 硬禁止违规直接不通过
        if hard_violations:
            return ComplianceCheck(
                passed=False,
                hard_violations=hard_violations,
                soft_violations=soft_violations,
                rewrite_needed=False,
                block_reason=f"Hard ban violated: {', '.join(hard_violations)}",
                compliance_score=0.0
            )

        # 软约束违规：计算合规度评分
        compliance_score = self._calculate_compliance_score(soft_violations)

        # 是否需要重写（合规度<0.95但不是硬禁止）
        rewrite_needed = compliance_score < 0.95 and compliance_score > 0.7

        passed = compliance_score >= 0.95

        return ComplianceCheck(
            passed=passed,
            hard_violations=[],
            soft_violations=soft_violations,
            rewrite_needed=rewrite_needed,
            block_reason=None if passed else "Low compliance score",
            compliance_score=compliance_score
        )

    def _check_hard_bans(self, text: str) -> List[str]:
        """
        检查硬禁止违规

        检查内容：
        - 禁止短语
        - 禁止模式（正则）
        - 链接政策
        - 私信引导
        """
        violations = []
        text_lower = text.lower()

        hard_bans = self.policies.get('hard_bans', {})

        # 检查禁止短语
        phrases = hard_bans.get('phrases', [])
        for phrase in phrases:
            if phrase.lower() in text_lower:
                violations.append(f"Phrase: {phrase}")

        # 检查禁止模式（正则）
        patterns = hard_bans.get('patterns', [])
        for pattern_item in patterns:
            regex = pattern_item.get('regex', '')
            description = pattern_item.get('description', '')
            if re.search(regex, text_lower):
                violations.append(f"Pattern: {description}")

        # 检查链接政策
        links_config = hard_bans.get('links', {})
        if not links_config.get('allow', False):
            # 检查是否包含链接
            url_pattern = r'https?://[^\s]+'
            if re.search(url_pattern, text):
                # 检查是否在白名单
                whitelist = links_config.get('whitelist', [])
                urls = re.findall(url_pattern, text)
                for url in urls:
                    if not any(domain in url for domain in whitelist):
                        violations.append(f"Unauthorized link: {url[:50]}")

        # 检查私信引导
        if not hard_bans.get('private_contact', True):
            private_keywords = ['dm me', 'pm me', 'message me', 'contact me']
            if any(kw in text_lower for kw in private_keywords):
                violations.append("Private contact solicitation")

        return violations

    def _check_soft_rules(self, text: str) -> List[Dict[str, Any]]:
        """
        检查软约束违规

        检查内容：
        - 情绪强度
        - 绝对化措辞
        - 长度
        - 句式多样性
        """
        violations = []
        soft_rules = self.policies.get('soft_rules', {})

        # 1. 情绪强度检查
        emotional_config = soft_rules.get('emotional_intensity', {})
        max_level = emotional_config.get('max_level', 2)
        check_words = emotional_config.get('check_words', [])

        emotional_count = sum(1 for word in check_words if word.lower() in text.lower())
        if emotional_count > max_level:
            violations.append({
                "rule": "emotional_intensity",
                "severity": "medium",
                "detail": f"{emotional_count} emotional words (max {max_level})"
            })

        # 2. 绝对化措辞检查
        absolutism_config = soft_rules.get('absolutism', {})
        max_ratio = absolutism_config.get('max_ratio', 0.1)
        trigger_words = absolutism_config.get('trigger_words', [])

        words = text.split()
        absolutism_count = sum(1 for word in words if word.lower() in trigger_words)
        absolutism_ratio = absolutism_count / max(len(words), 1)

        if absolutism_ratio > max_ratio:
            violations.append({
                "rule": "absolutism",
                "severity": "medium",
                "detail": f"{absolutism_ratio:.2%} absolutist words (max {max_ratio:.0%})"
            })

        # 3. 长度检查
        length_config = soft_rules.get('length', {})
        min_chars = length_config.get('min_chars', 20)
        max_chars = length_config.get('max_chars', 600)

        char_count = len(text)
        if char_count < min_chars:
            violations.append({
                "rule": "length",
                "severity": "high",
                "detail": f"Too short: {char_count} chars (min {min_chars})"
            })
        elif char_count > max_chars:
            violations.append({
                "rule": "length",
                "severity": "medium",
                "detail": f"Too long: {char_count} chars (max {max_chars})"
            })

        # 4. 句式多样性检查
        variety_config = soft_rules.get('sentence_variety', {})
        min_types = variety_config.get('min_sentence_types', 2)

        sentences = [s.strip() for s in re.split(r'[.!?]', text) if s.strip()]
        has_statement = any(not s.endswith('?') for s in sentences)
        has_question = any(s.endswith('?') for s in sentences)

        sentence_types = sum([has_statement, has_question])
        if sentence_types < min_types:
            violations.append({
                "rule": "sentence_variety",
                "severity": "low",
                "detail": f"Only {sentence_types} sentence types (min {min_types})"
            })

        return violations

    def _calculate_compliance_score(self, soft_violations: List[Dict]) -> float:
        """
        根据软约束违规计算合规度评分

        评分规则：
        - 起始1.0分
        - high severity: -0.10
        - medium severity: -0.05
        - low severity: -0.02
        """
        score = 1.0

        severity_penalty = {
            "high": 0.10,
            "medium": 0.05,
            "low": 0.02
        }

        for violation in soft_violations:
            severity = violation.get('severity', 'low')
            score -= severity_penalty.get(severity, 0.02)

        return max(0.0, score)

    def should_auto_append_disclaimer(self, intent_group: str) -> bool:
        """
        判断是否需要自动附加免责声明

        Args:
            intent_group: 意图组（A/B/C）

        Returns:
            是否需要附加免责声明
        """
        disclaimer_config = self.policies.get('soft_rules', {}).get('finance_disclaimer', {})
        auto_append = disclaimer_config.get('auto_append', False)
        trigger_groups = disclaimer_config.get('trigger_intent_groups', ['A', 'B'])

        return auto_append and intent_group in trigger_groups

    def get_disclaimer_text(self) -> str:
        """获取免责声明文本"""
        disclaimer_config = self.policies.get('soft_rules', {}).get('finance_disclaimer', {})
        return disclaimer_config.get('text', 'Not financial advice.')
