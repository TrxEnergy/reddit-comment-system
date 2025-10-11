"""
M4内容工厂优化验证测试
验证5项优化的实际效果：
1. 相关性评分提升（目标：0.47 → 0.65+）
2. 质量通过率提升（目标：20% → 60-70%）
3. Persona多样性（20个Persona）
4. 免责声明多样化（10种变体）
5. 口头禅丰富度（8-10个/类）

运行方式：
python test_m4_optimization.py
"""

import asyncio
from pathlib import Path
from collections import Counter
from typing import List

from src.content.content_pipeline import ContentPipeline
from src.content.models import CommentRequest


# 测试数据：20个真实Reddit帖子标题（覆盖A/B/C三组意图）
TEST_POSTS = [
    # A组：费用与转账（8个）
    {
        "post_id": "test_a_001",
        "title": "What's the cheapest way to send USDT from Binance to TronLink?",
        "subreddit": "Tronix",
        "score": 85,
        "age_hours": 3.2,
        "lang": "en",
        "screening_metadata": {
            "l1_score": 0.82,
            "l2_intent_prob": 0.91,
            "l2_topic_prob": 0.87,
            "suggestion": "Compare TRC20 vs ERC20 withdrawal fees",
            "intent_group": "A",
            "risk_level": "low"
        },
        "priority": 0.88,
        "account_id": "test_acc_001",
        "account_username": "test_user_001"
    },
    {
        "post_id": "test_a_002",
        "title": "Gas fees on Ethereum are insane, how do you guys deal with this?",
        "subreddit": "ethereum",
        "score": 120,
        "age_hours": 2.5,
        "lang": "en",
        "screening_metadata": {
            "l1_score": 0.80,
            "l2_intent_prob": 0.89,
            "l2_topic_prob": 0.85,
            "suggestion": "Share gas optimization strategies",
            "intent_group": "A",
            "risk_level": "low"
        },
        "priority": 0.86,
        "account_id": "test_acc_002",
        "account_username": "test_user_002"
    },
    {
        "post_id": "test_a_003",
        "title": "Cheapest NFT minting on Polygon or Ethereum?",
        "subreddit": "NFT",
        "score": 95,
        "age_hours": 4.0,
        "lang": "en",
        "screening_metadata": {
            "l1_score": 0.78,
            "l2_intent_prob": 0.88,
            "l2_topic_prob": 0.84,
            "suggestion": "Compare minting costs",
            "intent_group": "A",
            "risk_level": "low"
        },
        "priority": 0.84,
        "account_id": "test_acc_003",
        "account_username": "test_user_003"
    },
    {
        "post_id": "test_a_004",
        "title": "Best APY for stablecoin farming right now?",
        "subreddit": "defi",
        "score": 150,
        "age_hours": 1.8,
        "lang": "en",
        "screening_metadata": {
            "l1_score": 0.85,
            "l2_intent_prob": 0.92,
            "l2_topic_prob": 0.89,
            "suggestion": "Compare DeFi yields",
            "intent_group": "A",
            "risk_level": "medium"
        },
        "priority": 0.90,
        "account_id": "test_acc_004",
        "account_username": "test_user_004"
    },
    {
        "post_id": "test_a_005",
        "title": "Mining profitability calculator for ETH?",
        "subreddit": "EtherMining",
        "score": 80,
        "age_hours": 5.2,
        "lang": "en",
        "screening_metadata": {
            "l1_score": 0.77,
            "l2_intent_prob": 0.86,
            "l2_topic_prob": 0.83,
            "suggestion": "Share profitability resources",
            "intent_group": "A",
            "risk_level": "low"
        },
        "priority": 0.82,
        "account_id": "test_acc_005",
        "account_username": "test_user_005"
    },
    {
        "post_id": "test_a_006",
        "title": "¿Mejor forma de enviar crypto a América Latina?",
        "subreddit": "CryptoCurrency",
        "score": 60,
        "age_hours": 3.5,
        "lang": "es",
        "screening_metadata": {
            "l1_score": 0.79,
            "l2_intent_prob": 0.87,
            "l2_topic_prob": 0.84,
            "suggestion": "Recommend low-fee remittance options",
            "intent_group": "A",
            "risk_level": "low"
        },
        "priority": 0.83,
        "account_id": "test_acc_006",
        "account_username": "test_user_006"
    },
    {
        "post_id": "test_a_007",
        "title": "How to avoid high withdrawal fees on exchanges?",
        "subreddit": "CryptoCurrency",
        "score": 110,
        "age_hours": 2.8,
        "lang": "en",
        "screening_metadata": {
            "l1_score": 0.81,
            "l2_intent_prob": 0.90,
            "l2_topic_prob": 0.86,
            "suggestion": "Share fee optimization tips",
            "intent_group": "A",
            "risk_level": "low"
        },
        "priority": 0.87,
        "account_id": "test_acc_007",
        "account_username": "test_user_007"
    },
    {
        "post_id": "test_a_008",
        "title": "Energy cost vs mining profit - still worth it?",
        "subreddit": "BitcoinMining",
        "score": 75,
        "age_hours": 6.0,
        "lang": "en",
        "screening_metadata": {
            "l1_score": 0.76,
            "l2_intent_prob": 0.85,
            "l2_topic_prob": 0.82,
            "suggestion": "Discuss ROI calculations",
            "intent_group": "A",
            "risk_level": "low"
        },
        "priority": 0.81,
        "account_id": "test_acc_008",
        "account_username": "test_user_008"
    },

    # B组：交易所与钱包（6个）
    {
        "post_id": "test_b_001",
        "title": "USDT withdrawal stuck for 2 hours, is this normal?",
        "subreddit": "CryptoCurrency",
        "score": 120,
        "age_hours": 1.5,
        "lang": "en",
        "screening_metadata": {
            "l1_score": 0.78,
            "l2_intent_prob": 0.89,
            "l2_topic_prob": 0.85,
            "suggestion": "Provide troubleshooting steps",
            "intent_group": "B",
            "risk_level": "medium"
        },
        "priority": 0.92,
        "account_id": "test_acc_009",
        "account_username": "test_user_009"
    },
    {
        "post_id": "test_b_002",
        "title": "Ledger vs Trezor for cold storage?",
        "subreddit": "Bitcoin",
        "score": 140,
        "age_hours": 2.2,
        "lang": "en",
        "screening_metadata": {
            "l1_score": 0.80,
            "l2_intent_prob": 0.90,
            "l2_topic_prob": 0.87,
            "suggestion": "Compare hardware wallet features",
            "intent_group": "B",
            "risk_level": "low"
        },
        "priority": 0.89,
        "account_id": "test_acc_010",
        "account_username": "test_user_010"
    },
    {
        "post_id": "test_b_003",
        "title": "API rate limits on Binance - what's your workaround?",
        "subreddit": "algotrading",
        "score": 85,
        "age_hours": 3.8,
        "lang": "en",
        "screening_metadata": {
            "l1_score": 0.77,
            "l2_intent_prob": 0.87,
            "l2_topic_prob": 0.84,
            "suggestion": "Share API optimization tips",
            "intent_group": "B",
            "risk_level": "low"
        },
        "priority": 0.84,
        "account_id": "test_acc_011",
        "account_username": "test_user_011"
    },
    {
        "post_id": "test_b_004",
        "title": "How to spot phishing emails claiming to be from exchanges?",
        "subreddit": "CryptoCurrency",
        "score": 160,
        "age_hours": 1.2,
        "lang": "en",
        "screening_metadata": {
            "l1_score": 0.82,
            "l2_intent_prob": 0.91,
            "l2_topic_prob": 0.88,
            "suggestion": "Share security best practices",
            "intent_group": "B",
            "risk_level": "high"
        },
        "priority": 0.91,
        "account_id": "test_acc_012",
        "account_username": "test_user_012"
    },
    {
        "post_id": "test_b_005",
        "title": "Kraken vs Coinbase withdrawal limits for new users?",
        "subreddit": "CryptoCurrency",
        "score": 95,
        "age_hours": 4.5,
        "lang": "en",
        "screening_metadata": {
            "l1_score": 0.79,
            "l2_intent_prob": 0.88,
            "l2_topic_prob": 0.85,
            "suggestion": "Compare exchange limits",
            "intent_group": "B",
            "risk_level": "low"
        },
        "priority": 0.85,
        "account_id": "test_acc_013",
        "account_username": "test_user_013"
    },
    {
        "post_id": "test_b_006",
        "title": "Best practices for securing seed phrases?",
        "subreddit": "Bitcoin",
        "score": 180,
        "age_hours": 0.8,
        "lang": "en",
        "screening_metadata": {
            "l1_score": 0.84,
            "l2_intent_prob": 0.93,
            "l2_topic_prob": 0.90,
            "suggestion": "Share seed phrase security tips",
            "intent_group": "B",
            "risk_level": "high"
        },
        "priority": 0.93,
        "account_id": "test_acc_014",
        "account_username": "test_user_014"
    },

    # C组：学习与分享（6个）
    {
        "post_id": "test_c_001",
        "title": "Can someone explain what TRC20 means? I'm new to crypto",
        "subreddit": "CryptoCurrency",
        "score": 65,
        "age_hours": 4.8,
        "lang": "en",
        "screening_metadata": {
            "l1_score": 0.75,
            "l2_intent_prob": 0.86,
            "l2_topic_prob": 0.82,
            "suggestion": "Explain TRC20 in beginner-friendly terms",
            "intent_group": "C",
            "risk_level": "low"
        },
        "priority": 0.81,
        "account_id": "test_acc_015",
        "account_username": "test_user_015"
    },
    {
        "post_id": "test_c_002",
        "title": "What are the key metrics to track Bitcoin adoption?",
        "subreddit": "Bitcoin",
        "score": 100,
        "age_hours": 3.2,
        "lang": "en",
        "screening_metadata": {
            "l1_score": 0.78,
            "l2_intent_prob": 0.88,
            "l2_topic_prob": 0.85,
            "suggestion": "Share on-chain metrics",
            "intent_group": "C",
            "risk_level": "low"
        },
        "priority": 0.84,
        "account_id": "test_acc_016",
        "account_username": "test_user_016"
    },
    {
        "post_id": "test_c_003",
        "title": "ELI5: How does Proof of Stake work?",
        "subreddit": "ethereum",
        "score": 130,
        "age_hours": 2.0,
        "lang": "en",
        "screening_metadata": {
            "l1_score": 0.80,
            "l2_intent_prob": 0.89,
            "l2_topic_prob": 0.86,
            "suggestion": "Explain PoS in simple terms",
            "intent_group": "C",
            "risk_level": "low"
        },
        "priority": 0.87,
        "account_id": "test_acc_017",
        "account_username": "test_user_017"
    },
    {
        "post_id": "test_c_004",
        "title": "Best podcast episodes for learning about crypto history?",
        "subreddit": "CryptoCurrency",
        "score": 70,
        "age_hours": 5.5,
        "lang": "en",
        "screening_metadata": {
            "l1_score": 0.76,
            "l2_intent_prob": 0.85,
            "l2_topic_prob": 0.83,
            "suggestion": "Recommend educational podcasts",
            "intent_group": "C",
            "risk_level": "low"
        },
        "priority": 0.82,
        "account_id": "test_acc_018",
        "account_username": "test_user_018"
    },
    {
        "post_id": "test_c_005",
        "title": "Book recommendations for understanding Bitcoin economics?",
        "subreddit": "Bitcoin",
        "score": 85,
        "age_hours": 4.2,
        "lang": "en",
        "screening_metadata": {
            "l1_score": 0.77,
            "l2_intent_prob": 0.87,
            "l2_topic_prob": 0.84,
            "suggestion": "Recommend foundational books",
            "intent_group": "C",
            "risk_level": "low"
        },
        "priority": 0.83,
        "account_id": "test_acc_019",
        "account_username": "test_user_019"
    },
    {
        "post_id": "test_c_006",
        "title": "What online courses would you recommend for blockchain development?",
        "subreddit": "ethdev",
        "score": 90,
        "age_hours": 3.8,
        "lang": "en",
        "screening_metadata": {
            "l1_score": 0.78,
            "l2_intent_prob": 0.88,
            "l2_topic_prob": 0.85,
            "suggestion": "Recommend dev courses",
            "intent_group": "C",
            "risk_level": "low"
        },
        "priority": 0.85,
        "account_id": "test_acc_020",
        "account_username": "test_user_020"
    },
]


