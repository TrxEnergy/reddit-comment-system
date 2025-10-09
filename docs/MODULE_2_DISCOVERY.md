# Module 2: 发现引擎完整文档

## 概述

Module 2 发现引擎是Reddit评论自动化系统的第二阶段，负责从30个预定义的Subreddit簇中高效发现和收集符合条件的帖子。

**功能特性**:
- ✅ 30个内置Subreddit簇（5大类别）
- ✅ 3账号轮换系统（爬虫账号）
- ✅ 5通道并发搜索（hot/top/rising/new）
- ✅ 预算管理系统（帖子数/API调用/运行时间）
- ✅ 质量控制和去重
- ✅ 产能配方执行器（quick/standard/deep）

---

## 架构设计

```
DiscoveryPipeline (核心管道)
  │
  ├─ ClusterBuilder (簇构建器)
  │   └─ 30个内置Subreddit簇
  │
  ├─ CapacityExecutor (产能执行器)
  │   │
  │   ├─ CredentialManager (凭据管理)
  │   │   └─ 3账号轮换
  │   │
  │   ├─ MultiChannelSearch (多通道搜索)
  │   │   ├─ RateLimiter (速率限制)
  │   │   └─ 5个搜索通道
  │   │
  │   ├─ BudgetManager (预算管理)
  │   │   ├─ 帖子数预算
  │   │   ├─ API调用预算
  │   │   └─ 运行时间预算
  │   │
  │   └─ QualityControl (质量控制)
  │       ├─ DeduplicationEngine (去重)
  │       └─ 质量过滤器
  │
  └─ 结果存储 (JSONL格式)
```

---

## 核心组件

### 1. 簇构建器 (ClusterBuilder)

**文件**: `src/discovery/cluster_builder.py`

30个Subreddit簇，分为5大类别：

| 类别 | Subreddit数量 | 示例 |
|------|--------------|------|
| crypto_general | 8 | CryptoCurrency, Bitcoin, Ethereum |
| tron_ecosystem | 6 | Tronix, TronTRX, Tronscan |
| trading | 6 | CryptoMarkets, SatoshiStreetBets |
| development | 5 | CryptoDev, EthDev |
| meme_culture | 5 | CryptoMoonShots, SatoshiStreetDegens |

**使用示例**:
```python
from src.discovery import ClusterBuilder

builder = ClusterBuilder()
clusters = builder.get_all_clusters()  # 30个簇
crypto_clusters = builder.get_by_category("crypto_general")  # 8个簇
```

---

### 2. 凭据管理器 (CredentialManager)

**文件**: `src/discovery/credential_manager.py`

**功能**:
- 从JSONL文件加载3个爬虫账号
- 支持3种轮换策略: `round_robin`, `random`, `least_used`
- 自动冷却机制（达到请求上限后进入冷却期）
- 请求计数和统计

**配置**:
```python
CredentialConfig(
    credential_file=Path("爬虫账号.jsonl"),
    rotation_strategy="round_robin",  # 轮询策略
    max_requests_per_credential=100,  # 单账号最大请求数
    credential_cooldown_minutes=30,   # 冷却时间30分钟
    enable_auto_refresh=True          # 自动刷新token
)
```

**使用示例**:
```python
from src.discovery import CredentialManager

manager = CredentialManager(config)
credential = manager.get_credential()  # 获取下一个可用凭据
stats = manager.get_stats()            # 查看统计信息
```

---

### 3. 多通道搜索 (MultiChannelSearch)

**文件**: `src/discovery/multi_channel_search.py`

**5个搜索通道**:
| 通道 | 端点 | 时间过滤器 | 优先级 |
|------|------|-----------|--------|
| hot | /hot | - | 10 |
| top_day | /top | day | 9 |
| top_week | /top | week | 8 |
| rising | /rising | - | 7 |
| new | /new | - | 5 |

**速率限制**:
- 60请求/分钟
- 600请求/小时
- 自动重试（3次，5秒退避）

**使用示例**:
```python
from src.discovery import MultiChannelSearch

search = MultiChannelSearch(channels, credential_manager, rate_limit_config)

async for result in search.search_all_channels("tronix", max_posts=100):
    print(f"{result.channel}: {len(result.posts)} 帖子")
```

---

### 4. 预算管理器 (BudgetManager)

**文件**: `src/discovery/budget_manager.py`

**三维预算控制**:
1. **帖子数预算**: 最大收集帖子数
2. **API调用预算**: 最大API请求次数
3. **运行时间预算**: 最大运行时长（分钟）

**配置**:
```python
BudgetConfig(
    max_posts_per_run=1000,      # 最大1000帖子
    max_runtime_minutes=60,      # 最大60分钟
    max_api_calls=3000,          # 最大3000次API调用
    enable_budget_tracking=True, # 启用跟踪
    stop_on_budget_exceeded=True # 超预算时停止
)
```

**使用示例**:
```python
manager = BudgetManager(config)

manager.track_posts(50)      # 跟踪帖子
manager.track_api_call(5)    # 跟踪API调用

if manager.should_stop():
    print("预算已用尽，停止执行")

manager.print_status()       # 打印预算状态
```

---

### 5. 质量控制系统 (QualityControl)

**文件**: `src/discovery/quality_control.py`

**质量过滤器**:
- 最小分数要求（默认10）
- 最小评论数（默认5）
- 最大年龄限制（默认72小时）
- 标题长度限制（10-300字符）
- NSFW过滤
- 关键词过滤（禁止/必需）

**去重策略**:
| 策略 | 说明 |
|------|------|
| exact_title | 精确标题匹配 |
| fuzzy_title | 模糊标题匹配（Jaccard相似度） |
| url | URL匹配 |
| content_hash | 内容哈希匹配（MD5） |

