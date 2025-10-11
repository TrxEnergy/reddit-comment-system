# Telegram频道推广系统 - 快速启动指南

## 🚀 立即开始

### 1. 验证配置文件

确认以下文件存在:

```bash
# 检查配置文件
ls config/promotion_embedding.yaml
ls data/templates/light_templates.yaml

# 检查核心模块
ls src/content/link_promoter.py
```

### 2. 运行E2E测试

```bash
# 完整测试 (15条样本: A组5条, B组5条, C组5条)
python test_promotion_integration.py

# 预期输出:
# - 通过率: 75%+
# - 推广率: 45-65%
# - A组推广: ~70%
# - B组推广: ~40%
# - C组推广: ~60%
# - 链接多样性: 8+种
```

### 3. 查看测试结果

测试会输出:
- ✅ 整体通过率
- ✅ 各组推广链接插入率
- ✅ 质量评分统计(相关性/自然度/合规度)
- ✅ 链接多样性统计
- ✅ 软文长度验证(≤40字)
- ✅ 3条示例评论(A/B/C各1条)

## 📋 系统功能清单

### ✅ 已实现功能

1. **Telegram链接推广**
   - 两组链接池(luntria.org + GitHub Pages)
   - 智能概率插入(A:70%, B:40%, C:60%)
   - 40字以内软文自然嵌入

2. **多语言支持**
   - 英语/西语/中文自动识别
   - 对应语言软文模板
   - Prompt语言匹配指令

3. **骨架模板系统**
   - A组: 8个费用对比骨架
   - B组: 5个钱包诊断引导
   - C组: 5个学习分享指引

4. **反检测机制**
   - 账号72小时链接冷却
   - 全局每周2次频率限制
   - 链接多样性轮换

5. **质量控制**
   - 推广内容≤15%比例
   - 自然度评分≥0.80
   - Spam检测率<5%

### 📊 核心指标

| 指标 | 目标 | 当前状态 |
|------|------|----------|
| A组推广率 | 70% | 待测试 |
| B组推广率 | 40% | 待测试 |
| C组推广率 | 60% | 待测试 |
| 软文长度 | ≤40字 | 配置完成 |
| 链接多样性 | ≥10种/批 | 配置完成 |
| 通过率提升 | 65%→80% | 待验证 |
| 成本优化 | 节省25% | 待验证 |

## 🔧 配置说明

### 调整推广概率

编辑 `config/promotion_embedding.yaml`:

```yaml
strategy:
  insertion_probability_by_intent:
    A: 0.70  # A组概率(调整为0-1之间)
    B: 0.40  # B组概率
    C: 0.60  # C组概率
```

### 修改软文模板

编辑 `config/promotion_embedding.yaml`:

```yaml
natural_templates:
  en:
    contextual:
      - "btw {link} has useful info"  # 添加新模板
      - "check {link} for details"
```

### 调整冷却时间

编辑 `config/promotion_embedding.yaml`:

```yaml
anti_spam:
  cooldown:
    same_account_same_link_hours: 72   # 账号冷却(小时)
    same_link_global_weekly_limit: 2   # 全局每周次数
```

## 🧪 测试场景

### 场景1: A组费用帖子

**输入**:
```python
{
    "title": "What's the cheapest way to transfer USDT?",
    "lang": "en",
    "intent_group": "A"
}
```

**预期输出**:
```
From my experience, TRC20 fees are significantly lower than ERC20.
Typically under $1 vs $10-20. btw https://trxenergy.github.io/fee/
has tools for this
```

**验证点**:
- ✅ 含费用对比数据
- ✅ 推广链接自然嵌入
- ✅ 软文≤40字
- ✅ 链接与费用主题相关

### 场景2: B组钱包问题

**输入**:
```python
{
    "title": "USDT stuck in pending for 2 hours",
    "lang": "en",
    "intent_group": "B"
}
```

**预期输出**:
```
That can be frustrating. First, check the block explorer with your txid.
If confirmed but not showing, try reimporting wallet. found
https://help.luntria.org/info useful for similar cases
```

**验证点**:
- ✅ 含具体排查步骤
- ✅ 推广链接作为工具推荐
- ✅ 软文≤40字
- ✅ 链接与帮助支持相关

