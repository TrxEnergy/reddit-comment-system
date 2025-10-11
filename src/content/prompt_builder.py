"""
M4内容工厂 - Prompt构建器
负责模块化拼装6个Block构成完整的AI生成Prompt
[FIX 2025-10-10] 新增：轻量模板池、推广嵌入策略
"""

from typing import Dict, Any, Optional
from pathlib import Path
import random
import yaml

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
    [FIX 2025-10-10] 新增：模板骨架、推广情境嵌入
    """

    def __init__(
        self,
        policies_config: Dict,
        templates_path: Optional[Path] = None,
        promotion_config_path: Optional[Path] = None
    ):
        """
        初始化Prompt构建器

        Args:
            policies_config: content_policies.yaml配置
            templates_path: light_templates.yaml路径
            promotion_config_path: promotion_embedding.yaml路径
        """
        self.policies = policies_config

        # [FIX 2025-10-10] 加载轻量模板
        self.templates = {}
        if templates_path and templates_path.exists():
            with open(templates_path, 'r', encoding='utf-8') as f:
                templates_data = yaml.safe_load(f)
                self.templates = templates_data.get('templates', {})

        # [FIX 2025-10-10] 加载推广策略
        self.promotion_config = {}
        if promotion_config_path and promotion_config_path.exists():
            with open(promotion_config_path, 'r', encoding='utf-8') as f:
                self.promotion_config = yaml.safe_load(f)

    def build_prompt(
        self,
        persona: Persona,
        post: Dict[str, Any],
        intent_group: IntentGroup,
        style_guide: StyleGuide,
        suggestion: str = "",
        base_template: str = None
    ) -> str:
        """
        构建完整Prompt
        [FIX 2025-10-10] 新增：传递post_lang到format_block
        [FIX 2025-10-11] 改为模板加工模式

        Args:
            persona: Persona对象
            post: 帖子信息（title/subreddit/score/age/lang等）
            intent_group: 意图组
            style_guide: 风格卡
            suggestion: M3的评论建议
            base_template: 基础软文模板（来自template_loader）

        Returns:
            完整Prompt字符串
        """
        post_lang = post.get('lang', 'en')

        # [FIX 2025-10-11] 如果提供了base_template，使用加工模式
        if base_template:
            blocks = [
                self._build_role_block(persona),
                self._build_template_adaptation_block(base_template, post, style_guide),
                self._build_style_block(style_guide, persona),
                self._build_brevity_constraints()
            ]
        else:
            # 原有生成模式（保留向后兼容）
            blocks = [
                self._build_role_block(persona),
                self._build_context_block(post, style_guide, suggestion),
                self._build_intent_block(intent_group),
                self._build_style_block(style_guide, persona),
                self._build_safety_block(intent_group),
                self._build_format_block(style_guide, post_lang)
            ]

        prompt = "\n\n".join(blocks)

        logger.debug(
            "Built prompt",
            persona_id=persona.id,
            intent_group=intent_group.name,
            subreddit=style_guide.subreddit,
            post_lang=post_lang,
            mode="template_adaptation" if base_template else "generation"
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
        [FIX 2025-10-10] 新增：语言检测和匹配
        """
        title = post.get('title', '')
        subreddit = post.get('subreddit', '')
        score = post.get('score', 0)
        age_hours = post.get('age_hours', 0)
        post_lang = post.get('lang', 'en')

        freshness = "very fresh" if age_hours < 2 else "recent" if age_hours < 12 else "older"

        block = f"""[CONTEXT]
Post: "{title}"
Subreddit: r/{subreddit}
Post score: {score} | Age: {age_hours:.1f}h ({freshness})
Community tone: {style_guide.tone}
Post language: {post_lang}
"""

        if suggestion:
            block += f"Suggested angle: {suggestion}\n"

        return block.strip()

    def _build_intent_block(self, intent_group: IntentGroup) -> str:
        """
        构建意图Block
        定义响应目标和焦点
        [FIX 2025-10-10] 新增：轻量模板建议、推广情境嵌入
        """
        response_style = intent_group.response_style

        block = f"""[INTENT: {intent_group.name}]
Goal: {intent_group.description}
Focus on: {response_style.get('focus', '')}
Must include: {response_style.get('must_include', '')}
Avoid: {response_style.get('avoid', '')}
"""

        # [FIX 2025-10-10] 添加轻量模板建议
        template_hint = self._get_template_hint(intent_group.name)
        if template_hint:
            block += f"\nTemplate suggestion (optional): \"{template_hint}\"\n"

        # [FIX 2025-10-10] 添加推广情境（如果符合条件）
        promotion_context = self._get_promotion_context(intent_group.name)
        if promotion_context:
            block += f"\n{promotion_context}\n"

        return block.strip()

    def _get_template_hint(self, intent_group_name: str) -> str:
        """
        根据意图组获取模板提示
        """
        # 映射：A->fee_related, B->wallet_issues, C->learning_share
        template_map = {
            'A': 'fee_related',
            'B': 'wallet_issues',
            'C': 'learning_share'
        }

        template_category = template_map.get(intent_group_name)
        if not template_category or not self.templates:
            return ""

        templates_list = self.templates.get(template_category, [])
        if not templates_list:
            return ""

        # 随机选择一个模板
        template_item = random.choice(templates_list)
        return template_item.get('template', '')

    def _get_promotion_context(self, intent_group_name: str) -> str:
        """
        根据意图组获取推广情境提示（情境化嵌入TRC20优势）
        """
        if not self.promotion_config:
            return ""

        # 获取意图组的推广密度配置
        mention_styles = self.promotion_config.get('mention_style_by_intent', {})
        intent_key = f"intent_{intent_group_name}_" + ("fees" if intent_group_name == "A" else "wallet" if intent_group_name == "B" else "learning")

        intent_config = mention_styles.get(intent_key, {})
        mention_prob = intent_config.get('mention_probability', 0)

        # 根据概率决定是否添加推广提示
        if random.random() > mention_prob:
            return ""

        # 获取软提及示例
        soft_mentions = self.promotion_config.get('soft_mentions', {}).get('trc20_advantages', [])
        if not soft_mentions:
            return ""

        # 随机选择一个自然提及方式
        mention_item = random.choice(soft_mentions)
        mention_text = mention_item.get('mention', '')
        context_keywords = mention_item.get('context', [])

        if not mention_text:
            return ""

        return f"""[CONTEXTUAL MENTION - Optional]
IF the post discusses {', '.join(context_keywords[:2])}, you may naturally mention: "{mention_text}"
Remember: Only if truly relevant to the discussion. Do not force it."""

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

    def _build_format_block(self, style_guide: StyleGuide, post_lang: str = 'en') -> str:
        """
        构建格式Block
        定义句式结构和多样性要求
        [FIX 2025-10-10] 新增：语言匹配指令
        """
        lang_instruction = self._get_language_instruction(post_lang)

        block = f"""[FORMAT]
{lang_instruction}

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

    def _get_language_instruction(self, post_lang: str) -> str:
        """
        根据帖子语言生成语言匹配指令
        """
        lang_map = {
            'en': "Write your comment in English, matching the post's language.",
            'es': "Escribe tu comentario en español, matching el idioma del post.",
            'zh': "用中文写评论，与帖子语言保持一致。",
            'pt': "Escreva seu comentário em português, correspondendo ao idioma do post.",
            'ru': "Напишите комментарий на русском языке, соответствующий языку поста."
        }
        return lang_map.get(post_lang, "Write your comment in the same language as the post.")

    def _build_template_adaptation_block(
        self,
        base_template: str,
        post: Dict,
        style_guide: StyleGuide
    ) -> str:
        """
        [新增 2025-10-11] 构建模板加工Block

        将任务从"生成评论"改为"轻度加工模板"

        Args:
            base_template: 基础软文模板
            post: 帖子信息
            style_guide: 风格指南

        Returns:
            模板加工指令Block
        """
        post_title = post.get('title', '')
        post_lang = post.get('lang', 'en')
        subreddit = post.get('subreddit', '')

        block = f"""[TASK: ADAPT TEMPLATE]
