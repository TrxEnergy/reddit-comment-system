"""
M5 Publishing - 调度运行器
负责定时调度和M2→M3→M4→M5流程集成
"""

import asyncio
from datetime import datetime, time
from typing import List, Optional
from pathlib import Path

from src.publishing.models import PublishRequest
from src.publishing.pipeline_orchestrator import PipelineOrchestrator
from src.publishing.random_scheduler import UniformRandomScheduler
from src.publishing.local_account_manager import LocalAccountManager
from src.publishing.token_refresher import TokenRefresher
from src.publishing.reddit_client import RedditClient
from src.publishing.top_comment_fetcher import TopCommentFetcher
from src.publishing.post_comment_limiter import PostCommentLimiter
from src.core.logging import get_logger

logger = get_logger(__name__)


class SchedulerRunner:
    """
    调度运行器
    负责：
    1. 每日生成随机调度表（6:00-02:00窗口）
    2. 定时检查待执行任务
    3. 从M4获取评论内容
    4. 调用编排器执行发布
    """

    def __init__(
        self,
        orchestrator: PipelineOrchestrator,
        scheduler: UniformRandomScheduler,
        account_manager: LocalAccountManager,
        check_interval_seconds: int = 60
    ):
        """
        初始化调度运行器

        Args:
            orchestrator: 发布编排器
            scheduler: 随机调度器
            account_manager: 账号管理器
            check_interval_seconds: 检查间隔（秒）
        """
        self.orchestrator = orchestrator
        self.scheduler = scheduler
        self.account_manager = account_manager
        self.check_interval_seconds = check_interval_seconds

        self.current_schedule = {}
        self.is_running = False

        logger.info(
            "SchedulerRunner初始化完成",
            check_interval_seconds=check_interval_seconds
        )

    async def start(self):
        """启动调度循环"""
        self.is_running = True

        logger.info("调度运行器启动")

        # 初始化：生成今日调度表
        await self._generate_daily_schedule()

        # 主循环
        while self.is_running:
            try:
                await self._check_and_execute_tasks()

                # 等待下一次检查
                await asyncio.sleep(self.check_interval_seconds)

            except KeyboardInterrupt:
                logger.info("收到中断信号，停止调度")
                break

            except Exception as e:
                logger.error(
                    "调度循环异常",
                    error=str(e),
                    error_type=type(e).__name__
                )
                await asyncio.sleep(self.check_interval_seconds)

    def stop(self):
        """停止调度循环"""
        self.is_running = False
        logger.info("调度运行器停止")

    async def _generate_daily_schedule(self):
        """生成今日调度表"""
        logger.info("生成今日调度表...")

        # 重新加载账号（获取最新状态）
        self.account_manager.load_accounts(force_reload=True)

        # 获取可用账号列表
        available_accounts = self.account_manager.get_available_accounts()

        if not available_accounts:
            logger.warning("无可用账号，调度表为空")
            self.current_schedule = {}
            return

        # 生成随机调度表
        self.current_schedule = self.scheduler.schedule_accounts(
            account_ids=available_accounts,
            base_date=datetime.now()
        )

        # 验证调度分布
        stats = self.scheduler.validate_schedule_distribution(self.current_schedule)

        logger.info(
            "调度表生成完成",
            total_accounts=len(available_accounts),
            uniformity_score=stats.get('uniformity_score'),
            hour_distribution=stats.get('hour_distribution')
        )

    async def _check_and_execute_tasks(self):
        """检查并执行到期任务"""
        now = datetime.now()

        # 检查是否需要重置每日配额（0点）
        if now.hour == 0 and now.minute < 2:
            logger.info("检测到日期变更，重置配额并重新生成调度表")
            self.account_manager.reset_daily_quota()
            await self._generate_daily_schedule()

        # 获取到期任务
        pending_accounts = self.scheduler.get_pending_tasks(
            schedule=self.current_schedule,
            now=now
        )

        if not pending_accounts:
            logger.debug("当前无到期任务")
            return

        logger.info(
            "检测到到期任务",
            pending_count=len(pending_accounts)
        )

        # 执行任务
        for account_id in pending_accounts:
            try:
                await self._execute_task_for_account(account_id)

                # 从调度表中移除（已执行）
                if account_id in self.current_schedule:
                    del self.current_schedule[account_id]

            except Exception as e:
                logger.error(
                    "任务执行失败",
                    account_id=account_id,
                    error=str(e)
                )

                # 重新调度（30分钟后重试）
                self.scheduler.reschedule_failed_account(
                    account_id=account_id,
                    current_schedule=self.current_schedule,
                    retry_after_minutes=30
                )

    async def _execute_task_for_account(self, account_id: str):
        """
        为指定账号执行发布任务

        流程：
        1. 从M4获取评论内容（模拟）
        2. 创建PublishRequest
        3. 调用编排器执行发布

        Args:
            account_id: 账号Profile ID
        """
        logger.info(
            "开始执行任务",
            account_id=account_id
        )

        # TODO: 集成M4（内容工厂）获取评论内容
        # 目前使用模拟数据

        # 模拟：从M4获取评论请求
        request = await self._fetch_comment_from_m4(account_id)

        if not request:
            logger.warning(
                "M4无可用评论内容",
                account_id=account_id
            )
            return

        # 调用编排器执行发布
        result = await self.orchestrator.publish_single(request)

        if result.success:
            logger.info(
                "任务执行成功",
                account_id=account_id,
                comment_id=result.comment_id,
                reddit_id=result.reddit_id,
                permalink=result.permalink
            )
        else:
            logger.error(
                "任务执行失败",
                account_id=account_id,
                comment_id=result.comment_id,
                error_type=result.error_type,
                error_message=result.error_message
            )

    async def _fetch_comment_from_m4(self, account_id: str) -> Optional[PublishRequest]:
        """
        从M4内容工厂获取评论内容（待集成）

        Args:
            account_id: 账号Profile ID

        Returns:
            PublishRequest或None
        """
        # TODO: 实现M4集成
        # 1. 从M2发现帖子
        # 2. 通过M3筛选
        # 3. 从M4生成评论
        # 4. 返回PublishRequest

        logger.warning(
            "M4集成待实现，使用模拟数据",
            account_id=account_id
        )

        # 模拟返回
        return None


async def create_scheduler_runner() -> SchedulerRunner:
    """
    工厂函数：创建完整配置的SchedulerRunner

    Returns:
        SchedulerRunner实例
    """
    # 初始化所有组件
    account_manager = LocalAccountManager()
    account_manager.load_accounts()

    token_refresher = TokenRefresher()

    reddit_client = RedditClient()

    top_comment_fetcher = TopCommentFetcher(
        client_id="dummy",  # TODO: 从配置读取
        client_secret="dummy",
        user_agent="CommentSystem/0.5.0"
    )

    post_limiter = PostCommentLimiter()

    orchestrator = PipelineOrchestrator(
        account_manager=account_manager,
        token_refresher=token_refresher,
        reddit_client=reddit_client,
        top_comment_fetcher=top_comment_fetcher,
        post_limiter=post_limiter
    )

    scheduler = UniformRandomScheduler()

    runner = SchedulerRunner(
        orchestrator=orchestrator,
        scheduler=scheduler,
        account_manager=account_manager,
        check_interval_seconds=60
    )

    return runner


async def main():
    """主入口（用于测试）"""
    logger.info("=== M5 Publishing Scheduler Runner ===")

    runner = await create_scheduler_runner()

    try:
        await runner.start()
    except KeyboardInterrupt:
        logger.info("收到中断信号")
        runner.stop()


if __name__ == "__main__":
    asyncio.run(main())
