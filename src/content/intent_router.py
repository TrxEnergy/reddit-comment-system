"""
M4内容工厂 - 意图路由器
负责将帖子分类到意图组（A/B/C）
"""

import yaml
from pathlib import Path
from typing import Dict, Optional

from src.content.models import IntentGroup
from src.core.logging import get_logger

logger = get_logger(__name__)


class IntentRouter:
    """
    意图路由器
    根据帖子内容和M3元数据，将帖子分类到A/B/C意图组
    """

    def __init__(self, config_path: Path):
        """
        初始化意图路由器

        Args:
            config_path: intent_groups.yaml配置文件路径
        """
        self.config_path = config_path
        self.intent_groups: Dict[str, IntentGroup] = {}
        self.routing_rules: Dict = {}

        self._load_intent_groups()

    def _load_intent_groups(self):
        """从YAML文件加载意图组配置"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            groups_data = data.get('groups', {})
            for group_id, group_data in groups_data.items():
                group_data['name'] = group_id  # 使用A/B/C作为name
                intent_group = IntentGroup(**group_data)
                self.intent_groups[group_id] = intent_group

            self.routing_rules = data.get('routing_rules', {})

            logger.info(
                f"Loaded {len(self.intent_groups)} intent groups",
                groups=list(self.intent_groups.keys())
            )

        except Exception as e:
            logger.error(f"Failed to load intent groups: {e}")
            raise

    def route(
        self,
        post_title: str,
        post_metadata: Optional[Dict] = None
    ) -> IntentGroup:
        """
        根据帖子标题和元数据路由到意图组

        路由逻辑:
        1. 优先使用M3的suggestion字段（如果有明确意图）
        2. 统计各意图组的positive_clues匹配数
        3. 扣除negative_lookalikes匹配数
        4. 选择得分最高的意图组
        5. 如果无明确匹配，使用fallback_group（默认C）

        Args:
            post_title: 帖子标题
            post_metadata: M3元数据（可选，包含suggestion/intent_prob等）

        Returns:
            匹配的IntentGroup
        """
        title_lower = post_title.lower()

        # 如果M3提供了高置信度的意图建议，直接使用
        if post_metadata:
            suggestion = post_metadata.get('suggestion', '')
            intent_prob = post_metadata.get('intent_prob', 0)

            if intent_prob > 0.8:
                # 从suggestion中推断意图组
                inferred_group = self._infer_from_suggestion(suggestion)
                if inferred_group:
                    logger.debug(
                        "Using M3 intent suggestion",
                        inferred_group=inferred_group,
                        intent_prob=intent_prob
                    )
                    return self.intent_groups[inferred_group]

        # 统计各意图组的匹配得分
        scores = {}
        for group_id, intent_group in self.intent_groups.items():
            score = 0

            # 正向线索匹配
            for clue in intent_group.positive_clues:
                if clue.lower() in title_lower:
                    score += 1

            # 负向混淆词扣分
            for negative in intent_group.negative_lookalikes:
                if negative.lower() in title_lower:
                    score -= 1

            scores[group_id] = score

        # 选择得分最高的意图组
        if scores:
            best_group = max(scores, key=scores.get)
            best_score = scores[best_group]

            # 如果最高分>0，使用该组；否则使用fallback
            if best_score > 0:
                logger.info(
                    "Routed to intent group",
                    group=best_group,
                    score=best_score,
                    title=post_title[:50]
                )
                return self.intent_groups[best_group]

        # 使用fallback组（默认C）
        fallback = self.routing_rules.get('fallback_group', 'C')
        logger.info(
            "Using fallback intent group",
            group=fallback,
            title=post_title[:50]
        )
        return self.intent_groups[fallback]

    def _infer_from_suggestion(self, suggestion: str) -> Optional[str]:
        """
        从M3的suggestion字段推断意图组

        通过关键词匹配suggestion中的内容，推断A/B/C意图

        Args:
            suggestion: M3提供的评论建议

        Returns:
            意图组ID（A/B/C）或None
        """
        suggestion_lower = suggestion.lower()

        # A组关键词：费用、转账、能量
        a_keywords = ['fee', 'cost', 'transfer', 'energy', 'gas', 'withdrawal', 'cheaper']
        if any(kw in suggestion_lower for kw in a_keywords):
            return 'A'

        # B组关键词：交易所、钱包、KYC
        b_keywords = ['exchange', 'wallet', 'stuck', 'kyc', 'address', 'pending']
        if any(kw in suggestion_lower for kw in b_keywords):
            return 'B'

        # C组关键词：解释、学习、新手
        c_keywords = ['explain', 'learn', 'beginner', 'guide', 'understand', 'how']
        if any(kw in suggestion_lower for kw in c_keywords):
            return 'C'

        return None

    def get_intent_group(self, group_id: str) -> Optional[IntentGroup]:
        """
        根据ID获取意图组

        Args:
            group_id: 意图组ID（A/B/C）

        Returns:
            IntentGroup对象，如果不存在返回None
        """
        return self.intent_groups.get(group_id)

    def get_preferred_personas(self, group_id: str) -> list:
        """
        获取意图组的推荐Persona列表

        Args:
            group_id: 意图组ID

        Returns:
            推荐Persona ID列表
        """
        intent_group = self.intent_groups.get(group_id)
        if intent_group:
            return intent_group.preferred_personas
        return []
