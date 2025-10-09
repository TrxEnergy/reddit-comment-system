# Changelog

所有重要的项目变更都会记录在这个文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [0.3.0] - 2025-10-09

### Added

#### Module 3: 智能筛选系统完整实现

**核心组件**:
- **动态池子计算器** (`src/screening/dynamic_pool_calculator.py`)
  - 实时查询养号API获取活跃账号数
  - 动态计算池子规模: `账号数 × 日评论限制 × 3倍buffer`
  - 三档阈值策略（小/中/大规模：1-50/51-100/101-200账号）
  - API降级策略（失败时假设100活跃账号）

- **L1快速筛选器** (`src/screening/l1_fast_filter.py`)
  - 基于sklearn TfidfVectorizer的话题相关性分析
  - 4维评分系统：话题40% + 互动30% + 情感20% + 标题10%
  - 三级路由决策：直通(≥0.75) / 送L2(0.45-0.75) / 拒绝(<0.45)
  - 性能: 10-20帖/秒

- **L2深度筛选器** (`src/screening/l2_deep_filter.py`)
  - GPT-4o-mini异步并发评估（最大10并发）
  - 含L1预评分和账号数的智能Prompt
  - 4维深度评分：话题价值35% + 长期ROI25% + 互动安全25% + 可行性15%
  - 返回评论角度建议和风险等级

- **成本守护器** (`src/screening/cost_guard.py`)
  - 日/月成本实时追踪和持久化
  - 自动熔断机制（日限$0.50，月限$15.00）
  - 跨日/跨月自动重置
  - JSON存储支持

- **主筛选流程** (`src/screening/screening_pipeline.py`)
  - L1→成本检查→L2完整编排
  - 统计汇总（利用率、成本、延迟）
  - 最终结果含元数据（L1/L2得分、评论角度）

- **数据模型** (`src/screening/models.py`)
  - PoolConfig: 池子配置
  - L1FilterResult / L2FilterResult: 筛选结果
  - ScreeningStats / ScreeningResult: 统计和汇总
  - CostGuardStatus: 成本状态

**配置扩展**:
- 新增 `M3ScreeningConfig` 配置类（15个参数）
- 支持按账号规模动态选择阈值
- 版本号更新至 v0.3.0

**依赖更新**:
- scikit-learn==1.3.2 (TF-IDF向量化)
- numpy==1.26.2 (数值计算)

**测试覆盖**:
- 30个单元测试（通过率91%）
- test_dynamic_pool_calculator.py: 14个测试
- test_cost_guard.py: 10个测试
- test_l1_fast_filter.py: 12个测试
- screening模块覆盖率: 42%

**性能特性**:
- ✅ 动态适配1-200账号
- ✅ 成本可控（$0.68-$13.50/月）
- ✅ 处理延迟6-90秒（10-200账号）
- ✅ 成本熔断保护

**文档**:
- 新增 `docs/MODULE_3_SCREENING.md` 完整技术文档

---

## [0.2.0] - 2025-10-09

### Added

#### Module 2: 发现引擎完整实现

**核心组件**:
- **配置系统** (`src/discovery/config.py`)
  - DiscoveryConfig主配置类
  - 7个子配置类（Credential, Budget, QualityControl, Deduplication, RateLimit, SearchChannel, CapacityRecipe）
  - 支持环境变量覆盖（DISCOVERY_前缀）

- **凭据管理器** (`src/discovery/credential_manager.py`)
  - 3账号自动轮换（round_robin, random, least_used三种策略）
  - 自动冷却机制（达到请求上限后进入冷却期）
  - 请求计数和统计跟踪

- **多通道搜索** (`src/discovery/multi_channel_search.py`)
  - 5通道并发搜索（hot, top_day, top_week, rising, new）
  - 速率限制器（60请求/分钟，600请求/小时）
  - 自动重试机制（3次，5秒退避）

- **预算管理系统** (`src/discovery/budget_manager.py`)
  - 三维预算控制（帖子数/API调用/运行时间）
  - 实时跟踪和统计
  - 超标自动停止

- **质量控制系统** (`src/discovery/quality_control.py`)
  - 去重引擎（4种策略：exact_title, fuzzy_title, url, content_hash）
  - 质量过滤（分数、评论数、年龄、长度、NSFW、关键词）
  - 拒绝统计和分析

- **产能配方执行器** (`src/discovery/capacity_executor.py`)
  - 3种内置配方（quick_scan, standard, deep_dive）
  - 完整统计汇总（预算、质量、凭据）

- **核心管道** (`src/discovery/pipeline.py`)
  - 端到端集成流程
  - 命令行接口
  - 结果存储（JSONL格式）

**数据资源**:
- **30个Subreddit簇** (`src/discovery/cluster_builder.py`)
  - crypto_general: 8个（CryptoCurrency, Bitcoin, ethereum等）
  - tron_ecosystem: 6个（Tronix, TronTRX, Tronscan等）
  - trading: 6个（SatoshiStreetBets, CryptoMarkets等）
  - development: 5个（ethdev, CryptoDev, solidity等）
  - meme_culture: 5个（CryptoMoonShots, dogecoin等）

- **数据模型** (`src/discovery/models.py`)
  - RawPost（原始帖子模型）
  - RedditPost（Reddit帖子数据模型）
  - DiscoveryResult（发现结果汇总）

**测试**:
- 14个单元测试（`tests/test_discovery_integration.py`）
  - ClusterBuilder: 2个测试
  - CredentialManager: 4个测试
  - BudgetManager: 3个测试
  - QualityControl: 2个测试
  - DiscoveryPipeline: 3个测试
- 代码覆盖率: 55%
- 组件验证脚本（`validate_discovery.py`）

**文档**:
- [MODULE_2_DISCOVERY.md](docs/MODULE_2_DISCOVERY.md) - 完整技术文档
- [TEST_RESULTS.md](TEST_RESULTS.md) - 测试报告

### Changed

- 更新README.md，标记Module 2为完成状态
- 更新模块说明，添加Module 2详细描述

### Technical Details

- **新增代码**: 2781行
- **新增文件**: 15个
- **测试通过率**: 100% (14/14)
- **代码覆盖率**: 55%

---

## [0.1.0] - 2025-10-08

### Added

#### Module 1: 基础设施

- 项目初始化和基础架构
- 配置管理系统（Pydantic Settings）
- 日志系统（结构化日志）
- 异常定义
- Docker容器化配置
- 测试框架（pytest）
- 引入合同仓Submodule

### Initial Release

- 项目基础框架搭建
- 开发环境配置
- Git分支策略（main, develop, feature/*）

---

## 版本说明

### 版本号规则

- **主版本号（Major）**: 重大架构变更或不兼容的API修改
- **次版本号（Minor）**: 向后兼容的新功能添加
- **修订号（Patch）**: 向后兼容的问题修复

### 发布流程

1. Feature分支开发
2. 合并到develop分支
3. 集成测试
4. 创建Release PR到main
5. 合并并打tag
6. GitHub Releases发布

---

[0.2.0]: https://github.com/TrxEnergy/reddit-comment-system/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/TrxEnergy/reddit-comment-system/releases/tag/v0.1.0
