"""
模板加载器 - 从基础软文模板库中选择合适的模板

[创建日期 2025-10-11] M4模板化改造
"""
import json
import random
from typing import Dict, List, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class TemplateLoader:
    """
    从1017条基础软文模板中加载和选择模板

    模板结构:
    {
        "lang": "zh|en|es|pt|ar|hi|id|th|tr|vi",
        "category": "fee|speed|wallet|saving|experience|complaint",
        "tone": "casual|tip|complaint|recommendation|Q&A",
        "promo_level": "B|C",
        "text": "实际模板内容"
    }
    """

    def __init__(self, template_path: str):
        """
        初始化模板加载器

        Args:
            template_path: 模板文件路径
        """
        self.template_path = Path(template_path)
        self.templates: List[Dict] = []
        self._load_templates()
        self._build_index()

    def _load_templates(self):
        """加载所有模板"""
        try:
            if not self.template_path.exists():
                logger.error(f"模板文件不存在: {self.template_path}")
                return

            with open(self.template_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        template = json.loads(line)
                        self.templates.append(template)
                    except json.JSONDecodeError as e:
                        logger.warning(f"第{line_num}行JSON解析失败: {e}")

            logger.info(f"成功加载 {len(self.templates)} 条模板")

        except Exception as e:
            logger.error(f"加载模板失败: {e}")

    def _build_index(self):
        """构建索引以加速查询"""
        self.index = {}
        for template in self.templates:
            lang = template.get('lang')
            category = template.get('category')

            if lang not in self.index:
                self.index[lang] = {}
            if category not in self.index[lang]:
                self.index[lang][category] = []

            self.index[lang][category].append(template)

        logger.info(f"索引构建完成: {len(self.index)} 种语言")

    def select_template(
        self,
        post_lang: str,
        intent_group: str,
        fallback_lang: str = "en"
    ) -> Optional[Dict]:
        """
        根据帖子语言和意图组选择模板

        Args:
            post_lang: 帖子语言 (zh, en, es, pt, ar, hi, id, th, tr, vi)
            intent_group: 意图组 (A_fees_transfers, B_wallet_issues, C_learning_share)
            fallback_lang: 后备语言，当post_lang没有模板时使用

        Returns:
            选中的模板字典，如果没有找到返回None
        """
        # 意图组映射到类别
        intent_to_category = {
            'A_fees_transfers': 'fee',
            'B_wallet_issues': 'wallet',
            'C_learning_share': 'saving',
        }

        category = intent_to_category.get(intent_group)
        if not category:
            logger.warning(f"未知意图组: {intent_group}")
            return None

        # 尝试获取指定语言的模板
        candidates = self._get_candidates(post_lang, category)

        # 如果没找到，使用后备语言
        if not candidates and fallback_lang:
            logger.info(f"语言 {post_lang} 没有 {category} 类别模板，使用后备语言 {fallback_lang}")
            candidates = self._get_candidates(fallback_lang, category)

        # 随机选择
        if candidates:
            selected = random.choice(candidates)
            logger.info(f"选中模板: lang={selected['lang']}, category={selected['category']}, "
                       f"tone={selected['tone']}, text_preview={selected['text'][:30]}...")
            return selected

        logger.warning(f"未找到匹配的模板: post_lang={post_lang}, category={category}")
        return None

    def _get_candidates(self, lang: str, category: str) -> List[Dict]:
        """获取候选模板列表"""
        if lang in self.index and category in self.index[lang]:
            return self.index[lang][category]
        return []

    def get_stats(self) -> Dict:
        """获取模板统计信息"""
        stats = {
            'total': len(self.templates),
            'by_language': {},
            'by_category': {}
        }

        for template in self.templates:
            lang = template.get('lang', 'unknown')
            category = template.get('category', 'unknown')

            stats['by_language'][lang] = stats['by_language'].get(lang, 0) + 1
            stats['by_category'][category] = stats['by_category'].get(category, 0) + 1

        return stats

    def validate_coverage(self) -> Dict:
        """
        验证模板覆盖度

        Returns:
            覆盖度报告
        """
        expected_langs = ['zh', 'en', 'es', 'pt', 'ar', 'hi', 'id', 'th', 'tr', 'vi']
        expected_categories = ['fee', 'speed', 'wallet', 'saving', 'experience', 'complaint']

        coverage = {
            'missing_combinations': [],
            'coverage_percentage': 0
        }

        total_combinations = len(expected_langs) * len(expected_categories)
        covered = 0

        for lang in expected_langs:
            for category in expected_categories:
                candidates = self._get_candidates(lang, category)
                if candidates:
                    covered += 1
                else:
                    coverage['missing_combinations'].append(f"{lang}-{category}")

        coverage['coverage_percentage'] = (covered / total_combinations) * 100

        return coverage


# 全局单例
_loader_instance: Optional[TemplateLoader] = None


def get_template_loader(template_path: Optional[str] = None) -> TemplateLoader:
    """
    获取全局模板加载器实例

    Args:
        template_path: 模板文件路径（仅首次调用时需要）
    """
    global _loader_instance

    if _loader_instance is None:
        if template_path is None:
            raise ValueError("首次调用必须提供 template_path")
        _loader_instance = TemplateLoader(template_path)

    return _loader_instance
