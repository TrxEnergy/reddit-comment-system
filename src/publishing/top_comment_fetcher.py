"""
M5 Publishing - 热门评论获取器
获取帖子下热度最高的前N个评论ID
"""

import praw
from typing import List, Optional
from src.core.logging import get_logger

logger = get_logger(__name__)


class TopCommentFetcher:
    """
    热门评论获取器

    职责：
    1. 从Reddit帖子中获取前N个热门评论
    2. 过滤已删除/被移除/置顶的评论
    3. 返回评论ID列表供发布模块使用
    """

    def __init__(self, reddit_instance: Optional[praw.Reddit] = None):
        """
        初始化热门评论获取器

        Args:
            reddit_instance: PRAW Reddit实例（可选，用于复用）
        """
        if reddit_instance:
            self.reddit = reddit_instance
        else:
            # 使用只读Reddit实例（无需用户认证）
            # 注意：这里需要配置只读应用的credentials
            from src.core.config import settings

            self.reddit = praw.Reddit(
                client_id=settings.reddit.client_id,
                client_secret=settings.reddit.client_secret,
                user_agent="TronCommentBot/1.0 (Readonly)"
            )

    def get_top_comments(
        self,
        post_id: str,
        limit: int = 3
    ) -> List[str]:
        """
        获取帖子的前N个热门评论ID

        策略：
        - 按热度（score）排序
        - 过滤置顶评论（stickied）
        - 过滤已删除评论（author=None）
        - 只返回顶级评论（不包括回复）

        Args:
            post_id: Reddit帖子ID（如t3_xxxxx或xxxxx）
            limit: 获取数量（默认3）

        Returns:
            评论ID列表（如 ["abc123", "def456", "ghi789"]）
            如果失败或无评论，返回空列表
        """
        try:
            # 1. 标准化post_id（移除t3_前缀）
            clean_post_id = post_id.replace('t3_', '')

            # 2. 获取帖子对象
            submission = self.reddit.submission(id=clean_post_id)

            logger.info(
                f"Fetching top comments from post",
                post_id=clean_post_id,
                post_title=submission.title[:50] + "...",
                num_comments=submission.num_comments
            )

            # 3. 检查帖子是否有评论
            if submission.num_comments == 0:
                logger.warning(f"Post {clean_post_id} has no comments")
                return []

            # 4. 展开评论（限制递归深度为0，只获取顶级评论）
            submission.comments.replace_more(limit=0)

            # 5. 提取符合条件的顶级评论
            top_comment_ids = []

            for comment in submission.comments:
                # 过滤条件
                if comment.stickied:
                    logger.debug(
                        f"Skipping stickied comment",
                        comment_id=comment.id
                    )
                    continue

                if comment.author is None:
                    logger.debug(
                        f"Skipping deleted/removed comment",
                        comment_id=comment.id
                    )
                    continue

                # 添加到结果
                top_comment_ids.append(comment.id)

                logger.debug(
                    f"Found top comment",
                    comment_id=comment.id,
                    score=comment.score,
                    author=comment.author.name,
                    body_preview=comment.body[:50] + "..."
                )

                # 达到数量限制
                if len(top_comment_ids) >= limit:
                    break

            logger.info(
                f"Successfully fetched {len(top_comment_ids)} top comments",
                post_id=clean_post_id,
                comment_ids=top_comment_ids
            )

            return top_comment_ids

        except praw.exceptions.NotFound:
            logger.error(
                f"Post not found",
                post_id=post_id
            )
            return []

        except Exception as e:
            logger.error(
                f"Failed to fetch top comments",
                post_id=post_id,
                error=str(e),
                error_type=type(e).__name__
            )
            return []

    def get_comment_info(self, comment_id: str) -> Optional[dict]:
        """
        获取评论详细信息（用于调试/日志）

        Args:
            comment_id: 评论ID

        Returns:
            评论信息字典，包含author、score、body等
            失败返回None
        """
        try:
            comment = self.reddit.comment(id=comment_id)

            return {
                'id': comment.id,
                'author': comment.author.name if comment.author else '[deleted]',
                'score': comment.score,
                'created_utc': comment.created_utc,
                'body': comment.body,
                'body_preview': comment.body[:100] + "..." if len(comment.body) > 100 else comment.body,
                'permalink': f"https://reddit.com{comment.permalink}"
            }

        except Exception as e:
            logger.error(
                f"Failed to get comment info",
                comment_id=comment_id,
                error=str(e)
            )
            return None

    def validate_comment_available(self, comment_id: str) -> bool:
        """
        验证评论是否可用于回复

        检查：
        - 评论是否存在
        - 评论是否被锁定（locked）
        - 评论是否已归档（archived）

        Args:
            comment_id: 评论ID

        Returns:
            是否可以回复该评论
        """
        try:
            comment = self.reddit.comment(id=comment_id)

            # 检查锁定状态
            if comment.locked:
                logger.warning(
                    f"Comment is locked",
                    comment_id=comment_id
                )
                return False

            # 检查归档状态
            if comment.archived:
                logger.warning(
                    f"Comment is archived",
                    comment_id=comment_id
                )
                return False

            # 检查是否已删除
            if comment.author is None:
                logger.warning(
                    f"Comment is deleted/removed",
                    comment_id=comment_id
                )
                return False

            return True

        except Exception as e:
            logger.error(
                f"Failed to validate comment",
                comment_id=comment_id,
                error=str(e)
            )
            return False
