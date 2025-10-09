"""
M4内容工厂 - 自然化处理器
负责检查和优化评论的自然度和多样性
"""

import re
import random
import yaml
from pathlib import Path
from typing import List, Dict, Optional
from collections import Counter

from src.content.models import Persona
from src.core.logging import get_logger

logger = get_logger(__name__)


class Naturalizer:
    """
    自然化处理器
    检查句式多样性、口头禅密度、n-gram重复度
    [FIX 2025-10-10] 新增：口头禅注入、自然瑕疵添加、句式多样化
    """

    def __init__(
        self,
        ngram_window_days: int = 7,
        max_ngram_reuse: float = 0.35,
        naturalization_policy_path: Optional[Path] = None
    ):
        """
        初始化自然化处理器

        Args:
            ngram_window_days: n-gram去重窗口（天）
            max_ngram_reuse: 最大n-gram重复率
            naturalization_policy_path: 自然化策略配置文件路径
        """
        self.ngram_window_days = ngram_window_days
        self.max_ngram_reuse = max_ngram_reuse
        self.ngram_history: List[str] = []  # 存储历史8-gram

        # [FIX 2025-10-10] 加载自然化策略配置
        self.policy = {}
        if naturalization_policy_path and naturalization_policy_path.exists():
            with open(naturalization_policy_path, 'r', encoding='utf-8') as f:
                self.policy = yaml.safe_load(f)
        else:
            # 默认策略
            self.policy = self._default_policy()

    def process(
        self,
        comment_text: str,
        persona: Persona
    ) -> str:
        """
        处理评论文本，确保自然度

        [FIX 2025-10-10] 新增自动处理步骤：
        1. 注入口头禅（根据Persona）
        2. 添加自然瑕疵（表情、错字、口语词）
        3. 句式多样化
        4. 检查质量（句式、密度、n-gram）

        Args:
            comment_text: 原始评论文本
            persona: 使用的Persona

        Returns:
            处理后的自然化评论文本
        """
        # [FIX 2025-10-10] 步骤1：注入口头禅
        text = self.inject_catchphrases(comment_text, persona)

        # [FIX 2025-10-10] 步骤2：添加自然瑕疵
        text = self.add_natural_imperfections(text)

        # [FIX 2025-10-10] 步骤3：句式多样化
        text = self.vary_sentence_structure(text)

        # 原有检查流程
        sentence_issues = self._check_sentence_variety(text)
        if sentence_issues:
            logger.debug("Sentence variety issues detected", issues=sentence_issues)

        catchphrase_issues = self._check_catchphrase_density(
            text,
            persona.catchphrases
        )
        if catchphrase_issues:
            logger.debug("Catchphrase density issues detected", issues=catchphrase_issues)

        ngram_issues = self._check_ngram_uniqueness(text)
        if ngram_issues:
            logger.warning("N-gram repetition detected", issues=ngram_issues)

        self._record_ngrams(text)

        return text

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

    # [FIX 2025-10-10] 新增方法

    def inject_catchphrases(self, text: str, persona: Persona) -> str:
        """
        随机注入Persona口头禅（开头/过渡/结尾）

        策略：
        - 25%概率在开头注入opening catchphrase
        - 20%概率在中间注入transition catchphrase
        - 30%概率在结尾注入ending catchphrase
        """
        # [FIX 2025-10-10] 修复：使用更好的句子分割，保留标点
        sentences = re.split(r'(?<=[.!?])\s+', text)
        if len(sentences) < 2:
            return text  # 太短，不注入

        # 开头注入（25%概率）
        if random.random() < 0.25 and persona.catchphrases.get('opening'):
            opening_phrase = random.choice(persona.catchphrases['opening'])
            # 如果第一句不是以口头禅开头，则添加
            if not any(sentences[0].lower().startswith(p.lower()) for p in persona.catchphrases.get('opening', [])):
                sentences[0] = f"{opening_phrase} {sentences[0]}"

        # 过渡注入（20%概率，插入中间）
        if random.random() < 0.20 and persona.catchphrases.get('transition'):
            if len(sentences) >= 3:  # 至少3句才插入中间
                transition_phrase = random.choice(persona.catchphrases['transition'])
                mid_idx = len(sentences) // 2
                sentences[mid_idx] = f"{transition_phrase} {sentences[mid_idx]}"

        # 结尾注入（30%概率）
        if random.random() < 0.30 and persona.catchphrases.get('ending'):
            ending_phrase = random.choice(persona.catchphrases['ending'])
            # 在最后添加
            if not sentences[-1].endswith('.'):
                sentences[-1] += '.'
            sentences[-1] = sentences[-1].rstrip('.') + f'. {ending_phrase}'

        return ' '.join(sentences)

    def add_natural_imperfections(self, text: str) -> str:
        """
        添加自然瑕疵（表情、轻微错字、口语填充词）

        参考naturalization_policy.yaml:
        - emoji: 25%概率，最多1个
        - typo: 15%概率，最多1个
        - filler_words: 35%概率
        """
        # 1. 表情符号（25%概率）
        emoji_policy = self.policy.get('emoji_policy', {})
        if emoji_policy.get('allow', True) and random.random() < emoji_policy.get('probability', 0.25):
            emojis = emoji_policy.get('appropriate_emojis', ['👍', '😂', '🙏', '🤔', '👀'])
            emoji = random.choice(emojis)
            # 优先放在结尾
            text = text.rstrip() + f" {emoji}"

        # 2. 轻微错字（15%概率）
        typo_policy = self.policy.get('typo_policy', {})
        if typo_policy.get('allow_light_typos', True) and random.random() < typo_policy.get('probability', 0.15):
            allowed_typos = typo_policy.get('allowed_typos', [])
            if allowed_typos:
                typo_pair = random.choice(allowed_typos)
                original = typo_pair.get('original', '')
                typo = typo_pair.get('typo', '')
                # 只替换一次
                text = text.replace(original, typo, 1)

        # 3. 口语填充词（35%概率）
        filler_policy = self.policy.get('filler_words', {})
        if filler_policy.get('allow', True) and random.random() < filler_policy.get('probability', 0.35):
            fillers = filler_policy.get('common_fillers', ['tbh', 'imo', 'honestly'])
            filler = random.choice(fillers)
            # 插入到第一句开头
            sentences = re.split(r'([.!?])', text, maxsplit=1)
            if sentences:
                sentences[0] = f"{filler}, {sentences[0]}"
                text = ''.join(sentences)

        return text

    def vary_sentence_structure(self, text: str) -> str:
        """
        句式多样化（轻量实现）

        策略：
        - 添加省略号（20%概率）
        - 调整标点（避免过多感叹号）
        """
        punctuation = self.policy.get('punctuation_variety', {})

        # 省略号替换（20%概率）
        if punctuation.get('allow_ellipsis', True) and random.random() < punctuation.get('ellipsis_probability', 0.20):
            # 将某个句号替换为省略号
            text = re.sub(r'\.(\s+)', r'...\1', text, count=1)

        # 感叹号节制（最多1个）
        if punctuation.get('exclamation_moderation', True):
            exclamation_count = text.count('!')
            max_allowed = punctuation.get('max_exclamations_per_comment', 1)
            if exclamation_count > max_allowed:
                # 保留第一个，其余替换为句号
                parts = text.split('!')
                text = parts[0] + '!' + '.'.join(parts[1:])

        return text

    def _default_policy(self) -> Dict:
        """默认自然化策略（当配置文件不存在时）"""
        return {
            'emoji_policy': {
                'allow': True,
                'probability': 0.25,
                'max_per_comment': 1,
                'appropriate_emojis': ['👍', '😂', '🙏', '🤔', '👀']
            },
            'typo_policy': {
                'allow_light_typos': True,
                'probability': 0.15,
                'max_typo_ratio': 0.03,
                'allowed_typos': [
                    {'original': 'transfer', 'typo': 'tranfer'},
                    {'original': 'receive', 'typo': 'recieve'},
                    {'original': 'definitely', 'typo': 'definately'}
                ]
            },
            'filler_words': {
                'allow': True,
                'probability': 0.35,
                'common_fillers': ['tbh', 'imo', 'fwiw', 'honestly', 'actually'],
                'max_filler_ratio': 0.1
            },
            'punctuation_variety': {
                'allow_ellipsis': True,
                'ellipsis_probability': 0.20,
                'exclamation_moderation': True,
                'max_exclamations_per_comment': 1
            }
        }
