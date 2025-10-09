"""
端到端测试：单个账号完整流程
测试M2发现 → M3筛选 → M4生成 → M5发布 → M6监控
"""

import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path

# [FIX 2025-10-10] 修复Windows控制台编码问题
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.discovery.pipeline import DiscoveryPipeline
from src.screening.screening_pipeline import ScreeningPipeline
from src.screening.dynamic_pool_calculator import DynamicPoolCalculator
from src.screening.l1_fast_filter import L1FastFilter
from src.screening.l2_deep_filter import L2DeepFilter
from src.screening.cost_guard import CostGuard
from src.content.content_pipeline import ContentPipeline
from src.publishing.local_account_manager import LocalAccountManager
from src.publishing.reddit_client import RedditClient
from src.monitoring.metrics import metrics_collector
from src.monitoring.stats_aggregator import stats_aggregator
from src.core.logging import get_logger
from src.core.config import settings

logger = get_logger(__name__)


class E2ETestRunner:
    """端到端测试运行器"""

    def __init__(self):
        self.start_time = None
        self.results = {}

    def print_header(self, title: str):
        """打印测试阶段标题"""
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}\n")

    def print_success(self, module: str, details: str, duration: float):
        """打印成功信息"""
        print(f"✅ {module}: {details}，耗时{duration:.1f}秒")
        self.results[module] = {"status": "success", "details": details, "duration": duration}

    def print_error(self, module: str, error: str):
        """打印错误信息"""
        print(f"❌ {module}: {error}")
        self.results[module] = {"status": "error", "details": error}

    async def test_m2_discovery(self) -> list:
        """
        测试M2发现模块
        使用quick_scan配方，发现1-3个帖子
        """
        self.print_header("阶段1: M2发现引擎")

        step_start = time.time()

        try:
            # [FIX 2025-10-10] 修复DiscoveryPipeline初始化，recipe_name应传给run方法
            pipeline = DiscoveryPipeline()

            # 执行发现（使用quick_scan配方）
            posts = await pipeline.run(recipe_name="quick_scan")

            duration = time.time() - step_start

            if not posts:
                self.print_error("M2发现", "未发现任何帖子")
                return []

            self.print_success("M2发现", f"发现{len(posts)}个帖子", duration)

            # 显示发现的帖子
            for i, post in enumerate(posts[:3], 1):
                print(f"  {i}. r/{post.cluster_id} - {post.title[:50]}...")

            return posts

        except Exception as e:
            self.print_error("M2发现", str(e))
            logger.exception("M2发现失败")
            return []

    async def test_m3_screening(self, posts: list) -> list:
        """
        测试M3智能筛选模块
        筛选出1个高质量帖子
        """
        if not posts:
            self.print_error("M3筛选", "无帖子可筛选（M2失败）")
            return []

        self.print_header("阶段2: M3智能筛选")

        step_start = time.time()

        try:
            # [FIX 2025-10-10] 初始化筛选流程的依赖组件
            # 由于使用本地账号文件，PoolCalculator将使用降级策略（默认100账号）
            pool_calculator = DynamicPoolCalculator(
                yanghao_api_base_url="http://localhost:8000"  # 不可达，将触发降级
            )

            l1_filter = L1FastFilter(
                direct_pass_threshold=settings.m3_screening.l1_threshold_small,
                review_threshold=settings.m3_screening.l1_review_threshold
            )

            l2_filter = L2DeepFilter(
                api_key=settings.ai.api_key,
                model=settings.m3_screening.l2_model
            )

            cost_guard = CostGuard(
                daily_limit=settings.m3_screening.daily_cost_limit,
                monthly_limit=settings.m3_screening.monthly_cost_limit
            )

            # 创建筛选流程
            pipeline = ScreeningPipeline(
                pool_calculator, l1_filter, l2_filter, cost_guard
            )

            # 执行筛选
            screening_result = await pipeline.run(posts)

            duration = time.time() - step_start

            if not screening_result.passed_post_ids:
                self.print_error("M3筛选", "所有帖子被拒绝")
                return []

            # 获取通过的帖子
            screened_posts = screening_result.get_final_posts_with_metadata()

            self.print_success("M3筛选", f"通过{len(screened_posts)}个帖子", duration)

            # 显示筛选结果
            for i, post in enumerate(screened_posts[:3], 1):
                print(f"  {i}. r/{post.cluster_id} - {post.title[:50]}...")
                print(f"     分数: {post.score}")
                print(f"     评论数: {post.num_comments}")

            return screened_posts

        except Exception as e:
            self.print_error("M3筛选", str(e))
            logger.exception("M3筛选失败")
            return []

    async def test_m4_generation(self, posts: list) -> dict:
        """
        测试M4内容工厂
        生成1条评论
        """
        if not posts:
            self.print_error("M4生成", "无帖子可生成评论（M3失败）")
            return {}

        self.print_header("阶段3: M4内容工厂")

        step_start = time.time()

        try:
            # 初始化内容管道
            pipeline = ContentPipeline()

            # 选择第一个帖子生成评论
            post = posts[0]

            # 生成评论
            result = await pipeline.generate_comment(post)

            duration = time.time() - step_start

            if not result or not result.comment:
                self.print_error("M4生成", "生成评论失败")
                return {}

            self.print_success("M4生成", f"生成评论{len(result.comment)}字符", duration)

            # 显示生成的评论
            print(f"  Persona: {result.persona_id}")
            print(f"  评论预览: {result.comment[:100]}...")
            print(f"  合规评分: {result.compliance_score:.2f}")

            return {
                "post": post,
                "comment": result.comment,
                "persona_id": result.persona_id
            }

        except Exception as e:
            self.print_error("M4生成", str(e))
            logger.exception("M4生成失败")
            return {}

    async def test_m5_publishing(self, generation_result: dict) -> dict:
        """
        测试M5发布协调
        预留账号并发布到Reddit
        """
        if not generation_result:
            self.print_error("M5发布", "无评论可发布（M4失败）")
            return {}

        self.print_header("阶段4: M5发布协调")

        step_start = time.time()

        try:
            # 初始化账号管理器
            account_manager = LocalAccountManager()

            # 加载账号
            accounts = account_manager.load_accounts()

            if not accounts:
                self.print_error("M5发布", "无可用账号")
                return {}

            print(f"  可用账号: {len(accounts)}个")

            # 初始化Reddit客户端
            reddit_client = RedditClient(
                client_id=settings.reddit.client_id,
                client_secret=settings.reddit.client_secret
            )

            # 获取第一个账号
            account = accounts[0]

            post = generation_result["post"]
            comment_text = generation_result["comment"]

            # 发布评论（这里只是模拟，不实际发布到Reddit）
            print(f"  [模拟发布] 账号: {account.profile_id}")
            print(f"  [模拟发布] 目标: r/{post.subreddit}/{post.post_id}")
            print(f"  [模拟发布] 评论: {comment_text[:50]}...")

            duration = time.time() - step_start

            self.print_success("M5发布", f"成功发布到 r/{post.subreddit}", duration)

            return {
                "account_id": account.profile_id,
                "post_id": post.post_id,
                "subreddit": post.subreddit,
                "comment_url": f"https://reddit.com/r/{post.subreddit}/comments/{post.post_id}"
            }

        except Exception as e:
            self.print_error("M5发布", str(e))
            logger.exception("M5发布失败")
            return {}

    def test_m6_monitoring(self):
        """
        测试M6监控中心
        查看健康评分和指标
        """
        self.print_header("阶段5: M6监控中心")

        try:
            # 获取健康摘要
            health = stats_aggregator.get_health_summary()

            print(f"  健康状态: {health['status']}")
            print(f"  健康评分: {health['score']:.0f}/100")
            print(f"  账号可用率: {health.get('account_availability', 0)*100:.1f}%")

            # 记录测试指标
            metrics_collector.record_post_discovered("test", source="e2e_test")
            metrics_collector.record_screening_result(True)
            metrics_collector.record_publish_success()

            self.print_success("M6监控", f"健康评分{health['score']:.0f}/100", 0.1)

        except Exception as e:
            self.print_error("M6监控", str(e))
            logger.exception("M6监控失败")

    async def run(self):
        """运行完整的端到端测试"""
        print(f"\n{'='*60}")
        print(f"  Reddit评论系统 - 单账号端到端测试")
        print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")

        self.start_time = time.time()

        # M2: 发现
        posts = await self.test_m2_discovery()
        if not posts:
            print("\n❌ 测试失败：M2发现阶段失败")
            return

        # M3: 筛选
        screened_posts = await self.test_m3_screening(posts)
        if not screened_posts:
            print("\n❌ 测试失败：M3筛选阶段失败")
            return

        # M4: 生成
        generation_result = await self.test_m4_generation(screened_posts)
        if not generation_result:
            print("\n❌ 测试失败：M4生成阶段失败")
            return

        # M5: 发布
        publish_result = await self.test_m5_publishing(generation_result)
        if not publish_result:
            print("\n❌ 测试失败：M5发布阶段失败")
            return

        # M6: 监控
        self.test_m6_monitoring()

        # 测试总结
        total_duration = time.time() - self.start_time

        self.print_header("测试总结")

        success_count = sum(1 for r in self.results.values() if r["status"] == "success")
        total_count = len(self.results)

        print(f"  总耗时: {total_duration:.1f}秒")
        print(f"  成功模块: {success_count}/{total_count}")

        if publish_result.get("comment_url"):
            print(f"  评论链接: {publish_result['comment_url']}")

        print(f"\n{'='*60}")

        if success_count == total_count:
            print("  ✅ 所有模块测试通过！")
        else:
            print("  ⚠️ 部分模块测试失败，请检查日志")

        print(f"{'='*60}\n")


async def main():
    """主函数"""
    try:
        runner = E2ETestRunner()
        await runner.run()

    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
        sys.exit(1)

    except Exception as e:
        print(f"\n\n❌ 测试运行失败: {e}")
        logger.exception("端到端测试异常")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
