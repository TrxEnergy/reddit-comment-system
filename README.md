# Reddit评论系统

独立的Reddit评论自动化系统，通过API与养号系统解耦。

## 🎯 项目概述

- **定位**：独立评论服务，通过HTTP API调用养号系统
- **架构**：双仓解耦设计，通过合同仓（contracts）定义接口契约
- **技术栈**：Python 3.11 + FastAPI + PRAW + OpenAI/Anthropic

## 🚀 快速开始

### 前置要求

- Docker & Docker Compose
- Python 3.11+（本地开发）
- 养号系统运行中（http://localhost:8000）

### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/TrxEnergy/reddit-comment-system.git
cd reddit-comment-system

# 2. 初始化Submodule（合同仓）
git submodule update --init --recursive

# 3. 配置环境变量
cp config/.env.example .env
# 编辑.env，填入API密钥等配置

# 4. 启动Docker容器
cd docker
docker-compose up -d

# 5. 验证安装
docker-compose exec comment-system pytest tests/unit/ -v
```

## 📦 模块说明

### 当前模块（MVP阶段）

- ✅ **M1: 基础设施** - 配置、日志、Docker环境
- ✅ **M2: 发现引擎** - Reddit帖子发现和去重（30簇、5通道、3账号轮换）
- 🚧 **M3: 评论生成** - GPT-4驱动的评论生成系统
- 🚧 **M4: 内容工厂** - Persona化内容生成
- 🚧 **M5: 发布协调** - 账号预留和Reddit发布

### Module 2: 发现引擎（v0.2.0）

完整的Reddit帖子发现系统，支持：
- **30个Subreddit簇** - 覆盖5大类别（crypto_general, tron_ecosystem, trading, development, meme_culture）
- **5通道并发搜索** - hot, top_day, top_week, rising, new
- **3账号轮换** - 自动凭据管理和冷却机制
- **预算管理** - 帖子数/API调用/运行时间三维控制
- **质量控制** - 4种去重策略 + 完整质量过滤
- **产能配方** - quick_scan, standard, deep_dive三种内置配方

详见 [Module 2技术文档](docs/MODULE_2_DISCOVERY.md)

### 配置说明

所有配置通过环境变量管理，支持嵌套配置：

```bash
# 养号API
YANGHAO__BASE_URL=http://localhost:8000

# AI服务
AI__PROVIDER=openai
AI__API_KEY=sk-xxx

# Reddit
REDDIT__MAX_COMMENTS_PER_DAY=5
```

详见 `config/.env.example`

## 🧪 测试

```bash
# 运行所有测试
pytest tests/ -v

# 单元测试
pytest tests/unit/ -v

# 集成测试
pytest tests/integration/ -v

# 测试覆盖率
pytest tests/ --cov=src --cov-report=html
```

## 📚 文档

- [架构设计](./ARCHITECTURE.md)
- [合同仓接口](./contracts/README.md)

## 🤝 贡献

本项目采用模块化开发策略，每个模块独立测试后再集成。

## 📄 许可

仅供学习和研究使用
