# 软件产品维护与开发指南

> 基于 Claude Code v2.1.69–v2.1.101（27个版本、738条 changelog）的逆向工程分析。
> 这不是猜测——每个结论都有数据支撑。

---

## 一、核心发现：产品感的来源

Claude Code 给用户的感觉是「每天都在变好」。拆开数据看：

```
738 条 changelog 条目的分布：

  Fixed:    494 条 (66%)    ← 三分之二的工作是修bug
  Added:    115 条 (15%)    ← 新功能只占六分之一
  Improved: 109 条 (14%)    ← 打磨已有功能
  Changed:   16 条  (2%)
  Removed:    4 条  (0%)
```

**结论：产品感不来自新功能的数量，来自已有功能在所有场景下都可靠。**

用户不会记住你加了什么新功能，但会记住「上次那个bug终于修了」「错误信息终于能看懂了」「Windows上终于不崩了」。

---

## 二、开发工作的六个层次

按 Claude Code 的实际工作分配，产品维护分为六个层次，优先级从高到低：

### 第1层：修复（66%的工作量）

494条 Fix 的精细分类：

| 类别 | 占比 | 含义 |
|------|------|------|
| 会话/状态恢复 | 24% | 用户最在意的：我的工作别丢 |
| 插件/扩展兼容 | 16% | 生态系统的可靠性 |
| 平台/终端兼容 | 16% | Windows、各种终端模拟器、云平台 |
| 权限/认证 | 16% | 安全相关，不能有任何侥幸 |
| 渲染/UI | 10% | 视觉层面的正确性 |
| 键盘/输入 | 10% | 基础交互的可靠性 |
| 配置/设置 | 9% | 用户自定义不能炸 |
| 内存/性能 | 7% | 长时间运行不退化 |
| 工作区/Git | 6% | 代码操作的安全性 |
| 沙箱/安全 | 5% | 防止恶意行为 |
| 重试/超时 | 4% | 网络层面的韧性 |

**规律**：修复的优先级 = 用户数据安全 > 功能正确性 > 平台兼容性 > 交互体验 > 性能。

#### 怎么做

**每个 bug 修复的标准流程：**

1. **写复现测试** — 在修代码之前，先写一个测试证明 bug 存在
2. **最小修复** — 只改必须改的代码，不顺手重构周围的东西
3. **回归保护** — 测试自动进入 CI，永久防止复发
4. **changelog 条目** — 用用户能理解的语言描述，不用内部术语

**写 Fixed 条目的格式：**

```
好：Fixed `--resume` losing conversation context on large sessions
    when the loader anchored on a dead-end branch
    ↑ 描述了什么坏了、在什么条件下、为什么

坏：Fixed a bug in the resume feature
    ↑ 用户读了和没读一样
```

**公式：`Fixed [什么功能] [出了什么问题] [在什么条件下触发]`**

---

### 第2层：改善（14%的工作量）

109条 Improved 的分类：

| 类别 | 数量 | 含义 |
|------|------|------|
| UX/显示优化 | 31 | 信息展示更清晰 |
| 性能提升 | 20 | 更快、更省内存 |
| 错误信息改善 | 19 | 用户能自己诊断问题 |
| 其他 | 39 | 各种细节打磨 |

#### 怎么做

**改善的三个方向：**

**方向A：让错误可自诊断**
```
之前：Error: connection failed
之后：Error: Bedrock SigV4 authentication failed with 403.
      Check that AWS_BEARER_TOKEN_BEDROCK is set and not expired.
      Run `claude doctor` to diagnose.
```

每条错误信息包含：什么失败了 + 为什么 + 怎么修。

**方向B：让操作有反馈**
```
之前：（索引中……长时间无输出）
之后：Indexing: 3,247/10,000 functions (32%) — ETA 45s
```

任何超过2秒的操作都需要进度反馈。

**方向C：让默认值更聪明**
```
之前：用户需要手动配置每个选项
之后：自动检测环境并应用合理默认值，只在需要时提问
```

Claude Code 的 Bedrock/Vertex setup wizard 就是这个思路——不让用户读文档，引导他走完配置。

**写 Improved 条目的格式：**

```
好：Improved rate-limit retry messages to show which limit was hit
    and when it resets instead of an opaque seconds countdown
    ↑ 对比了改善前后的差异

坏：Improved error handling
    ↑ 没有信息量
```

