"""
模拟10个账号的M2搜索量测试 v2
"""
import asyncio
import sys
import os
import time
from pathlib import Path

# [FIX 2025-10-10] 强制UTF-8输出，避免GBK编码错误
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    os.environ['PYTHONIOENCODING'] = 'utf-8'

sys.path.insert(0, str(Path(__file__).parent))

from src.discovery.pipeline import DiscoveryPipeline


async def main():
    """模拟10个账号场景"""

    # 模拟10个账号的池子配置
    account_count = 10
    daily_comment_limit = 1
    buffer_ratio = 3.0

    pool_size = int(account_count * daily_comment_limit * buffer_ratio)
    target_posts = pool_size + 2

    print("="*60)
    print("  模拟10个账号的M2发现测试 v2")
    print("="*60)
    print(f"  账号数量: {account_count}")
    print(f"  池子规模: {pool_size}个（{account_count}×{daily_comment_limit}×{buffer_ratio}）")
    print(f"  搜索目标: {target_posts}个帖子（含缓冲）")
    print(f"  每簇基础配额: {max(1, target_posts // 30)}个帖子")
    print(f"  每簇搜索量: {max(1, target_posts // 30) * 3}个（3倍缓冲）")
    print("="*60)
    print()

    # 执行发现流程
    pipeline = DiscoveryPipeline()
    posts = await pipeline.run(
        recipe_name="deep_dive",
        target_posts=target_posts
    )

    print()
    print("="*60)
    print("  测试结果总结")
    print("="*60)
    print(f"[RESULT] 目标: {target_posts}个帖子")
    print(f"[RESULT] 实际获得: {len(posts)}个帖子")
    print(f"[RESULT] 完成率: {len(posts)/target_posts*100:.1f}%")

    if len(posts) >= target_posts:
        print("[SUCCESS] 达到目标！")
    elif len(posts) >= target_posts * 0.8:
        print("[GOOD] 接近目标（80%以上）")
    elif len(posts) >= target_posts * 0.5:
        print("[PARTIAL] 部分完成（50%以上）")
    else:
        print("[FAIL] 完成率过低")

    print()

    # 显示帖子详情（前10个）
    if posts:
        print(f"[INFO] 获得的帖子列表（显示前10个）:")
        for i, post in enumerate(posts[:10], 1):
            age_hours = (time.time() - post.created_utc) / 3600
            print(f"  {i}. r/{post.cluster_id} - {post.title[:60]}...")
            print(f"     分数:{post.score} | 评论:{post.num_comments} | 年龄:{age_hours:.1f}小时")

    return posts


if __name__ == "__main__":
    asyncio.run(main())
