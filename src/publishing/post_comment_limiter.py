"""
M5 Publishing - 单帖子评论限制器
确保每个帖子只发布一条评论（避免spam检测）
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Set
from src.core.logging import get_logger

logger = get_logger(__name__)


class PostCommentLimiter:
    """
    单帖子评论限制器

    核心约束：
    1. 每个帖子只能有1条我们的评论
    2. 同一账号不能重复评论同一帖子
    3. 记录保存24小时后自动清理

    数据结构：
    {
        "post_id": {
            "status": "commented",  # 或 "attempted_failed"
            "account_ids": ["profile1", "profile2"],
            "first_comment_at": "2025-10-10T08:15:00",
            "comment_count": 1,
            "failure_reason": null  # attempted_failed时记录原因
        }
    }
    """

    def __init__(
        self,
        history_file: Path = None,
        ttl_hours: int = 24,
        auto_save: bool = True
    ):
        """
        初始化单帖子限制器

        Args:
            history_file: 历史记录文件路径（默认data/publishing/post_history.json）
            ttl_hours: 记录保存时长（小时）
            auto_save: 是否自动保存到文件
        """
        if history_file is None:
            history_file = Path("data/publishing/post_history.json")

        self.history_file = history_file
        self.ttl_hours = ttl_hours
        self.auto_save = auto_save

        # 内存数据结构
        self.post_comment_history: Dict[str, dict] = {}

        # 加载历史记录
        self._load_from_file()

        # 清理过期记录
        self._cleanup_old_records()

        logger.info(
            f"PostCommentLimiter initialized",
            history_file=str(self.history_file),
            ttl_hours=ttl_hours,
            current_posts=len(self.post_comment_history)
        )

    def can_comment_on_post(
        self,
        post_id: str,
        account_id: str
    ) -> bool:
        """
        检查是否可以在该帖子发布评论

        规则：
        1. 该帖子没有任何记录 → 可以
        2. 该帖子已成功发布评论 → 不可以
        3. 该帖子尝试但失败（Top3不可回复）→ 不可以
        4. 同一账号已评论该帖子 → 不可以（额外保护）

        Args:
            post_id: Reddit帖子ID
            account_id: 账号Profile ID

        Returns:
            是否可以评论
        """
        # 清理过期记录（每次检查时）
        self._cleanup_old_records()

        # 检查该帖子是否有记录
        if post_id not in self.post_comment_history:
            # 新帖子，可以评论
            return True

        post_record = self.post_comment_history[post_id]

        # 检查1：该帖子状态
        status = post_record.get('status', 'commented')

        if status == 'commented' and post_record.get('comment_count', 0) > 0:
            logger.debug(
                "帖子已有评论，跳过",
                post_id=post_id,
                comment_count=post_record['comment_count']
            )
            return False

        if status == 'attempted_failed':
            logger.debug(
                "帖子已尝试但失败，跳过",
                post_id=post_id,
                failure_reason=post_record.get('failure_reason')
            )
            return False

        # 检查2：同一账号是否已评论该帖子（额外保护）
        if account_id in post_record.get('account_ids', []):
            logger.debug(
                "账号已操作过该帖子，跳过",
                post_id=post_id,
                account_id=account_id
            )
            return False

        # 通过所有检查
        return True

    def record_comment(
        self,
        post_id: str,
        account_id: str
    ):
        """
        记录评论发布成功

        Args:
            post_id: Reddit帖子ID
            account_id: 账号Profile ID
        """
        now = datetime.now()

        # 初始化帖子记录
        if post_id not in self.post_comment_history:
            self.post_comment_history[post_id] = {
                'status': 'commented',
                'account_ids': [],
                'first_comment_at': now.isoformat(),
                'comment_count': 0,
                'failure_reason': None
            }

        # 更新记录
        post_record = self.post_comment_history[post_id]

        post_record['status'] = 'commented'

        if account_id not in post_record['account_ids']:
            post_record['account_ids'].append(account_id)

        post_record['comment_count'] += 1
        post_record['failure_reason'] = None

        logger.info(
            "记录评论成功",
            post_id=post_id,
            account_id=account_id,
            total_comments=post_record['comment_count']
        )

        # 自动保存
        if self.auto_save:
            self._save_to_file()

    def mark_post_as_attempted(
        self,
        post_id: str,
        account_id: str,
        failure_reason: str = "all_top3_unavailable"
    ):
        """
        标记帖子为"已尝试但失败"（Top3评论均不可回复）

        Args:
            post_id: Reddit帖子ID
            account_id: 尝试使用的账号
            failure_reason: 失败原因
        """
        now = datetime.now()

        self.post_comment_history[post_id] = {
            'status': 'attempted_failed',
            'account_ids': [account_id],
            'first_comment_at': now.isoformat(),
            'comment_count': 0,
            'failure_reason': failure_reason
        }

        logger.info(
            "标记帖子为已尝试但失败",
            post_id=post_id,
            account_id=account_id,
            failure_reason=failure_reason
        )

        # 自动保存
        if self.auto_save:
            self._save_to_file()

    def get_post_comment_count(self, post_id: str) -> int:
        """
        获取帖子的评论数（我们发布的）

        Args:
            post_id: Reddit帖子ID

        Returns:
            评论数
        """
        if post_id not in self.post_comment_history:
            return 0

        return self.post_comment_history[post_id]['comment_count']

    def get_commented_accounts(self, post_id: str) -> List[str]:
        """
        获取在该帖子评论过的账号列表

        Args:
            post_id: Reddit帖子ID

        Returns:
            账号Profile ID列表
        """
        if post_id not in self.post_comment_history:
            return []

        return self.post_comment_history[post_id]['account_ids'].copy()

    def _cleanup_old_records(self):
        """
        清理过期记录（超过TTL的记录）
        """
        now = datetime.now()
        cutoff_time = now - timedelta(hours=self.ttl_hours)

        expired_posts = []

        for post_id, record in self.post_comment_history.items():
            try:
                first_comment_at = datetime.fromisoformat(record['first_comment_at'])

                if first_comment_at < cutoff_time:
                    expired_posts.append(post_id)

            except (KeyError, ValueError) as e:
                logger.warning(
                    f"Invalid record format, removing",
                    post_id=post_id,
                    error=str(e)
                )
                expired_posts.append(post_id)

        # 删除过期记录
        for post_id in expired_posts:
            del self.post_comment_history[post_id]

        if expired_posts:
            logger.info(
                f"Cleaned up expired records",
                count=len(expired_posts),
                remaining=len(self.post_comment_history)
            )

            # 自动保存
            if self.auto_save:
                self._save_to_file()

    def _save_to_file(self):
        """保存历史记录到文件"""
        try:
            # 确保目录存在
            self.history_file.parent.mkdir(parents=True, exist_ok=True)

            # 写入JSON
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(
                    self.post_comment_history,
                    f,
                    indent=2,
                    ensure_ascii=False
                )

            logger.debug(
                f"Saved post history",
                file=str(self.history_file),
                posts=len(self.post_comment_history)
            )

        except Exception as e:
            logger.error(
                f"Failed to save post history",
                file=str(self.history_file),
                error=str(e)
            )

    def _load_from_file(self):
        """从文件加载历史记录"""
        if not self.history_file.exists():
            logger.info(
                f"No existing post history file, starting fresh",
                file=str(self.history_file)
            )
            return

        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                self.post_comment_history = json.load(f)

            logger.info(
                f"Loaded post history",
                file=str(self.history_file),
                posts=len(self.post_comment_history)
            )

        except Exception as e:
            logger.error(
                f"Failed to load post history, starting fresh",
                file=str(self.history_file),
                error=str(e)
            )
            self.post_comment_history = {}

    def reset_all(self):
        """重置所有记录（测试/调试用）"""
        self.post_comment_history = {}

        if self.auto_save:
            self._save_to_file()

        logger.warning("Reset all post comment history")

    def get_stats(self) -> dict:
        """
        获取统计信息

        Returns:
            统计字典
        """
        total_posts = len(self.post_comment_history)
        total_comments = sum(
            record['comment_count']
            for record in self.post_comment_history.values()
        )

        unique_accounts = set()
        for record in self.post_comment_history.values():
            unique_accounts.update(record['account_ids'])

        return {
            'total_posts_tracked': total_posts,
            'total_comments_published': total_comments,
            'unique_accounts_used': len(unique_accounts),
            'avg_comments_per_post': total_comments / total_posts if total_posts > 0 else 0,
            'ttl_hours': self.ttl_hours
        }
