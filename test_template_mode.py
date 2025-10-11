"""
快速测试M4模板化改造效果

[创建日期 2025-10-11] 验证模板加载、双模式推广
"""
import asyncio
from pathlib import Path

from src.content.template_loader import TemplateLoader
from src.content.link_promoter import LinkPromoter


def test_template_loader():
    """测试模板加载器"""
    print("=" * 60)
    print("测试1: 模板加载器")
    print("=" * 60)

    template_path = r"C:\Users\beima\Desktop\BaiduSyncdisk\Trx相关\reddit账号\基础软文模板.json"
    loader = TemplateLoader(template_path)

    # 统计信息
    stats = loader.get_stats()
    print(f"\n总模板数: {stats['total']}")
    print(f"语言分布: {stats['by_language']}")
    print(f"类别分布: {stats['by_category']}")

    # 覆盖度检查
    coverage = loader.validate_coverage()
    print(f"\n覆盖率: {coverage['coverage_percentage']:.1f}%")
    if coverage['missing_combinations']:
        print(f"缺失组合: {coverage['missing_combinations'][:5]}...")

    # 选择测试
    print("\n" + "=" * 60)
    print("模板选择测试")
    print("=" * 60)

    test_cases = [
        ("zh", "A_fees_transfers"),
        ("en", "B_wallet_issues"),
        ("es", "C_learning_share"),
        ("ar", "A_fees_transfers")
    ]

    for lang, intent in test_cases:
        template = loader.select_template(lang, intent)
        if template:
            print(f"\n{lang} + {intent}:")
            # 处理特殊字符编码
            try:
                print(f"  模板: {template['text']}")
            except UnicodeEncodeError:
                print(f"  模板: [包含非ASCII字符，长度={len(template['text'])}]")
            print(f"  语气: {template['tone']}, 级别: {template['promo_level']}")
        else:
            print(f"\n{lang} + {intent}: 未找到")


def test_link_promoter_dual_mode():
    """测试双模式推广"""
    print("\n" + "=" * 60)
    print("测试2: 双模式推广")
    print("=" * 60)

    config_path = Path("d:/reddit-comment-system/config/promotion_embedding.yaml")
    promoter = LinkPromoter(config_path)

    # 测试case 1: 允许链接的子版 (whitelist_only)
    print("\n场景1: Tronix子版 (允许链接)")
    style_guide_allow = {
        'compliance': {
            'link_policy': 'whitelist_only'
        }
    }

    comment = "转账手续费太贵了，能量租赁能省80%"
    result, link = promoter.insert_link(
        comment_text=comment,
        intent_group="A",
        account_id="test_001",
        post_lang="zh",
        subreddit="Tronix",
        style_guide=style_guide_allow
    )

    print(f"原评论: {comment}")
    print(f"推广后: {result}")
    print(f"模式: URL模式，链接={link[:30] if link else 'None'}...")

    # 测试case 2: 禁止链接的子版 (none)
    print("\n场景2: CryptoCurrency子版 (禁止链接)")
    style_guide_block = {
        'compliance': {
            'link_policy': 'none'
        }
    }

    comment = "honestly transfer fees used to kill me, energy rental saved me tons"
    result, link = promoter.insert_link(
        comment_text=comment,
        intent_group="A",
        account_id="test_002",
        post_lang="en",
        subreddit="CryptoCurrency",
        style_guide=style_guide_block
    )

    print(f"原评论: {comment}")
    print(f"推广后: {result}")
    print(f"模式: 文字描述模式，链接={link}")


def test_integration():
    """测试完整集成流程"""
    print("\n" + "=" * 60)
    print("测试3: 完整流程模拟")
    print("=" * 60)

    template_path = r"C:\Users\beima\Desktop\BaiduSyncdisk\Trx相关\reddit账号\基础软文模板.json"
    loader = TemplateLoader(template_path)

    config_path = Path("d:/reddit-comment-system/config/promotion_embedding.yaml")
    promoter = LinkPromoter(config_path)

    # 模拟流程
    print("\n流程: 帖子语言=en, 意图组=A, 子版=Tronix (允许链接)")

    # 1. 选择模板
    template = loader.select_template("en", "A_fees_transfers")
    if not template:
        print("错误: 未找到模板")
        return

    print(f"\n步骤1 - 选中模板: {template['text']}")

    # 2. 模拟AI轻度加工 (这里直接使用模板)
    adapted_comment = template['text']
    print(f"步骤2 - AI轻度加工: {adapted_comment}")

    # 3. 模拟naturalizer添加表情 (简化)
    adapted_comment += " 👍"
    print(f"步骤3 - Naturalizer处理: {adapted_comment}")

    # 4. 推广插入
    style_guide = {
        'compliance': {
            'link_policy': 'whitelist_only'
        }
    }

    final_comment, link = promoter.insert_link(
        comment_text=adapted_comment,
        intent_group="A",
        account_id="test_003",
        post_lang="en",
        subreddit="Tronix",
        style_guide=style_guide
    )

    print(f"步骤4 - 推广插入: {final_comment}")
    print(f"使用链接: {link[:40] if link else 'None'}...")

    print("\n流程完成！最终评论长度:", len(final_comment), "字符")


if __name__ == "__main__":
    try:
        test_template_loader()
        test_link_promoter_dual_mode()
        test_integration()

        print("\n" + "=" * 60)
        print("所有测试完成！✓")
        print("=" * 60)

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
