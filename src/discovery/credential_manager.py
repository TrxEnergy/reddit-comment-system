import json
import time
from pathlib import Path
from typing import List, Optional, Dict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import random

from .config import CredentialConfig


@dataclass
class Credential:
    """Reddit API凭据"""

    profile_id: str
    client_id: str
    client_secret: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 86400
    scopes: str = "identity read submit"

    token_created_at: float = field(default_factory=time.time)
    request_count: int = 0
    last_used_at: float = 0.0
    cooldown_until: float = 0.0

    @property
    def is_expired(self) -> bool:
        """检查token是否过期"""
        return time.time() - self.token_created_at > self.expires_in

    @property
    def is_in_cooldown(self) -> bool:
        """检查是否在冷却期"""
        return time.time() < self.cooldown_until

    @property
    def is_usable(self) -> bool:
        """检查是否可用"""
        return not self.is_expired and not self.is_in_cooldown

    def mark_used(self):
        """标记使用"""
        self.request_count += 1
        self.last_used_at = time.time()

    def enter_cooldown(self, minutes: int):
        """进入冷却期"""
        self.cooldown_until = time.time() + (minutes * 60)

    def reset_request_count(self):
        """重置请求计数"""
        self.request_count = 0


class CredentialManager:
    """凭据管理器 - 3账号轮换系统"""

    def __init__(self, config: CredentialConfig):
        self.config = config
        self.credentials: List[Credential] = []
        self.current_index: int = 0
        self.stats: Dict[str, int] = defaultdict(int)

        self._load_credentials()

    def _load_credentials(self):
        """从JSONL文件加载凭据"""
        credential_file = Path(self.config.credential_file)

        if not credential_file.exists():
            raise FileNotFoundError(f"凭据文件不存在: {credential_file}")

        with open(credential_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    token_response = data.get("token_response", {})

                    credential = Credential(
                        profile_id=data["profile_id"],
                        client_id=data["client_id"],
                        client_secret=data["client_secret"],
                        access_token=token_response.get("access_token", ""),
                        refresh_token=token_response.get("refresh_token", ""),
                        token_type=token_response.get("token_type", "bearer"),
                        expires_in=token_response.get("expires_in", 86400),
                        scopes=data.get("scopes", "identity read submit"),
                        token_created_at=data.get("ts", time.time()),
                    )

                    self.credentials.append(credential)

        if not self.credentials:
            raise ValueError("未加载到任何凭据")

        print(f"已加载 {len(self.credentials)} 个凭据")

    def get_credential(self) -> Optional[Credential]:
        """获取下一个可用凭据（根据轮换策略）"""

        if self.config.rotation_strategy == "round_robin":
            return self._get_round_robin()
        elif self.config.rotation_strategy == "random":
            return self._get_random()
        elif self.config.rotation_strategy == "least_used":
            return self._get_least_used()
        else:
            return self._get_round_robin()

    def _get_round_robin(self) -> Optional[Credential]:
        """轮询策略"""
        attempts = 0
        total = len(self.credentials)

        while attempts < total:
            credential = self.credentials[self.current_index]
            self.current_index = (self.current_index + 1) % total

            if self._is_credential_available(credential):
                credential.mark_used()
                self.stats["total_requests"] += 1
                return credential

            attempts += 1

        return None

    def _get_random(self) -> Optional[Credential]:
        """随机策略"""
        available = [c for c in self.credentials if self._is_credential_available(c)]

        if not available:
            return None

        credential = random.choice(available)
        credential.mark_used()
        self.stats["total_requests"] += 1
        return credential

    def _get_least_used(self) -> Optional[Credential]:
        """最少使用策略"""
        available = [c for c in self.credentials if self._is_credential_available(c)]

        if not available:
            return None

        credential = min(available, key=lambda c: c.request_count)
        credential.mark_used()
        self.stats["total_requests"] += 1
        return credential

    def _is_credential_available(self, credential: Credential) -> bool:
        """检查凭据是否可用"""

        # [FIX 2025-10-10] 如果token过期，尝试自动刷新
        if credential.is_expired:
            if self.refresh_token(credential):
                # 刷新成功，继续检查其他条件
                pass
            else:
                # 刷新失败，凭据不可用
                return False

        # 检查冷却状态
        if credential.is_in_cooldown:
            return False

        # 检查请求计数，达到上限则进入冷却
        if credential.request_count >= self.config.max_requests_per_credential:
            credential.enter_cooldown(self.config.credential_cooldown_minutes)
            credential.reset_request_count()
            self.stats["cooldowns_triggered"] += 1
            return False

        return True

    def refresh_token(self, credential: Credential) -> bool:
        """刷新OAuth2 token"""

        if not self.config.enable_auto_refresh:
            return False

        # [FIX 2025-10-10] 实现真正的OAuth2 token刷新
        import requests

        try:
            print(f"[Token刷新] {credential.profile_id}")

            # Reddit OAuth2 token刷新端点
            token_url = "https://www.reddit.com/api/v1/access_token"

            # Basic Auth (client_id:client_secret)
            auth = requests.auth.HTTPBasicAuth(
                credential.client_id,
                credential.client_secret
            )

            # 刷新请求
            data = {
                "grant_type": "refresh_token",
                "refresh_token": credential.refresh_token
            }

            headers = {
                "User-Agent": f"python:discovery:v1.0 (by /u/{credential.profile_id})"
            }

            response = requests.post(
                token_url,
                auth=auth,
                data=data,
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                token_data = response.json()

                # 更新凭据
                credential.access_token = token_data["access_token"]
                credential.token_type = token_data.get("token_type", "bearer")
                credential.expires_in = token_data.get("expires_in", 86400)
                credential.token_created_at = time.time()

                # 注意: refresh_token通常不会更新，沿用原值
                print(f"[Token刷新成功] {credential.profile_id}")
                return True
            else:
                print(f"[Token刷新失败 {response.status_code}] {credential.profile_id}")
                print(f"   响应: {response.text[:200]}")
                return False

        except Exception as e:
            print(f"[Token刷新异常] {credential.profile_id} - {e}")
            return False

    def get_stats(self) -> Dict[str, any]:
        """获取统计信息"""
        return {
            "total_credentials": len(self.credentials),
            "total_requests": self.stats["total_requests"],
            "cooldowns_triggered": self.stats["cooldowns_triggered"],
            "credentials": [
                {
                    "profile_id": c.profile_id,
                    "request_count": c.request_count,
                    "is_usable": c.is_usable,
                    "is_in_cooldown": c.is_in_cooldown,
                    "last_used_at": datetime.fromtimestamp(c.last_used_at).isoformat()
                    if c.last_used_at > 0
                    else None,
                }
                for c in self.credentials
            ],
        }

    def reset_all(self):
        """重置所有凭据状态"""
        for credential in self.credentials:
            credential.reset_request_count()
            credential.cooldown_until = 0.0
        self.stats.clear()
        print("已重置所有凭据状态")