**配置**:
```python
QualityControlConfig(
    min_post_score=10,
    min_comment_count=5,
    max_post_age_hours=72,
    enable_nsfw_filter=True,
    enable_duplicate_filter=True
)

DeduplicationConfig(
    strategy="exact_title",      # 去重策略
    similarity_threshold=0.85,   # 相似度阈值
    lookback_days=7,             # 回溯7天
    cache_size=10000             # 缓存1万条
)
```

---

### 6. 产能配方执行器 (CapacityExecutor)

**文件**: `src/discovery/capacity_executor.py`

**3个内置配方**:

| 配方 | 目标帖子 | 最大时间 | 搜索通道 | 最小分数 | 最大年龄 |
|------|---------|---------|---------|---------|---------|
| quick_scan | 100 | 10分钟 | hot, rising | 20 | 24小时 |
| standard | 500 | 30分钟 | hot, top_day, rising | 10 | 48小时 |
| deep_dive | 1000 | 60分钟 | 全部5个通道 | 5 | 72小时 |

**使用示例**:
```python
from src.discovery import CapacityExecutor

executor = CapacityExecutor(config)
posts = await executor.execute_recipe(recipe, cluster_ids)

stats = executor.get_all_stats()  # 获取所有统计
```

---

## 核心管道 (DiscoveryPipeline)

**文件**: `src/discovery/pipeline.py`

**完整工作流**:
1. 加载30个Subreddit簇
2. 加载3个爬虫账号
3. 选择产能配方
4. 并发搜索所有通道
5. 质量控制和去重
6. 预算管理
7. 保存结果（JSONL格式）

**命令行运行**:
```bash
cd d:\reddit-comment-system
python -m src.discovery.pipeline
```

**程序化使用**:
```python
import asyncio
from src.discovery import DiscoveryPipeline

async def main():
    pipeline = DiscoveryPipeline()

    # 打印配置摘要
    pipeline.print_config_summary()

    # 执行标准配方
    posts = await pipeline.run("standard")

    print(f"收集到 {len(posts)} 个帖子")

asyncio.run(main())
```

---

## 配置系统

**文件**: `src/discovery/config.py`

**完整配置类**: `DiscoveryConfig`

**子配置**:
- `CredentialConfig`: 凭据配置
- `BudgetConfig`: 预算配置
- `QualityControlConfig`: 质量控制配置
- `DeduplicationConfig`: 去重配置
- `RateLimitConfig`: 速率限制配置
- `SearchChannelConfig`: 搜索通道配置
- `CapacityRecipeConfig`: 产能配方配置

**环境变量**:
```bash
# 使用 DISCOVERY_ 前缀
export DISCOVERY_LOG_LEVEL=INFO
export DISCOVERY_ENABLE_METRICS=true
```

---

## 数据模型

**文件**: `src/discovery/models.py`

**RawPost** (原始帖子):
```python
@dataclass
class RawPost:
    post_id: str              # Reddit帖子ID
    cluster_id: str           # 所属簇ID
    title: str                # 标题
    author: str               # 作者
    score: int                # 分数
    num_comments: int         # 评论数
    created_utc: float        # 创建时间戳
    url: str                  # URL
    permalink: str            # 永久链接
    selftext: str             # 正文
    is_self: bool             # 是否自发帖
    over_18: bool             # 是否NSFW
    spoiler: bool             # 是否剧透
    stickied: bool            # 是否置顶
    raw_json: Dict            # 原始JSON数据
    discovered_at: datetime   # 发现时间
```

**输出格式** (JSONL):
```json
{"post_id":"abc123","cluster_id":"tronix","title":"...","score":150,...}
{"post_id":"def456","cluster_id":"ethereum","title":"...","score":200,...}
```

---

## 测试

**文件**: `tests/test_discovery_integration.py`

**运行测试**:
```bash
pytest tests/test_discovery_integration.py -v
```

**测试覆盖**:
- ✅ ClusterBuilder - 簇加载和分类
- ✅ CredentialManager - 凭据加载和轮换
- ✅ BudgetManager - 预算跟踪和超标检测
- ✅ QualityControl - 质量过滤和去重
- ✅ DiscoveryPipeline - 端到端集成

---

## 性能指标

**基准测试** (standard配方):
- 目标帖子: 500个
- 运行时间: ~20-30分钟
- API调用: ~200-300次
- 凭据轮换: 自动（每100次请求）
- 去重率: ~15-20%

**优化建议**:
- 并发通道数: 保持5个（平衡速度和速率限制）
- 凭据数量: 3个（覆盖24小时运行）
- 缓存大小: 10000条（足够7天去重）

---

## 故障排查

### 1. 凭据加载失败
```
FileNotFoundError: 凭据文件不存在
```
**解决**: 检查凭据文件路径，确保JSONL文件存在

### 2. 速率限制
```
HTTP 429: 速率限制，等待60s
```
**解决**: 自动重试，或降低`requests_per_minute`配置

### 3. 预算超标
```
⚠️ 预算超标: 帖子数超标
```
**解决**: 正常行为，系统会自动停止

### 4. 无可用凭据
```
[错误] 无可用凭据
```
**解决**: 等待冷却期结束，或增加凭据数量

---

## 下一步

Module 2完成后，进入Module 3（评论生成系统）:
- 从发现的帖子中筛选评论目标
- 使用GPT-4生成评论内容
- 与Module 1（评论账号）集成
- 执行评论发布和监控

---

## 版本历史

- **v1.0** (2025-10-09): 初始版本
  - 30个簇构建器
  - 3账号轮换系统
  - 5通道搜索
  - 预算管理
  - 质量控制和去重
  - 产能配方执行器
