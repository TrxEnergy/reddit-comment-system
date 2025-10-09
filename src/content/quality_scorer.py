"""
M4内容工厂 - 质量评分器
使用三分法（相关性/自然度/合规度）评估评论质量
"""

import re
from typing import Dict, Any, List
from collections import Counter

from src.content.models import QualityScores
from src.core.logging import get_logger

logger = get_logger(__name__)


class QualityScorer:
    """
    质量评分器
    采用三分法评分：relevance + natural + compliance
    """

    def score(
        self,
        comment_text: str,
        post: Dict[str, Any],
        compliance_score: float,
        persona_catchphrases: Dict[str, List[str]] = None
    ) -> QualityScores:
        """
        综合评分

        Args:
            comment_text: 评论文本
            post: 帖子信息
            compliance_score: 合规度评分（由ComplianceChecker提供）
            persona_catchphrases: Persona口头禅（用于自然度评分）

        Returns:
            QualityScores对象
        """
        relevance = self._score_relevance(comment_text, post)
        natural = self._score_natural(comment_text, persona_catchphrases)

        scores = QualityScores(
            relevance=relevance,
            natural=natural,
            compliance=compliance_score,
            overall=0.0  # 会自动计算
        )

        logger.debug(
            "Scored comment",
            relevance=relevance,
            natural=natural,
            compliance=compliance_score,
            overall=scores.overall
        )

        return scores

    def _score_relevance(self, comment_text: str, post: Dict) -> float:
        """
        相关性评分

        评分维度：
        - 关键词覆盖（40%）
        - 复述匹配（30%）
        - 长度适配（30%）
        """
        title = post.get('title', '').lower()
        comment_lower = comment_text.lower()

        # 1. 关键词覆盖
        title_words = set(re.findall(r'\w+', title))
        # 过滤停用词
        stopwords = {'a', 'an', 'the', 'is', 'are', 'was', 'were', 'to', 'of', 'for', 'in', 'on'}
        title_words = title_words - stopwords

        if not title_words:
            keyword_score = 0.5
        else:
            comment_words = set(re.findall(r'\w+', comment_lower))
            overlap = len(title_words & comment_words)
            keyword_score = min(1.0, overlap / len(title_words))

        # 2. 复述匹配（检查是否提到了帖子主题）
        # 简化：检查是否包含title中的核心名词
        core_nouns = self._extract_core_terms(title)
        restatement_score = sum(1 for noun in core_nouns if noun in comment_lower) / max(len(core_nouns), 1)

        # 3. 长度适配（50-400字符为最佳）
        char_count = len(comment_text)
        if 50 <= char_count <= 400:
            length_score = 1.0
        elif char_count < 50:
            length_score = char_count / 50
        else:
            length_score = max(0.5, 1 - (char_count - 400) / 400)

        # 综合评分（加权）
        relevance = (
            keyword_score * 0.40 +
            restatement_score * 0.30 +
            length_score * 0.30
        )

        return min(1.0, relevance)

    def _score_natural(
        self,
        comment_text: str,
        catchphrases: Dict[str, List[str]] = None
    ) -> float:
        """
        自然度评分

        评分维度：
        - 长度档位（30%）
        - 句式分布（30%）
        - n-gram唯一性（20%）
        - 口头禅适度（20%）
        """
        # 1. 长度档位（50-400最佳）
        char_count = len(comment_text)
        if 50 <= char_count <= 400:
            length_score = 1.0
        elif char_count < 50:
            length_score = char_count / 50
        else:
            length_score = max(0.6, 1 - (char_count - 400) / 400)

        # 2. 句式分布
        sentences = [s.strip() for s in re.split(r'[.!?]', comment_text) if s.strip()]
        if not sentences:
            sentence_score = 0.5
        else:
            # 统计句式类型
            statements = sum(1 for s in sentences if not s.endswith('?'))
            questions = sum(1 for s in sentences if s.endswith('?'))

            # 理想比例：陈述6:疑问1
            ideal_ratio = 6 / 1 if questions > 0 else 6
            actual_ratio = statements / max(questions, 1)
            sentence_score = 1 - min(0.5, abs(actual_ratio - ideal_ratio) / ideal_ratio)

        # 3. n-gram唯一性（检查重复）
        words = comment_text.split()
        if len(words) < 8:
            ngram_score = 1.0
        else:
            bigrams = [tuple(words[i:i+2]) for i in range(len(words)-1)]
            unique_ratio = len(set(bigrams)) / len(bigrams)
            ngram_score = unique_ratio

        # 4. 口头禅适度（不超过20%）
        if catchphrases:
            all_phrases = []
            for phrases_list in catchphrases.values():
                all_phrases.extend(phrases_list)

            comment_lower = comment_text.lower()
            catchphrase_count = sum(1 for phrase in all_phrases if phrase.lower() in comment_lower)
            catchphrase_ratio = catchphrase_count / max(len(sentences), 1)

            # 1-2个口头禅最佳
            if catchphrase_ratio <= 0.2:
                catchphrase_score = 1.0
            else:
                catchphrase_score = max(0.5, 1 - catchphrase_ratio)
        else:
            catchphrase_score = 1.0

        # 综合评分
        natural = (
            length_score * 0.30 +
            sentence_score * 0.30 +
            ngram_score * 0.20 +
            catchphrase_score * 0.20
        )

        return min(1.0, natural)

    def _extract_core_terms(self, text: str) -> List[str]:
        """
        从文本中提取核心术语

        简化策略：提取长度>4的单词（可能是关键词）
        """
        words = re.findall(r'\w+', text.lower())
        core_terms = [w for w in words if len(w) > 4]
        return core_terms[:5]  # 最多5个核心词
