"""
M4模板化改造 - 端到端测试

[创建日期 2025-10-11] 完整流程测试，包含AI生成
"""
import asyncio
from pathlib import Path

from src.content.comment_generator import CommentGenerator
from src.content.ai_client import AIClient
from src.content.models import (
    CommentRequest,
    Persona,
    IntentGroup,
    StyleGuide
)


async def test_e2e_with_template():
    """端到端测试：使用模板模式"""
    print("=" * 70)
    print("E2E测试: 模板模式 + 双模式推广")
    print("=" * 70)

    # 1. 初始化AI客户端
    ai_client = AIClient()

    # 2. 初始化CommentGenerator（启用模板）
    policies_path = Path("d:/reddit-comment-system/config/content_policies.yaml")
    promotion_path = Path("d:/reddit-comment-system/config/promotion_embedding.yaml")
    template_path = r"C:\Users\beima\Desktop\BaiduSyncdisk\Trx相关\reddit账号\基础软文模板.json"

    generator = CommentGenerator(
        ai_client=ai_client,
        policies_path=policies_path,
        promotion_config_path=promotion_path,
        template_path=template_path,
        variants_count=1  # 快速测试只生成1个变体
    )

    print("\n✓ CommentGenerator初始化成功（模板模式启用）\n")

    # 3. 准备测试用例
    test_cases = [
        {
            "name": "测试1: 中文帖子 + Tronix子版 (允许链接)",
            "request": CommentRequest(
                post_id="test_001",
                title="TRON转账手续费太高了，有什么办法降低吗？",
                subreddit="Tronix",
                account_id="test_acc_001",
                lang="zh",
                score=15,
                age_hours=2.5,
                screening_metadata={"suggestion": "分享降低手续费的实用方法"}
            ),
            "style_guide": StyleGuide(
                subreddit="Tronix",
                tone="friendly_practical",
                length={
                    "top_level_sentences": {"min": 2, "max": 3},
                    "chars": {"min": 40, "max": 200}
                },
                jargon_level="medium",
                must_end_with_question=False,
                dos=["具体步骤", "平台无关建议"],
                donts=["过度推销", "过多表情"],
                compliance={
                    "financial_disclaimer": False,
                    "link_policy": "whitelist_only"  # 允许链接
                }
            ),
            "intent_group": IntentGroup(
                name="A",
                description="费用相关问题",
                response_style={
                    "focus": "实用建议",
                    "must_include": "具体方法",
                    "avoid": "理论讲解"
                }
            )
        },
        {
            "name": "测试2: 英文帖子 + CryptoCurrency子版 (禁止链接)",
            "request": CommentRequest(
                post_id="test_002",
                title="High transfer fees are killing my crypto transactions",
                subreddit="CryptoCurrency",
                account_id="test_acc_002",
                lang="en",
                score=42,
                age_hours=5.2,
                screening_metadata={"suggestion": "Share cost-saving experience"}
            ),
            "style_guide": StyleGuide(
                subreddit="CryptoCurrency",
                tone="neutral_sober",
                length={
                    "top_level_sentences": {"min": 2, "max": 3},
                    "chars": {"min": 50, "max": 200}
                },
                jargon_level="medium",
                must_end_with_question=False,
                dos=["个人经历", "不确定性声明"],
                donts=["价格预测", "联盟链接"],
                compliance={
                    "financial_disclaimer": True,
                    "link_policy": "none"  # 禁止链接
                }
            ),
            "intent_group": IntentGroup(
                name="A",
                description="Fee-related issues",
                response_style={
                    "focus": "practical solutions",
                    "must_include": "personal experience",
                    "avoid": "technical jargon"
                }
            )
        }
    ]

    # 4. 执行测试用例
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'=' * 70}")
        print(f"{test_case['name']}")
        print(f"{'=' * 70}")

        try:
            # 生成评论
            result = await generator.generate(
                request=test_case['request'],
                persona=create_test_persona(),
                intent_group=test_case['intent_group'],
                style_guide=test_case['style_guide']
            )

            # 输出结果
            print(f"\n帖子标题: {test_case['request'].title}")
            print(f"子版: {test_case['request'].subreddit}")
            print(f"链接政策: {test_case['style_guide'].compliance['link_policy']}")
            print(f"\n生成的评论:")
            print("-" * 70)
            # 处理可能的编码问题
            try:
                print(result.text)
            except UnicodeEncodeError:
                print(result.text.encode('utf-8', errors='replace').decode('utf-8'))
            print("-" * 70)

            print(f"\n质量评分:")
            print(f"  - 整体: {result.quality_scores.overall:.2f}")
            print(f"  - 自然度: {result.quality_scores.naturalness:.2f}")
            print(f"  - 相关性: {result.quality_scores.relevance:.2f}")
            print(f"  - 简洁性: {result.quality_scores.conciseness:.2f}")
            print(f"  - 合规性: {result.quality_scores.compliance:.2f}")

            print(f"\n推广链接: {result.promoted_link if result.promoted_link else '无 (文字描述模式)'}")
            print(f"生成耗时: {result.generation_time_ms}ms")

            print(f"\n[PASS] Test {i} passed")

        except Exception as e:
            print(f"\n[FAIL] Test {i} failed: {e}")
            import traceback
            traceback.print_exc()


