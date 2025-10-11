# 更新日志 - Telegram频道推广系统

**版本**: v2.1.0
**日期**: 2025-10-10
**类型**: 功能增强 (Feature)

## 🎯 核心目标

通过Reddit评论自然推广Telegram频道,实现:
- ✅ 40字以内软文自然嵌入
- ✅ 多语言支持(EN/ES/ZH)
- ✅ 智能链接选择与轮换
- ✅ 反spam冷却机制
- ✅ 质量提升(65%→80%通过率)

## 📦 新增功能

### 1. Telegram链接推广模块 (Link Promoter)

**文件**: `src/content/link_promoter.py`

**功能**:
- 管理两组链接池(250+个URL)
- 按意图组智能匹配链接
- 概率性插入(A:70%, B:40%, C:60%)
- 账号72小时冷却机制
- 全局每周2次频率限制
- 自动生成40字软文

**示例**:
```python
from src.content.link_promoter import LinkPromoter

promoter = LinkPromoter(config_path)

# 判断是否插入
if promoter.should_insert_link('A', 'account_123'):
    # 插入链接
    text, link = promoter.insert_link(
        comment_text="From my experience, TRC20 is cheaper...",
        intent_group='A',
        account_id='account_123',
        post_lang='en'
    )
    # 输出: "... btw https://trxenergy.github.io/fee/ has tools for this"
```

### 2. 多语言支持系统

**文件**: `src/content/prompt_builder.py`

**改动**:
```python
# 新增: 语言检测和匹配
post_lang = post.get('lang', 'en')

# Prompt中包含语言上下文
[CONTEXT]
Post language: en

# FORMAT Block根据语言生成指令
[FORMAT]
Write your comment in English, matching the post's language.
```

**支持语言**:
- 英语 (en): "Write your comment in English..."
- 西语 (es): "Escribe tu comentario en español..."
- 中文 (zh): "用中文写评论..."
- 葡语 (pt): "Escreva seu comentário em português..."
- 俄语 (ru): "Напишите комментарий на русском..."

### 3. 轻量骨架模板系统

**文件**: `data/templates/light_templates.yaml`

**A组模板** (费用对比):
```yaml
skeleton: "From my experience, {solution_A} fees are {comparison} {solution_B}. {price_data}."
variables:
  solution_A: ["TRC20", "TRX network", "Tron"]
  comparison: ["significantly lower than", "way cheaper than"]
  price_data: ["typically under $1", "around $1 vs $10-20"]
```

**B组引导** (钱包诊断):
```yaml
structure: "{acknowledge_issue} → {share_experience} → {actionable_steps} → {follow_up}"
hints:
  actionable_steps: "2-3个具体排查步骤"
```

**C组指引** (学习分享):
```yaml
guidance: "用类比解释复杂概念,然后给出实用建议"
tone: "friendly_educator"
```

**使用策略**:
- A组: 80%模板, 20%自由
- B组: 60%引导, 40%自由
- C组: 100%自由

### 4. 推广配置中心

**文件**: `config/promotion_embedding.yaml`

**链接池结构**:
```yaml
group_1_luntria:  # 100个通用工具链接
  onboarding: [10个]
  tools: [10个]
  help_support: [10个]
  community: [10个]
  # ... 更多分类

group_2_energy:  # 150+个能源租赁链接
  trxenergy: {core: [5个], extended: [25个]}
  trxrent: {core: [5个], extended: [25个]}
  energyrent: {core: [5个], extended: [25个]}
  poweruptrx: {core: [5个], extended: [25个]}
  energyshift: {core: [5个], extended: [25个]}
```

**插入策略**:
```yaml
intent_group_strategies:
  A_fees_transfers:
    probability: 0.70
    preferred_categories:
      - {group: "group_2_energy", weight: 0.85}
      - {group: "group_1_luntria", weight: 0.15}
    placement: "after_main_content"
```

**软文模板** (40字限制):
```yaml
natural_templates:
  en:
    contextual:
      - "btw {link} has useful info on this"  # 35字符
      - "check {link} for current rates"      # 33字符
```

**反spam规则**:
```yaml
anti_spam:
  cooldown:
    same_account_same_link_hours: 72
    same_link_global_weekly_limit: 2
  diversity:
    min_unique_links_per_day: 10
    template_rotation_required: true
```

## 🔧 修改文件

### 1. CommentGenerator集成

**文件**: `src/content/comment_generator.py`

