"""
Subreddit健康检查器
检测subreddit的可访问性状态
"""
import asyncio
import httpx
from typing import List, Dict, Optional
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

from src.core.logging import get_logger

logger = get_logger(__name__)


class HealthStatus(Enum):
    """健康状态枚举"""
    ACTIVE = "active"              # 可正常访问
    PRIVATE = "private"            # 私密社区（需要邀请）
    BANNED = "banned"              # 被Reddit封禁
    REDIRECT = "redirect"          # 重定向（可能改名或合并）
    NOT_FOUND = "not_found"        # 不存在
    RATE_LIMITED = "rate_limited"  # 速率限制
    UNKNOWN = "unknown"            # 未知错误


@dataclass
class HealthCheckResult:
    """健康检查结果"""
    subreddit: str
    status: HealthStatus
    http_code: int
    reason: Optional[str] = None
    checked_at: Optional[datetime] = None
    subscribers: Optional[int] = None  # 订阅者数（仅active状态）
    active_users: Optional[int] = None  # 在线用户数


class SubredditHealthChecker:
    """Subreddit健康检查器"""

    def __init__(self, credential_manager=None):
        """
        初始化健康检查器

        Args:
            credential_manager: 凭据管理器（用于OAuth认证）
        """
        self.credential_manager = credential_manager
        self.concurrent_limit = 3  # 并发限制（避免速率限制）

    async def check_subreddit(
        self,
        subreddit_name: str,
        credential: Optional[object] = None
    ) -> HealthCheckResult:
        """
        检查单个subreddit的健康状态

        Args:
            subreddit_name: subreddit名称
            credential: OAuth凭据（可选，用于访问私密社区）

        Returns:
            HealthCheckResult: 健康检查结果
        """
        url = f"https://oauth.reddit.com/r/{subreddit_name}/about.json"

        headers = {
            "User-Agent": "python:discovery:v1.0"
        }

        # 如果提供了凭据，使用OAuth认证
        if credential:
            headers["Authorization"] = f"Bearer {credential.access_token}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers, follow_redirects=False)

                # 根据HTTP状态码判断健康状态
                if response.status_code == 200:
                    # 尝试解析订阅者数据
                    try:
                        data = response.json()
                        subreddit_data = data.get("data", {})
                        subscribers = subreddit_data.get("subscribers", 0)
                        active_users = subreddit_data.get("accounts_active", 0)

                        return HealthCheckResult(
                            subreddit=subreddit_name,
                            status=HealthStatus.ACTIVE,
                            http_code=200,
                            reason="OK",
                            checked_at=datetime.now(),
                            subscribers=subscribers,
                            active_users=active_users
                        )
                    except Exception as e:
                        logger.warning(f"解析{subreddit_name}数据失败: {e}")
                        return HealthCheckResult(
                            subreddit=subreddit_name,
                            status=HealthStatus.ACTIVE,
                            http_code=200,
                            reason="OK (no data)",
                            checked_at=datetime.now()
                        )

                elif response.status_code == 403:
                    # 私密社区
                    reason = self._parse_error_reason(response)
                    return HealthCheckResult(
                        subreddit=subreddit_name,
                        status=HealthStatus.PRIVATE,
                        http_code=403,
                        reason=reason or "Forbidden",
                        checked_at=datetime.now()
                    )

                elif response.status_code == 404:
                    # 被封禁或不存在
                    reason = self._parse_error_reason(response)
                    if reason == "banned":
                        status = HealthStatus.BANNED
                    else:
                        status = HealthStatus.NOT_FOUND

                    return HealthCheckResult(
                        subreddit=subreddit_name,
                        status=status,
                        http_code=404,
                        reason=reason or "Not Found",
                        checked_at=datetime.now()
                    )

                elif response.status_code in [301, 302, 307, 308]:
                    # 重定向
                    return HealthCheckResult(
                        subreddit=subreddit_name,
                        status=HealthStatus.REDIRECT,
                        http_code=response.status_code,
                        reason=f"Redirect to {response.headers.get('Location', 'unknown')}",
                        checked_at=datetime.now()
                    )

                elif response.status_code == 429:
                    # 速率限制
                    return HealthCheckResult(
                        subreddit=subreddit_name,
                        status=HealthStatus.RATE_LIMITED,
                        http_code=429,
                        reason="Rate limited",
                        checked_at=datetime.now()
                    )

                else:
                    # 其他未知错误
                    return HealthCheckResult(
                        subreddit=subreddit_name,
                        status=HealthStatus.UNKNOWN,
                        http_code=response.status_code,
                        reason=f"HTTP {response.status_code}",
                        checked_at=datetime.now()
                    )

        except httpx.TimeoutException:
            return HealthCheckResult(
                subreddit=subreddit_name,
                status=HealthStatus.UNKNOWN,
                http_code=0,
                reason="Timeout",
                checked_at=datetime.now()
            )

        except Exception as e:
            logger.error(f"检查{subreddit_name}失败: {e}")
            return HealthCheckResult(
                subreddit=subreddit_name,
                status=HealthStatus.UNKNOWN,
                http_code=0,
                reason=str(e),
                checked_at=datetime.now()
            )

    def _parse_error_reason(self, response: httpx.Response) -> Optional[str]:
        """
        从错误响应中解析reason字段

        Args:
            response: HTTP响应

        Returns:
            str: 错误原因（如"banned", "private"等）
        """
        try:
            data = response.json()
            return data.get("reason")
        except:
            return None

    async def batch_check(
        self,
        subreddits: List[str],
        use_auth: bool = True
    ) -> Dict[str, HealthCheckResult]:
        """
        批量检查多个subreddit的健康状态

        Args:
            subreddits: subreddit名称列表
            use_auth: 是否使用OAuth认证

        Returns:
            Dict[str, HealthCheckResult]: subreddit名称 -> 健康检查结果
        """
        results = {}

        # 获取凭据（如果需要）
        credential = None
        if use_auth and self.credential_manager:
            credential = self.credential_manager.get_credential()

        # 使用信号量限制并发数
        semaphore = asyncio.Semaphore(self.concurrent_limit)

        async def check_with_limit(subreddit: str):
            async with semaphore:
                result = await self.check_subreddit(subreddit, credential)
                # 添加小延迟避免速率限制
                await asyncio.sleep(0.5)
                return subreddit, result

        # 并发执行所有检查
        tasks = [check_with_limit(sub) for sub in subreddits]
        completed = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        for item in completed:
            if isinstance(item, Exception):
                logger.error(f"批量检查异常: {item}")
                continue

            subreddit, result = item
            results[subreddit] = result

        return results

    def generate_report(self, results: Dict[str, HealthCheckResult]) -> str:
        """
        生成可读的健康检查报告

        Args:
            results: 健康检查结果字典

        Returns:
            str: 格式化的报告文本
        """
        total = len(results)
        status_counts = {}

        # 统计各状态数量
        for result in results.values():
            status = result.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        # 生成报告
        report_lines = [
            "="*60,
            "  Subreddit健康检查报告",
            "="*60,
            f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"总计: {total}个subreddit",
            "",
            "状态统计:",
        ]

        # 添加状态统计
        for status, count in sorted(status_counts.items()):
            percentage = count / total * 100
            report_lines.append(f"  {status:15s}: {count:3d} ({percentage:5.1f}%)")

        report_lines.append("")
        report_lines.append("详细列表:")

        # 分类显示详细信息
        for status_filter in [HealthStatus.ACTIVE, HealthStatus.PRIVATE,
                              HealthStatus.BANNED, HealthStatus.REDIRECT,
                              HealthStatus.NOT_FOUND, HealthStatus.UNKNOWN]:
            filtered = [r for r in results.values() if r.status == status_filter]

            if not filtered:
                continue

            report_lines.append(f"\n[{status_filter.value.upper()}] ({len(filtered)}个):")

            for result in filtered:
                if result.status == HealthStatus.ACTIVE:
                    # Active状态显示订阅者数
                    subs = f"{result.subscribers:,}" if result.subscribers else "N/A"
                    report_lines.append(f"  r/{result.subreddit:25s} - {subs} 订阅者")
                else:
                    # 其他状态显示原因
                    report_lines.append(f"  r/{result.subreddit:25s} - {result.reason}")

        report_lines.append("="*60)

        return "\n".join(report_lines)

    async def check_and_report(self, subreddits: List[str]) -> str:
        """
        检查并生成报告（便捷方法）

        Args:
            subreddits: subreddit名称列表

        Returns:
            str: 格式化的报告
        """
        logger.info(f"开始批量健康检查 - {len(subreddits)}个subreddit")
        results = await self.batch_check(subreddits)
        report = self.generate_report(results)
        logger.info("健康检查完成")
        return report