async def run_optimization_test():
    """运行M4优化验证测试"""
    import sys
    import io

    # 修复Windows GBK编码问题
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    print("=" * 80)
    print("M4内容工厂优化验证测试")
    print("=" * 80)
    print()

    # 初始化Pipeline
    config_base = Path(__file__).parent
    pipeline = ContentPipeline(config_base)

    print(f"测试数据集：{len(TEST_POSTS)}个帖子")
    print(f"  - A组（费用与转账）：8个")
    print(f"  - B组（交易所与钱包）：6个")
    print(f"  - C组（学习与分享）：6个")
    print()

    # 处理测试数据
    print("正在生成评论...")
    results = await pipeline.process_batch(TEST_POSTS)

    print(f"生成完成：{len(results)}/{len(TEST_POSTS)} 条评论通过质量检查")
    print()

    # 统计分析
    print("=" * 80)
    print("优化效果分析")
    print("=" * 80)
    print()

    # 1. 相关性评分统计
    relevance_scores = [r.quality_scores.relevance for r in results]
    avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0

    print("[1] 相关性评分提升")
    print(f"   目标：0.47 -> 0.65+")
    print(f"   实际：{avg_relevance:.2f}")
    print(f"   状态：{'PASS' if avg_relevance >= 0.65 else 'FAIL'}")
    print(f"   分布：min={min(relevance_scores):.2f}, max={max(relevance_scores):.2f}")
    print()

    # 2. 质量通过率
    pass_rate = len(results) / len(TEST_POSTS) * 100

    print("[2] 质量通过率提升")
    print(f"   目标：20% -> 60-70%")
    print(f"   实际：{pass_rate:.1f}%")
    print(f"   状态：{'PASS' if pass_rate >= 60 else 'FAIL'}")
    print()

    # 3. Persona多样性
    persona_usage = Counter([r.persona_used for r in results])
    unique_personas = len(persona_usage)

    print("[3] Persona多样性")
    print(f"   目标：20个Persona可用")
    print(f"   实际使用：{unique_personas}种Persona")
    print(f"   分布：{dict(persona_usage)}")
    print()

    # 4. 免责声明多样性分析
    disclaimers_found = []
    disclaimer_variants = [
        "Not financial advice.",
        "DYOR as always.",
        "Just my 2 cents.",
        "Do your own research first.",
        "Not advice, just sharing my experience.",
        "Always verify before making decisions.",
        "This is just my perspective.",
        "Take it with a grain of salt.",
        "Everyone's situation is different.",
        "Make your own informed decision."
    ]

    for result in results:
        for variant in disclaimer_variants:
            if variant in result.text:
                disclaimers_found.append(variant)
                break

    unique_disclaimers = len(set(disclaimers_found))

    print("[4] 免责声明多样化")
    print(f"   目标：10种变体")
    print(f"   实际出现：{unique_disclaimers}种不同的免责声明")
    if disclaimers_found:
        print(f"   分布：{Counter(disclaimers_found)}")
    print()

    # 5. 整体质量评分
    overall_scores = [r.quality_scores.overall for r in results]
    avg_overall = sum(overall_scores) / len(overall_scores) if overall_scores else 0

    print("[5] 整体质量评分")
    print(f"   平均分：{avg_overall:.2f}")
    print(f"   分布：min={min(overall_scores):.2f}, max={max(overall_scores):.2f}")
    print()

    # 6. 意图组覆盖
    intent_coverage = Counter([r.intent_group for r in results])

    print("[6] 意图组覆盖")
    print(f"   A组（费用与转账）：{intent_coverage.get('A', 0)}条")
    print(f"   B组（交易所与钱包）：{intent_coverage.get('B', 0)}条")
    print(f"   C组（学习与分享）：{intent_coverage.get('C', 0)}条")
    print()

    # 最终总结
    print("=" * 80)
    print("测试总结")
    print("=" * 80)

    success_criteria = {
        "相关性评分 ≥ 0.65": avg_relevance >= 0.65,
        "质量通过率 ≥ 60%": pass_rate >= 60,
        "Persona多样性 ≥ 5种": unique_personas >= 5,
        "免责声明变体 ≥ 3种": unique_disclaimers >= 3,
    }

    passed = sum(success_criteria.values())
    total = len(success_criteria)

    for criterion, result in success_criteria.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}  {criterion}")

    print()
    print(f"最终结果：{passed}/{total} 项达标")

    if passed == total:
        print(">>> 所有优化目标均已达成！")
    elif passed >= total * 0.75:
        print(">>> 大部分优化目标达成，系统显著改善")
    else:
        print(">>> 部分优化目标未达成，需要进一步调整")

    print()
    print("=" * 80)

    # 显示几个示例评论
    if results:
        print("评论示例（前3条）：")
        print("=" * 80)
        for i, result in enumerate(results[:3], 1):
            print(f"\n示例 {i}:")
            print(f"帖子ID: {result.request_id}")
            print(f"Persona: {result.persona_used}")
            print(f"意图组: {result.intent_group}")
            print(f"质量评分: relevance={result.quality_scores.relevance:.2f}, "
                  f"natural={result.quality_scores.natural:.2f}, "
                  f"compliance={result.quality_scores.compliance:.2f}, "
                  f"overall={result.quality_scores.overall:.2f}")
            print(f"评论内容:\n{result.text}")
            print("-" * 80)


if __name__ == "__main__":
    asyncio.run(run_optimization_test())