**公式：`Improved [什么功能] to [现在怎样] instead of [以前怎样]`**

---

### 第3层：新功能（15%的工作量）

115条 Added 的分类：

| 类别 | 数量 | 含义 |
|------|------|------|
| 配置/设置项 | 36 | 给高级用户更多控制 |
| UI功能/模式 | 28 | 新的交互方式 |
| 新工具/命令 | 23 | 核心能力扩展 |
| 平台支持 | 10 | 新的云平台/认证方式 |
| Setup/向导 | 5 | 降低上手门槛 |

#### 怎么做

**新功能的筛选标准（必须满足至少2条）：**

1. 有明确的用户操作序列（不是抽象需求）
2. 现有功能无法通过组合实现
3. 失败时不会破坏用户数据
4. 能在一个 PR 内完成（跨层不超过2层）

**新功能的开发节奏：**

```
每个版本最多 1-2 个新功能
其余全是修复和改善
```

Claude Code 27个版本、115条 Added，平均每个版本 4.3 条新增。但其中 36 条是配置项（一行代码的事），真正的「新功能」每个版本只有 1-2 个。

**写 Added 条目的格式：**

```
好：Added Monitor tool for streaming events from background scripts

好：Added per-model and cache-hit breakdown to `/cost` for subscription users

坏：Added new feature
```

**公式：`Added [什么东西] for [什么用途/什么用户]`**

---

### 第4层：变更（2%的工作量）

16条 Changed——极少的 breaking change。

#### 怎么做

- 变更默认行为时，提供 opt-out 机制（环境变量或配置项）
- 重命名时，保留旧名称的兼容层至少一个版本周期
- 在 changelog 中明确标注影响范围

---

### 第5层：移除（<1%的工作量）

仅4条 Removed。删除功能是最后的选择。

#### 怎么做

- 先标记为 deprecated（至少一个版本周期）
- 确认无用户依赖后才真正移除
- 提供迁移路径

---

### 第6层：安全（贯穿所有层次）

57条安全相关修复单独统计，因为它们横跨 Fixed 和 Added：

- 命令注入修复
- 权限绕过修复
- 沙箱逃逸修复
- 新的安全配置项

#### 怎么做

- 安全修复的优先级高于一切——发现即修，不排队
- 安全相关的 changelog 条目要描述清楚影响范围，但不泄露利用细节
- 每次安全修复都伴随防御性测试

---

## 三、发布节奏

### Claude Code 的实际节奏

```
27个版本 / 36天 = 平均 1.3天一个版本
每版平均 32 条条目（从一行配置项到复杂安全修复）
```

### 怎么做

**日常开发节奏（适用于小团队/个人项目）：**

```
每天的时间分配：
├── 50% — 修复 + 改善（P0/P1）
│   ├── 修一个 bug（带回归测试）
│   └── 改善一条错误信息 或 优化一个性能瓶颈
├── 30% — 平台兼容 + 场景覆盖（P2）
│   └── 让功能在更多环境/输入下正确工作
└── 20% — 新功能（P3）
    └── 推进一个新功能的一个切片
```

**版本发布策略：**

| 场景 | 发布时机 |
|------|---------|
| 安全修复 | 立即发布，不等其他改动 |
| 功能性 bug 修复积累 3-5 个 | 打一个 patch 版本 |
| 新功能完成 | 打一个 minor 版本 |
| Breaking change | 打一个 major 版本，附迁移指南 |

---

## 四、Changelog 写作规范

### 分类标签

```markdown
## [x.y.z] — YYYY-MM-DD

### Added      ← 全新功能、新命令、新配置项
### Fixed      ← Bug 修复（用户可感知的行为修正）
### Improved   ← 已有功能的增强（更快、更清晰、更智能）
### Changed    ← 行为变更（可能影响已有用户）
### Removed    ← 功能移除
### Security   ← 安全修复（单独列出，高优先级）
```

### 写作模板

每条 changelog 条目遵循：

```
[动词] [具体功能] [做了什么改变] [在什么条件下/为什么重要]
```