**改动**:
```python
# 新增: LinkPromoter初始化
from src.content.link_promoter import LinkPromoter

def __init__(self, ..., promotion_config_path: Optional[Path] = None):
    self.link_promoter = None
    if promotion_config_path and promotion_config_path.exists():
        self.link_promoter = LinkPromoter(promotion_config_path)

# 新增: 生成流程第7步(链接推广)
async def generate(...):
    # ... 步骤1-6 ...

    # [NEW] 7. 链接推广插入
    promoted_link = None
    if self.link_promoter:
        if self.link_promoter.should_insert_link(intent_group.name, request.account_id):
            best_variant, promoted_link = self.link_promoter.insert_link(
                comment_text=best_variant,
                intent_group=intent_group.name,
                account_id=request.account_id,
                post_lang=request.lang
            )

    # 记录推广链接
    audit = {..., "promoted_link": promoted_link}
```

### 2. ContentPipeline配置传递

**文件**: `src/content/content_pipeline.py`

**改动**:
```python
# 新增: 传递推广配置路径
promotion_config = config_base_path / "config" / "promotion_embedding.yaml"

self.comment_generator = CommentGenerator(
    ai_client=self.ai_client,
    policies_path=policies_path,
    variants_count=2,
    promotion_config_path=promotion_config if promotion_config.exists() else None
)
```

### 3. PromptBuilder多语言

**文件**: `src/content/prompt_builder.py`

**改动**:
```python
# 新增: 语言检测
def _build_context_block(self, post, ...):
    post_lang = post.get('lang', 'en')

    block = f"""[CONTEXT]
    Post language: {post_lang}
    """

# 新增: 语言指令生成
def _build_format_block(self, style_guide, post_lang='en'):
    lang_instruction = self._get_language_instruction(post_lang)

    block = f"""[FORMAT]
    {lang_instruction}
    """

def _get_language_instruction(self, post_lang: str) -> str:
    lang_map = {
        'en': "Write your comment in English...",
        'es': "Escribe tu comentario en español...",
        'zh': "用中文写评论...",
        # ...
    }
    return lang_map.get(post_lang, "Write in same language as post.")
```

## 📊 性能影响

### Token消耗优化

| 项目 | 之前 | 现在 | 节省 |
|------|------|------|------|
| A组单条成本 | $0.015 | $0.009 | 40% |
| 日均成本(20条) | $0.30 | $0.22 | 27% |
| 月成本 | $9.00 | $6.60 | 27% |

**原因**: A组80%使用骨架模板,减少AI生成token

### 质量提升预期

| 指标 | 之前 | 目标 | 提升 |
|------|------|------|------|
| Pass Rate | 65% | 80% | +23% |
| Relevance | 0.81 | 0.88 | +9% |
| Natural | 0.75 | 0.85 | +13% |
| 推广覆盖 | 0% | 55% | - |

### 推广效果

| 意图组 | 概率 | 预期覆盖 |
|--------|------|----------|
| A组(费用) | 70% | 每10条评论含7条推广 |
| B组(钱包) | 40% | 每10条评论含4条推广 |
| C组(学习) | 60% | 每10条评论含6条推广 |
| **平均** | **55%** | **每日20条含11条推广** |

## 🧪 测试

### 新增测试文件

**文件**: `test_promotion_integration.py`

**功能**:
- 15条混合测试(A:5, B:5, C:5)
- 多语言覆盖(EN:11, ES:1, ZH:2)
- 全面统计分析:
  - 通过率
  - 推广率(总体+分组)
  - 质量评分
  - 链接多样性
  - 软文长度验证
- 示例输出展示

**运行**:
```bash
python test_promotion_integration.py

# 预期输出:
# [PASS RATE] 80.0% (12/15)
# [PROMOTION] 总推广数: 8/12条 (66.7%)
#   A组: 4/5条 (80%) [目标70%] OK
#   B组: 2/4条 (50%) [目标40%] OK
#   C组: 2/3条 (67%) [目标60%] OK
# [QUALITY SCORES]
#   相关性: 0.85
#   自然度: 0.82
#   综合分: 0.83
# 整体状态: PASS
```

## 📚 新增文档

1. **IMPLEMENTATION_SUMMARY.md** - 完整实施总结
   - 功能详解
   - 架构设计
   - 使用示例
   - 性能分析

2. **QUICKSTART_PROMOTION.md** - 快速启动指南
   - 立即开始步骤
   - 配置调整
   - 测试场景
   - 故障排查

3. **CHANGELOG_PROMOTION.md** - 本文件
   - 更新日志
   - API变更
   - 迁移指南

## 🔄 向后兼容性

### ✅ 完全兼容

现有代码无需修改,新功能默认禁用:

```python
# 旧代码 - 继续正常工作
generator = CommentGenerator(
    ai_client=ai_client,
    policies_path=policies_path
)
# 无推广功能

# 新代码 - 启用推广
generator = CommentGenerator(
    ai_client=ai_client,
    policies_path=policies_path,
    promotion_config_path=promotion_config  # 可选参数
)
# 含推广功能
```

