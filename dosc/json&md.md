# JSON vs Markdown：对未优化 Agent 系统的影响

**不一样。** 差异主要体现在以下几个维度：

## 1. Token 效率

```json
{"name": "get_user", "params": {"id": 123}, "return": "User"}
```
```markdown
- **name**: get_user
- **params**: id → 123  
- **return**: User
```

- JSON 的 `{}`, `""`, `:` 等结构符号消耗大量 token
- Markdown 更接近自然语言，token 密度更高（同样信息量用更少 token）
- **在大型代码库场景下，这直接影响 context window 的利用率**

## 2. LLM 的"原生亲和度"

LLM 训练语料中 Markdown 占比远高于结构化 JSON：

| 格式 | 训练语料来源 | LLM 理解能力 |
|------|-------------|-------------|
| Markdown | GitHub README、文档、博客、wiki | 极强，几乎是"母语" |
| JSON | API 响应、配置文件、数据集 | 强，但容易在深层嵌套时出错 |

## 3. 具体差异表现

**JSON 的问题：**
- 深层嵌套（>3层）时 LLM 容易丢失层级关系
- 长数组中间的元素容易被"遗忘"（lost in the middle 效应）
- 严格语法要求导致 LLM 生成时容易出格式错误（漏逗号、多逗号）
- 大段 JSON 作为 context 注入时，LLM 倾向于跳读

**Markdown 的优势：**
- 标题层级（`#`, `##`, `###`）天然形成语义分块，LLM 更容易定位信息
- 更适合混合内容（代码 + 描述 + 关系说明）
- LLM 生成 Markdown 几乎不会出格式错误

## 4. 但 JSON 也有不可替代的场景

- **工具调用的输入输出**：需要程序解析时，JSON 是刚需
- **精确结构化数据**：类型、枚举值等需要无歧义表示
- **机器间通信**：Agent 与外部 API 交互

## 实践结论

对于未做特定优化的 Agent 系统：

```
知识存储 / 上下文注入 → 优先 Markdown
工具调用 / 结构化交互 → 必须 JSON
混合场景 → Markdown 包裹 JSON 片段
```

一个常见的有效模式是：

```markdown
## 模块：auth

认证模块，处理用户登录和 token 管理。

### 核心函数
- `authenticate(user, password)` → `Token`
- `refresh_token(token)` → `Token`

### 调用关系
auth.authenticate → db.query_user → cache.get_session
```

这比等价的 JSON 对 LLM 更友好，同时人类可读性也更好。

**你的项目如果在向 Agent 注入知识图谱查询结果时，将 JSON 转为 Markdown 格式，大概率能提升定位准确率。** 需要我看看你项目中目前的格式处理方式吗？