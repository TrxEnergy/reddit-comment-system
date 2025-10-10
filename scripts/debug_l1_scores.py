"""
L1筛选器调试工具
查看每个帖子的详细评分和拒绝原因
"""

import asyncio
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.discovery.models import RawPost
from src.screening.l1_fast_filter import L1FastFilter
from src.core.config import settings


def load_posts_from_jsonl(filepath: str) -> list:
    """从JSONL文件加载帖子"""
    posts = []
    with open(filepath, encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            posts.append(RawPost(**data))
    return posts


def main():
    # 加载最新的发现结果
    discovery_file = "data/discovery/discovery_quick_scan_20251010_042107.jsonl"
    posts = load_posts_from_jsonl(discovery_file)

    print(f"\n加载了 {len(posts)} 个帖子\n")

    # 初始化L1筛选器
    l1_filter = L1FastFilter(
        direct_pass_threshold=settings.m3_screening.l1_threshold_small,
        review_threshold=settings.m3_screening.l1_review_threshold
    )

    # 准备TF-IDF
    l1_filter._prepare_tfidf_vectorizer(posts)

    # [FIX 2025-10-10] 先运行完整筛选，看返回结果
    l1_results = l1_filter.filter_posts(posts)
    print(f"\n完整筛选结果统计：")
    print(f"  总计: {len(l1_results)}")
    if l1_results:
        print(f"  示例结果[0]: {l1_results[0]}")
        print(f"  决策字段类型: {type(l1_results[0].decision)}")
        print(f"  决策字段值: {l1_results[0].decision}")
    print()

    # 逐个分析帖子
    for i, post in enumerate(posts[:10], 1):  # 只看前10个
        print(f"{'='*80}")
        print(f"帖子 {i}: {post.title[:60]}...")
        print(f"  Subreddit: r/{post.cluster_id}")
        print(f"  分数: {post.score} | 评论数: {post.num_comments}")
        print(f"  作者: u/{post.author}")

        # 计算各维度分数
        topic_score = l1_filter._calculate_topic_relevance(post, posts)
        interaction_score = l1_filter._calculate_interaction_potential(post)
        sentiment_score = l1_filter._calculate_sentiment_score(post)
        title_score = l1_filter._calculate_title_quality(post)

        # 计算综合分数
        composite_score = l1_filter._calculate_composite_score(
            topic_score, interaction_score, sentiment_score, title_score
        )

        # 判断决策
        decision = l1_filter._make_decision(composite_score)

        print(f"\n  【评分详情】")
        print(f"    话题相关性: {topic_score:.3f} (权重40%)")
        print(f"    互动潜力:   {interaction_score:.3f} (权重30%)")
        print(f"    情感倾向:   {sentiment_score:.3f} (权重20%)")
        print(f"    标题质量:   {title_score:.3f} (权重10%)")
        print(f"    ------------------------------")
        print(f"    综合得分:   {composite_score:.3f}")
        print(f"    决策:       {decision.value}")
        print(f"    (直通阈值≥{l1_filter.direct_pass_threshold}, 送审阈值≥{l1_filter.review_threshold})")
        print()


if __name__ == "__main__":
    main()
