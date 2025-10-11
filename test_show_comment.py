"""
查看生成的完整评论
"""

import asyncio
from pathlib import Path
from src.discovery.pipeline import DiscoveryPipeline
from src.screening.screening_pipeline import ScreeningPipeline
from src.screening.dynamic_pool_calculator import DynamicPoolCalculator
from src.screening.l1_fast_filter import L1FastFilter
from src.screening.l2_deep_filter import L2DeepFilter
from src.screening.cost_guard import CostGuard
from src.content.content_pipeline import ContentPipeline
from src.core.config import settings


async def main():
    # M2: 发现1个帖子
    pipeline = DiscoveryPipeline()
    posts = await pipeline.run(recipe_name="deep_dive", target_posts=1)

    if not posts:
        print("没有发现帖子")
        return

    post = posts[0]
    print(f"\n目标帖子:")
    print(f"  标题: {post.title}")
    print(f"  子版: r/{post.cluster_id}")
    print(f"  分数: {post.score}")
    print(f"  URL: {post.url}")

    # M3: 筛选（简化）
    pool_calculator = DynamicPoolCalculator("http://localhost:8000")
    l1_filter = L1FastFilter(0.8, 0.01)
    l2_filter = L2DeepFilter(settings.ai.api_key, settings.m3_screening.l2_model, 0.30)
    cost_guard = CostGuard(0.5, 15.0)

    screening = ScreeningPipeline(pool_calculator, l1_filter, l2_filter, cost_guard)
    result = await screening.run([post])

    if not result.passed_post_ids:
        print("\n帖子未通过筛选")
        return

    # M4: 生成评论
    content_pipeline = ContentPipeline(Path(__file__).parent)

    screening_result = {
        "post_bundle": {
            "post_id": post.post_id,
            "title": post.title,
            "subreddit": post.cluster_id,
            "url": post.url,
            "selftext": post.selftext,
            "score": post.score,
            "num_comments": post.num_comments,
            "created_utc": post.created_utc
        },
        "metadata": {
            "l1_score": 0.5,
            "l2_score": 0.8,
            "decision_path": "l2_pass"
        },
        "account_id": "test_account"
    }

    comments = await content_pipeline.process_batch([screening_result])

    if not comments:
        print("\n评论生成失败")
        return

    comment = comments[0]

    print(f"\n\n{'='*60}")
    print(f"生成的评论内容:")
    print(f"{'='*60}")
    print(f"\n{comment.text}\n")
    print(f"{'='*60}")
    print(f"Persona: {comment.persona_used}")
    print(f"意图组: {comment.intent_group}")
    print(f"质量得分: {comment.quality_scores.overall:.2f}")
    print(f"  - 相关性: {comment.quality_scores.relevance:.2f}")
    print(f"  - 自然度: {comment.quality_scores.natural:.2f}")
    print(f"  - 合规度: {comment.quality_scores.compliance:.2f}")
    print(f"变体数: {len(comment.variants) if comment.variants else 0}")
    print(f"生成时间: {comment.timestamps.get('generated_at', 'N/A')}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
