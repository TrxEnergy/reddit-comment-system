"""
M4内容工厂 - 自然化处理器
负责检查和优化评论的自然度和多样性
"""

import re
from typing import List, Dict
from collections import Counter

from src.content.models import Persona
from src.core.logging import get_logger

logger = get_logger(__name__)


class Naturalizer:
    """
    自然化处理器
    检查句式多样性、口头禅密度、n-gram重复度
    """

    def __init__(self, ngram_window_days: int = 7, max_ngram_reuse: float = 0.35):
        """
        初始化自然化处理器

        Args:
            ngram_window_days: n-gram去重窗口（天）
            max_ngram_reuse: 最大n-gram重复率
        """
        self.ngram_window_days = ngram_window_days
        self.max_ngram_reuse = max_ngram_reuse
        self.ngram_history: List[str] = []  # 存储历史8-gram

    def process(
        self,
        comment_text: str,
        persona: Persona
    ) -> str:
        """
        处理评论文本，确保自然度

        处理步骤：
        1. 检查句式多样性
        2. 检查口头禅密度
        3. 检查n-gram重复（与历史对比）
        4. 必要时返回修改建议

        Args:
            comment_text: 原始评论文本
            persona: 使用的Persona

        Returns:
            处理后的评论文本（当前版本直接返回，未来可加自动修改）
        """
        # 1. 句式多样性检查
        sentence_issues = self._check_sentence_variety(comment_text)
        if sentence_issues:
            logger.debug("Sentence variety issues detected", issues=sentence_issues)

        # 2. 口头禅密度检查
        catchphrase_issues = self._check_catchphrase_density(
            comment_text,
            persona.catchphrases
        )
        if catchphrase_issues:
            logger.debug("Catchphrase density issues detected", issues=catchphrase_issues)

        # 3. n-gram重复度检查
        ngram_issues = self._check_ngram_uniqueness(comment_text)
        if ngram_issues:
            logger.warning("N-gram repetition detected", issues=ngram_issues)

        # 记录当前评论的8-gram到历史
        self._record_ngrams(comment_text)

        # 当前版本直接返回，未来可根据issues自动修改
        return comment_text

    def _check_sentence_variety(self, text: str) -> List[str]:
        """
        检查句式多样性

        检查：
        - 是否至少包含2种句式（陈述/疑问/列表）
        - 句式结构重复率是否超过50%
        """
        issues = []

        sentences = [s.strip() for s in re.split(r'[.!?]', text) if s.strip()]
        if len(sentences) < 2:
            return issues  # 太短，无需检查

        # 统计句式类型
        statements = sum(1 for s in sentences if not s.endswith('?'))
        questions = sum(1 for s in sentences if s.endswith('?'))

        sentence_types = sum([statements > 0, questions > 0])
        if sentence_types < 2:
            issues.append("Only one sentence type detected")

        # 检查句子结构重复（简化：检查开头词）
        opening_words = [s.split()[0].lower() for s in sentences if s.split()]
        if opening_words:
            most_common_count = Counter(opening_words).most_common(1)[0][1]
            repeat_ratio = most_common_count / len(opening_words)
            if repeat_ratio > 0.5:
                issues.append(f"Sentence structure repetition: {repeat_ratio:.0%}")

        return issues

    def _check_catchphrase_density(
        self,
        text: str,
        catchphrases: Dict[str, List[str]]
    ) -> List[str]:
        """
        检查口头禅密度

        目标：同persona 7天内口头禅不超过20%
        """
        issues = []

        all_phrases = []
        for phrases_list in catchphrases.values():
            all_phrases.extend(phrases_list)

        text_lower = text.lower()
        sentences = [s.strip() for s in re.split(r'[.!?]', text) if s.strip()]

        catchphrase_count = sum(1 for phrase in all_phrases if phrase.lower() in text_lower)
        if not sentences:
            return issues

        density = catchphrase_count / len(sentences)
        if density > 0.20:
            issues.append(f"Catchphrase density too high: {density:.0%} (max 20%)")

        return issues

    def _check_ngram_uniqueness(self, text: str) -> List[str]:
        """
        检查8-gram重复度

        与历史记录对比，重复率不超过35%
        """
        issues = []

        current_ngrams = self._extract_8grams(text)
        if not current_ngrams:
            return issues

        # 与历史对比
        if self.ngram_history:
            overlap = sum(1 for ng in current_ngrams if ng in self.ngram_history)
            reuse_ratio = overlap / len(current_ngrams)

            if reuse_ratio > self.max_ngram_reuse:
                issues.append(
                    f"8-gram reuse rate: {reuse_ratio:.0%} (max {self.max_ngram_reuse:.0%})"
                )

        return issues

    def _extract_8grams(self, text: str) -> List[str]:
        """
        提取文本中的8-gram（连续8个词）

        Returns:
            8-gram字符串列表
        """
        words = text.split()
        if len(words) < 8:
            return []

        ngrams = []
        for i in range(len(words) - 7):
            ngram = ' '.join(words[i:i+8])
            ngrams.append(ngram.lower())

        return ngrams

    def _record_ngrams(self, text: str):
        """记录当前评论的8-gram到历史"""
        ngrams = self._extract_8grams(text)
        self.ngram_history.extend(ngrams)

        # 限制历史大小（保留最近1000个）
        if len(self.ngram_history) > 1000:
            self.ngram_history = self.ngram_history[-1000:]

    def clear_history(self):
        """清空n-gram历史（测试/调试用）"""
        self.ngram_history.clear()
        logger.info("Cleared n-gram history")