Your task is to LIGHTLY ADAPT this template into a natural Reddit comment:

Template: "{base_template}"

Post context:
- Title: "{post_title}"
- Subreddit: r/{subreddit}
- Post language: {post_lang}

CRITICAL RULES:
1. If template language matches post language → Use template directly or add MINIMAL filler words (tbh, imo, honestly)
2. If languages differ → Translate but KEEP IT SHORT (under 30 words)
3. DO NOT expand the template - stay close to original length
4. DO NOT add questions, disclaimers, or extra sentences
5. DO NOT explain or elaborate beyond the template
6. Maintain the casual, direct tone of the original template

Output ONLY the adapted comment text (no explanations):"""

        return block.strip()

    def _build_brevity_constraints(self) -> str:
        """
        [新增 2025-10-11] 构建简洁性约束Block

        强制AI保持简短输出

        Returns:
            简洁性约束Block
        """
        block = """[BREVITY CONSTRAINTS]
ABSOLUTE REQUIREMENTS:
- Maximum 30 words total
- Maximum 2 sentences
- DO NOT add any content beyond adapting the template
- DO NOT add "Not financial advice" or similar disclaimers (promotion will add them)
- Keep it SHORT and DIRECT - users won't read long comments

Output format: Just the adapted comment text, nothing else."""

        return block.strip()