| 动词 | 用于 | 示例 |
|------|------|------|
| Added | 新功能 | Added `/team-onboarding` command to generate a teammate ramp-up guide |
| Fixed | Bug | Fixed `--resume` losing context on large sessions when loader anchored on dead-end branch |
| Improved | 增强 | Improved rate-limit retry messages to show which limit was hit instead of opaque countdown |
| Changed | 变更 | Changed default effort level from medium to high for API-key users |
| Removed | 移除 | Removed `/vim` command (toggle via `/config` → Editor mode) |

### 反面示例

```
❌ Fixed a bug                          → 没有任何信息量
❌ Improved performance                 → 哪里的性能？改善了多少？
❌ Added new feature for better UX      → 什么功能？什么UX？
❌ Updated dependencies                 → 更新了什么？为什么？有影响吗？
❌ Various bug fixes and improvements   → 这不是 changelog，这是摆烂
```

---

## 五、质量指标

不用功能数量衡量产品健康度。用这些指标：

### 可靠性指标

| 指标 | 怎么看 | 目标 |
|------|--------|------|
| 核心路径成功率 | 主要功能在标准输入下的通过率 | > 99.9% |
| 边界条件覆盖 | 每个公开接口至少一个「翻车场景」测试 | 100% |
| 回归测试全绿 | CI 全量测试通过 | 100% |
| 安全修复响应时间 | 从发现到修复的小时数 | < 24h |

### 可诊断性指标

| 指标 | 怎么看 | 目标 |
|------|--------|------|
| 错误信息质量 | 每条错误包含 what / why / how-to-fix | 100% |
| 静默失败数量 | `except: pass` 或 log-and-continue 的数量 | 趋近 0 |
| 诊断工具覆盖 | 用户能否自行排查常见问题 | 覆盖 top 10 问题 |

### 兼容性指标

| 指标 | 怎么看 | 目标 |
|------|--------|------|
| 平台覆盖 | 在所有声明支持的平台上测试通过 | 100% |
| 向后兼容 | 旧版本数据/配置能被新版本正确处理 | 100% |
| 迁移路径 | 每个 breaking change 有明确的迁移指南 | 100% |

---

## 六、从 Claude Code 提取的具体模式

### 模式1：Setup Wizard 模式

Claude Code 为 Bedrock、Vertex、OAuth 等复杂配置都做了交互式向导。

**适用场景**：任何需要用户配置超过3个参数的场景。

**做法**：
- 自动检测环境（已有凭证、已有配置文件）
- 逐步引导，每步只问一个问题
- 每步验证输入，失败时解释原因并允许重试
- 完成后显示汇总和下一步操作

### 模式2：渐进式暴露

Claude Code 有 brief mode、focus mode、effort level——同一个功能对不同用户暴露不同深度。

**做法**：
- 默认行为覆盖80%的用户需求
- 高级选项通过配置项/flag暴露，不污染主界面
- 新增配置项时，默认值必须是「不改变现有行为」的那个

### 模式3：优雅降级

Claude Code 在 ripgrep 二进制损坏时自动 fallback 到系统 rg，在 streaming 失败时 fallback 到非 streaming。

**做法**：
- 主路径失败时，尝试备选方案
- 降级时告知用户（log warning），不静默
- 降级后的功能子集必须是可用的，不能半死不活

### 模式4：Session 韧性

Claude Code 24% 的 bug 修复都和会话恢复相关——这是用户最在意的。

**适用场景**：任何有持久化状态的功能。

**做法**：
- 中断后能恢复到最后已知的好状态
- 状态文件损坏时能检测并重建，而非 crash
- 状态迁移有版本号，旧版本数据能被新版本读取

### 模式5：权限最小化

Claude Code 大量工作在精确控制什么操作需要用户确认、什么可以自动执行。

**做法**：
- 读操作默认允许，写操作默认询问
- 权限规则支持通配符，但 deny 永远优先于 allow
- 权限变更实时生效，不需要重启

---

## 七、检查清单

每次发布前过一遍：

```
□ 所有新代码都有测试
□ 所有 bug 修复都有回归测试
□ 所有公开接口的错误信息包含 what/why/how-to-fix
□ 没有新增的静默失败（log-and-continue 需要明确理由）
□ changelog 条目用用户语言写成，遵循动词+功能+变化+条件格式
□ 没有 breaking change；如有，提供迁移路径和 opt-out
□ CI 全绿（pre-existing failures 不算）
□ 在所有声明支持的平台上验证过
```