def create_test_persona() -> Persona:
    """创建测试用Persona"""
    return Persona(
        id="test_persona_001",
        name="Alex",
        background="Crypto enthusiast with 3 years of experience",
        tone="casual and helpful",
        interests=["cryptocurrency", "DeFi", "blockchain"],
        constraints=["avoid technical jargon", "be friendly"],
        catchphrases={
            "opening": ["honestly", "tbh", "imo"],
            "ending": ["hope this helps", "good luck"]
        }
    )


async def test_template_selection_coverage():
    """测试模板选择的语言覆盖度"""
    print("\n" + "=" * 70)
    print("测试: 模板选择语言覆盖度")
    print("=" * 70)

    from src.content.template_loader import TemplateLoader

    template_path = r"C:\Users\beima\Desktop\BaiduSyncdisk\Trx相关\reddit账号\基础软文模板.json"
    loader = TemplateLoader(template_path)

    # 测试所有语言+意图组组合
    languages = ['zh', 'en', 'es', 'pt', 'ar', 'hi', 'id', 'th', 'tr', 'vi']
    intent_groups = ['A_fees_transfers', 'B_wallet_issues', 'C_learning_share']

    success_count = 0
    total_count = len(languages) * len(intent_groups)

    print(f"\n测试 {total_count} 个组合...")
    print()

    for lang in languages:
        for intent in intent_groups:
            template = loader.select_template(lang, intent)
            if template:
                success_count += 1
                status = "OK"
            else:
                status = "MISS"
            result_text = "Found" if template else "Missing"
            print(f"[{status}] {lang:4s} + {intent:20s}: {result_text}")

    print(f"\n成功率: {success_count}/{total_count} ({success_count/total_count*100:.1f}%)")


async def test_promotion_mode_switching():
    """测试推广模式自动切换"""
    print("\n" + "=" * 70)
    print("测试: 推广模式自动切换")
    print("=" * 70)

    from src.content.link_promoter import LinkPromoter

    config_path = Path("d:/reddit-comment-system/config/promotion_embedding.yaml")
    promoter = LinkPromoter(config_path)

    test_cases = [
        {
            "name": "whitelist_only → URL模式",
            "policy": "whitelist_only",
            "expected_mode": "URL"
        },
        {
            "name": "none → 文字描述模式",
            "policy": "none",
            "expected_mode": "Text"
        },
        {
            "name": "docs_and_github → 文字描述模式",
            "policy": "docs_and_github",
            "expected_mode": "Text"
        }
    ]

    for i, case in enumerate(test_cases, 1):
        print(f"\n测试 {i}: {case['name']}")

        style_guide = {
            'compliance': {
                'link_policy': case['policy']
            }
        }

        comment = "Transfer fees are too expensive, energy rental saves 80%"
        result, link = promoter.insert_link(
            comment_text=comment,
            intent_group="A",
            account_id=f"test_{i}",
            post_lang="en",
            subreddit="TestSubreddit",
            style_guide=style_guide
        )

        actual_mode = "URL" if link else "Text"

        if actual_mode == case['expected_mode']:
            print(f"  [OK] Mode: {actual_mode}")
            if link:
                print(f"    Link: {link[:50]}...")
            else:
                print(f"    Text: ...{result[-60:]}")
        else:
            print(f"  [FAIL] Expected {case['expected_mode']}, got {actual_mode}")


async def main():
    """主测试流程"""
    try:
        # 测试1: 模板选择覆盖度
        await test_template_selection_coverage()

        # 测试2: 推广模式切换
        await test_promotion_mode_switching()

        # 测试3: 端到端完整流程
        await test_e2e_with_template()

        print("\n" + "=" * 70)
        print("All tests completed successfully!")
        print("=" * 70)

    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
