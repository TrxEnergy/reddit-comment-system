"""
测试实际发布到Reddit（dry-run模式，只连接不发布）
"""

import asyncio
import sys
import io
from pathlib import Path

# Windows编码修复
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from src.publishing.local_account_manager import LocalAccountManager
from src.publishing.reddit_client import RedditClient
from src.core.logging import get_logger

logger = get_logger(__name__)


async def main():
    print("\n" + "="*60)
    print("  Reddit发布测试（Dry-Run模式）")
    print("="*60 + "\n")

    # 1. 加载账号
    print("[1/4] 加载账号...")
    account_manager = LocalAccountManager()
    accounts = account_manager.load_accounts()

    if not accounts:
        print("❌ 没有可用账号")
        return

    account = accounts[0]
    print(f"✅ 已加载账号: {account.profile_id}")

    # 2. 测试Reddit连接
    print("\n[2/4] 测试Reddit API连接...")
    reddit_client = RedditClient()

    success, result = reddit_client.test_connection(account)

    if not success:
        print(f"❌ Reddit连接失败: {result}")
        return

    print(f"✅ Reddit连接成功！")
    print(f"  用户名: {result}")

    # 3. 准备测试评论
    print("\n[3/4] 准备测试评论...")
    test_comment = """
From my experience with TRON, the network fees are generally much lower
than Ethereum. For USDT transfers, TRC20 typically costs less than $1,
while ERC20 can be $10-20 depending on gas prices.

Have you checked if your exchange supports TRC20? Most major platforms
like Binance do, and the savings can be significant if you're making
frequent transfers.
""".strip()

    print(f"✅ 测试评论已准备（{len(test_comment)}字符）")
    print(f"\n预览:\n{test_comment[:100]}...\n")

    # 4. Dry-Run说明
    print("\n[4/4] Dry-Run模式说明:")
    print("  ✓ 账号连接成功验证")
    print("  ✓ Reddit API可达")
    print("  ✗ 未实际发布评论（需要parent_comment_id）")
    print("\n如需实际发布，请：")
    print("  1. 找到目标帖子的顶级评论ID")
    print("  2. 调用 reddit_client.publish_comment(account, PublishRequest(...))")
    print("  3. 确认评论符合子版规则")

    print("\n" + "="*60)
    print("  ✅ Dry-Run测试通过！系统已准备好发布")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
