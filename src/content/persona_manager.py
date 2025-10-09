"""
M4内容工厂 - Persona管理器
负责加载、选择和管理Persona，处理冷却和使用统计
"""

import yaml
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from src.content.models import Persona, PersonaUsageRecord
from src.core.logging import get_logger

logger = get_logger(__name__)


class PersonaManager:
    """
    Persona管理器
    负责Persona的加载、选择、冷却管理和使用统计
    """

    def __init__(self, config_path: Path):
        """
        初始化Persona管理器

        Args:
            config_path: persona_bank.yaml配置文件路径
        """
        self.config_path = config_path
        self.personas: Dict[str, Persona] = {}
        self.usage_history: List[PersonaUsageRecord] = []
        self.usage_stats: Dict[str, int] = defaultdict(int)

        self._load_personas()

    def _load_personas(self):
        """从YAML文件加载Persona配置"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            personas_data = data.get('personas', [])
            for persona_data in personas_data:
                persona = Persona(**persona_data)
                self.personas[persona.id] = persona

            logger.info(
                f"Loaded {len(self.personas)} personas",
                persona_ids=list(self.personas.keys())
            )

        except Exception as e:
            logger.error(f"Failed to load personas: {e}")
            raise

    def get_persona(self, persona_id: str) -> Optional[Persona]:
        """
        根据ID获取Persona

        Args:
            persona_id: Persona ID

        Returns:
            Persona对象，如果不存在返回None
        """
        return self.personas.get(persona_id)

    def select_persona(
        self,
        intent_group: str,
        subreddit: str,
        post_metadata: Optional[Dict] = None
    ) -> Persona:
        """
        根据意图组和子版选择最佳Persona

        选择逻辑:
        1. 筛选intent_group匹配的personas
        2. 检查compatible_subreddits（如果有定义）
        3. 检查冷却状态（720分钟内未在同子版使用）
        4. 根据使用频率选择最少使用的

        Args:
            intent_group: 意图组（A/B/C）
            subreddit: 子版名称
            post_metadata: 帖子元数据（可选，用于进一步筛选）

        Returns:
            选中的Persona

        Raises:
            ValueError: 无可用Persona时
        """
        # 1. 筛选intent_group匹配的personas
        candidates = [
            p for p in self.personas.values()
            if intent_group in p.intent_groups
        ]

        if not candidates:
            raise ValueError(f"No personas found for intent group: {intent_group}")

        # 2. 检查subreddit兼容性
        candidates = self._filter_by_subreddit(candidates, subreddit)

        # 3. 检查冷却状态
        candidates = self._filter_by_cooldown(candidates, subreddit)

        if not candidates:
            logger.warning(
                "No personas available after cooldown filter",
                intent_group=intent_group,
                subreddit=subreddit
            )
            # 降级：忽略冷却，重新筛选
            candidates = [
                p for p in self.personas.values()
                if intent_group in p.intent_groups
            ]
            candidates = self._filter_by_subreddit(candidates, subreddit)

        if not candidates:
            raise ValueError(
                f"No eligible personas for intent={intent_group}, subreddit={subreddit}"
            )

        # 4. 选择使用频率最少的
        selected = self._select_least_used(candidates)

        logger.info(
            "Selected persona",
            persona_id=selected.id,
            intent_group=intent_group,
            subreddit=subreddit
        )

        return selected

    def _filter_by_subreddit(
        self,
        candidates: List[Persona],
        subreddit: str
    ) -> List[Persona]:
        """
        根据subreddit兼容性筛选Persona

        如果Persona定义了compatible_subreddits，则只保留匹配的；
        如果未定义，则认为兼容所有子版
        """
        filtered = []
        for persona in candidates:
            compatible_subs = persona.constraints.get('compatible_subreddits')
            if compatible_subs is None or subreddit in compatible_subs:
                filtered.append(persona)

        return filtered if filtered else candidates

    def _filter_by_cooldown(
        self,
        candidates: List[Persona],
        subreddit: str
    ) -> List[Persona]:
        """
        根据冷却状态筛选Persona

        检查每个persona在该subreddit的最近使用时间，
        如果在冷却期内（默认720分钟），则排除
        """
        now = datetime.now()
        filtered = []

        for persona in candidates:
            cooldown_minutes = persona.constraints.get('cool_down_minutes_same_post', 720)
            cooldown_delta = timedelta(minutes=cooldown_minutes)

            # 查找该persona在该subreddit的最近使用记录
            recent_usage = [
                record for record in self.usage_history
                if (
                    record.persona_id == persona.id and
                    record.subreddit == subreddit and
                    now - record.used_at < cooldown_delta
                )
            ]

            if not recent_usage:
                filtered.append(persona)
            else:
                logger.debug(
                    "Persona in cooldown",
                    persona_id=persona.id,
                    subreddit=subreddit,
                    last_used=recent_usage[-1].used_at
                )

        return filtered

    def _select_least_used(self, candidates: List[Persona]) -> Persona:
        """
        从候选列表中选择使用频率最少的Persona

        使用usage_stats计数器，选择计数最小的；
        如果有多个相同计数，选择第一个（稳定排序）
        """
        return min(candidates, key=lambda p: self.usage_stats[p.id])

    def mark_persona_used(
        self,
        persona_id: str,
        subreddit: str,
        post_id: str,
        comment_id: Optional[str] = None
    ):
        """
        记录Persona使用，用于冷却管理和统计

        Args:
            persona_id: 使用的Persona ID
            subreddit: 子版名称
            post_id: 帖子ID
            comment_id: 评论ID（可选）
        """
        record = PersonaUsageRecord(
            persona_id=persona_id,
            subreddit=subreddit,
            post_id=post_id,
            used_at=datetime.now(),
            comment_id=comment_id
        )

        self.usage_history.append(record)
        self.usage_stats[persona_id] += 1

        logger.debug(
            "Marked persona used",
            persona_id=persona_id,
            subreddit=subreddit,
            total_usage=self.usage_stats[persona_id]
        )

    def get_persona_stats(self) -> Dict:
        """
        返回Persona使用统计

        Returns:
            统计信息字典，包含：
            - total_personas: 总Persona数
            - usage_counts: 各Persona使用次数
            - recent_usage: 最近24小时使用记录
        """
        now = datetime.now()
        recent_cutoff = now - timedelta(hours=24)

        recent_usage = [
            record for record in self.usage_history
            if record.used_at > recent_cutoff
        ]

        return {
            "total_personas": len(self.personas),
            "usage_counts": dict(self.usage_stats),
            "recent_usage_24h": len(recent_usage),
            "usage_by_persona": {
                pid: sum(1 for r in recent_usage if r.persona_id == pid)
                for pid in self.personas.keys()
            }
        }

    def reset_cooldowns(self):
        """重置所有冷却（测试/调试用）"""
        self.usage_history.clear()
        logger.info("Reset all persona cooldowns")

    def get_available_personas(
        self,
        intent_group: str,
        subreddit: str
    ) -> List[Persona]:
        """
        获取当前可用的Persona列表（考虑冷却）

        Args:
            intent_group: 意图组
            subreddit: 子版

        Returns:
            可用的Persona列表
        """
        candidates = [
            p for p in self.personas.values()
            if intent_group in p.intent_groups
        ]
        candidates = self._filter_by_subreddit(candidates, subreddit)
        candidates = self._filter_by_cooldown(candidates, subreddit)

        return candidates
