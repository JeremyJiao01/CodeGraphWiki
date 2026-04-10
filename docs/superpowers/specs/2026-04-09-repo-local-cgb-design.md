# Repo-Local `.terrain/` Artifact Directory

**Date:** 2026-04-09
**Status:** Approved

## Problem

团队共享由 Terrain 生成的数据库，DB 随代码提交到远程仓库。当前 Terrain 只在 workspace（`~/.terrain-ai/`）中查找 artifact，团队成员 clone 后无法直接使用仓库内的 DB。

## Solution

支持仓库根目录下的 `.terrain/` 目录作为优先 artifact 来源。优先级：`{repo_path}/.terrain/` > workspace `{name}_{hash}/`。

## `.terrain/` 目录结构

平铺，与 workspace 中 `{name}_{hash}/` 内容一致，去掉外层 hash 目录：

```
{repo_root}/.terrain/
├── meta.json
├── graph.db
├── vectors.pkl
├── api_docs/
│   ├── index.md
│   └── {module}/
└── wiki/
    ├── index.md
    └── wiki/
```

`meta.json` 保持相同 schema，`_load_services()` 无需改动。

## 改动点

### 1. MCP 侧：`tools.py` `_try_auto_load()`

从 workspace `active.txt` 读取 artifact_dir → 读 `meta.json` 获得 `repo_path` → **新增**：检查 `{repo_path}/.terrain/graph.db` 是否存在，存在则替换 artifact_dir 为 `{repo_path}/.terrain/`。

### 2. CLI 侧：路径解析

CLI 命令（`terrain status` 等）解析 active artifact_dir 后，同样优先检测 `{repo_path}/.terrain/`。

### 3. CLI 侧：`terrain index` 输出目标选择

索引完成后，使用 `_select_menu()`（与 `cgb config` 一致的 tree-style UI）让用户选择输出目标：

```
  ● Output destination
  │  Use ↑↓ to navigate, Enter to confirm
  │
  │  › .terrain/  (repo-local, shareable via git)
  │    ~/.terrain-ai/repo_abc123/  (workspace)
```

- 默认高亮 `.terrain/`
- 选 `.terrain/`：产物直接写入 `{repo_root}/.terrain/`，workspace 中仅保留精简 `meta.json`（含 `repo_path`、`steps`），确保 `_try_auto_load()` 发现链正常工作
- 选 workspace：行为不变
- 支持 `--output local` / `--output workspace` 参数跳过交互

### 4. `pipeline.py` 产物写入

当选择 `.terrain/` 时，直接平铺写入 `{repo_root}/.terrain/`。

## 不变的部分

- `_load_services(artifact_dir)` — 只接收 artifact_dir 并加载，不变
- `meta.json` schema — 保持一致
- `artifact_dir_for()` — 仍用于 workspace 场景
- `.env` 配置管理 — 仍在 workspace 中

## Windows 兼容性

- 统一使用 `pathlib.Path`，不硬编码路径分隔符
- `.terrain/` 模式下产物直接写入，不涉及 symlink
- Windows 上 `.` 开头目录名合法，git 正常跟踪
- `meta.json` 中路径使用 `as_posix()` 存储，与现有一致

## 影响范围

| 文件 | 改动类型 |
|------|----------|
| `entrypoints/mcp/tools.py` | `_try_auto_load()` 新增 `.terrain/` 优先检测 |
| `entrypoints/cli/cli.py` | CLI 路径解析新增 `.terrain/` 优先检测；`terrain index` 新增输出目标选择 |
| `entrypoints/mcp/pipeline.py` | 产物写入支持 `.terrain/` 目标路径 |
