import asyncio
import time
from typing import List, Dict, Optional, AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timedelta
import httpx

from .config import SearchChannelConfig, RateLimitConfig
from .credential_manager import CredentialManager, Credential
from .models import RawPost


@dataclass
class SearchResult:
    """搜索结果"""

    channel: str
    posts: List[RawPost]
    fetch_time: datetime
    api_calls: int
    errors: List[str]


class RateLimiter:
    """速率限制器"""

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.minute_requests: List[float] = []
        self.hour_requests: List[float] = []

    async def wait_if_needed(self):
        """如果超过速率限制则等待"""
        now = time.time()

        self.minute_requests = [t for t in self.minute_requests if now - t < 60]
        self.hour_requests = [t for t in self.hour_requests if now - t < 3600]

        if len(self.minute_requests) >= self.config.requests_per_minute:
            wait_time = 60 - (now - self.minute_requests[0])
            if wait_time > 0:
                print(f"速率限制：等待 {wait_time:.1f}s")
                await asyncio.sleep(wait_time)

        if len(self.hour_requests) >= self.config.requests_per_hour:
            wait_time = 3600 - (now - self.hour_requests[0])
            if wait_time > 0:
                print(f"速率限制（小时）：等待 {wait_time:.1f}s")
                await asyncio.sleep(wait_time)

        self.minute_requests.append(now)
        self.hour_requests.append(now)


class MultiChannelSearch:
    """多通道搜索系统"""

    def __init__(
        self,
        channels: List[SearchChannelConfig],
        credential_manager: CredentialManager,
        rate_limit_config: RateLimitConfig,
    ):
        self.channels = sorted(channels, key=lambda c: c.priority, reverse=True)
        self.credential_manager = credential_manager
        self.rate_limiter = RateLimiter(rate_limit_config)
        self.rate_limit_config = rate_limit_config

    async def search_all_channels(
        self, cluster_id: str, max_posts: int
    ) -> AsyncIterator[SearchResult]:
        """并发搜索所有通道"""

        tasks = []
        for channel in self.channels:
            if not channel.enabled:
                continue

            task = self._search_channel(channel, cluster_id, max_posts)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                print(f"通道搜索失败: {result}")
                continue
            yield result

    async def _search_channel(
        self, channel: SearchChannelConfig, cluster_id: str, max_posts: int
    ) -> SearchResult:
        """搜索单个通道"""

        print(f"搜索通道: {channel.channel_name} (优先级: {channel.priority})")

        posts = []
        api_calls = 0
        errors = []
        after = None

        async with httpx.AsyncClient(timeout=30.0) as client:
            while len(posts) < max_posts:
                credential = self.credential_manager.get_credential()
                if not credential:
                    error_msg = "无可用凭据"
                    errors.append(error_msg)
                    print(f"[错误] {error_msg}")
                    break

                await self.rate_limiter.wait_if_needed()

                url = self._build_url(channel, cluster_id, after)
                headers = self._build_headers(credential)

                try:
                    response = await client.get(url, headers=headers)
                    api_calls += 1

                    if response.status_code == 200:
                        data = response.json()
                        new_posts = self._parse_posts(data, cluster_id)
                        posts.extend(new_posts)

                        after = data.get("data", {}).get("after")
                        if not after or not new_posts:
                            break

                        print(
                            f"  {channel.channel_name}: 已获取 {len(posts)}/{max_posts} 帖子"
                        )

                    elif response.status_code == 429:
                        retry_after = int(response.headers.get("retry-after", 60))
                        error_msg = f"速率限制，等待 {retry_after}s"
                        errors.append(error_msg)
                        print(f"[速率限制] {error_msg}")
                        await asyncio.sleep(retry_after)

                    else:
                        error_msg = f"HTTP {response.status_code}: {response.text[:100]}"
                        errors.append(error_msg)
                        print(f"[错误] {error_msg}")
                        break

                except Exception as e:
                    error_msg = f"请求异常: {str(e)}"
                    errors.append(error_msg)
                    print(f"[异常] {error_msg}")

                    if api_calls < self.rate_limit_config.retry_attempts:
                        await asyncio.sleep(self.rate_limit_config.retry_backoff_seconds)
                    else:
                        break

        return SearchResult(
            channel=channel.channel_name,
            posts=posts,
            fetch_time=datetime.now(),
            api_calls=api_calls,
            errors=errors,
        )

    def _build_url(
        self, channel: SearchChannelConfig, cluster_id: str, after: Optional[str]
    ) -> str:
        """构建Reddit API URL"""

        base_url = f"https://oauth.reddit.com/r/{cluster_id}{channel.endpoint}.json"
        params = [f"limit={channel.limit}"]

        if channel.time_filter:
            params.append(f"t={channel.time_filter}")

        if after:
            params.append(f"after={after}")

        return f"{base_url}?{'&'.join(params)}"

    def _build_headers(self, credential: Credential) -> Dict[str, str]:
        """构建请求头"""
        return {
            "Authorization": f"{credential.token_type} {credential.access_token}",
            "User-Agent": f"python:reddit-discovery:v1.0 (by /u/{credential.profile_id})",
        }

    def _parse_posts(self, data: Dict, cluster_id: str) -> List[RawPost]:
        """解析Reddit API响应"""
        posts = []

        for child in data.get("data", {}).get("children", []):
            post_data = child.get("data", {})

            try:
                post = RawPost(
                    post_id=post_data["id"],
                    cluster_id=cluster_id,
                    title=post_data.get("title", ""),
                    author=post_data.get("author", "[deleted]"),
                    score=post_data.get("score", 0),
                    num_comments=post_data.get("num_comments", 0),
                    created_utc=post_data.get("created_utc", 0),
                    url=post_data.get("url", ""),
                    permalink=post_data.get("permalink", ""),
                    selftext=post_data.get("selftext", ""),
                    is_self=post_data.get("is_self", False),
                    over_18=post_data.get("over_18", False),
                    spoiler=post_data.get("spoiler", False),
                    stickied=post_data.get("stickied", False),
                    raw_json=post_data,
                )
                posts.append(post)

            except KeyError as e:
                print(f"解析帖子失败，缺少字段: {e}")
                continue

        return posts
