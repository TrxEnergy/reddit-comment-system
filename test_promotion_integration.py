"""
E2E测试 - Telegram频道推广功能验证
[CREATE 2025-10-10] 验证推广链接插入、多语言支持、质量评分
"""

import asyncio
import sys
import io
from pathlib import Path
from typing import List, Dict

# Windows GBK编码修复
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from src.content.content_pipeline import ContentPipeline

# 测试数据集(15条混合场景)
TEST_POSTS = [
    # A组 - 费用转账 (5条)
    {
        "post_id": "promo_a1",
        "title": "What's the cheapest way to transfer USDT?",
        "subreddit": "CryptoCurrency",
        "score": 150,
        "age_hours": 2.5,
        "lang": "en",
        "screening_metadata": {
            "intent_group": "A",
            "intent_prob": 0.92,
            "suggestion": "Compare TRC20 vs ERC20 fees"
        },
        "priority": 0.9,
        "account_id": "test_acc_001",
        "account_username": "crypto_saver"
    },
    {
        "post_id": "promo_a2",
        "title": "¿Cuál es la forma más barata de transferir USDT?",
        "subreddit": "CryptoMercado",
        "score": 80,
        "age_hours": 1.2,
        "lang": "es",
        "screening_metadata": {
            "intent_group": "A",
            "intent_prob": 0.89,
            "suggestion": "Mencionar costos de red"
        },
        "priority": 0.85,
        "account_id": "test_acc_002",
        "account_username": "crypto_latino"
    },
    {
        "post_id": "promo_a3",
        "title": "USDT转账手续费太高了,有什么省钱办法?",
        "subreddit": "BitcoinCN",
        "score": 45,
        "age_hours": 3.0,
        "lang": "zh",
        "screening_metadata": {
            "intent_group": "A",
            "intent_prob": 0.94,
            "suggestion": "对比不同网络费用"
        },
        "priority": 0.88,
        "account_id": "test_acc_003",
        "account_username": "crypto_cn_user"
    },
    {
        "post_id": "promo_a4",
        "title": "Why are ERC20 withdrawal fees so expensive?",
        "subreddit": "ethereum",
        "score": 200,
        "age_hours": 4.5,
        "lang": "en",
        "screening_metadata": {
            "intent_group": "A",
            "intent_prob": 0.91,
            "suggestion": "Explain gas fees and alternatives"
        },
        "priority": 0.87,
        "account_id": "test_acc_004",
        "account_username": "eth_user"
    },
    {
        "post_id": "promo_a5",
        "title": "Best network for frequent small USDT transfers?",
        "subreddit": "Tether",
        "score": 65,
        "age_hours": 2.0,
        "lang": "en",
        "screening_metadata": {
            "intent_group": "A",
            "intent_prob": 0.90,
            "suggestion": "Recommend cost-effective options"
        },
        "priority": 0.86,
        "account_id": "test_acc_005",
        "account_username": "usdt_trader"
    },

    # B组 - 钱包问题 (5条)
    {
        "post_id": "promo_b1",
        "title": "USDT stuck in pending for 3 hours, what should I do?",
        "subreddit": "CryptoHelp",
        "score": 30,
        "age_hours": 1.5,
        "lang": "en",
        "screening_metadata": {
            "intent_group": "B",
            "intent_prob": 0.88,
            "suggestion": "Troubleshoot transaction status"
        },
        "priority": 0.80,
        "account_id": "test_acc_006",
        "account_username": "help_seeker"
    },
    {
        "post_id": "promo_b2",
        "title": "Binance withdrawal not showing in wallet",
        "subreddit": "binance",
        "score": 55,
        "age_hours": 2.3,
        "lang": "en",
        "screening_metadata": {
            "intent_group": "B",
            "intent_prob": 0.85,
            "suggestion": "Check network and confirmations"
        },
        "priority": 0.78,
        "account_id": "test_acc_007",
        "account_username": "binance_user"
    },
    {
        "post_id": "promo_b3",
        "title": "Sent USDT to wrong network, is it recoverable?",
        "subreddit": "CryptoBeginners",
        "score": 90,
        "age_hours": 5.0,
        "lang": "en",
        "screening_metadata": {
            "intent_group": "B",
            "intent_prob": 0.92,
            "suggestion": "Explain recovery options"
        },
        "priority": 0.82,
        "account_id": "test_acc_008",
        "account_username": "beginner_crypto"
    },
    {
        "post_id": "promo_b4",
        "title": "Trust Wallet not showing balance after transfer",
        "subreddit": "trustapp",
        "score": 40,
        "age_hours": 3.5,
        "lang": "en",
        "screening_metadata": {
            "intent_group": "B",
            "intent_prob": 0.87,
            "suggestion": "Reimport or refresh wallet"
        },
        "priority": 0.75,
        "account_id": "test_acc_009",
        "account_username": "trust_user"
    },
    {
        "post_id": "promo_b5",
        "title": "How long does TRC20 USDT transfer usually take?",
        "subreddit": "Tron",
        "score": 25,
        "age_hours": 1.8,
        "lang": "en",
        "screening_metadata": {
            "intent_group": "B",
            "intent_prob": 0.83,
            "suggestion": "Explain confirmation times"
        },
        "priority": 0.73,
        "account_id": "test_acc_010",
        "account_username": "tron_newbie"
    },

    # C组 - 学习分享 (5条)
    {
        "post_id": "promo_c1",
        "title": "ELI5: What's the difference between TRC20 and ERC20?",
        "subreddit": "CryptoBeginners",
        "score": 120,
        "age_hours": 6.0,
        "lang": "en",
        "screening_metadata": {
            "intent_group": "C",
            "intent_prob": 0.90,
            "suggestion": "Simple explanation with analogy"
        },
        "priority": 0.88,
        "account_id": "test_acc_011",
        "account_username": "curious_learner"
    },
    {
        "post_id": "promo_c2",
        "title": "New to crypto: which network should I use for USDT?",
        "subreddit": "CryptoCurrency",
        "score": 75,
        "age_hours": 4.2,
        "lang": "en",
        "screening_metadata": {
            "intent_group": "C",
            "intent_prob": 0.86,
            "suggestion": "Beginner-friendly comparison"
        },
        "priority": 0.84,
        "account_id": "test_acc_012",
        "account_username": "crypto_newbie"
    },
    {
        "post_id": "promo_c3",
        "title": "Can someone explain blockchain networks in simple terms?",
        "subreddit": "BitcoinBeginners",
        "score": 95,
        "age_hours": 3.8,
        "lang": "en",
        "screening_metadata": {
            "intent_group": "C",
            "intent_prob": 0.88,
            "suggestion": "Use everyday examples"
        },
        "priority": 0.85,
        "account_id": "test_acc_013",
        "account_username": "learning_crypto"
    },
    {
        "post_id": "promo_c4",
        "title": "Why do different networks charge different fees?",
        "subreddit": "ethereum",
        "score": 110,
        "age_hours": 5.5,
        "lang": "en",
        "screening_metadata": {
            "intent_group": "C",
            "intent_prob": 0.89,
            "suggestion": "Explain network economics"
        },
        "priority": 0.87,
        "account_id": "test_acc_014",
        "account_username": "eth_student"
    },
    {
        "post_id": "promo_c5",
        "title": "资源分享：新手如何选择USDT转账网络？",
        "subreddit": "BitcoinCN",
        "score": 50,
        "age_hours": 2.5,
        "lang": "zh",
        "screening_metadata": {
            "intent_group": "C",
            "intent_prob": 0.85,
            "suggestion": "新手友好的建议"
        },
        "priority": 0.83,
        "account_id": "test_acc_015",
        "account_username": "crypto_cn_teacher"
    }
]