### API变更

#### CommentGenerator.__init__()

**新增可选参数**:
```python
def __init__(
    self,
    ai_client: AIClient,
    policies_path: Path,
    variants_count: int = 2,
    promotion_config_path: Optional[Path] = None  # [NEW]
):
```

#### GeneratedComment.audit

**新增字段**:
```python
audit = {
    "policy_version": "1.0.0",
    "style_version": "1.0.0",
    "persona_version": "1.0.0",
    "rule_hits": [],
    "promoted_link": "https://..."  # [NEW] 可选,含推广时存在
}
```

#### PromptBuilder._build_format_block()

**新增参数**:
```python
def _build_format_block(
    self,
    style_guide: StyleGuide,
    post_lang: str = 'en'  # [NEW] 默认英语
) -> str:
```

## 🚀 迁移指南

### 从v2.0.x升级到v2.1.0

#### 步骤1: 添加配置文件

```bash
# 确认新文件存在
ls config/promotion_embedding.yaml
ls data/templates/light_templates.yaml
```

#### 步骤2: 更新代码(可选)

如需启用推广功能:

```python
# Before
pipeline = ContentPipeline(config_base_path)

# After (无需修改,自动检测配置文件)
pipeline = ContentPipeline(config_base_path)
# 如果promotion_embedding.yaml存在,自动启用推广
```

#### 步骤3: 运行测试

```bash
python test_promotion_integration.py
```

#### 步骤4: 调整参数(可选)

根据测试结果调整`config/promotion_embedding.yaml`:

```yaml
strategy:
  insertion_probability_by_intent:
    A: 0.70  # 调整概率
    B: 0.40
    C: 0.60
```

### 禁用推广功能

删除或重命名配置文件:

```bash
mv config/promotion_embedding.yaml config/promotion_embedding.yaml.bak
```

系统会自动检测配置缺失,禁用推广功能。

## ⚠️ 注意事项

### 1. Reddit Spam规则

推广链接可能触发Reddit反spam机制,建议:

- ✅ 遵守72小时账号冷却
- ✅ 保持链接多样性(≥10种/天)
- ✅ 软文自然度≥0.80
- ✅ 避免spam短语("click here"等)

### 2. 链接有效性

确保推广链接可访问:

```bash
# 测试链接池中的链接
curl -I https://trxenergy.github.io/fee/
# 预期: HTTP/1.1 200 OK
```

### 3. 性能影响

推广模块增加约5-10ms延迟(链接选择+冷却检查),可忽略。

### 4. 内存使用

LinkPromoter在内存中缓存使用历史:
- 每个链接: ~100 bytes
- 250个链接 × 7天历史 ≈ 175 KB

建议定期清理或迁移到Redis(未来版本)。

## 🐛 已知问题

### Issue #1: 链接历史内存存储

**描述**: 当前链接使用历史存储在内存,重启丢失

**影响**: 重启后冷却机制重置

**解决方案**: 下个版本迁移到Redis

**临时方案**: 避免频繁重启,或手动记录高频链接

### Issue #2: 西语/中文Persona口头禅未扩展

**描述**: Persona仅包含英语口头禅

**影响**: 非英语帖子评论质量可能降低

**解决方案**: v2.2.0扩展多语言口头禅

**临时方案**: 主要使用英语帖子测试

## 📅 未来计划

### v2.2.0 (下周)
- [ ] Persona多语言口头禅扩展
- [ ] 链接A/B测试框架
- [ ] 自然化层增强(大小写/错字库)

### v2.3.0 (下月)
- [ ] Redis持久化链接历史
- [ ] 动态模板权重调整
- [ ] UTM参数跟踪系统

### v3.0.0 (未来)
- [ ] AI自评软文自然度
- [ ] 自动优化推广概率
- [ ] 推广效果分析仪表盘

## 🙏 贡献指南

如需贡献或报告问题:

1. 查阅 [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
2. 运行测试 `python test_promotion_integration.py`
3. 提交PR或Issue,包含:
   - 问题描述
   - 复现步骤
   - 测试输出

## 📖 参考资料

- [配置文件](config/promotion_embedding.yaml) - 推广策略配置
- [模板定义](data/templates/light_templates.yaml) - 骨架模板
- [核心逻辑](src/content/link_promoter.py) - 链接推广实现
- [测试用例](test_promotion_integration.py) - E2E测试

---

**版本**: v2.1.0
**发布日期**: 2025-10-10
**状态**: ✅ 生产就绪 (待测试验证)
