"""
M5 Publishing - Token刷新器
负责使用refresh_token换取新的access_token
"""

import httpx
from datetime import datetime, timedelta
from typing import Optional, Tuple

from src.publishing.models import RedditAccount
from src.core.logging import get_logger

logger = get_logger(__name__)


class TokenRefresher:
    """
    Reddit OAuth2 Token刷新器
    使用refresh_token换取新的access_token
    """

    REDDIT_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
    USER_AGENT = "CommentSystem/0.5.0"
    DEFAULT_TIMEOUT = 10.0

    def __init__(self, timeout: float = DEFAULT_TIMEOUT):
        """
        初始化Token刷新器

        Args:
            timeout: HTTP请求超时（秒）
        """
        self.timeout = timeout

    async def refresh_token(
        self,
        account: RedditAccount
    ) -> Tuple[bool, Optional[str], Optional[datetime]]:
        """
        刷新指定账号的Access Token

        Args:
            account: 账号对象

        Returns:
            (是否成功, 新access_token, 新过期时间)
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.REDDIT_TOKEN_URL,
                    auth=(account.client_id, account.client_secret),
                    headers={"User-Agent": self.USER_AGENT},
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": account.refresh_token
                    }
                )

                if response.status_code != 200:
                    logger.error(
                        "Token刷新失败",
                        profile_id=account.profile_id,
                        status_code=response.status_code,
                        response=response.text
                    )
                    return False, None, None

                data = response.json()

                new_access_token = data.get("access_token")
                expires_in = data.get("expires_in", 3600)

                if not new_access_token:
                    logger.error(
                        "Token刷新响应无效",
                        profile_id=account.profile_id,
                        data=data
                    )
                    return False, None, None

                # 计算新的过期时间（提前5分钟）
                new_expires_at = datetime.now() + timedelta(seconds=expires_in - 300)

                logger.info(
                    "Token刷新成功",
                    profile_id=account.profile_id,
                    expires_at=new_expires_at.isoformat()
                )

                return True, new_access_token, new_expires_at

        except httpx.TimeoutException:
            logger.error(
                "Token刷新超时",
                profile_id=account.profile_id,
                timeout=self.timeout
            )
            return False, None, None

        except httpx.HTTPError as e:
            logger.error(
                "Token刷新HTTP错误",
                profile_id=account.profile_id,
                error=str(e)
            )
            return False, None, None

        except Exception as e:
            logger.error(
                "Token刷新未知错误",
                profile_id=account.profile_id,
                error=str(e)
            )
            return False, None, None

    async def ensure_token_valid(
        self,
        account: RedditAccount,
        account_manager
    ) -> bool:
        """
        确保Token有效（如果过期则自动刷新）

        Args:
            account: 账号对象
            account_manager: 账号管理器（用于更新Token）

        Returns:
            Token是否有效
        """
        # 如果Token还有30分钟以上有效期，不刷新
        if not account.is_token_expired:
            time_until_expiry = account.token_expires_at - datetime.now()
            if time_until_expiry > timedelta(minutes=30):
                logger.debug(
                    "Token仍然有效",
                    profile_id=account.profile_id,
                    remaining_minutes=time_until_expiry.total_seconds() / 60
                )
                return True

        # Token即将过期或已过期，执行刷新
        logger.info(
            "Token即将过期，执行刷新",
            profile_id=account.profile_id,
            expires_at=account.token_expires_at.isoformat()
        )

        success, new_token, new_expires = await self.refresh_token(account)

        if not success:
            logger.error(
                "Token刷新失败，账号不可用",
                profile_id=account.profile_id
            )
            return False

        # 更新账号管理器中的Token
        account_manager.update_tokens(
            profile_id=account.profile_id,
            access_token=new_token,
            expires_at=new_expires
        )

        return True
