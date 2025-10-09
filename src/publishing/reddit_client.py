"""
M5 Publishing - Reddit发布客户端
负责实际发布评论到Reddit（支持顶级评论和回复评论）
"""

import praw
from typing import Optional, Tuple
from datetime import datetime

from src.publishing.models import RedditAccount, PublishRequest, PublishResult, PublishState
from src.core.logging import get_logger

logger = get_logger(__name__)


class RedditClient:
    """
    Reddit发布客户端（PRAW封装）
    M5策略：仅支持回复评论模式（不支持顶级评论）
    """

    USER_AGENT = "CommentSystem/0.5.0"

    def __init__(self):
        """初始化Reddit客户端"""
        pass

    def get_reddit_instance(self, account: RedditAccount) -> praw.Reddit:
        """
        为指定账号创建PRAW实例

        Args:
            account: 账号对象

        Returns:
            PRAW Reddit实例
        """
        return praw.Reddit(
            client_id=account.client_id,
            client_secret=account.client_secret,
            user_agent=self.USER_AGENT,
            access_token=account.access_token,
            refresh_token=account.refresh_token
        )

    async def publish_comment(
        self,
        account: RedditAccount,
        request: PublishRequest
    ) -> PublishResult:
        """
        发布评论（统一入口）
        M5策略要求必须回复评论，不支持顶级评论

        Args:
            account: 使用的账号
            request: 发布请求

        Returns:
            发布结果
        """
        start_time = datetime.now()

        try:
            # M5策略强制检查
            if not request.parent_comment_id:
                raise ValueError("M5策略要求必须回复评论（parent_comment_id不能为空）")

            reddit = self.get_reddit_instance(account)

            # 仅支持回复评论
            result = await self._publish_reply_to_comment(
                reddit=reddit,
                request=request
            )

            # 计算延迟
            latency = (datetime.now() - start_time).total_seconds()
            result.latency_seconds = latency
            result.account_used = account.profile_id
            result.published_at = datetime.now()

            return result

        except Exception as e:
            logger.error(
                "发布评论异常",
                comment_id=request.comment_id,
                error=str(e),
                error_type=type(e).__name__
            )

            return PublishResult(
                comment_id=request.comment_id,
                success=False,
                state=PublishState.FAILED,
                error_type=type(e).__name__,
                error_message=str(e),
                latency_seconds=(datetime.now() - start_time).total_seconds(),
                account_used=account.profile_id
            )

    async def _publish_top_level_comment(
        self,
        reddit: praw.Reddit,
        request: PublishRequest
    ) -> PublishResult:
        """
        发布顶级评论（直接回复帖子）

        Args:
            reddit: PRAW实例
            request: 发布请求

        Returns:
            发布结果
        """
        try:
            # 清理post_id（去除t3_前缀）
            post_id = request.post_id.replace("t3_", "")

            # 获取Submission对象
            submission = reddit.submission(id=post_id)

            # 发布评论
            comment = submission.reply(request.comment_text)

            logger.info(
                "顶级评论发布成功",
                comment_id=request.comment_id,
                post_id=request.post_id,
                reddit_id=comment.id,
                permalink=f"https://reddit.com{comment.permalink}"
            )

            return PublishResult(
                comment_id=request.comment_id,
                success=True,
                state=PublishState.SUCCESS,
                permalink=f"https://reddit.com{comment.permalink}",
                reddit_id=comment.id
            )

        except praw.exceptions.APIException as e:
            logger.error(
                "Reddit API错误（顶级评论）",
                comment_id=request.comment_id,
                error_type=e.error_type,
                message=e.message
            )

            return PublishResult(
                comment_id=request.comment_id,
                success=False,
                state=PublishState.FAILED,
                error_type=f"PRAW_API_{e.error_type}",
                error_message=e.message
            )

        except Exception as e:
            logger.error(
                "顶级评论发布失败",
                comment_id=request.comment_id,
                error=str(e)
            )

            return PublishResult(
                comment_id=request.comment_id,
                success=False,
                state=PublishState.FAILED,
                error_type=type(e).__name__,
                error_message=str(e)
            )

    async def _publish_reply_to_comment(
        self,
        reddit: praw.Reddit,
        request: PublishRequest
    ) -> PublishResult:
        """
        发布回复（回复评论）

        Args:
            reddit: PRAW实例
            request: 发布请求

        Returns:
            发布结果
        """
        try:
            # 清理comment_id（去除t1_前缀）
            parent_comment_id = request.parent_comment_id.replace("t1_", "")

            # 获取父评论对象
            parent_comment = reddit.comment(id=parent_comment_id)

            # 检查父评论是否可回复
            if parent_comment.locked or parent_comment.archived:
                logger.warning(
                    "父评论已锁定或归档",
                    comment_id=request.comment_id,
                    parent_comment_id=request.parent_comment_id,
                    locked=parent_comment.locked,
                    archived=parent_comment.archived
                )

                return PublishResult(
                    comment_id=request.comment_id,
                    success=False,
                    state=PublishState.FAILED,
                    error_type="COMMENT_NOT_REPLYABLE",
                    error_message="父评论已锁定或归档"
                )

            # 发布回复
            reply = parent_comment.reply(request.comment_text)

            logger.info(
                "回复评论发布成功",
                comment_id=request.comment_id,
                parent_comment_id=request.parent_comment_id,
                reddit_id=reply.id,
                permalink=f"https://reddit.com{reply.permalink}"
            )

            return PublishResult(
                comment_id=request.comment_id,
                success=True,
                state=PublishState.SUCCESS,
                permalink=f"https://reddit.com{reply.permalink}",
                reddit_id=reply.id
            )

        except praw.exceptions.APIException as e:
            logger.error(
                "Reddit API错误（回复评论）",
                comment_id=request.comment_id,
                parent_comment_id=request.parent_comment_id,
                error_type=e.error_type,
                message=e.message
            )

            return PublishResult(
                comment_id=request.comment_id,
                success=False,
                state=PublishState.FAILED,
                error_type=f"PRAW_API_{e.error_type}",
                error_message=e.message
            )

        except Exception as e:
            logger.error(
                "回复评论发布失败",
                comment_id=request.comment_id,
                parent_comment_id=request.parent_comment_id,
                error=str(e)
            )

            return PublishResult(
                comment_id=request.comment_id,
                success=False,
                state=PublishState.FAILED,
                error_type=type(e).__name__,
                error_message=str(e)
            )

    def test_connection(self, account: RedditAccount) -> Tuple[bool, Optional[str]]:
        """
        测试账号连接

        Args:
            account: 账号对象

        Returns:
            (是否成功, 用户名或错误信息)
        """
        try:
            reddit = self.get_reddit_instance(account)
            username = reddit.user.me().name

            logger.info(
                "Reddit连接测试成功",
                profile_id=account.profile_id,
                username=username
            )

            return True, username

        except Exception as e:
            logger.error(
                "Reddit连接测试失败",
                profile_id=account.profile_id,
                error=str(e)
            )

            return False, str(e)
