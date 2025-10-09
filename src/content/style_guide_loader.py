"""
M4内容工厂 - 子版风格卡加载器
负责加载和管理Subreddit风格指南
"""

import yaml
from pathlib import Path
from typing import Dict, Optional

from src.content.models import StyleGuide
from src.core.logging import get_logger

logger = get_logger(__name__)


class StyleGuideLoader:
    """
    子版风格卡加载器
    负责加载特定Subreddit的风格指南，提供默认fallback
    """

    def __init__(self, config_path: Path):
        """
        初始化风格卡加载器

        Args:
            config_path: sub_style_guides.yaml配置文件路径
        """
        self.config_path = config_path
        self.style_guides: Dict[str, StyleGuide] = {}
        self.default_guide: Optional[StyleGuide] = None

        self._load_style_guides()

    def _load_style_guides(self):
        """从YAML文件加载风格卡配置"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            styles_data = data.get('styles', [])
            for style_data in styles_data:
                style_guide = StyleGuide(**style_data)

                if style_guide.subreddit == 'default':
                    self.default_guide = style_guide
                else:
                    self.style_guides[style_guide.subreddit] = style_guide

            logger.info(
                f"Loaded {len(self.style_guides)} style guides",
                subreddits=list(self.style_guides.keys())
            )

        except Exception as e:
            logger.error(f"Failed to load style guides: {e}")
            raise

    def load(self, subreddit: str) -> StyleGuide:
        """
        加载指定Subreddit的风格卡

        如果该子版没有专属风格卡，返回默认风格卡

        Args:
            subreddit: 子版名称

        Returns:
            StyleGuide对象
        """
        style_guide = self.style_guides.get(subreddit)

        if style_guide:
            logger.debug(f"Loaded style guide for {subreddit}")
            return style_guide
        else:
            logger.debug(
                f"No specific style guide for {subreddit}, using default"
            )
            return self.default_guide

    def get_all_subreddits(self) -> list:
        """
        获取所有已配置的Subreddit列表

        Returns:
            Subreddit名称列表
        """
        return list(self.style_guides.keys())

    def has_guide(self, subreddit: str) -> bool:
        """
        检查是否有特定子版的风格卡

        Args:
            subreddit: 子版名称

        Returns:
            是否存在专属风格卡
        """
        return subreddit in self.style_guides
