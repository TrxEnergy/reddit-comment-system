# M4内容工厂代码审查材料包

**目的**：请ChatGPT审查M4评论生成系统的架构和实现，提出改进建议

---

## 📋 系统概述

### 功能定位
M4内容工厂是Reddit评论自动生成系统，负责：
1. 接收M3筛选的优质帖子
2. 根据帖子意图（A/B/C组）生成相关评论
3. 确保评论质量、自然度、合规性

### 核心指标（当前）
- **质量通过率**: 65% (13/20测试)
- **相关性评分**: 0.81 (目标0.65+)
- **整体质量**: 0.85/1.0
- **失败原因**: 35%因合规失败或AI生成跑偏

---

## 🏗️ 系统架构

### 处理流程
```
M3结果 → ContentPipeline → 评论生成流程
  ├─ IntentRouter: 路由到A/B/C意图组
  ├─ PersonaManager: 选择Persona角色
  ├─ StyleGuideLoader: 加载子版风格卡
  └─ CommentGenerator: 生成评论
       ├─ PromptBuilder: 构建AI Prompt（6个Block）
       ├─ AIClient: 调用OpenAI GPT-4o-mini
       ├─ Naturalizer: 口头禅注入 + 自然瑕疵
       ├─ ComplianceChecker: 合规检查
       └─ QualityScorer: 质量评分（relevance/natural/compliance）
```

### 意图组分类
- **A组（费用与转账）**: 需要准确数据（如"TRC20费用$1-2 vs ERC20 $10+"）
- **B组（交易所与钱包）**: 故障排查、技术指导
- **C组（学习与分享）**: 解释概念、推荐资源

---

## 📂 核心文件清单

### 1. 主流程编排
**文件**: `src/content/content_pipeline.py` (239行)
**职责**:
- 初始化所有模块
- 编排完整生成流程
- 处理M3批量输入

**关键方法**:
```python
async def process_batch(self, m3_results: List[Dict]) -> List[GeneratedComment]:
    # 1. 解析M3结果为CommentRequest
    # 2. 检查配额
    # 3. 路由意图组
    # 4. 选择Persona
    # 5. 生成评论
    # 6. 质量检查
```

### 2. Prompt构建器
**文件**: `src/content/prompt_builder.py` (约400行)
**职责**: 模块化拼装6个Block构成AI Prompt
- ROLE_BLOCK: Persona背景
- CONTEXT_BLOCK: 帖子信息
- INTENT_BLOCK: 意图目标
- STYLE_BLOCK: 风格约束
- SAFETY_BLOCK: 合规提示
- FORMAT_BLOCK: 格式要求

**关键方法**:
```python
def build_prompt(persona, post, intent_group, style_guide, suggestion) -> str:
    # 拼装6个Block
    # 返回完整Prompt字符串
```

### 3. 评论生成器
**文件**: `src/content/comment_generator.py` (235行)
**职责**:
- 调用AI生成评论
- 自然化处理
- 合规检查
- 质量评分

**流程**:
```python
async def generate(request, persona, intent_group, style_guide) -> GeneratedComment:
    # 1. 构建Prompt
    # 2. AI生成（n=2个变体）
    # 3. Naturalizer处理（口头禅+瑕疵）
    # 4. 合规检查（过滤不合格）
    # 5. 质量评分
    # 6. 选择最佳候选
```

### 4. 自然化处理器
**文件**: `src/content/naturalizer.py` (359行)
**职责**:
- 注入Persona口头禅（opening/transition/ending）
- 添加自然瑕疵（emoji 25%、typo 15%、filler words 35%）
- 句式多样化

**关键方法**:
```python
def process(comment_text, persona) -> str:
    # 1. 注入口头禅（25%/20%/30%概率）
    # 2. 添加自然瑕疵
    # 3. 句式多样化
    # 4. 检查n-gram重复度
```

### 5. 质量评分器
**文件**: `src/content/quality_scorer.py` (约300行)
**职责**: 三维评分系统
- **相关性** (40%权重): 关键词匹配、主题复述
- **自然度** (30%权重): 句式多样性、口头禅密度
- **合规度** (30%权重): 合规检查结果

**评分算法**:
```python
# [FIX 2025-10-10] 优化：扩充停用词50+，分层匹配策略
def score_relevance(comment, post):
    # 1. 提取标题核心词（过滤50+停用词）
    # 2. 关键词覆盖率评分（≥50%=1.0, ≥30%=0.8）
    # 3. 主题复述检测
    # 4. 长度适配
```

### 6. 合规检查器
**文件**: `src/content/compliance_checker.py` (304行)
**职责**:
- 硬禁止检查（18个禁止短语、6个正则模式）
- 软约束检查（情绪强度、绝对化措辞、长度）
- 免责声明管理（10种变体、80%概率、3种位置）

