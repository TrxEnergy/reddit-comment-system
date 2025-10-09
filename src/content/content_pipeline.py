"""
M4内容工厂 - 主管道
端到端的评论生成流程编排
[FIX 2025-10-10] 更新：传入新配置文件路径（模板/自然化/推广/分层）
"""

import asyncio
import yaml
from pathlib import Path
from typing import List, Dict, Any

from src.content.models import CommentRequest, GeneratedComment
from src.content.persona_manager import PersonaManager
from src.content.intent_router import IntentRouter
from src.content.style_guide_loader import StyleGuideLoader
from src.content.comment_generator import CommentGenerator
from src.content.quota_manager import QuotaManager
from src.content.ai_client import AIClient
from src.content.prompt_builder import PromptBuilder
from src.content.naturalizer import Naturalizer
from src.core.logging import get_logger
from src.core.config import settings

logger = get_logger(__name__)


class ContentPipeline:
    """
    M4主管道
    协调所有模块，实现端到端的评论生成流程
    """

    def __init__(self, config_base_path: Path):
        """
        初始化内容管道
        [FIX 2025-10-10] 新增：加载轻量模板、自然化、推广、分层配置

        Args:
            config_base_path: 配置文件基础路径（项目根目录）
        """
        self.config_base = config_base_path

        # [FIX 2025-10-10] 加载content_policies（PromptBuilder需要）
        policies_path = config_base_path / "config" / "content_policies.yaml"
        with open(policies_path, 'r', encoding='utf-8') as f:
            policies_config = yaml.safe_load(f)

        # 初始化各模块
        self.persona_manager = PersonaManager(
            config_path=config_base_path / "data" / "personas" / "persona_bank.yaml",
            account_tiers_path=config_base_path / "config" / "account_tiers.yaml"  # [FIX 2025-10-10]
        )
        self.intent_router = IntentRouter(
            config_base_path / "data" / "intents" / "intent_groups.yaml"
        )
        self.style_guide_loader = StyleGuideLoader(
            config_base_path / "data" / "styles" / "sub_style_guides.yaml"
        )

        # [FIX 2025-10-10] 初始化PromptBuilder（传入模板和推广配置）
        self.prompt_builder = PromptBuilder(
            policies_config=policies_config,
            templates_path=config_base_path / "data" / "templates" / "light_templates.yaml",
            promotion_config_path=config_base_path / "config" / "promotion_embedding.yaml"
        )

        # [FIX 2025-10-10] 初始化Naturalizer（传入自然化策略）
        self.naturalizer = Naturalizer(
            naturalization_policy_path=config_base_path / "config" / "naturalization_policy.yaml"
        )

        self.ai_client = AIClient()
        self.comment_generator = CommentGenerator(
            ai_client=self.ai_client,
            policies_path=policies_path,
            variants_count=2
        )

        self.quota_manager = QuotaManager(
            account_daily_limit=1,
            window_type="rolling"
        )

        # 统计
        self.stats = {
            "processed": 0,
            "generated": 0,
            "quota_denied": 0,
            "quality_failed": 0,
            "errors": 0
        }

        logger.info("ContentPipeline initialized with enhanced configs")

    async def process_batch(
        self,
        screening_results: List[Dict[str, Any]]
    ) -> List[GeneratedComment]:
        """
        批量处理M3筛选结果

        流程:
        1. 意图路由
        2. Persona选择
        3. 风格卡加载
        4. 配额预检
        5. 生成评论
        6. 质量放行检查
        7. 配额记账

        Args:
            screening_results: M3筛选结果列表（包含post_bundle和metadata）

        Returns:
            合格的GeneratedComment列表
        """
        results = []

        for post_bundle in screening_results:
            try:
                self.stats["processed"] += 1

                # 解析CommentRequest
                request = self._parse_request(post_bundle)

                # 1. 意图路由
                intent_group = self.intent_router.route(
                    post_title=request.title,
                    post_metadata=request.screening_metadata
                )

                # 2. Persona选择
                try:
                    persona = self.persona_manager.select_persona(
                        intent_group=intent_group.name,
                        subreddit=request.subreddit,
                        post_metadata=request.screening_metadata
                    )
                except ValueError as e:
                    logger.warning(f"No eligible persona: {e}")
                    self.stats["errors"] += 1
                    continue

                # 3. 风格卡加载
                style_guide = self.style_guide_loader.load(request.subreddit)

                # 4. 配额预检（账户日配额=1）
                if not self.quota_manager.check_account_quota(request.account_id):
                    logger.info(
                        "Account quota exceeded",
                        account_id=request.account_id
                    )
                    self.stats["quota_denied"] += 1
                    continue

                # 5. 生成评论
                try:
                    comment = await self.comment_generator.generate(
                        request=request,
                        persona=persona,
                        intent_group=intent_group,
                        style_guide=style_guide
                    )
                except Exception as e:
                    logger.error(f"Generation failed: {e}")
                    self.stats["errors"] += 1
                    continue

                # 6. 质量放行检查
                if not self._meets_thresholds(comment.quality_scores.model_dump()):
                    logger.info(
                        "Comment failed quality threshold",
                        scores=comment.quality_scores.model_dump()
                    )
                    self.stats["quality_failed"] += 1
                    continue

                # 7. 配额记账
                self.quota_manager.mark_account_used(request.account_id)
                self.persona_manager.mark_persona_used(
                    persona_id=persona.id,
                    subreddit=request.subreddit,
                    post_id=request.post_id
                )

                results.append(comment)
                self.stats["generated"] += 1

                logger.info(
                    "Comment generated and approved",
                    request_id=request.post_id,
                    account_id=request.account_id,
                    quality=comment.quality_scores.overall
                )

            except Exception as e:
                logger.error(f"Unexpected error processing post: {e}")
                self.stats["errors"] += 1
                continue

        logger.info(
            "Batch processing completed",
            stats=self.stats
        )

        return results

    def _parse_request(self, post_bundle: Dict) -> CommentRequest:
        """
        从M3结果解析CommentRequest

        Args:
            post_bundle: M3的post_bundle字典

        Returns:
            CommentRequest对象
        """
        return CommentRequest(
            post_id=post_bundle.get('post_id', post_bundle.get('id', 'unknown')),
            title=post_bundle.get('title', ''),
            subreddit=post_bundle.get('subreddit', ''),
            score=post_bundle.get('score', 0),
            age_hours=post_bundle.get('age_hours', 0),
            lang=post_bundle.get('lang', 'en'),
            screening_metadata=post_bundle.get('screening_metadata', {}),
            priority=post_bundle.get('priority', 0.5),
            account_id=post_bundle.get('account_id', 'test_account'),
            account_username=post_bundle.get('account_username', 'test_user')
        )

    def _meets_thresholds(self, scores: Dict[str, float]) -> bool:
        """
        检查质量评分是否达到放行阈值

        顶级评论阈值:
        - relevance ≥ 0.85
        - natural ≥ 0.85
        - compliance ≥ 0.95

        Args:
            scores: 质量评分字典

        Returns:
            是否达到阈值
        """
        return (
            scores.get('relevance', 0) >= 0.85 and
            scores.get('natural', 0) >= 0.85 and
            scores.get('compliance', 0) >= 0.95
        )

    def get_stats(self) -> Dict:
        """获取管道统计信息"""
        return {
            **self.stats,
            "persona_stats": self.persona_manager.get_persona_stats(),
            "quota_statuses": self.quota_manager.get_all_statuses()
        }

    def reset_stats(self):
        """重置统计（测试用）"""
        self.stats = {
            "processed": 0,
            "generated": 0,
            "quota_denied": 0,
            "quality_failed": 0,
            "errors": 0
        }
        logger.info("Pipeline stats reset")


# CLI接口（可选，用于命令行测试）
async def main():
    """命令行入口"""
    import json
    from pathlib import Path

    # 示例：从文件加载M3筛选结果
    pipeline = ContentPipeline(Path(__file__).parent.parent.parent)

    # 示例测试数据
    test_data = [
        {
            "post_id": "test_001",
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
    ]

    results = await pipeline.process_batch(test_data)

    print(f"\n✅ Generated {len(results)} comments")
    for comment in results:
        print(f"\n--- Comment ---")
        print(f"Persona: {comment.persona_used}")
        print(f"Quality: {comment.quality_scores.overall:.2f}")
        print(f"Text: {comment.text}")

    print(f"\n📊 Stats: {pipeline.get_stats()}")


if __name__ == "__main__":
    asyncio.run(main())
