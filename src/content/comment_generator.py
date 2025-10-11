"""
M4内容工厂 - 评论生成器
整合所有模块，执行完整的评论生成流程
[FIX 2025-10-10] 新增：链接推广模块集成
"""

from pathlib import Path
from typing import List, Optional

from src.content.models import (
    Persona,
    IntentGroup,
    StyleGuide,
    CommentRequest,
    GeneratedComment,
    QualityScores,
    ComplianceCheck
)
from src.content.ai_client import AIClient
from src.content.prompt_builder import PromptBuilder
from src.content.naturalizer import Naturalizer
from src.content.compliance_checker import ComplianceChecker
from src.content.quality_scorer import QualityScorer
from src.content.link_promoter import LinkPromoter
from src.content.template_loader import TemplateLoader
from src.core.logging import get_logger

logger = get_logger(__name__)


class CommentGenerator:
    """
    评论生成器
    负责完整的评论生成流程：Prompt构建 → AI生成 → 自然化 → 合规检查 → 质量评分
    """

    def __init__(
        self,
        ai_client: AIClient,
        policies_path: Path,
        variants_count: int = 2,
        promotion_config_path: Optional[Path] = None,
        template_path: Optional[str] = None
    ):
        """
        初始化评论生成器
        [FIX 2025-10-10] 新增：推广配置路径参数
        [FIX 2025-10-11] 新增：模板路径参数

        Args:
            ai_client: AI客户端
            policies_path: content_policies.yaml路径
            variants_count: 生成变体数量
            promotion_config_path: promotion_embedding.yaml路径(可选)
            template_path: 基础软文模板路径(可选)
        """
        self.ai_client = ai_client
        self.variants_count = variants_count

        # 加载合规政策
        self.compliance_checker = ComplianceChecker(policies_path)

        # 初始化子模块
        self.prompt_builder = PromptBuilder(self.compliance_checker.policies)
        self.naturalizer = Naturalizer()
        self.quality_scorer = QualityScorer()

        # [FIX 2025-10-10] 初始化链接推广器
        self.link_promoter = None
        if promotion_config_path and promotion_config_path.exists():
            self.link_promoter = LinkPromoter(promotion_config_path)
            logger.info("LinkPromoter enabled")

        # [FIX 2025-10-11] 初始化模板加载器
        self.template_loader = None
        if template_path:
            self.template_loader = TemplateLoader(template_path)
            stats = self.template_loader.get_stats()
            logger.info(f"TemplateLoader enabled: {stats['total']} templates loaded")

        logger.info("CommentGenerator initialized")

    async def generate(
        self,
        request: CommentRequest,
        persona: Persona,
        intent_group: IntentGroup,
        style_guide: StyleGuide
    ) -> GeneratedComment:
        """
        生成评论（完整流程）

        流程:
        1. 构建Prompt
        2. 调用AI生成（含变体）
        3. 自然化处理
        4. 合规审查（过滤不合格的）
        5. 质量评分
        6. 返回最佳候选

        Args:
            request: 评论生成请求
            persona: 使用的Persona
            intent_group: 意图组
            style_guide: 风格卡

        Returns:
            GeneratedComment对象

        Raises:
            Exception: 无法生成合格评论时
        """
        logger.info(
            "Generating comment",
            request_id=request.post_id,
            persona=persona.id,
            intent_group=intent_group.name
        )

        # [FIX 2025-10-11] 0. 如果启用模板加载器，选择基础模板
        base_template = None
        if self.template_loader:
            template_obj = self.template_loader.select_template(
                post_lang=request.lang,
                intent_group=intent_group.name
            )
            if template_obj:
                base_template = template_obj['text']
                logger.info(f"Selected template: {base_template[:50]}...")
            else:
                logger.warning("No template found, fallback to generation mode")

        # 1. 构建Prompt
        post_dict = {
            "title": request.title,
            "subreddit": request.subreddit,
            "score": request.score,
            "age_hours": request.age_hours,
            "lang": request.lang
        }
        suggestion = request.screening_metadata.get('suggestion', '')

        prompt = self.prompt_builder.build_prompt(
            persona=persona,
            post=post_dict,
            intent_group=intent_group,
            style_guide=style_guide,
            suggestion=suggestion,
            base_template=base_template
        )

        # 2. AI生成（含重试）
        try:
            variants = await self.ai_client.generate(
                prompt=prompt,
                n=self.variants_count
            )
        except Exception as e:
            logger.error(f"AI generation failed: {e}")
            raise Exception(f"Failed to generate comment: {e}")

        if not variants:
            raise Exception("AI generated no variants")

        # 3. 自然化处理
        processed_variants = []
        for variant in variants:
            processed = self.naturalizer.process(variant, persona)
            processed_variants.append(processed)

        # 4. 合规审查 + 自动附加免责声明
        # [FIX 2025-10-10] 支持位置随机化（开头/中间/结尾）和概率性添加
        compliant_variants = []
        for variant in processed_variants:
            # 检查是否需要附加免责声明
            if self.compliance_checker.should_auto_append_disclaimer(intent_group.name):
                position, disclaimer = self.compliance_checker.get_disclaimer_insertion_strategy()
                variant = self._insert_disclaimer(variant, disclaimer, position)

            compliance_check = self.compliance_checker.check(variant)

            if compliance_check.passed:
                compliant_variants.append((variant, compliance_check))
            else:
                logger.debug(
                    "Variant failed compliance",
                    reason=compliance_check.block_reason
                )

        if not compliant_variants:
            raise Exception("No variants passed compliance check")

        # 5. 质量评分
        scored_variants = []
        for variant_text, compliance_check in compliant_variants:
            scores = self.quality_scorer.score(
                comment_text=variant_text,
                post=post_dict,
                compliance_score=compliance_check.compliance_score,
                persona_catchphrases=persona.catchphrases
            )
            scored_variants.append((variant_text, scores))

        # 6. 选择最佳候选（按overall得分）
        best_variant, best_scores = max(
            scored_variants,
            key=lambda x: x[1].overall
        )

        # [FIX 2025-10-10] 7. 链接推广插入(在最终文本生成后)
        # [FIX 2025-10-11] 传递subreddit和style_guide以支持双模式推广
        promoted_link = None
        if self.link_promoter:
            should_promote = self.link_promoter.should_insert_link(
                intent_group=intent_group.name,
                account_id=request.account_id,
                subreddit=request.subreddit,
                style_guide=style_guide.__dict__
            )

            if should_promote:
                best_variant, promoted_link = self.link_promoter.insert_link(
                    comment_text=best_variant,
                    intent_group=intent_group.name,
                    account_id=request.account_id,
                    post_lang=request.lang,
                    subreddit=request.subreddit,
                    style_guide=style_guide.__dict__
                )

        # 构建GeneratedComment
        result = GeneratedComment(
            text=best_variant,
            persona_used=persona.id,
            intent_group=intent_group.name,
            style_guide_id=style_guide.subreddit,
            quality_scores=best_scores,
            audit={
                "policy_version": "1.0.0",
                "style_version": "1.0.0",
                "persona_version": "1.0.0",
                "rule_hits": [],
                "promoted_link": promoted_link  # 记录推广链接
            },
            timestamps={
                "generated_at": __import__('datetime').datetime.now(),
                "passed_checks_at": __import__('datetime').datetime.now()
            },
            variants=[v for v, _ in scored_variants if v != best_variant],
            request_id=request.post_id
        )

        logger.info(
            "Comment generated successfully",
            request_id=request.post_id,
            quality=best_scores.overall,
            variants_count=len(scored_variants),
            promoted=promoted_link is not None
        )

        return result

    def _insert_disclaimer(self, text: str, disclaimer: str, position: str) -> str:
        """
        在指定位置插入免责声明

        [FIX 2025-10-10] 新增：支持开头/中间/结尾三种位置

        Args:
            text: 原始评论文本
            disclaimer: 免责声明文本
            position: 插入位置（"start" | "middle" | "end"）

        Returns:
            插入免责声明后的文本
        """
        if position == "start":
            return f"{disclaimer} {text}"

        elif position == "middle":
            # 在文本中间插入（找到句子中点）
            sentences = [s.strip() for s in text.split('.') if s.strip()]
            if len(sentences) <= 1:
                # 只有一句话，追加到结尾
                return f"{text} {disclaimer}"

            # 插入到中间句子之后
            mid_point = len(sentences) // 2
            first_half = '. '.join(sentences[:mid_point]) + '.'
            second_half = '. '.join(sentences[mid_point:]) + '.'
            return f"{first_half} {disclaimer} {second_half}"

        else:  # position == "end"
            return f"{text} {disclaimer}"