**关键配置**:
```yaml
# config/content_policies.yaml
hard_bans:
  phrases: ["guaranteed profit", "pump", "dump", ...]
  patterns: [非白名单外链, 私信渠道, 推荐码]

soft_rules:
  finance_disclaimer:
    variants: [10种变体]
    append_probability: 0.8
    position_options: ["end", "middle", "start"]
    position_weights: [0.7, 0.2, 0.1]
```

### 7. 意图路由器
**文件**: `src/content/intent_router.py` (180行)
**职责**: 将帖子分类到A/B/C意图组

**路由逻辑**:
```python
def route(post_title, post_metadata):
    # 1. 优先使用M3的explicit intent_group
    # 2. 根据suggestion推断（80%置信度）
    # 3. 统计positive_clues匹配分数
    # 4. 扣除negative_lookalikes分数
    # 5. 得分>0使用该组，否则fallback到C组
```

**当前问题**: 路由准确率62-67%，部分帖子fallback到C组

---

## 📊 数据配置文件

### 1. Persona库
**文件**: `data/personas/persona_bank.yaml` (313行)
**内容**: 20个Persona定义
- A组（费用）: 6个 (crypto_expert, gas_optimizer, defi_farmer, nft_collector, miner, multilingual_user)
- B组（钱包）: 6个 (wallet_helper, exchange_user, risk_aware_investor, security_expert, api_trader, hardware_wallet_user)
- C组（教育）: 8个 (beginner_mentor, market_observer, data_nerd, tech_explainer, content_creator, podcast_listener, book_reader, course_student)

**每个Persona包含**:
- `background`: 背景故事
- `tone`: 语气风格
- `interests`: 兴趣主题
- `catchphrases`: 口头禅（opening/transition/ending各8-10个）

### 2. 合规政策
**文件**: `config/content_policies.yaml` (75行)
**内容**:
- 硬禁止: 18个短语 + 6个正则模式
- 软约束: 情绪强度、绝对化、长度、句式
- 免责声明: 10种变体配置

### 3. 风格卡
**文件**: `data/styles/sub_style_guides.yaml`
**内容**: 5个子版的风格约束
- `tone`: 语气（neutral_sober / friendly_practical）
- `jargon_level`: 术语等级
- `must_end_with_question`: 是否必须以问题结尾
- `compliance`: 合规要求

---

## 🔧 最近优化记录

### 2025-10-10优化（已完成）
1. **相关性评分算法** - 停用词50+ + 分层匹配 → 评分0.47→0.81
2. **质量阈值策略** - AND逻辑改加权总分 → 通过率20%→65%
3. **Persona库扩充** - 10个→20个（翻倍）
4. **免责声明多样化** - 1种→10种变体 + 概率性添加
5. **口头禅扩充** - 每类3-4个→8-10个
6. **Intent Router修复** - 支持M3的explicit intent_group字段

### 当前问题
1. **35%失败率** - 主要原因是合规检查失败或AI生成跑偏
2. **Intent路由准确率** - 62-67%（目标80%+）
3. **A组评论质量不稳定** - 费用对比类评论有时缺乏具体数据
4. **免责声明位置** - 70%在结尾，中间位置更自然但概率低

---

## 🎯 待审查的关键问题

### 问题1: AI生成"跑偏"
**现象**: A组（费用对比）评论有时不包含具体数据，只泛泛而谈

**示例**:
- ❌ 差评论: "TRC20比ERC20便宜很多，建议使用TRC20"（无数据）
- ✅ 好评论: "TRC20费用$1-2，ERC20费用$10+，差距明显"（有数据）

**当前策略**:
- Prompt Builder提供M3的`suggestion`字段（如"Compare TRC20 vs ERC20 fees"）
- AI直接生成完整评论
- 无强制约束确保包含具体事实

**待讨论**:
1. 是否需要"模板骨架+AI填充"两阶段生成？
2. 是否在Prompt中强制要求"MUST include specific numbers"？
3. 是否对A组单独实施更严格的结构化Prompt？

### 问题2: 质量检查的时机
**当前流程**: AI生成 → Naturalizer → ComplianceChecker → QualityScorer

**问题**:
- Naturalizer会修改AI生成内容（注入口头禅、添加emoji）
- 这可能导致原本合规的内容变不合规（如添加emoji触发违规）

**待讨论**:
1. 是否应该先检查合规，再自然化？
2. Naturalizer的修改幅度是否应该受限？

### 问题3: Intent Router的fallback机制
**现象**: 当帖子关键词匹配得分≤0时，fallback到C组

**问题**:
- A组"Cheapest NFT minting"因无"fee/cost"关键词，fallback到C组
- 导致免责声明未添加（C组不触发）

