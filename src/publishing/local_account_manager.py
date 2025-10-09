"""
M5 Publishing - 本地账号池管理器
负责从tokens.jsonl加载账号，管理锁定和配额
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from threading import Lock
from collections import defaultdict

from src.publishing.models import RedditAccount
from src.core.logging import get_logger

logger = get_logger(__name__)


class LocalAccountManager:
    """
    本地账号池管理器
    从硬编码路径加载tokens.jsonl，提供账号锁定和配额管理
    """

    ACCOUNTS_FILE = r"C:\Users\beima\Desktop\BaiduSyncdisk\Trx相关\reddit账号\tokens.jsonl"

    def __init__(self):
        """初始化账号管理器"""
        self._accounts: Dict[str, RedditAccount] = {}
        self._lock = Lock()
        self._last_load_time: Optional[datetime] = None
        self._daily_comment_counts: Dict[str, int] = defaultdict(int)
        self._last_comment_times: Dict[str, datetime] = {}
        self._quota_reset_date: Optional[datetime] = None

    def load_accounts(self, force_reload: bool = False) -> List[RedditAccount]:
        """
        从JSONL文件加载所有账号

        Args:
            force_reload: 强制重新加载（忽略缓存）

        Returns:
            账号列表

        Raises:
            FileNotFoundError: 账号文件不存在
            json.JSONDecodeError: 文件格式错误
        """
        accounts_path = Path(self.ACCOUNTS_FILE)

        if not accounts_path.exists():
            raise FileNotFoundError(f"账号文件不存在: {self.ACCOUNTS_FILE}")

        # 如果5分钟内加载过，且非强制重新加载，则返回缓存
        if not force_reload and self._last_load_time:
            if datetime.now() - self._last_load_time < timedelta(minutes=5):
                logger.debug("使用缓存的账号列表")
                return list(self._accounts.values())

        with self._lock:
            loaded_accounts = []

            with open(accounts_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                        account = self._parse_account_data(data)
                        loaded_accounts.append(account)

                    except json.JSONDecodeError as e:
                        logger.error(f"解析账号数据失败（行{line_num}）: {e}")
                        continue
                    except Exception as e:
                        logger.error(f"处理账号数据失败（行{line_num}）: {e}")
                        continue

            # 更新内存账号池
            self._accounts = {acc.profile_id: acc for acc in loaded_accounts}
            self._last_load_time = datetime.now()

            logger.info(
                "账号加载完成",
                total=len(loaded_accounts),
                file=self.ACCOUNTS_FILE
            )

            return loaded_accounts

    def _parse_account_data(self, data: dict) -> RedditAccount:
        """
        解析JSONL中的账号数据

        Args:
            data: JSONL中的一行数据

        Returns:
            RedditAccount对象
        """
        token_response = data.get("token_response", {})

        # 计算Token过期时间（ts + expires_in）
        ts = data.get("ts", 0)
        expires_in = token_response.get("expires_in", 3600)
        token_expires_at = datetime.fromtimestamp(ts + expires_in)

        profile_id = data.get("profile_id")

        # 恢复运行时状态
        daily_count = self._daily_comment_counts.get(profile_id, 0)
        last_comment = self._last_comment_times.get(profile_id)

        return RedditAccount(
            profile_id=profile_id,
            client_id=data.get("client_id"),
            client_secret=data.get("client_secret"),
            access_token=token_response.get("access_token"),
            refresh_token=token_response.get("refresh_token"),
            token_expires_at=token_expires_at,
            daily_comment_count=daily_count,
            last_comment_at=last_comment
        )

    def get_account(self, profile_id: str) -> Optional[RedditAccount]:
        """
        获取指定账号

        Args:
            profile_id: Profile ID

        Returns:
            账号对象，不存在返回None
        """
        return self._accounts.get(profile_id)

    def get_available_accounts(self) -> List[str]:
        """
        获取可用账号列表（未锁定 + 有配额 + Token未过期）

        Returns:
            可用账号的Profile ID列表
        """
        self._check_and_reset_daily_quota()

        available = []

        for profile_id, account in self._accounts.items():
            if (
                not account.is_locked
                and account.can_publish_today
                and not account.is_token_expired
            ):
                available.append(profile_id)

        logger.debug(
            "可用账号统计",
            total_accounts=len(self._accounts),
            available_accounts=len(available)
        )

        return available

    def acquire_account(self, profile_id: str, task_id: str) -> bool:
        """
        锁定账号（原子操作）

        Args:
            profile_id: Profile ID
            task_id: 任务ID

        Returns:
            是否成功锁定
        """
        with self._lock:
            account = self._accounts.get(profile_id)

            if not account:
                logger.warning(f"账号不存在: {profile_id}")
                return False

            if account.is_locked:
                logger.warning(
                    f"账号已被锁定: {profile_id}",
                    locked_by=account.locked_by
                )
                return False

            if not account.can_publish_today:
                logger.warning(f"账号配额已用完: {profile_id}")
                return False

            if account.is_token_expired:
                logger.warning(f"账号Token已过期: {profile_id}")
                return False

            # 锁定账号
            account.is_locked = True
            account.locked_at = datetime.now()
            account.locked_by = task_id

            logger.info(
                "账号已锁定",
                profile_id=profile_id,
                task_id=task_id
            )

            return True

    def release_account(
        self,
        profile_id: str,
        success: bool,
        increment_quota: bool = True
    ) -> bool:
        """
        释放账号并更新配额

        Args:
            profile_id: Profile ID
            success: 任务是否成功
            increment_quota: 是否增加配额计数（默认True）

        Returns:
            是否成功释放
        """
        with self._lock:
            account = self._accounts.get(profile_id)

            if not account:
                logger.warning(f"账号不存在: {profile_id}")
                return False

            # 释放锁
            account.is_locked = False
            locked_by = account.locked_by
            account.locked_at = None
            account.locked_by = None

            # 如果成功发布，更新配额
            if success and increment_quota:
                account.daily_comment_count += 1
                account.last_comment_at = datetime.now()

                # 同步到内存字典（持久化状态）
                self._daily_comment_counts[profile_id] = account.daily_comment_count
                self._last_comment_times[profile_id] = account.last_comment_at

                logger.info(
                    "账号已释放（发布成功）",
                    profile_id=profile_id,
                    task_id=locked_by,
                    daily_count=account.daily_comment_count
                )
            else:
                logger.info(
                    "账号已释放（未发布）",
                    profile_id=profile_id,
                    task_id=locked_by,
                    success=success
                )

            return True

    def update_tokens(
        self,
        profile_id: str,
        access_token: str,
        expires_at: datetime
    ) -> bool:
        """
        更新账号的Token（刷新后调用）
        注意：不写回文件，只更新内存

        Args:
            profile_id: Profile ID
            access_token: 新的Access Token
            expires_at: 新的过期时间

        Returns:
            是否成功更新
        """
        with self._lock:
            account = self._accounts.get(profile_id)

            if not account:
                logger.warning(f"账号不存在: {profile_id}")
                return False

            account.access_token = access_token
            account.token_expires_at = expires_at

            logger.info(
                "Token已更新",
                profile_id=profile_id,
                expires_at=expires_at.isoformat()
            )

            return True

    def reset_daily_quota(self):
        """重置所有账号的每日配额（每天0点调用）"""
        with self._lock:
            for account in self._accounts.values():
                account.daily_comment_count = 0
                account.last_comment_at = None

            # 清空内存字典
            self._daily_comment_counts.clear()
            self._last_comment_times.clear()
            self._quota_reset_date = datetime.now().date()

            logger.info("每日配额已重置", total_accounts=len(self._accounts))

    def _check_and_reset_daily_quota(self):
        """检查是否需要重置每日配额"""
        today = datetime.now().date()

        if self._quota_reset_date is None:
            self._quota_reset_date = today
            return

        if today > self._quota_reset_date:
            logger.info("检测到日期变更，重置配额")
            self.reset_daily_quota()

    def get_account_stats(self) -> dict:
        """
        获取账号池统计信息

        Returns:
            统计字典
        """
        self._check_and_reset_daily_quota()

        total = len(self._accounts)
        locked = sum(1 for acc in self._accounts.values() if acc.is_locked)
        no_quota = sum(1 for acc in self._accounts.values() if not acc.can_publish_today)
        expired = sum(1 for acc in self._accounts.values() if acc.is_token_expired)
        available = len(self.get_available_accounts())

        return {
            "total_accounts": total,
            "locked_accounts": locked,
            "no_quota_accounts": no_quota,
            "expired_token_accounts": expired,
            "available_accounts": available,
            "last_load_time": self._last_load_time.isoformat() if self._last_load_time else None,
            "quota_reset_date": self._quota_reset_date.isoformat() if self._quota_reset_date else None
        }

    def force_unlock_all(self):
        """强制解锁所有账号（调试用）"""
        with self._lock:
            unlocked_count = 0

            for account in self._accounts.values():
                if account.is_locked:
                    account.is_locked = False
                    account.locked_at = None
                    account.locked_by = None
                    unlocked_count += 1

            logger.warning(f"强制解锁所有账号: {unlocked_count}个")
