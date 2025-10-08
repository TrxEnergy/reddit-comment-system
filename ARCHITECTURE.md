# 架构设计

## 系统架构

### 双仓解耦设计

```
┌─────────────────────────────┐
│ 合同仓 (reddit-contracts)   │
│  ├─ account_api.py          │
│  └─ error_codes.py          │
└─────────────────────────────┘
       ↑ Submodule        ↑ Submodule
       │                  │
┌──────┴──────────┐  ┌───┴──────────────┐
│ 养号系统         │  │ 评论系统          │
│ (已完成)         │  │ (本项目)          │
├─────────────────┤  ├──────────────────┤
│ FastAPI :8000   │◄─┤ HTTP Client       │
│ 20个健康账号    │  │ AI生成+发布       │
└─────────────────┘  └──────────────────┘
```

## 模块架构

### 核心模块（MVP）

1. **基础设施** (`src/core/`)
   - 配置管理：Pydantic Settings
   - 日志系统：Structlog
   - 异常定义：自定义异常层次

2. **发现引擎** (`src/discovery/`)
   - Reddit爬虫：PRAW
   - MinHash去重
   - 规则初筛

3. **智能筛选** (`src/screening/`)
   - 两级筛选：规则+AI
   - GPT深度分析

4. **内容工厂** (`src/content/`)
   - Persona管理
   - AI生成
   - 合规检查

5. **发布协调** (`src/publishing/`)
   - 账号预留（调用养号API）
   - Reddit发布
   - 频率控制

## 数据流

```
关键词 → 发现 → 去重 → 筛选 → 生成 → 发布
         ↓      ↓      ↓      ↓      ↓
       1500   1320   900    420    400
```

## 技术选型

| 模块 | 技术 | 理由 |
|------|------|------|
| 配置 | Pydantic Settings | 类型安全 |
| 日志 | Structlog | 结构化 |
| HTTP | httpx | 异步 |
| AI | OpenAI/Anthropic | 成熟 |
| Reddit | PRAW | 官方 |
| 去重 | MinHash | 高效 |
