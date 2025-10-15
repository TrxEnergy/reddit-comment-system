"""
最终拟人化系统综合测试报告
测试所有11个拟人化特征的触发率和组合效果
"""
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from src.content.naturalizer import Naturalizer

def main():
    base_dir = Path(__file__).parent
    naturalizer = Naturalizer(
        naturalization_policy_path=base_dir / "config" / "naturalization_policy.yaml"
    )

    # 包含所有可触发点的测试文本
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

    print("=" * 80)
    print("  最终拟人化系统综合测试 - 150次迭代")
    print("=" * 80)
    print()

    all_features = {
        'lowercase_start': 0,
        'all_caps': 0,
        'casual_nouns': 0,
        'typo': 0,
        'apostrophe_drop': 0,
        'crypto_slang': 0,
        'filler_words': 0,
        'emoji': 0,
        'ellipsis': 0,
        'missing_period': 0,
        'multiple_exclamations': 0,
    }

    excellent_examples = []  # 4个以上特征的优秀示例

    for i in range(150):
        text = test_texts[i % len(test_texts)]
        humanized = naturalizer.add_natural_imperfections(text)

        features_in_this = []

        # 检测所有特征
        if humanized and humanized[0].islower():
            all_features['lowercase_start'] += 1
            features_in_this.append('句首小写')

        caps_words = ['HODL', 'DYOR', 'NFA', 'FOMO', 'FUD', 'WAGMI', 'WTF', 'LOL',
                      'OMG', 'FINALLY', 'THIS', 'FAST', 'CRAZY', 'BEST', 'INSANE',
                      'AMAZING', 'NEVER', 'ALWAYS']
        if any(word in humanized for word in caps_words):
            all_features['all_caps'] += 1
            features_in_this.append('全大写')

        casual_nouns = ['bitcoin', 'ethereum', 'coinbase', 'metamask', 'uniswap']
        if any(noun in humanized for noun in casual_nouns):
            all_features['casual_nouns'] += 1
            features_in_this.append('小写专有名词')

        typos = ['tranfer', 'recieve', 'seperate', 'definately', 'occured', 'withdrawl',
                 'transation', 'walet', 'cryprocurrency', 'exhange', 'adress',
                 'block chain', 'reccomend', 'experiance', 'beleive']
        if any(typo in humanized.lower() for typo in typos):
            all_features['typo'] += 1
            features_in_this.append('错别字')

        if any(casual in humanized for casual in ["dont", "cant", "wont", "didnt", "its", "thats", "whats"]):
            all_features['apostrophe_drop'] += 1
            features_in_this.append('省略撇号')

        slang = ['hodl', 'hodling', 'rekt', 'moon', 'mooning', 'lambo', 'fud', 'fomo',
                 'dyor', 'nfa', 'wagmi', 'gm', 'pricey af']
        if any(s in humanized.lower() for s in slang):
            all_features['crypto_slang'] += 1
            features_in_this.append('加密俚语')

        fillers = ['tbh', 'imo', 'honestly', 'literally', 'basically', 'actually',
                   'like', 'you know', 'I mean', 'right', 'fr', 'ngl', 'fwiw',
                   'btw', 'sorta', 'kinda', 'probably']
        if any(filler in humanized.lower() for filler in fillers):
            all_features['filler_words'] += 1
            features_in_this.append('填充词')

        emojis = ['👍', '😂', '🙏', '🚀', '💎', '💀', '🔥', '💪', '🤔', '👀',
                  '📈', '💰', '🪙', '📉', '🤷', '😅', '✅']
        if any(emoji in humanized for emoji in emojis):
            all_features['emoji'] += 1
            features_in_this.append('emoji')

        if '...' in humanized or '…' in humanized or '..' in humanized:
            all_features['ellipsis'] += 1
            features_in_this.append('省略号')

        if not humanized.rstrip().endswith(('.', '!', '?', '…')):
            all_features['missing_period'] += 1
            features_in_this.append('省略句号')

        if '!!' in humanized or '!!!' in humanized or '?!' in humanized:
            all_features['multiple_exclamations'] += 1
            features_in_this.append('多感叹号')

        # 收集优秀示例（4个以上特征）
        if len(features_in_this) >= 4:
            excellent_examples.append({
                'iteration': i + 1,
                'text': humanized,
                'features': features_in_this,
                'count': len(features_in_this)
            })

    # 打印详细统计
    print("【特征触发统计】(150次迭代)\n")

    high_freq = []
    mid_freq = []
    low_freq = []

    for feature, count in all_features.items():
        percentage = count / 150 * 100
        if count >= 45:
            high_freq.append((feature, count, percentage))
        elif count >= 15:
            mid_freq.append((feature, count, percentage))
        else:
            low_freq.append((feature, count, percentage))

    print("高频特征 (≥30%):")
    for feature, count, pct in sorted(high_freq, key=lambda x: x[1], reverse=True):
        print(f"  {feature:20s}: {count:3d}/150  ({pct:5.1f}%)")

    print("\n中频特征 (10-30%):")
    for feature, count, pct in sorted(mid_freq, key=lambda x: x[1], reverse=True):
        print(f"  {feature:20s}: {count:3d}/150  ({pct:5.1f}%)")

    if low_freq:
        print("\n低频特征 (<10%):")
        for feature, count, pct in sorted(low_freq, key=lambda x: x[1], reverse=True):
            print(f"  {feature:20s}: {count:3d}/150  ({pct:5.1f}%)")

    total_features = sum(all_features.values())
    avg_features = total_features / 150
    coverage = sum(1 for count in all_features.values() if count > 0)

    print("\n" + "=" * 80)
    print(f"总特征应用次数: {total_features}")
    print(f"平均每条特征数: {avg_features:.2f}")
    print(f"特征覆盖度:     {coverage}/11 ({coverage/11*100:.0f}%)")
    print("=" * 80)

    # 打印优秀示例
    print("\n【优秀示例】(4+特征)\n")
    for idx, example in enumerate(excellent_examples[:15], 1):
        print(f"第{example['iteration']}次迭代 [{example['count']}个特征]:")
        print(f"  特征: {', '.join(example['features'])}")
        print(f"  文本: \"{example['text']}\"")
        print()

    print(f"共找到 {len(excellent_examples)} 个4+特征示例 (占比 {len(excellent_examples)/150*100:.1f}%)")

    # 目标达成度评估
    print("\n" + "=" * 80)
    print("【目标达成度评估】\n")

    targets = {
        'emoji': (45, 55),
        'lowercase_start': (25, 35),
        'filler_words': (40, 50),
        'typo': (35, 50),
        'apostrophe_drop': (20, 30),
        'crypto_slang': (20, 30),
        'all_caps': (12, 30),
        'ellipsis': (25, 35),
        'missing_period': (35, 45),
    }

    all_met = True
    for feature, (min_target, max_target) in targets.items():
        actual = all_features[feature] / 150 * 100
        if min_target <= actual <= max_target:
            status = "✅"
        elif actual < min_target:
            status = "⚠️ 偏低"
            all_met = False
        else:
            status = "⚠️ 偏高"
            all_met = False

        print(f"{feature:20s}: {actual:5.1f}%  (目标 {min_target}-{max_target}%)  {status}")

    print("\n" + "=" * 80)
    if all_met:
        print("✅ 所有特征均达到目标范围！系统拟人化程度: 优秀")
    else:
        print("⚠️ 部分特征未达目标，建议微调概率配置")
    print("=" * 80)

if __name__ == "__main__":
    main()
