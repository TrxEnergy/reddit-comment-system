"""
每周Subreddit簇健康检查任务
- 检查所有簇的健康状态
- 更新黑名单
- 寻找替代簇建议
- 生成详细报告
"""
import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.discovery.cluster_builder import ClusterBuilder
from src.discovery.cluster_health_checker import SubredditHealthChecker, HealthStatus
from src.discovery.cluster_blacklist import ClusterBlacklist
from src.discovery.alternative_cluster_finder import AlternativeClusterFinder
from src.discovery.credential_manager import CredentialManager
from src.discovery.config import CredentialConfig


async def main():
    """执行每周健康检查和维护"""
    print("="*70)
    print("  每周Subreddit簇健康检查")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    print()

    # 初始化
    builder = ClusterBuilder()
    all_clusters = builder.get_all_clusters()
    subreddit_names = [c.subreddit_name for c in all_clusters]

    cred_config = CredentialConfig()
    cred_manager = CredentialManager(cred_config)

    # 阶段1: 健康检查
    print("阶段1: 批量健康检查")
    print(f"  检查{len(subreddit_names)}个簇...")
    print()

    checker = SubredditHealthChecker(cred_manager)
    results = await checker.batch_check(subreddit_names, use_auth=True)

    report = checker.generate_report(results)
    print(report)
    print()

    # 阶段2: 更新黑名单
    print("阶段2: 更新黑名单")
    print()

    blacklist = ClusterBlacklist()

    # 先清理过期条目
    expired = blacklist.remove_expired()
    if expired:
        print(f"  清理过期黑名单: {len(expired)}个")

    # 导入新的无效簇
    blacklist.import_from_health_check(results)

    blacklist_report = blacklist.get_report()
    print(blacklist_report)
    print()

    # 阶段3: 寻找替代簇建议
    print("阶段3: 寻找替代簇建议")
    print()

    finder = AlternativeClusterFinder(cred_manager)

    # 统计哪些类别缺失簇
    invalid_categories = {}
    for cluster in all_clusters:
        result = results.get(cluster.subreddit_name)
        if result and result.status != HealthStatus.ACTIVE:
            category = cluster.category
            invalid_categories[category] = invalid_categories.get(category, 0) + 1

    if invalid_categories:
        print(f"  发现{len(invalid_categories)}个类别有无效簇:")
        for category, count in invalid_categories.items():
            print(f"    - {category}: {count}个无效")
        print()

        # 为每个受影响类别寻找替代
        suggestions = {}
        for category in invalid_categories.keys():
            print(f"  搜索'{category}'的替代簇...")
            category_suggestions = await finder.get_replacement_suggestions(
                category,
                limit=3,
                use_search=False  # 只使用备用池，避免API限流
            )
            suggestions[category] = category_suggestions

        # 保存建议到文件
        suggestions_file = Path("data/discovery/cluster_suggestions.json")
        suggestions_file.parent.mkdir(parents=True, exist_ok=True)

        suggestions_data = {
            "generated_at": datetime.now().isoformat(),
            "suggestions": {
                category: [
                    {
                        "name": c.subreddit_name,
                        "category": c.category,
                        "description": c.description
                    }
                    for c in clusters
                ]
                for category, clusters in suggestions.items()
            }
        }

        with open(suggestions_file, 'w', encoding='utf-8') as f:
            json.dump(suggestions_data, f, ensure_ascii=False, indent=2)

        print()
        print(f"  替代簇建议已保存: {suggestions_file}")
        print()

        # 显示建议摘要
        for category, clusters in suggestions.items():
            if clusters:
                print(f"  {category} 建议:")
                for cluster in clusters:
                    print(f"    + r/{cluster.subreddit_name} - {cluster.description}")
    else:
        print("  所有类别的簇都健康，无需寻找替代")

    print()

    # 阶段4: 生成总结报告
    print("="*70)
    print("  健康检查总结")
    print("="*70)

    active_count = sum(1 for r in results.values() if r.status == HealthStatus.ACTIVE)
    invalid_count = len(results) - active_count
    blacklisted_count = len(blacklist.get_active())

    print(f"✓ 可用簇: {active_count}/{len(results)} ({active_count/len(results)*100:.1f}%)")
    print(f"✗ 无效簇: {invalid_count}个")
    print(f"⏰ 黑名单: {blacklisted_count}个（含过期）")

    if suggestions:
        total_suggestions = sum(len(s) for s in suggestions.values())
        print(f"💡 替代建议: {total_suggestions}个")

    print()
    print("下次检查时间: 7天后")
    print()


if __name__ == "__main__":
    asyncio.run(main())
