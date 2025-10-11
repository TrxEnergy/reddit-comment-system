"""
测试不同意图组的Persona多样性和推广功能
"""

import asyncio
import sys
import io
from pathlib import Path

# Windows编码修复
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from src.content.intent_router import IntentRouter
from src.content.persona_manager import PersonaManager
from src.content.style_guide_loader import StyleGuideLoader


async def main():
    print("\n" + "="*60)
    print("  意图组与Persona映射测试")
    print("="*60)

    # 初始化组件
    project_root = Path(__file__).parent

    intent_router = IntentRouter(
        project_root / "data" / "intents" / "intent_groups.yaml"
    )

    persona_manager = PersonaManager(
        config_path=project_root / "data" / "personas" / "persona_bank.yaml",
        account_tiers_path=project_root / "config" / "account_tiers.yaml"
    )

    style_loader = StyleGuideLoader(
        project_root / "data" / "styles" / "sub_style_guides.yaml"
    )

    # 测试用例：不同意图的帖子
    test_cases = [
        {
            "name": "意图组A - 费用相关",
            "title": "TRON transfer fees are too high, any way to reduce them?",
            "keywords": ["fees", "transfer", "cost", "expensive"]
        },
        {
            "name": "意图组B - 钱包/交易所问题",
            "title": "My Binance withdrawal is stuck, what should I do?",
            "keywords": ["binance", "withdrawal", "stuck", "exchange"]
        },
        {
            "name": "意图组C - 新手学习",
            "title": "What is TRON and how does it compare to Ethereum?",
            "keywords": ["what is", "how does", "compare", "beginner"]
        }
    ]

    print("\n测试场景：为3种不同意图的帖子选择Persona\n")

    results = []

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"  场景{i}: {test_case['name']}")
        print(f"{'='*60}")
        print(f"帖子标题: {test_case['title']}")
        print(f"关键词: {', '.join(test_case['keywords'])}")

        # 路由到意图组
        intent_group = intent_router.route(
            post_title=test_case['title'],
            post_metadata={}
        )

        print(f"\n✅ 路由结果: 意图组{intent_group.name}")
        print(f"  描述: {intent_group.description}")
        print(f"  推荐Personas: {', '.join(intent_group.preferred_personas)}")

        # 选择Persona（测试5次看多样性）
        print(f"\n尝试选择Persona（5次）:")
        personas_selected = []

        for j in range(5):
            try:
                persona = persona_manager.select_persona(
                    intent_group=intent_group.name,
                    subreddit="CryptoCurrency",
                    post_metadata={}
                )
                personas_selected.append(persona.id)
                print(f"  {j+1}. {persona.id} ({persona.name})")
            except Exception as e:
                print(f"  {j+1}. ❌ 选择失败: {e}")

        # 统计Persona多样性
        unique_personas = set(personas_selected)
        diversity_ratio = len(unique_personas) / len(personas_selected) if personas_selected else 0

        print(f"\n📊 多样性: {len(unique_personas)}/{len(personas_selected)} = {diversity_ratio*100:.0f}%")

        # 测试推广策略
        print(f"\n推广策略:")
        subreddits_to_test = [
            ("Tronix", "whitelist_only"),  # 允许链接
            ("CryptoCurrency", "none")      # 禁止链接
        ]

        for subreddit, expected_policy in subreddits_to_test:
            style_guide = style_loader.load(subreddit)
            actual_policy = style_guide.compliance.get('link_policy', 'none')

            print(f"  r/{subreddit}: {actual_policy}")
            if actual_policy == 'whitelist_only':
                print(f"    → 将使用URL模式（插入真实链接）")
            else:
                print(f"    → 将使用文字模式（luntriaOfficialChannel提及）")

        results.append({
            "intent": intent_group.name,
            "personas": personas_selected,
            "diversity": diversity_ratio
        })

    # 总体统计
    print(f"\n\n{'='*60}")
    print("  总体统计")
    print(f"{'='*60}\n")

    all_personas = []
    for r in results:
        all_personas.extend(r['personas'])

    from collections import Counter
    persona_counts = Counter(all_personas)

    print(f"总共选择: {len(all_personas)}次")
    print(f"不同Persona: {len(persona_counts)}个")
    print(f"\nPersona使用频率:")
    for persona_id, count in persona_counts.most_common():
        print(f"  {persona_id}: {count}次")

    print(f"\n各意图组多样性:")
    for r in results:
        print(f"  意图组{r['intent']}: {r['diversity']*100:.0f}%")

    avg_diversity = sum(r['diversity'] for r in results) / len(results)

    print(f"\n{'='*60}")
    if avg_diversity >= 0.6:
        print(f"  ✅ 结论: Persona选择多样性良好 ({avg_diversity*100:.0f}%)")
    elif avg_diversity >= 0.4:
        print(f"  ⚠️  结论: Persona多样性中等 ({avg_diversity*100:.0f}%)")
    else:
        print(f"  ❌ 结论: Persona多样性偏低 ({avg_diversity*100:.0f}%)")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