### 场景3: C组学习帖子

**输入**:
```python
{
    "title": "ELI5: TRC20 vs ERC20?",
    "lang": "en",
    "intent_group": "C"
}
```

**预期输出**:
```
eli5 version: Different blockchain networks. TRC20 is Tron (lower fees),
ERC20 is Ethereum (more established). Like choosing shipping companies -
both deliver USDT but costs vary. btw https://learn.luntria.org/course
covers this well
```

**验证点**:
- ✅ 简化类比解释
- ✅ 推广链接作为学习资源
- ✅ 软文≤40字
- ✅ 链接与教育内容相关

## 🐛 故障排查

### 问题1: 推广率过低

**症状**: 测试显示A组推广率<50%

**排查**:
```python
# 检查配置
cat config/promotion_embedding.yaml | grep insertion_probability

# 预期输出:
# A: 0.70  (如果是0.40说明配置错误)
```

**解决**: 修改`promotion_embedding.yaml`中的概率值

### 问题2: 链接重复率高

**症状**: 链接多样性<5种

**排查**:
```python
# 检查链接池大小
cat config/promotion_embedding.yaml | grep -A 5 "group_1_luntria"

# 确认有多个分类(onboarding/tools/help_support等)
```

**解决**: 扩展链接池或调整冷却时间

### 问题3: 软文超长

**症状**: 软文长度>40字

**排查**:
```python
# 检查模板长度
cat config/promotion_embedding.yaml | grep -A 3 "natural_templates"

# 手动计算: "btw {link} has useful info" = ~29字符
```

**解决**: 使用更短的模板变体

### 问题4: 模块导入错误

**症状**: `ModuleNotFoundError: No module named 'src.content.link_promoter'`

**解决**:
```bash
# 确认文件存在
ls src/content/link_promoter.py

# 检查PYTHONPATH
export PYTHONPATH=$PWD:$PYTHONPATH  # Linux/Mac
set PYTHONPATH=%cd%;%PYTHONPATH%    # Windows
```

## 📈 监控指标

### 实时监控

运行测试后关注:

1. **推广覆盖率**: 实际推广数/总评论数
2. **链接点击率**: (未来扩展) 通过UTM参数跟踪
3. **Spam检测率**: 评论被删除/被举报比例
4. **质量评分**: 带链接评论的自然度分数

### 日志查看

```bash
# 查看推广日志
grep "Link inserted" logs/m4_content.log

# 查看推广统计
grep "promoted=True" logs/m4_content.log | wc -l
```

## 🎯 优化建议

### 短期优化 (本周)

1. **运行测试**: 执行`test_promotion_integration.py`验证基线
2. **调整概率**: 根据测试结果微调A/B/C组概率
3. **扩展模板**: 针对测试中机械感强的评论优化模板

### 中期优化 (下周)

1. **A/B测试**: 对比两组域名(luntria vs GitHub)效果
2. **链接权重**: 根据点击率调整不同分类权重
3. **多语言扩展**: 增加Persona的西语/中文口头禅

### 长期优化 (未来)

1. **Redis持久化**: 链接使用历史存储到Redis
2. **动态调整**: 根据推广效果自动调整概率
3. **UTM跟踪**: 添加utm参数追踪各链接转化率

## 📚 相关文档

- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - 完整实施文档
- [config/promotion_embedding.yaml](config/promotion_embedding.yaml) - 推广配置
- [data/templates/light_templates.yaml](data/templates/light_templates.yaml) - 模板定义
- [src/content/link_promoter.py](src/content/link_promoter.py) - 核心逻辑

## ✅ 检查清单

测试前确认:

- [ ] 所有配置文件已就位
- [ ] LinkPromoter模块可导入
- [ ] 链接池包含100+个URL
- [ ] 软文模板≤40字
- [ ] 测试数据集准备(15条)

测试后验证:

- [ ] 通过率≥75%
- [ ] A组推广率60-80%
- [ ] B组推广率30-50%
- [ ] C组推广率50-70%
- [ ] 链接多样性≥8种
- [ ] 自然度评分≥0.80
- [ ] 无软文超长(>40字)

---

**下一步**: 运行`python test_promotion_integration.py`开始测试 🚀
