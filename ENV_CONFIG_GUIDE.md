# 环境配置指南

**文件位置**: `D:\reddit-comment-system\.env`

⚠️ **重要**：`.env`文件已从模板复制，你需要填入真实凭据才能进行端到端测试。

---

## 🔑 必须配置的凭据

### 1. OpenAI API密钥

**位置**: 第9行

```bash
AI__API_KEY=sk-your-api-key-here
```

**获取方式**:
1. 访问 https://platform.openai.com/api-keys
2. 创建新的API密钥
3. 复制完整密钥（格式：`sk-proj-...`或`sk-...`）
4. 粘贴到`.env`文件第9行

**示例**:
```bash
AI__API_KEY=sk-proj-abcd1234efgh5678ijkl9012mnop3456qrst7890uvwx
```

---

### 2. Reddit应用凭据

**位置**: 第16-17行

```bash
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
```

**获取方式**:
1. 访问 https://www.reddit.com/prefs/apps
2. 点击"create another app..."或"are you a developer? create an app..."
3. 填写信息：
   - **name**: Reddit Comment Bot（任意名称）
   - **App type**: 选择 **script**
   - **description**: 自动评论测试（可选）
   - **about url**: 留空
   - **redirect uri**: http://localhost:8080（必填但不使用）
4. 点击"create app"
5. 记录凭据：
   - **client_id**: 应用名称下方的一串字符（14字符）
   - **client_secret**: "secret"标签后的字符串

**示例**:
```bash
REDDIT_CLIENT_ID=AbCd1234EfGh56
REDDIT_CLIENT_SECRET=aBcDeFgHiJkLmNoPqRsTuVwXyZ1234567890
```

---

### 3. 养号系统地址（可选）

**位置**: 第2行

```bash
YANGHAO__BASE_URL=http://localhost:8000
```

**说明**:
- 如果养号系统运行在本地8000端口，保持默认即可
- 如果运行在其他地址，修改为实际URL（例如：`http://192.168.1.100:8000`）

**验证养号系统可用**:
```bash
# 方法1：浏览器访问
http://localhost:8000/docs

# 方法2：命令行测试
curl http://localhost:8000/health
```

---

## 📝 配置步骤

### 第1步：编辑.env文件

```bash
# Windows
notepad .env

# 或使用VS Code
code .env
```

### 第2步：填入真实凭据

修改以下3行：
```bash
# 第9行 - OpenAI API密钥
AI__API_KEY=sk-proj-你的真实密钥

# 第16行 - Reddit Client ID
REDDIT_CLIENT_ID=你的14字符ID

# 第17行 - Reddit Client Secret
REDDIT_CLIENT_SECRET=你的Secret字符串
```

### 第3步：保存文件

确保保存后`.env`文件包含真实凭据。

---

## ✅ 验证配置

运行以下命令验证配置是否正确：

```bash
# 验证环境变量加载
cd /d/reddit-comment-system
python -c "from src.core.config import Settings; s=Settings(); print('AI Provider:', s.ai.provider); print('Reddit ID:', s.reddit.client_id[:4]+'...')"
```

**预期输出**:
```
AI Provider: openai
Reddit ID: AbCd...
```

---

## 🔒 安全提醒

⚠️ **`.env`文件已添加到`.gitignore`**，不会被提交到Git仓库

⚠️ **切勿分享**你的API密钥和Secret，这些凭据可以控制你的账号和费用

⚠️ **定期轮换**API密钥，特别是怀疑泄露时立即撤销

---

## 🚀 完成配置后

配置完成后，继续执行端到端测试：

```bash
# 启动Docker服务
cd docker
docker-compose up -d

# 运行端到端测试脚本（待创建）
python scripts/test_e2e_single_account.py
```

---

**配置完成？请告诉我，我会继续下一步：创建测试分支和编写测试脚本。**