**待讨论**:
1. 是否应该废除fallback，强制路由到得分最高的组？
2. 是否扩充positive_clues关键词库？
3. 是否引入语义相似度计算（而非简单关键词匹配）？

### 问题4: 多样性 vs 质量的平衡
**现状**:
- 生成n=2个变体，选择质量最高的
- Naturalizer注入口头禅概率：25%/20%/30%

**问题**:
- 概率性注入导致同Persona不同评论风格不一致
- 有时过度注入（口头禅密度>20%触发警告）

**待讨论**:
1. 是否应该强制每个评论都包含至少1个口头禅？
2. 注入概率是否应该与Persona的`tone`属性关联？
3. 是否需要"风格一致性检查"机制？

### 问题5: 评分权重是否合理
**当前权重**:
```python
overall = relevance * 0.4 + natural * 0.3 + compliance * 0.3
threshold = 0.70
```

**问题**:
- A组（费用对比）相关性最重要，但权重仅40%
- C组（教育解释）自然度更重要，但权重也是30%

**待讨论**:
1. 是否应该根据Intent Group动态调整权重？
2. 是否引入"关键信息完整性"维度（特别是A组）？

---

## 📈 性能数据

### 测试数据集
- 20个真实Reddit帖子（A/B/C各8/6/6）
- 包含英语、西班牙语
- 覆盖费用、NFT、DeFi、安全、教育等主题

### 测试结果（2025-10-10）
```
处理: 20个帖子
成功: 13条评论（65%）
失败: 7条

失败原因分布:
- 合规检查失败: 5条（"No variants passed compliance check"）
- AI生成错误: 2条

质量评分分布:
- 最低: 0.74
- 最高: 0.91
- 平均: 0.85
- 中位数: 0.85

相关性评分:
- 最低: 0.64
- 最高: 0.90
- 平均: 0.81

Intent路由准确性:
- A组: 5/8成功 (62.5%)
- B组: 4/6成功 (66.7%)
- C组: 4/6成功 (66.7%)
```

### API成本
- 平均每评论: ~3-4秒
- Token消耗: 估计~2.5K tokens/评论
- 失败重试: 无自动重试机制

---

## 🤔 请ChatGPT重点审查的方面

### 1. 架构设计
- [ ] 单阶段直接生成 vs 两阶段（骨架+包装）哪个更好？
- [ ] 模块职责划分是否合理？
- [ ] 流程顺序是否最优（特别是Naturalizer的时机）？

### 2. 质量控制
- [ ] 如何防止AI生成"跑偏"（特别是A组费用对比）？
- [ ] 质量评分维度和权重是否合理？
- [ ] 是否需要"关键信息完整性检查"？

### 3. Intent路由
- [ ] 简单关键词匹配是否足够？
- [ ] fallback机制是否合理？
- [ ] 如何提升路由准确率至80%+？

### 4. 多样性策略
- [ ] Naturalizer的概率性注入是否合理？
- [ ] 20个Persona是否足够？
- [ ] 口头禅8-10个/类是否足够？

### 5. 性能优化
- [ ] 35%失败率是否可接受？
- [ ] 是否需要失败重试机制？
- [ ] 如何减少API调用成本？

### 6. 可扩展性
- [ ] 如何支持更多语言（当前只有EN/ES）？
- [ ] 如何快速适配新的subreddit？
- [ ] 如何支持更多Intent Group（当前只有A/B/C）？

---

## 📎 附件文件建议

如果ChatGPT需要更详细的代码，可提供：

1. **核心流程代码**（优先级最高）
   - `content_pipeline.py` - 主流程
   - `comment_generator.py` - 生成器
   - `prompt_builder.py` - Prompt构建

2. **质量控制代码**
   - `quality_scorer.py` - 评分算法
   - `compliance_checker.py` - 合规检查
   - `naturalizer.py` - 自然化

3. **路由和选择代码**
   - `intent_router.py` - 意图路由
   - `persona_manager.py` - Persona选择

4. **配置文件**
   - `content_policies.yaml` - 合规政策
   - `persona_bank.yaml` - Persona定义
   - `sub_style_guides.yaml` - 风格卡

5. **测试代码**
   - `test_m4_optimization.py` - E2E测试
   - 测试结果日志

---

## 🎯 期望ChatGPT给出的建议

1. **架构改进建议**：是否需要重构某些模块？
2. **质量提升方案**：如何将通过率从65%提升至80%+？
3. **跑偏防止策略**：如何确保A组评论包含准确数据？
4. **多样性优化**：如何在质量和多样性之间取得平衡？
5. **性能优化建议**：如何降低API成本、减少失败率？
6. **可维护性建议**：代码结构、命名、文档是否需要改进？

---

**生成时间**: 2025-10-10
**系统版本**: M4 v1.2 (优化后)
**测试通过率**: 65% (13/20)
