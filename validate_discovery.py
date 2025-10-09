#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""快速验证Module 2发现引擎"""

from src.discovery import ClusterBuilder, CredentialManager
from src.discovery.config import CredentialConfig

print("\n验证Module 2发现引擎组件...\n")

# 1. 簇构建器
builder = ClusterBuilder()
clusters = builder.get_all_clusters()
print(f"[OK] ClusterBuilder: {len(clusters)} 个Subreddit簇")

# 2. 凭据管理器
config = CredentialConfig()
manager = CredentialManager(config)
print(f"[OK] CredentialManager: {len(manager.credentials)} 个凭据")

# 3. 凭据轮换测试
cred1 = manager.get_credential()
cred2 = manager.get_credential()
print(f"[OK] 凭据轮换: {cred1.profile_id} -> {cred2.profile_id}")

print("\n所有核心组件正常工作！\n")
