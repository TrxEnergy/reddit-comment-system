"""
L1快速筛选器
基于TF-IDF和规则引擎的快速帖子质量评估
"""

import time
import math
import re
from typing import List, Dict
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

from src.core.logging import get_logger
from src.discovery.models import RawPost
from src.screening.models import L1FilterResult, FilterDecision

logger = get_logger(__name__)


class L1FastFilter:
    """L1快速筛选器 - TF-IDF + 规则引擎"""

    def __init__(
        self,
        direct_pass_threshold: float = 0.75,
        review_threshold: float = 0.45,
        topic_weight: float = 0.40,
        interaction_weight: float = 0.30,
        sentiment_weight: float = 0.20,
        title_quality_weight: float = 0.10
    ):
        """
        初始化L1筛选器

        Args:
            direct_pass_threshold: 直通阈值（≥此值直接通过）
            review_threshold: 送审阈值（≥此值送L2，<此值拒绝）
            topic_weight: 话题相关性权重
            interaction_weight: 互动潜力权重
            sentiment_weight: 情感倾向权重
            title_quality_weight: 标题质量权重
        """
        self.direct_pass_threshold = direct_pass_threshold
        self.review_threshold = review_threshold

        self.weights = {
            'topic': topic_weight,
            'interaction': interaction_weight,
            'sentiment': sentiment_weight,
            'title': title_quality_weight
        }

        self.tfidf_vectorizer = None
        self.reference_vectors = None

        logger.info(
            f"L1筛选器初始化 - 直通阈值:{direct_pass_threshold}, "
            f"送审阈值:{review_threshold}"
        )

    def _prepare_tfidf_vectorizer(self, posts: List[RawPost]):
        """准备TF-IDF向量化器"""
        if self.tfidf_vectorizer is None:
            self.tfidf_vectorizer = TfidfVectorizer(
                max_features=1000,
                stop_words='english',
                ngram_range=(1, 2),
                min_df=1
            )

            texts = [f"{post.title} {post.selftext}" for post in posts]
            self.tfidf_vectorizer.fit(texts)
            logger.debug("TF-IDF向量化器训练完成")

    def _calculate_topic_relevance(self, post: RawPost, posts: List[RawPost]) -> float:
        """
        计算话题相关性（TF-IDF余弦相似度）

        Args:
            post: 待评分帖子
            posts: 所有帖子（用于计算平均相似度）

        Returns:
            话题相关性得分 0-1
        """
        try:
            post_text = f"{post.title} {post.selftext}"
            post_vector = self.tfidf_vectorizer.transform([post_text])

            all_texts = [f"{p.title} {p.selftext}" for p in posts if p.post_id != post.post_id]
            if not all_texts:
                return 0.5

            all_vectors = self.tfidf_vectorizer.transform(all_texts)

            similarities = cosine_similarity(post_vector, all_vectors)[0]
            avg_similarity = float(np.mean(similarities))

            return min(1.0, avg_similarity * 2)

        except Exception as e:
            logger.warning(f"话题相关性计算失败: {e}")
            return 0.5

    def _calculate_interaction_potential(self, post: RawPost) -> float:
        """
        计算互动潜力（基于评论数和分数）

        Args:
            post: 待评分帖子

        Returns:
            互动潜力得分 0-1
        """
        comment_score = min(1.0, math.log(post.num_comments + 1) / math.log(101))

        upvote_score = min(1.0, post.score / 1000.0) if post.score > 0 else 0.0

        hours_since_post = (time.time() - post.created_utc) / 3600
        if hours_since_post <= 6:
            freshness = 1.0
        elif hours_since_post <= 24:
            freshness = 0.8
        elif hours_since_post <= 48:
            freshness = 0.5
        else:
            freshness = 0.3

        combined = (comment_score * 0.6 + upvote_score * 0.4) * freshness

        return min(1.0, combined)

    def _calculate_sentiment_score(self, post: RawPost) -> float:
        """
        计算情感倾向（简单规则：避免争议性内容）

        Args:
            post: 待评分帖子

        Returns:
            情感得分 0-1（正面/中性越高越好）
        """
        text = f"{post.title} {post.selftext}".lower()

        positive_keywords = [
            'help', 'question', 'advice', 'guide', 'tip', 'learn',
            'thank', 'appreciate', 'recommend', 'best', 'good'
        ]
        negative_keywords = [
            'hate', 'worst', 'terrible', 'scam', 'fraud', 'illegal',
            'fuck', 'shit', 'stupid', 'idiot', 'ban', 'war', 'kill'
        ]

        positive_count = sum(1 for kw in positive_keywords if kw in text)
        negative_count = sum(1 for kw in negative_keywords if kw in text)

        if negative_count >= 2:
            return 0.2
        elif negative_count == 1:
            return 0.5
        elif positive_count >= 2:
            return 0.9
        elif positive_count == 1:
            return 0.7
        else:
            return 0.6

    def _calculate_title_quality(self, post: RawPost) -> float:
        """
        计算标题质量

        Args:
            post: 待评分帖子

        Returns:
            标题质量得分 0-1
        """
        score = 0.5

        if '?' in post.title:
            score += 0.2

        if re.search(r'\d+', post.title):
            score += 0.1

        title_len = len(post.title)
        if 30 <= title_len <= 100:
            score += 0.2
        elif 15 <= title_len < 30 or 100 < title_len <= 150:
            score += 0.1

        return min(1.0, score)

    def _calculate_composite_score(
        self,
        topic_score: float,
        interaction_score: float,
        sentiment_score: float,
        title_score: float
    ) -> float:
        """
        计算综合得分（加权平均）

        Returns:
            综合得分 0-1
        """
        composite = (
            topic_score * self.weights['topic'] +
            interaction_score * self.weights['interaction'] +
            sentiment_score * self.weights['sentiment'] +
            title_score * self.weights['title']
        )
        return min(1.0, composite)

    def _make_decision(self, score: float) -> FilterDecision:
        """
        根据得分做出筛选决策

        Args:
            score: 综合得分

        Returns:
            筛选决策
        """
        if score >= self.direct_pass_threshold:
            return FilterDecision.DIRECT_PASS
        elif score >= self.review_threshold:
            return FilterDecision.SEND_TO_L2
        else:
            return FilterDecision.DIRECT_REJECT

    def filter_posts(self, posts: List[RawPost]) -> List[L1FilterResult]:
        """
        批量筛选帖子

        Args:
            posts: 待筛选帖子列表

        Returns:
            L1筛选结果列表
        """
        if not posts:
            logger.warning("输入帖子列表为空")
            return []

        self._prepare_tfidf_vectorizer(posts)

        results = []
        for post in posts:
            start_time = time.time()

            topic_score = self._calculate_topic_relevance(post, posts)
            interaction_score = self._calculate_interaction_potential(post)
            sentiment_score = self._calculate_sentiment_score(post)
            title_score = self._calculate_title_quality(post)

            composite_score = self._calculate_composite_score(
                topic_score, interaction_score, sentiment_score, title_score
            )

            decision = self._make_decision(composite_score)

            processing_time = (time.time() - start_time) * 1000

            result = L1FilterResult(
                post_id=post.post_id,
                score=composite_score,
                decision=decision,
                topic_relevance_score=topic_score,
                interaction_potential_score=interaction_score,
                sentiment_score=sentiment_score,
                title_quality_score=title_score,
                processing_time_ms=processing_time
            )

            results.append(result)

        direct_pass_count = sum(1 for r in results if r.decision == FilterDecision.DIRECT_PASS)
        send_to_l2_count = sum(1 for r in results if r.decision == FilterDecision.SEND_TO_L2)
        reject_count = sum(1 for r in results if r.decision == FilterDecision.DIRECT_REJECT)

        logger.info(
            f"L1筛选完成 - 总计:{len(results)}帖, "
            f"直通:{direct_pass_count}, 送L2:{send_to_l2_count}, 拒绝:{reject_count}"
        )

        return results
