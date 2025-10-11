"""
立即检测并修复无效的Subreddit簇
- 执行健康检查
- 生成黑名单
- 显示报告
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.discovery.cluster_builder import ClusterBuilder
from src.discovery.cluster_health_checker import SubredditHealthChecker
from src.discovery.cluster_blacklist import ClusterBlacklist
from src.discovery.credential_manager import CredentialManager
from src.discovery.config import CredentialConfig


async def main():
    """立即检测并修复无效簇"""
    print("="*70)
    print("  立即修复无效Subreddit簇")
    print("="*70)
    print()

    # 1. 加载所有簇
    builder = ClusterBuilder()
    all_clusters = builder.get_all_clusters()
    subreddit_names = [c.subreddit_name for c in all_clusters]

    print(f"步骤1: 加载簇配置")
    print(f"  总计: {len(subreddit_names)}个簇")
    print()

    # 2. 初始化凭据管理器（用于健康检查）
    cred_config = CredentialConfig()
    cred_manager = CredentialManager(cred_config)

    # 3. 执行健康检查
    print(f"步骤2: 执行健康检查（这可能需要1-2分钟）...")
    print()

    checker = SubredditHealthChecker(cred_manager)
    results = await checker.batch_check(subreddit_names, use_auth=True)

    # 显示健康检查报告
    report = checker.generate_report(results)
    print(report)
    print()

    # 4. 更新黑名单
    print(f"步骤3: 更新黑名单")
    print()

    blacklist = ClusterBlacklist()
    blacklist.import_from_health_check(results)

    # 显示黑名单报告
    blacklist_report = blacklist.get_report()
    print(blacklist_report)
    print()

    # 5. 统计结果
    from src.discovery.cluster_health_checker import HealthStatus

    active_count = sum(1 for r in results.values() if r.status == HealthStatus.ACTIVE)
    invalid_count = len(results) - active_count

    print("="*70)
    print("  修复完成")
    print("="*70)
    print(f"[OK] 可用簇: {active_count}个")
    print(f"[FAIL] 无效簇: {invalid_count}个（已加入黑名单）")
    print(f"[SAVE] 黑名单文件: data/discovery/cluster_blacklist.json")
    print()
    print("建议: 现在可以运行10账号测试验证效果")
    print("  python test_10_accounts_simple.py")
    print()


if __name__ == "__main__":
    asyncio.run(main())
