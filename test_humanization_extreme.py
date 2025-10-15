"""
极限拟人化测试 - 100次迭代强制触发所有特征
"""

import asyncio
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from src.content.naturalizer import Naturalizer
from src.content.models import Persona


async def test_extreme_humanization():
    """极限测试 - 100次迭代"""
    print("\n" + "="*80)
    print("  极限拟人化测试 - 100次迭代")
    print("="*80)

    base_dir = Path(__file__).parent
    naturalizer = Naturalizer(
        naturalization_policy_path=base_dir / "config" / "naturalization_policy.yaml"
    )

    test_persona = Persona(
        id="gas_optimizer",
        name="Priya R",
        background="Power-user",
        tone="practical_helpful",
        interests=["crypto", "fees"],
        intent_groups=["A"],
        catchphrases={
            "opening": ["here's what worked for me:", "imo"],
            "transition": ["that said", "honestly"],
            "ending": ["hope this helps!", "let me know!"]
        },
        constraints={}
    )

    # [FIX 2025-10-15] 包含所有可触发点的测试文本 - 新增触发词
    test_texts = [
        "I can't believe Bitcoin transfer fees are so high. I definitely recommend using optimization.",
        "Don't worry, Ethereum blockchain transactions are fast. It's the best option I have found.",
        "The cryptocurrency exchange I use has low fees. It is amazing and I won't use anything else.",
        "MetaMask wallet address verification occurred without issues. I received my funds immediately.",
        "This is crazy! The fees are so expensive. I won't pay that much for a simple transfer.",
        "Hold your coins, don't sell now. The price will increase a lot very soon.",
        "That's the best wallet I have found. It's fast and easy to use.",
        "I can't wait to see Bitcoin rising again. It's never been this low before.",
    ]

    all_features = {
        'lowercase_start': 0,
        'all_caps': 0,
        'missing_period': 0,
        'typo': 0,
        'apostrophe_drop': 0,
        'crypto_slang': 0,
        'emoji': 0,
        'multiple_exclamations': 0,
        'casual_nouns': 0,
        'filler_words': 0,
        'ellipsis': 0
    }

    total_iterations = 100
    rare_features_found = []

    print(f"\n开始{total_iterations}次迭代测试...\n")

    for i in range(total_iterations):
        test_text = test_texts[i % len(test_texts)]
        humanized = naturalizer.add_natural_imperfections(test_text)

        # 统计
        features_in_this = []

        if humanized and humanized[0].islower():
            all_features['lowercase_start'] += 1

        if any(word.isupper() and len(word) > 2 for word in humanized.split()):
            all_features['all_caps'] += 1
            features_in_this.append('全大写')

        if not humanized.rstrip().endswith(('.', '!', '?')):
            all_features['missing_period'] += 1

        typos = ['tranfer', 'recieve', 'seperate', 'definately', 'occured',
                 'withdrawl', 'transation', 'walet', 'exhange', 'adress', 'block chain']
        if any(typo in humanized.lower() for typo in typos):
            all_features['typo'] += 1
            features_in_this.append('错别字')

        if any(casual in humanized for casual in ["dont", "cant", "wont", "didnt", "its", "thats", "whats"]):
            all_features['apostrophe_drop'] += 1
            features_in_this.append('省略撇号')

        slang = ['hodl', 'hodling', 'rekt', 'moon', 'mooning', 'lambo', 'fud', 'fomo', 'dyor', 'nfa', 'wagmi', 'gm', 'pricey af']
        if any(s in humanized.lower() for s in slang):
            all_features['crypto_slang'] += 1
            features_in_this.append('加密俚语')

        emojis = ['👍', '😂', '🙏', '🚀', '💎', '💀', '🔥', '💪', '🤔', '👀', '📈', '💰', '🪙', '📉', '🤷', '😅', '✅']
        if any(emoji in humanized for emoji in emojis):
            all_features['emoji'] += 1

        if '!!' in humanized or '!!!' in humanized or '?!' in humanized:
            all_features['multiple_exclamations'] += 1
            features_in_this.append('多感叹号')

        casual_nouns = ['bitcoin', 'ethereum', 'tron', 'binance', 'coinbase', 'metamask', 'uniswap']
        if any(noun in humanized.lower() and noun.capitalize() not in humanized for noun in casual_nouns):
            all_features['casual_nouns'] += 1

        fillers = ['tbh', 'imo', 'idk', 'ngl', 'fwiw', 'kinda', 'sorta', 'basically',
                  'honestly', 'actually', 'probably', 'fr', 'lowkey', 'literally',
                  'like', 'I mean', 'you know', 'right']
        if any(filler in humanized.lower() for filler in fillers):
            all_features['filler_words'] += 1

        if '...' in humanized or '…' in humanized:
            all_features['ellipsis'] += 1
            features_in_this.append('省略号')

        # 记录稀有特征示例
        if features_in_this:
            rare_features_found.append({
                'iteration': i + 1,
                'features': features_in_this,
                'text': humanized
            })

    # 输出结果
    print("="*80)
    print(f"  统计结果 ({total_iterations}次迭代)")
    print("="*80)

    print(f"\n【高频特征】(>30次)")
    high_freq = [(k, v) for k, v in all_features.items() if v > 30]
    for feature, count in sorted(high_freq, key=lambda x: x[1], reverse=True):
        print(f"  {feature:20s}: {count:3d}/{total_iterations}  ({count}%)")

    print(f"\n【中频特征】(10-30次)")
    mid_freq = [(k, v) for k, v in all_features.items() if 10 <= v <= 30]
    for feature, count in sorted(mid_freq, key=lambda x: x[1], reverse=True):
        print(f"  {feature:20s}: {count:3d}/{total_iterations}  ({count}%)")

    print(f"\n【低频特征】(<10次)")
    low_freq = [(k, v) for k, v in all_features.items() if v < 10]
    for feature, count in sorted(low_freq, key=lambda x: x[1], reverse=True):
        print(f"  {feature:20s}: {count:3d}/{total_iterations}  ({count}%)")

    # 展示稀有特征示例
    if rare_features_found:
        print(f"\n【稀有特征示例】(前10个)")
        for example in rare_features_found[:10]:
            features_str = ', '.join(example['features'])
            print(f"  第{example['iteration']:3d}次: [{features_str}]")
            print(f"          {example['text']}\n")

    total_features_applied = sum(all_features.values())
    avg_features = total_features_applied / total_iterations

    print("\n" + "="*80)
    print(f"  总拟人化特征应用次数: {total_features_applied}")
    print(f"  平均每条特征数:       {avg_features:.2f}")

    # 特征覆盖度
    features_with_hits = sum(1 for v in all_features.values() if v > 0)
    total_feature_types = len(all_features)
    coverage = features_with_hits / total_feature_types * 100

    print(f"  特征类型覆盖度:       {features_with_hits}/{total_feature_types} ({coverage:.0f}%)")
    print("="*80 + "\n")

    # 诊断低频特征
    print("【低频特征诊断】")
    if all_features['typo'] < 10:
        print(f"  ⚠️  错别字仅{all_features['typo']}次 - 检查typo_policy配置")
    if all_features['apostrophe_drop'] < 10:
        print(f"  ⚠️  省略撇号仅{all_features['apostrophe_drop']}次 - 检查contraction_policy配置")
    if all_features['crypto_slang'] < 10:
        print(f"  ⚠️  加密俚语仅{all_features['crypto_slang']}次 - 检查crypto_slang配置")
    if all_features['all_caps'] < 5:
        print(f"  ⚠️  全大写仅{all_features['all_caps']}次 - 检查capitalization_policy配置")
    if all_features['ellipsis'] < 10:
        print(f"  ⚠️  省略号仅{all_features['ellipsis']}次 - 检查punctuation_variety配置")

    print()


if __name__ == "__main__":
    asyncio.run(test_extreme_humanization())
