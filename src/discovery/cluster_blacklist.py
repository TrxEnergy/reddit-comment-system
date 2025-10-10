"""
Subreddit簇黑名单管理器
管理无效簇的黑名单，支持TTL和自动过期
"""
import json
import os
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path

from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class BlacklistEntry:
    """黑名单条目"""
    subreddit: str
    reason: str  # private, banned, redirect, not_found等
    added_at: str  # ISO格式时间戳
    expires_at: str  # ISO格式时间戳
    retry_count: int = 0
    last_check: Optional[str] = None  # 最后一次检查时间


class ClusterBlacklist:
    """Subreddit簇黑名单管理器"""

    def __init__(self, filepath: str = "data/discovery/cluster_blacklist.json"):
        """
        初始化黑名单管理器

        Args:
            filepath: 黑名单JSON文件路径
        """
        self.filepath = filepath
        self.blacklist: Dict[str, BlacklistEntry] = {}
        self._ensure_data_dir()
        self.load()

    def _ensure_data_dir(self):
        """确保数据目录存在"""
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)

    def load(self):
        """从文件加载黑名单"""
        if not os.path.exists(self.filepath):
            logger.info(f"黑名单文件不存在，创建新文件: {self.filepath}")
            self.blacklist = {}
            self.save()
            return

        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 将JSON转换为BlacklistEntry对象
            self.blacklist = {}
            for entry_dict in data.get("blacklist", []):
                entry = BlacklistEntry(**entry_dict)
                self.blacklist[entry.subreddit] = entry

            logger.info(f"黑名单加载成功: {len(self.blacklist)}个条目")

        except Exception as e:
            logger.error(f"加载黑名单失败: {e}")
            self.blacklist = {}

    def save(self):
        """保存黑名单到文件"""
        try:
            data = {
                "blacklist": [asdict(entry) for entry in self.blacklist.values()],
                "updated_at": datetime.now().isoformat()
            }

            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"黑名单已保存: {len(self.blacklist)}个条目")

        except Exception as e:
            logger.error(f"保存黑名单失败: {e}")

    def add(
        self,
        subreddit: str,
        reason: str,
        ttl_days: int = 7
    ):
        """
        添加subreddit到黑名单

        Args:
            subreddit: subreddit名称
            reason: 原因（private, banned, redirect等）
            ttl_days: 过期时间（天数），默认7天后自动重试
        """
        now = datetime.now()
        expires_at = now + timedelta(days=ttl_days)

        # 如果已存在，更新retry_count
        if subreddit in self.blacklist:
            existing = self.blacklist[subreddit]
            existing.retry_count += 1
            existing.last_check = now.isoformat()
            existing.expires_at = expires_at.isoformat()
            logger.info(f"更新黑名单: r/{subreddit} (重试{existing.retry_count}次)")
        else:
            # 新增条目
            entry = BlacklistEntry(
                subreddit=subreddit,
                reason=reason,
                added_at=now.isoformat(),
                expires_at=expires_at.isoformat(),
                retry_count=0,
                last_check=now.isoformat()
            )
            self.blacklist[subreddit] = entry
            logger.info(f"添加到黑名单: r/{subreddit} ({reason})")

        self.save()

    def remove(self, subreddit: str):
        """
        从黑名单移除subreddit

        Args:
            subreddit: subreddit名称
        """
        if subreddit in self.blacklist:
            del self.blacklist[subreddit]
            logger.info(f"从黑名单移除: r/{subreddit}")
            self.save()

    def is_blacklisted(self, subreddit: str) -> bool:
        """
        检查subreddit是否在黑名单中（考虑TTL过期）

        Args:
            subreddit: subreddit名称

        Returns:
            bool: 是否在黑名单中
        """
        if subreddit not in self.blacklist:
            return False

        entry = self.blacklist[subreddit]

        # 检查是否过期
        try:
            expires_at = datetime.fromisoformat(entry.expires_at)
            if datetime.now() > expires_at:
                logger.info(f"黑名单条目已过期: r/{subreddit}，允许重试")
                return False
        except:
            logger.warning(f"黑名单条目时间格式错误: r/{subreddit}")
            return True  # 格式错误时保守处理，仍然黑名单

        return True

    def remove_expired(self) -> List[str]:
        """
        清理所有过期的黑名单条目

        Returns:
            List[str]: 被清理的subreddit列表
        """
        now = datetime.now()
        expired_subs = []

        for subreddit, entry in list(self.blacklist.items()):
            try:
                expires_at = datetime.fromisoformat(entry.expires_at)
                if now > expires_at:
                    expired_subs.append(subreddit)
                    del self.blacklist[subreddit]
            except Exception as e:
                logger.error(f"检查过期时间失败: r/{subreddit} - {e}")

        if expired_subs:
            logger.info(f"清理过期黑名单: {len(expired_subs)}个 - {expired_subs}")
            self.save()

        return expired_subs

    def get_all(self) -> List[BlacklistEntry]:
        """
        获取所有黑名单条目（包括过期的）

        Returns:
            List[BlacklistEntry]: 所有黑名单条目
        """
        return list(self.blacklist.values())

    def get_active(self) -> List[BlacklistEntry]:
        """
        获取所有有效的黑名单条目（未过期）

        Returns:
            List[BlacklistEntry]: 有效黑名单条目
        """
        now = datetime.now()
        active = []

        for entry in self.blacklist.values():
            try:
                expires_at = datetime.fromisoformat(entry.expires_at)
                if now <= expires_at:
                    active.append(entry)
            except:
                # 时间格式错误的条目也视为有效（保守处理）
                active.append(entry)

        return active

    def get_by_reason(self, reason: str) -> List[BlacklistEntry]:
        """
        按原因过滤黑名单条目

        Args:
            reason: 原因（private, banned等）

        Returns:
            List[BlacklistEntry]: 匹配的黑名单条目
        """
        return [entry for entry in self.blacklist.values() if entry.reason == reason]

    def get_report(self) -> str:
        """
        生成黑名单报告

        Returns:
            str: 格式化的报告文本
        """
        report_lines = [
            "="*60,
            "  Subreddit黑名单报告",
            "="*60,
            f"报告时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"总计: {len(self.blacklist)}个条目",
            ""
        ]

        # 统计各原因数量
        reasons = {}
        for entry in self.blacklist.values():
            reasons[entry.reason] = reasons.get(entry.reason, 0) + 1

        report_lines.append("按原因统计:")
        for reason, count in sorted(reasons.items()):
            report_lines.append(f"  {reason:15s}: {count:3d}")

        # 按原因分类显示详细信息
        report_lines.append("\n详细列表:")

        for reason in sorted(reasons.keys()):
            entries = self.get_by_reason(reason)
            report_lines.append(f"\n[{reason.upper()}] ({len(entries)}个):")

            for entry in entries:
                # 检查是否过期
                try:
                    expires_at = datetime.fromisoformat(entry.expires_at)
                    is_expired = datetime.now() > expires_at
                    status = "已过期" if is_expired else "有效"

                    # 计算剩余天数
                    if not is_expired:
                        days_left = (expires_at - datetime.now()).days
                        status = f"剩{days_left}天"

                    report_lines.append(
                        f"  r/{entry.subreddit:25s} - {status:8s} (重试{entry.retry_count}次)"
                    )
                except:
                    report_lines.append(
                        f"  r/{entry.subreddit:25s} - 时间错误 (重试{entry.retry_count}次)"
                    )

        report_lines.append("="*60)

        return "\n".join(report_lines)

    def clear_all(self):
        """清空整个黑名单（慎用！）"""
        self.blacklist = {}
        logger.warning("黑名单已清空")
        self.save()

    def batch_add(self, subreddits: List[str], reason: str, ttl_days: int = 7):
        """
        批量添加到黑名单

        Args:
            subreddits: subreddit名称列表
            reason: 原因
            ttl_days: 过期天数
        """
        for subreddit in subreddits:
            self.add(subreddit, reason, ttl_days)

    def import_from_health_check(self, health_results: Dict):
        """
        从健康检查结果导入黑名单

        Args:
            health_results: 健康检查结果字典（来自SubredditHealthChecker）
        """
        from .cluster_health_checker import HealthStatus

        # 需要加入黑名单的状态
        blacklist_statuses = [
            HealthStatus.PRIVATE,
            HealthStatus.BANNED,
            HealthStatus.REDIRECT,
            HealthStatus.NOT_FOUND
        ]

        count = 0
        for subreddit, result in health_results.items():
            if result.status in blacklist_statuses:
                self.add(subreddit, result.status.value, ttl_days=7)
                count += 1

        logger.info(f"从健康检查导入黑名单: {count}个条目")
