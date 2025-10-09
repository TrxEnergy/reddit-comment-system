# Changelog

所有重要的项目变更都会记录在这个文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [0.4.0] - 2025-10-09

### Added

#### Module 4: Persona内容工厂完整实现

**核心组件**:
- **Persona管理器** (`src/content/persona_manager.py`)
  - 10个轻量Persona覆盖A/B/C三组意图
  - Persona选择、冷却管理和使用统计
  - 支持子版兼容性过滤和720分钟冷却

- **意图路由器** (`src/content/intent_router.py`)
  - 三大意图组路由：A（费用转账）、B（钱包问题）、C（新手学习）
  - 基于positive_clues和negative_lookalikes分类
  - 支持M3 metadata中的intent_group直接传递

- **Prompt构建器** (`src/content/prompt_builder.py`)
  - 6模块Prompt拼装：ROLE/CONTEXT/INTENT/STYLE/SAFETY/FORMAT
  - Persona背景和口头禅动态注入
  - 子版风格卡和M3建议整合

- **AI客户端** (`src/content/ai_client.py`)
  - 双客户端支持：OpenAI（gpt-4o-mini）+ Anthropic（claude-3-haiku）
  - 重试机制（最多2次，指数退避）
  - 超时控制（单次15秒）和异常处理

- **评论生成器** (`src/content/comment_generator.py`)
  - 完整7步流程：Prompt→AI→自然化→合规→评分→变体选择
  - 生成2个变体并选择最佳候选
  - 自动附加金融免责声明（A/B组）

- **自然化处理器** (`src/content/naturalizer.py`)
  - 口头禅随机注入（opening/transition/ending）
  - 句式多样化和模板痕迹去除
  - 长度调整（50-400字符最优区间）

- **合规审查器** (`src/content/compliance_checker.py`)
  - 硬禁止：12短语 + 3正则（外链/私信/推荐码）
  - 软约束：情绪强度、绝对化比例、长度范围
  - 自动免责声明附加（Intent A/B组）

- **质量评分器** (`src/content/quality_scorer.py`)
  - 三分法评分：relevance/natural/compliance（0-1分）
  - 放行阈值：≥0.85/0.85/0.95
  - 结合M3 metadata的intent_prob权重

- **配额管理器** (`src/content/quota_manager.py`)
  - 账户日限1条（滚动24小时或自然日）
  - 防止配额意外消耗（仅在质量通过后记账）
  - 支持批量状态查询

- **风格卡加载器** (`src/content/style_guide_loader.py`)
  - 6个子版风格卡（CryptoCurrency/Tronix/ethereum/Bitcoin/CryptoMarkets/default）
  - tone/jargon/length/dos/donts配置
  - 未覆盖子版自动回退到default

- **主管道** (`src/content/content_pipeline.py`)
  - 端到端流程编排：M3解析→路由→选择→生成→评分→记账
  - 统计汇总（processed/generated/quota_denied/quality_failed）
  - CLI测试入口（可独立运行）

- **数据模型** (`src/content/models.py`)
  - Persona、IntentGroup、StyleGuide、CommentRequest
  - GeneratedComment、QualityScores、ComplianceCheck
  - PersonaUsageRecord

**配置文件**:
- `data/personas/persona_bank.yaml`: 10个Persona完整定义
- `data/intents/intent_groups.yaml`: A/B/C三组意图规则
- `data/styles/sub_style_guides.yaml`: 6个子版风格卡
- `config/content_policies.yaml`: 硬禁止和软约束政策
- `data/languages/language_glossary.yaml`: 多语言术语和混写策略
- `config/scoring_thresholds.env`: 44行完整阈值配置
- `config/ab_experiments.yaml`: A/B试验框架（draft）

**测试套件**:
- `tests/unit/test_content_pipeline.py`: 16个管道流程测试
- `tests/unit/test_compliance_checker.py`: 25个合规审查测试
- `tests/integration/test_m3_m4_integration.py`: 20个M3→M4集成测试
- 当前状态：18个测试通过，覆盖率12%（核心模块97%）

**文档**:
- `docs/MODULE_4_CONTENT.md`: 完整模块文档
  - 系统架构和数据流图
  - 10个Persona设计说明
  - 6步Prompt构建策略
  - 配置文件详解和使用示例
  - 性能指标和故障排查指南

**关键特性**:
- ✅ 每账户每日最多1条评论（强制配额）
- ✅ Persona冷却720分钟（同persona-subreddit不重复）
- ✅ 子版冷却72小时（避免相似主题重复）
- ✅ 成本守护：日限$0.40、月限$12、生成$0.002/次
- ✅ 质量阈值：rel≥0.85, nat≥0.85, comp≥0.95
- ✅ 双AI客户端：OpenAI + Anthropic
- ✅ 多语言支持：EN/ES/ZH术语混写

**依赖更新**:
- openai>=1.3.0 (OpenAI API客户端)
- anthropic>=0.8.0 (Anthropic API客户端)

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
