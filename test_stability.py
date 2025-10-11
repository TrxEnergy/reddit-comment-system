"""
测试生成稳定性：连续生成3条评论，检查质量一致性
"""

import asyncio
import sys
import io
from pathlib import Path

# Windows编码修复
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from src.discovery.pipeline import DiscoveryPipeline
from src.screening.screening_pipeline import ScreeningPipeline
from src.screening.dynamic_pool_calculator import DynamicPoolCalculator
from src.screening.l1_fast_filter import L1FastFilter
from src.screening.l2_deep_filter import L2DeepFilter
from src.screening.cost_guard import CostGuard
from src.content.content_pipeline import ContentPipeline
from src.core.config import settings


async def generate_comment_for_post(post, round_num):
    """为一个帖子生成评论"""
    print(f"\n{'='*60}")
    print(f"  第{round_num}轮生成")
    print(f"{'='*60}")
    print(f"帖子: {post.title[:60]}...")
    print(f"子版: r/{post.cluster_id}")

    # M3: 筛选
    pool_calculator = DynamicPoolCalculator("http://localhost:8000")
    l1_filter = L1FastFilter(0.8, 0.01)
    l2_filter = L2DeepFilter(settings.ai.api_key, settings.m3_screening.l2_model, 0.30)
    cost_guard = CostGuard(0.5, 15.0)

    screening = ScreeningPipeline(pool_calculator, l1_filter, l2_filter, cost_guard)
    result = await screening.run([post])

    if not result.passed_post_ids:
        print("❌ 筛选未通过")
        return None

    # M4: 生成
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
        "metadata": {"l1_score": 0.5, "l2_score": 0.8, "decision_path": "l2_pass"},
        "account_id": f"test_account_{round_num}"
    }

    comments = await content_pipeline.process_batch([screening_result])

    if not comments:
        print("❌ 生成失败")
        return None

    comment = comments[0]

    print(f"\n✅ 生成成功")
    print(f"  Persona: {comment.persona_used}")
    print(f"  意图组: {comment.intent_group}")
    print(f"  质量得分: {comment.quality_scores.overall:.3f}")
    print(f"    - 相关性: {comment.quality_scores.relevance:.3f}")
    print(f"    - 自然度: {comment.quality_scores.natural:.3f}")
    print(f"    - 合规度: {comment.quality_scores.compliance:.3f}")
    print(f"  长度: {len(comment.text)}字符")
    print(f"\n  预览: {comment.text[:120]}...")

    return {
        "round": round_num,
        "persona": comment.persona_used,
        "intent": comment.intent_group,
        "quality": comment.quality_scores.overall,
        "relevance": comment.quality_scores.relevance,
        "natural": comment.quality_scores.natural,
        "compliance": comment.quality_scores.compliance,
        "length": len(comment.text),
        "text": comment.text
    }


async def main():
    print("\n" + "="*60)
    print("  评论生成稳定性测试（3轮）")
    print("="*60)

    # M2: 发现3个帖子
    print("\n[M2] 发现帖子...")
    pipeline = DiscoveryPipeline()
    posts = await pipeline.run(recipe_name="deep_dive", target_posts=3)

    if len(posts) < 3:
        print(f"❌ 只发现{len(posts)}个帖子，需要至少3个")
        return

    print(f"✅ 已发现{len(posts)}个帖子\n")

    # 对前3个帖子分别生成评论
    results = []
    for i, post in enumerate(posts[:3], 1):
        result = await generate_comment_for_post(post, i)
        if result:
            results.append(result)
        await asyncio.sleep(1)  # 避免API限流

    # 统计分析
    print(f"\n\n{'='*60}")
    print("  稳定性分析")
    print(f"{'='*60}")

    if not results:
        print("❌ 没有成功的生成")
        return

    print(f"\n成功率: {len(results)}/3 = {len(results)/3*100:.0f}%")

    if len(results) >= 2:
        # 质量得分统计
        qualities = [r['quality'] for r in results]
        relevances = [r['relevance'] for r in results]
        naturals = [r['natural'] for r in results]
        compliances = [r['compliance'] for r in results]
        lengths = [r['length'] for r in results]

        print(f"\n质量得分:")
        print(f"  平均: {sum(qualities)/len(qualities):.3f}")
        print(f"  最高: {max(qualities):.3f}")
        print(f"  最低: {min(qualities):.3f}")
        print(f"  标准差: {(sum((q - sum(qualities)/len(qualities))**2 for q in qualities) / len(qualities))**0.5:.3f}")

        print(f"\n相关性得分:")
        print(f"  平均: {sum(relevances)/len(relevances):.3f}")
        print(f"  范围: {min(relevances):.3f} - {max(relevances):.3f}")

        print(f"\n自然度得分:")
        print(f"  平均: {sum(naturals)/len(naturals):.3f}")
        print(f"  范围: {min(naturals):.3f} - {max(naturals):.3f}")

        print(f"\n合规度得分:")
        print(f"  平均: {sum(compliances)/len(compliances):.3f}")
        print(f"  范围: {min(compliances):.3f} - {max(compliances):.3f}")

        print(f"\n评论长度:")
        print(f"  平均: {sum(lengths)/len(lengths):.0f}字符")
        print(f"  范围: {min(lengths)} - {max(lengths)}字符")

        # Persona多样性
        personas = [r['persona'] for r in results]
        unique_personas = set(personas)
        print(f"\nPersona多样性:")
        print(f"  使用了{len(unique_personas)}个不同Persona（共{len(results)}条评论）")
        for p in unique_personas:
            print(f"    - {p}: {personas.count(p)}次")

        # 结论
        print(f"\n{'='*60}")
        avg_quality = sum(qualities) / len(qualities)
        quality_std = (sum((q - avg_quality)**2 for q in qualities) / len(qualities))**0.5

        if avg_quality >= 0.70 and quality_std <= 0.05:
            print("  ✅ 结论: 系统生成稳定，质量一致")
        elif avg_quality >= 0.65:
            print("  ⚠️  结论: 系统基本稳定，质量波动略大")
        else:
            print("  ❌ 结论: 系统不稳定，需要优化")

        print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
