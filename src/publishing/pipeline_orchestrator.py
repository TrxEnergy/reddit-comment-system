"""
M5 Publishing - 发布管道编排器
负责协调账号、Top3评论获取、发布执行的完整流程
"""

import random
from typing import List, Optional
from datetime import datetime

from src.publishing.models import (
    PublishRequest,
    PublishResult,
    PublishState,
    PublishingStats,
    RedditAccount
)
from src.publishing.local_account_manager import LocalAccountManager
from src.publishing.token_refresher import TokenRefresher
from src.publishing.reddit_client import RedditClient
from src.publishing.top_comment_fetcher import TopCommentFetcher
from src.publishing.post_comment_limiter import PostCommentLimiter
from src.core.logging import get_logger

logger = get_logger(__name__)


class PipelineOrchestrator:
    """
    发布管道编排器
    核心策略：从Top3评论中随机选择，全部失败则跳过帖子
    """

    def __init__(
        self,
        account_manager: LocalAccountManager,
        token_refresher: TokenRefresher,
        reddit_client: RedditClient,
        top_comment_fetcher: TopCommentFetcher,
        post_limiter: PostCommentLimiter
    ):
        """
        初始化编排器

        Args:
            account_manager: 账号管理器
            token_refresher: Token刷新器
            reddit_client: Reddit客户端
            top_comment_fetcher: Top评论获取器
            post_limiter: 帖子限制器
        """
        self.account_manager = account_manager
        self.token_refresher = token_refresher
        self.reddit_client = reddit_client
        self.top_comment_fetcher = top_comment_fetcher
        self.post_limiter = post_limiter

        logger.info("PipelineOrchestrator初始化完成")

    async def publish_single(
        self,
        request: PublishRequest
    ) -> PublishResult:
        """
        发布单条评论（完整流程）

        流程：
        1. 检查PostLimiter（是否已评论或已尝试失败）
        2. 获取可用账号
        3. 获取Top3评论，随机打乱顺序
        4. 依次尝试回复Top3评论
        5. 全部失败则标记为attempted_failed

        Args:
            request: 发布请求

        Returns:
            发布结果
        """
        start_time = datetime.now()

        # 步骤1：获取账号
        account_id = request.account_profile_id

        if not account_id:
            # 自动分配账号
            available_accounts = self.account_manager.get_available_accounts()

            if not available_accounts:
                logger.error("无可用账号")
                return PublishResult(
                    comment_id=request.comment_id,
                    success=False,
                    state=PublishState.FAILED,
                    error_type="NO_AVAILABLE_ACCOUNTS",
                    error_message="无可用账号（已用尽配额或全部被锁定）",
                    latency_seconds=(datetime.now() - start_time).total_seconds()
                )

            account_id = random.choice(available_accounts)

        # 步骤2：检查PostLimiter
        if not self.post_limiter.can_comment_on_post(request.post_id, account_id):
            logger.info(
                "帖子已操作过，跳过",
                post_id=request.post_id,
                account_id=account_id
            )
            return PublishResult(
                comment_id=request.comment_id,
                success=False,
                state=PublishState.FAILED,
                error_type="POST_ALREADY_HANDLED",
                error_message="该帖子已发布评论或已尝试失败",
                latency_seconds=(datetime.now() - start_time).total_seconds()
            )

        # 步骤3：锁定账号
        task_id = f"publish_{request.comment_id}"

        if not self.account_manager.acquire_account(account_id, task_id):
            logger.error(
                "账号锁定失败",
                account_id=account_id,
                task_id=task_id
            )
            return PublishResult(
                comment_id=request.comment_id,
                success=False,
                state=PublishState.FAILED,
                error_type="ACCOUNT_LOCK_FAILED",
                error_message="账号锁定失败（可能已被其他任务使用）",
                latency_seconds=(datetime.now() - start_time).total_seconds()
            )

        try:
            # 步骤4：获取账号对象
            account = self.account_manager.get_account(account_id)

            if not account:
                logger.error(f"账号不存在: {account_id}")
                return PublishResult(
                    comment_id=request.comment_id,
                    success=False,
                    state=PublishState.FAILED,
                    error_type="ACCOUNT_NOT_FOUND",
                    error_message=f"账号不存在: {account_id}",
                    account_used=account_id,
                    latency_seconds=(datetime.now() - start_time).total_seconds()
                )

            # 步骤5：确保Token有效
            token_valid = await self.token_refresher.ensure_token_valid(
                account,
                self.account_manager
            )

            if not token_valid:
                logger.error(
                    "Token刷新失败",
                    account_id=account_id
                )
                return PublishResult(
                    comment_id=request.comment_id,
                    success=False,
                    state=PublishState.FAILED,
                    error_type="TOKEN_REFRESH_FAILED",
                    error_message="Token刷新失败，账号不可用",
                    account_used=account_id,
                    latency_seconds=(datetime.now() - start_time).total_seconds()
                )

            # 步骤6：获取Top3评论
            try:
                top_comments = self.top_comment_fetcher.get_top_comments(
                    post_id=request.post_id,
                    limit=3
                )

                if not top_comments:
                    logger.warning(
                        "帖子无可用评论",
                        post_id=request.post_id
                    )

                    # 标记为attempted_failed
                    self.post_limiter.mark_post_as_attempted(
                        post_id=request.post_id,
                        account_id=account_id,
                        failure_reason="no_comments_available"
                    )

                    return PublishResult(
                        comment_id=request.comment_id,
                        success=False,
                        state=PublishState.FAILED,
                        error_type="NO_COMMENTS_AVAILABLE",
                        error_message="帖子无可用评论",
                        account_used=account_id,
                        latency_seconds=(datetime.now() - start_time).total_seconds()
                    )

                logger.info(
                    "获取Top评论成功",
                    post_id=request.post_id,
                    top_comments_count=len(top_comments)
                )

            except Exception as e:
                logger.error(
                    "获取Top评论失败",
                    post_id=request.post_id,
                    error=str(e)
                )

                self.post_limiter.mark_post_as_attempted(
                    post_id=request.post_id,
                    account_id=account_id,
                    failure_reason="fetch_comments_error"
                )

                return PublishResult(
                    comment_id=request.comment_id,
                    success=False,
                    state=PublishState.FAILED,
                    error_type="FETCH_COMMENTS_ERROR",
                    error_message=f"获取Top评论失败: {str(e)}",
                    account_used=account_id,
                    latency_seconds=(datetime.now() - start_time).total_seconds()
                )

            # 步骤7：随机打乱Top3评论顺序，依次尝试
            random.shuffle(top_comments)

            last_error = None

            for comment_id in top_comments:
                # 验证评论可用性
                try:
                    if not self.top_comment_fetcher.validate_comment_available(comment_id):
                        logger.debug(
                            "评论不可回复，尝试下一个",
                            comment_id=comment_id
                        )
                        continue

                except Exception as e:
                    logger.warning(
                        "验证评论可用性失败",
                        comment_id=comment_id,
                        error=str(e)
                    )
                    continue

                # 尝试发布回复
                request.parent_comment_id = comment_id

                logger.info(
                    "尝试回复评论",
                    comment_id=comment_id,
                    post_id=request.post_id
                )

                result = await self.reddit_client.publish_comment(
                    account=account,
                    request=request
                )

                if result.success:
                    # 发布成功！
                    logger.info(
                        "评论发布成功",
                        comment_id=request.comment_id,
                        parent_comment_id=comment_id,
                        reddit_id=result.reddit_id,
                        permalink=result.permalink
                    )

                    # 记录到PostLimiter
                    self.post_limiter.record_comment(
                        post_id=request.post_id,
                        account_id=account_id
                    )

                    # 释放账号（成功）
                    self.account_manager.release_account(
                        profile_id=account_id,
                        success=True
                    )

                    result.latency_seconds = (datetime.now() - start_time).total_seconds()
                    result.account_used = account_id
                    return result

                else:
                    # 发布失败，记录错误并尝试下一个
                    last_error = result.error_message
                    logger.warning(
                        "回复评论失败，尝试下一个",
                        comment_id=comment_id,
                        error_type=result.error_type,
                        error_message=result.error_message
                    )

            # 步骤8：Top3全部失败，标记为attempted_failed
            logger.warning(
                "Top3评论全部回复失败",
                post_id=request.post_id,
                account_id=account_id
            )

            self.post_limiter.mark_post_as_attempted(
                post_id=request.post_id,
                account_id=account_id,
                failure_reason="all_top3_failed"
            )

            return PublishResult(
                comment_id=request.comment_id,
                success=False,
                state=PublishState.FAILED,
                error_type="ALL_TOP3_FAILED",
                error_message=f"Top3评论全部回复失败，最后错误: {last_error}",
                account_used=account_id,
                latency_seconds=(datetime.now() - start_time).total_seconds()
            )

        finally:
            # 确保账号释放（失败时）
            self.account_manager.release_account(
                profile_id=account_id,
                success=False,
                increment_quota=False
            )

    async def publish_batch(
        self,
        requests: List[PublishRequest],
        max_concurrent: int = 5
    ) -> PublishingStats:
        """
        批量发布评论

        Args:
            requests: 发布请求列表
            max_concurrent: 最大并发数

        Returns:
            发布统计
        """
        stats = PublishingStats()
        stats.total_requests = len(requests)

        logger.info(
            "开始批量发布",
            total_requests=len(requests),
            max_concurrent=max_concurrent
        )

        # 简化版：顺序发布（未来可使用asyncio.gather实现并发）
        for request in requests:
            result = await self.publish_single(request)

            if result.success:
                stats.successful_publishes += 1
            else:
                stats.failed_publishes += 1

                if result.error_type == "NO_AVAILABLE_ACCOUNTS":
                    stats.account_acquisition_failures += 1
                elif "PRAW_API" in result.error_type:
                    stats.reddit_api_failures += 1

            stats.total_latency_seconds += result.latency_seconds

        logger.info(
            "批量发布完成",
            total_requests=stats.total_requests,
            successful=stats.successful_publishes,
            failed=stats.failed_publishes,
            success_rate=f"{stats.success_rate * 100:.2f}%"
        )

        return stats
