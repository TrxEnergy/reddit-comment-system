"""
M4内容工厂 - Prompt构建器
负责模块化拼装6个Block构成完整的AI生成Prompt
"""

from typing import Dict, Any
import random

from src.content.models import Persona, IntentGroup, StyleGuide
from src.core.logging import get_logger

logger = get_logger(__name__)


class PromptBuilder:
    """
    Prompt构建器
    采用6个Block模块化拼装策略：
    - ROLE_BLOCK: Persona背景和口头禅
    - CONTEXT_BLOCK: 帖子信息和子版风格
    - INTENT_BLOCK: 意图组目标
    - STYLE_BLOCK: 风格约束
    - SAFETY_BLOCK: 合规提示
    - FORMAT_BLOCK: 格式要求
    """

    def __init__(self, policies_config: Dict):
        """
        初始化Prompt构建器

        Args:
            policies_config: content_policies.yaml配置
        """
        self.policies = policies_config

    def build_prompt(
        self,
        persona: Persona,
        post: Dict[str, Any],
        intent_group: IntentGroup,
        style_guide: StyleGuide,
        suggestion: str = ""
    ) -> str:
        """
        构建完整Prompt

        Args:
            persona: Persona对象
            post: 帖子信息（title/subreddit/score/age等）
            intent_group: 意图组
            style_guide: 风格卡
            suggestion: M3的评论建议

        Returns:
            完整Prompt字符串
        """
        blocks = [
            self._build_role_block(persona),
            self._build_context_block(post, style_guide, suggestion),
            self._build_intent_block(intent_group),
            self._build_style_block(style_guide, persona),
            self._build_safety_block(intent_group),
            self._build_format_block(style_guide)
        ]

        prompt = "\n\n".join(blocks)

        logger.debug(
            "Built prompt",
            persona_id=persona.id,
            intent_group=intent_group.name,
            subreddit=style_guide.subreddit
        )

        return prompt

    def _build_role_block(self, persona: Persona) -> str:
        """
        构建角色Block
        包含Persona的背景、语气和口头禅示例
        """
        # 随机选择2-3个口头禅示例
        opening_examples = random.sample(
            persona.catchphrases['opening'],
            min(2, len(persona.catchphrases['opening']))
        )
        ending_examples = random.sample(
            persona.catchphrases['ending'],
            min(2, len(persona.catchphrases['ending']))
        )

        block = f"""[ROLE]
You are {persona.name}. {persona.background}
Your tone is {persona.tone}.
You naturally use phrases like: {', '.join(opening_examples)} (to open), {', '.join(ending_examples)} (to close).
Your areas of interest: {', '.join(persona.interests[:3])}.
"""
        return block.strip()

    def _build_context_block(
        self,
        post: Dict,
        style_guide: StyleGuide,
        suggestion: str
    ) -> str:
        """
        构建上下文Block
        包含帖子信息、子版风格和M3建议
        """
        title = post.get('title', '')
        subreddit = post.get('subreddit', '')
        score = post.get('score', 0)
        age_hours = post.get('age_hours', 0)

        freshness = "very fresh" if age_hours < 2 else "recent" if age_hours < 12 else "older"

        block = f"""[CONTEXT]
Post: "{title}"
Subreddit: r/{subreddit}
Post score: {score} | Age: {age_hours:.1f}h ({freshness})
Community tone: {style_guide.tone}
"""

        if suggestion:
            block += f"Suggested angle: {suggestion}\n"

        return block.strip()

    def _build_intent_block(self, intent_group: IntentGroup) -> str:
        """
        构建意图Block
        定义响应目标和焦点
        """
        response_style = intent_group.response_style

        block = f"""[INTENT: {intent_group.name}]
Goal: {intent_group.description}
Focus on: {response_style.get('focus', '')}
Must include: {response_style.get('must_include', '')}
Avoid: {response_style.get('avoid', '')}
"""
        return block.strip()

    def _build_style_block(
        self,
        style_guide: StyleGuide,
        persona: Persona
    ) -> str:
        """
        构建风格Block
        定义长度、语气和子版特定要求
        """
        length = style_guide.length
        chars_range = f"{length.get('chars', {}).get('min', 50)}-{length.get('chars', {}).get('max', 400)}"

        block = f"""[STYLE]
Length: {chars_range} characters, {length.get('top_level_sentences', {}).get('min', 2)}-{length.get('top_level_sentences', {}).get('max', 4)} sentences
Jargon level: {style_guide.jargon_level}
Must end with question: {style_guide.must_end_with_question}

DO:
{chr(10).join('- ' + item for item in style_guide.dos[:3])}

DON'T:
{chr(10).join('- ' + item for item in style_guide.donts[:3])}
"""
        return block.strip()

    def _build_safety_block(self, intent_group: IntentGroup) -> str:
        """
        构建安全Block
        包含合规要求和禁止事项
        """
        hard_bans = self.policies.get('hard_bans', {})
        phrases = hard_bans.get('phrases', [])[:5]

        block = f"""[SAFETY]
Absolutely forbidden: {', '.join(phrases)}
No links, no private contact info, no referral codes.
"""

        # A/B组需要金融免责声明
        if intent_group.name in ['A', 'B']:
            block += "End with: 'Not financial advice.'\n"

        return block.strip()

    def _build_format_block(self, style_guide: StyleGuide) -> str:
        """
        构建格式Block
        定义句式结构和多样性要求
        """
        block = """[FORMAT]
Structure:
1. Opening with a catchphrase or direct response
2. Main point with specific details or personal experience
3. Closing with a question or helpful suggestion (if required by subreddit)

Sentence variety:
- Mix statements, questions, and brief lists
- Avoid repeating sentence structures
- Use natural transitions
"""
        return block.strip()