async def test_promotion_integration():
    """
    E2E测试主函数
    """
    print("\n" + "="*80)
    print("Telegram频道推广功能 - E2E测试")
    print("="*80)

    # 初始化管道
    base_path = Path(__file__).parent
    pipeline = ContentPipeline(base_path)

    print(f"\n[INFO] 测试数据集: {len(TEST_POSTS)}条帖子")
    print(f"       A组(费用): 5条 | B组(钱包): 5条 | C组(学习): 5条")
    print(f"       语言分布: EN=11, ES=1, ZH=2")

    # 执行生成
    print("\n[STEP 1] 开始生成评论...")
    results = await pipeline.process_batch(TEST_POSTS)

    print(f"\n[RESULT] 生成成功: {len(results)}/{len(TEST_POSTS)}条")

    # 统计分析
    print("\n" + "-"*80)
    print("统计分析")
    print("-"*80)

    # 1. 整体通过率
    pass_rate = len(results) / len(TEST_POSTS) * 100
    print(f"\n[PASS RATE] {pass_rate:.1f}% ({len(results)}/{len(TEST_POSTS)})")

    # 2. 推广链接统计
    promoted_count = sum(1 for r in results if r.audit.get('promoted_link'))
    promotion_rate = promoted_count / len(results) * 100 if results else 0

    print(f"\n[PROMOTION]")
    print(f"  总推广数: {promoted_count}/{len(results)}条 ({promotion_rate:.1f}%)")

    # 按意图组统计
    intent_stats = {'A': {'total': 0, 'promoted': 0},
                    'B': {'total': 0, 'promoted': 0},
                    'C': {'total': 0, 'promoted': 0}}

    for result in results:
        intent = result.intent_group
        intent_stats[intent]['total'] += 1
        if result.audit.get('promoted_link'):
            intent_stats[intent]['promoted'] += 1

    for intent in ['A', 'B', 'C']:
        stats = intent_stats[intent]
        if stats['total'] > 0:
            rate = stats['promoted'] / stats['total'] * 100
            target = {'A': 70, 'B': 40, 'C': 60}[intent]
            status = "OK" if abs(rate - target) < 15 else "WARN"
            print(f"  {intent}组: {stats['promoted']}/{stats['total']}条 ({rate:.0f}%) [目标{target}%] {status}")

    # 3. 质量评分统计
    avg_relevance = sum(r.quality_scores.relevance for r in results) / len(results) if results else 0
    avg_natural = sum(r.quality_scores.natural for r in results) / len(results) if results else 0
    avg_compliance = sum(r.quality_scores.compliance for r in results) / len(results) if results else 0
    avg_overall = sum(r.quality_scores.overall for r in results) / len(results) if results else 0

    print(f"\n[QUALITY SCORES]")
    print(f"  相关性: {avg_relevance:.2f}")
    print(f"  自然度: {avg_natural:.2f}")
    print(f"  合规度: {avg_compliance:.2f}")
    print(f"  综合分: {avg_overall:.2f}")

    # 4. 链接多样性
    unique_links = set(r.audit.get('promoted_link') for r in results if r.audit.get('promoted_link'))
    print(f"\n[LINK DIVERSITY]")
    print(f"  唯一链接数: {len(unique_links)}个")
    print(f"  链接重复率: {(promoted_count - len(unique_links)) / promoted_count * 100:.1f}%" if promoted_count > 0 else "  N/A")

    # 5. 软文长度验证
    print(f"\n[PROMO TEXT LENGTH]")
    promo_lengths = []
    for result in results:
        if result.audit.get('promoted_link'):
            # 提取推广文本(简化估算：链接前后40字)
            link = result.audit['promoted_link']
            if link in result.text:
                # 找到链接位置，提取前后文本估算软文长度
                link_pos = result.text.find(link)
                context_start = max(0, link_pos - 50)
                context_end = min(len(result.text), link_pos + len(link) + 50)
                promo_snippet = result.text[context_start:context_end]
                # 估算软文部分（链接+引入语）
                promo_text_est = promo_snippet.replace(link, '').strip()
                promo_lengths.append(len(promo_text_est[:60]))  # 取前60字符估算

    if promo_lengths:
        avg_promo_len = sum(promo_lengths) / len(promo_lengths)
        max_promo_len = max(promo_lengths)
        violations = sum(1 for l in promo_lengths if l > 40)
        print(f"  平均长度: {avg_promo_len:.0f}字符")
        print(f"  最大长度: {max_promo_len}字符")
        print(f"  超限(>40): {violations}条 {'FAIL' if violations > 0 else 'PASS'}")

    # 6. 示例输出
    print("\n" + "-"*80)
    print("示例评论 (各组1条)")
    print("-"*80)

    for intent in ['A', 'B', 'C']:
        samples = [r for r in results if r.intent_group == intent]
        if samples:
            sample = samples[0]
            print(f"\n[{intent}组示例] {sample.request_id}")
            print(f"Persona: {sample.persona_used}")
            print(f"Quality: {sample.quality_scores.overall:.2f}")
            print(f"Promoted: {'YES' if sample.audit.get('promoted_link') else 'NO'}")
            if sample.audit.get('promoted_link'):
                print(f"Link: {sample.audit['promoted_link'][:50]}...")
            print(f"\nText:\n{sample.text}\n")

    # 最终评估
    print("\n" + "="*80)
    print("最终评估")
    print("="*80)

    success_criteria = {
        "通过率 >= 75%": pass_rate >= 75,
        "推广率 45-65%": 45 <= promotion_rate <= 65,
        "综合质量 >= 0.75": avg_overall >= 0.75,
        "自然度 >= 0.80": avg_natural >= 0.80,
        "链接多样性 >= 8": len(unique_links) >= 8
    }

    passed = sum(success_criteria.values())
    total = len(success_criteria)

    print(f"\n成功标准: {passed}/{total}")
    for criterion, result in success_criteria.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} {criterion}")

    overall_status = "PASS" if passed >= 4 else "FAIL"
    print(f"\n整体状态: {overall_status}")

    return results


async def main():
    """入口函数"""
    try:
        results = await test_promotion_integration()
        print(f"\n[OK] 测试完成，共生成 {len(results)} 条评论")
        return 0
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
