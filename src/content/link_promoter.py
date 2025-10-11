"""
M4内容工厂 - 链接推广器
[CREATE 2025-10-10] 智能嵌入Telegram频道链接,40字以内软文
"""

import random
import yaml
from pathlib import Path
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta

from src.core.logging import get_logger

logger = get_logger(__name__)


class LinkPromoter:
    """
    链接推广器
    负责智能选择和嵌入Telegram频道链接,确保自然度和反spam
    """

    def __init__(self, promotion_config_path: Path):
        """
        初始化链接推广器

        Args:
            promotion_config_path: promotion_embedding.yaml路径
        """
        with open(promotion_config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        # 链接使用历史跟踪(内存存储,可扩展为Redis)
        self.link_usage_history = {}  # {link: last_used_timestamp}
        self.account_link_history = {}  # {account_id: {link: last_used_timestamp}}

        logger.info("LinkPromoter initialized")

    def should_insert_link(
        self,
        intent_group: str,
        account_id: str,
        subreddit: str = None,
        style_guide: dict = None
    ) -> bool:
        """
        判断是否应该插入推广链接

        [FIX 2025-10-11] 移除概率控制，只要子版允许就100%插入

        Args:
            intent_group: 意图组(A/B/C)
            account_id: 账号ID
            subreddit: 子版名称
            style_guide: 子版风格指南

        Returns:
            True=应该插入, False=跳过
        """
        # [FIX 2025-10-11] 不再使用概率控制，直接返回True
        # 只要调用此方法就应该插入推广（模式由insert_link决定）

        logger.debug(
            "Promotion decision",
            intent_group=intent_group,
            subreddit=subreddit,
            decision=True
        )

        return True

    def insert_link(
        self,
        comment_text: str,
        intent_group: str,
        account_id: str,
        post_lang: str = 'en',
        subreddit: str = None,
        style_guide: dict = None
    ) -> Tuple[str, Optional[str]]:
        """
        在评论中插入推广链接(40字以内软文)

        [FIX 2025-10-11] 新增双模式推广：链接模式 vs 文字描述模式

        Args:
            comment_text: 原始评论文本
            intent_group: 意图组(A/B/C)
            account_id: 账号ID
            post_lang: 帖子语言
            subreddit: 子版名称
            style_guide: 子版风格指南

        Returns:
            (带推广的评论文本, 使用的链接URL或None)
        """
        # [FIX 2025-10-11] 检查子版link_policy决定推广模式
        link_policy = self._get_link_policy(style_guide)

        if link_policy == 'whitelist_only':
            # 模式A：允许链接，插入URL
            return self._insert_url_mode(
                comment_text, intent_group, account_id, post_lang
            )
        else:
            # 模式B：禁止链接，使用文字描述
            # 包括: 'none', 'docs_and_github'（我们的链接不是文档类）
            return self._insert_text_mode(
                comment_text, post_lang
            )

    def _get_link_policy(self, style_guide: dict) -> str:
        """
        从style_guide中提取link_policy

        Args:
            style_guide: 子版风格指南

        Returns:
            link_policy值（none/whitelist_only/docs_and_github）
        """
        if not style_guide:
            return 'none'

        compliance = style_guide.get('compliance', {})
        return compliance.get('link_policy', 'none')

    def _insert_url_mode(
        self,
        comment_text: str,
        intent_group: str,
        account_id: str,
        post_lang: str
    ) -> Tuple[str, Optional[str]]:
        """
        模式A：插入URL链接

        Returns:
            (带链接的评论, 链接URL)
        """
        # 选择合适的链接
        selected_link = self._select_link(intent_group, account_id)
        if not selected_link:
            logger.debug("No suitable link found, skipping promotion")
            return comment_text, None

        # 生成自然嵌入文本(40字以内)
        promo_text = self._generate_promo_text(selected_link, intent_group, post_lang)

        # 确定插入位置
        placement = self._get_placement_position(intent_group)
        final_text = self._insert_at_position(comment_text, promo_text, placement)

        # 记录使用历史
        self._record_usage(selected_link, account_id)

        logger.info(
            "Link inserted (URL mode)",
            intent_group=intent_group,
            link=selected_link[:30],
            promo_length=len(promo_text)
        )

        return final_text, selected_link

    def _insert_text_mode(
        self,
        comment_text: str,
        post_lang: str
    ) -> Tuple[str, None]:
        """
        模式B：插入文字描述（luntriaOfficialChannel提及）

        [FIX 2025-10-11] 子版禁止链接时，用自然文字描述推广

        Returns:
            (带文字描述的评论, None)
        """
        # 文字描述模板（自然提及频道+价值主张）
        text_templates = {
            'en': [
                "btw luntriaOfficialChannel on TG helped me cut fees by 80%",
                "I've been using luntriaOfficialChannel on Telegram, saved me like 80% on transfer fees",
                "fwiw luntriaOfficialChannel (on TG) cuts transfer costs by ~80%"
            ],
            'zh': [
                "btw Telegram上的luntriaOfficialChannel能省80%转账费",
                "我用luntriaOfficialChannel（TG频道），手续费省了80%",
                "luntriaOfficialChannel这个TG频道能节省80%手续费"
            ],
            'es': [
                "btw luntriaOfficialChannel en TG me ayudó a reducir tarifas 80%",
                "uso luntriaOfficialChannel en Telegram, ahorro 80% en tarifas"
            ],
            'pt': [
                "btw luntriaOfficialChannel no TG me ajudou a reduzir taxas em 80%",
                "uso luntriaOfficialChannel no Telegram, economizo 80% em taxas"
            ]
        }

        # 选择对应语言模板（fallback到英文）
        templates = text_templates.get(post_lang, text_templates['en'])
        promo_text = random.choice(templates)

        # 插入到评论末尾
        final_text = f"{comment_text} {promo_text}"

        logger.info(
            "Text description inserted (Text mode)",
            post_lang=post_lang,
            promo_text=promo_text
        )

        return final_text, None

    def _select_link(self, intent_group: str, account_id: str) -> Optional[str]:
        """
        根据意图组和账号历史智能选择链接

        选择策略:
        1. 根据intent_group匹配preferred_categories
        2. 过滤冷却期内的链接(账号72小时,全局每周2次)
        3. 加权随机选择

        Returns:
            链接URL或None
        """
        # 获取意图组策略
        strategies = self.config.get('intent_group_strategies', {})
        intent_key = f"{intent_group}_fees_transfers" if intent_group == "A" else \
                     f"{intent_group}_exchange_wallet" if intent_group == "B" else \
                     f"{intent_group}_learning_sharing"

        intent_strategy = strategies.get(intent_key, {})
        preferred_cats = intent_strategy.get('preferred_categories', [])

        # 收集候选链接
        candidates = []
        for cat_config in preferred_cats:
            group_name = cat_config['group']
            subcategories = cat_config['subcategories']
            weight = cat_config['weight']

            links = self._get_links_from_group(group_name, subcategories)
            candidates.extend([(link, weight) for link in links])

        if not candidates:
            return None

        # 过滤冷却期链接
        valid_candidates = []
        now = datetime.now()

        for link, weight in candidates:
            # 检查账号级冷却(72小时)
            account_history = self.account_link_history.get(account_id, {})
            if link in account_history:
                last_used = account_history[link]
                if (now - last_used).total_seconds() < 72 * 3600:
                    continue

            # 检查全局冷却(每周2次)
            if link in self.link_usage_history:
                recent_uses = sum(
                    1 for ts in self.link_usage_history.get(link, [])
                    if (now - ts).days < 7
                )
                if recent_uses >= 2:
                    continue

            valid_candidates.append((link, weight))

        if not valid_candidates:
            # 无有效候选,放宽限制只检查账号冷却
            valid_candidates = [
                (link, weight) for link, weight in candidates
                if link not in account_history or
                (now - account_history[link]).total_seconds() >= 72 * 3600
            ]

        if not valid_candidates:
            return None

        # 加权随机选择
        links, weights = zip(*valid_candidates)
        selected = random.choices(links, weights=weights, k=1)[0]

        return selected

    def _get_links_from_group(
        self,
        group_name: str,
        subcategories: list
    ) -> list:
        """
        从配置中提取指定组和子类别的链接

        Args:
            group_name: "group_1_luntria" 或 "group_2_energy"
            subcategories: ["core", "extended"] 或 ["onboarding", "tools"]

        Returns:
            链接列表
        """
        group_data = self.config.get(group_name, {})

        links = []
        for subcat in subcategories:
            if subcat in group_data:
                subcat_data = group_data[subcat]
                if isinstance(subcat_data, list):
                    links.extend(subcat_data)
                elif isinstance(subcat_data, dict):
                    # 可能是嵌套结构(如trxenergy.core)
                    for key, value in subcat_data.items():
                        if isinstance(value, list):
                            links.extend(value)

        return links

    def _generate_promo_text(
        self,
        link: str,
        intent_group: str,
        post_lang: str
    ) -> str:
        """
        生成自然嵌入文本(40字以内)

        Args:
            link: 链接URL
            intent_group: 意图组
            post_lang: 帖子语言

        Returns:
            推广文本(含链接)
        """
        # 获取语言对应的模板
        templates = self.config.get('natural_templates', {})
        lang_templates = templates.get(post_lang, templates.get('en', {}))

        # 随机选择模板类型(contextual/experience/resource)
        template_types = list(lang_templates.keys())
        if not template_types:
            # fallback
            return f"btw {link} has useful info"

        template_type = random.choice(template_types)
        template_list = lang_templates[template_type]

        # 随机选择具体模板
        template = random.choice(template_list)

        # 填充链接
        promo_text = template.replace('{link}', link)

        # 确保不超过40字
        if len(promo_text) > 40:
            # 简化为最短形式
            promo_text = f"{link}"

        return promo_text

    def _get_placement_position(self, intent_group: str) -> str:
        """
        根据意图组获取推荐插入位置

        Args:
            intent_group: A/B/C

        Returns:
            "after_main_content" | "after_solution" | "end_as_bonus"
        """
        strategies = self.config.get('intent_group_strategies', {})
        intent_key = f"{intent_group}_fees_transfers" if intent_group == "A" else \
                     f"{intent_group}_exchange_wallet" if intent_group == "B" else \
                     f"{intent_group}_learning_sharing"

        strategy = strategies.get(intent_key, {})
        return strategy.get('placement', 'end_as_bonus')

    def _insert_at_position(
        self,
        comment_text: str,
        promo_text: str,
        placement: str
    ) -> str:
        """
        在指定位置插入推广文本

        Args:
            comment_text: 原评论
            promo_text: 推广文本
            placement: 位置策略

        Returns:
            插入后的完整文本
        """
        sentences = [s.strip() for s in comment_text.split('.') if s.strip()]

        if placement == "after_main_content":
            # 主要内容后(第一句话后)
            if len(sentences) >= 2:
                first = sentences[0] + '.'
                rest = '. '.join(sentences[1:]) + '.'
                return f"{first} {promo_text}. {rest}"
            else:
                return f"{comment_text} {promo_text}"

        elif placement == "after_solution":
            # 解决方案后(倒数第二句后)
            if len(sentences) >= 2:
                main = '. '.join(sentences[:-1]) + '.'
                last = sentences[-1] + '.'
                return f"{main} {promo_text}. {last}"
            else:
                return f"{comment_text} {promo_text}"

        else:  # "end_as_bonus"
            # 结尾处
            return f"{comment_text} {promo_text}"

    def _record_usage(self, link: str, account_id: str):
        """
        记录链接使用历史

        Args:
            link: 使用的链接
            account_id: 账号ID
        """
        now = datetime.now()

        # 全局历史
        if link not in self.link_usage_history:
            self.link_usage_history[link] = []
        self.link_usage_history[link].append(now)

        # 账号历史
        if account_id not in self.account_link_history:
            self.account_link_history[account_id] = {}
        self.account_link_history[account_id][link] = now

        # 清理7天前的历史(节省内存)
        cutoff = now - timedelta(days=7)
        self.link_usage_history[link] = [
            ts for ts in self.link_usage_history[link] if ts > cutoff
        ]
