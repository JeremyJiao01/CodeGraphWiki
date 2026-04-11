# P0 可靠性实施方案

> 按严重度和修复复杂度排序。每个条目包含：问题、位置、修复方案、验证方式。

---

## 一、增量更新可靠性（4个CRITICAL）

增量更新是最脆弱的模块——删除和插入分两步执行，没有事务，任何中间状态的失败都会导致图谱损坏。

### 1.1 force-push/rebase 后静默跳过（不触发重建）

**问题**：`git diff <old_commit> <new_commit>` 中 old_commit 被rebase删除后，git返回exit 128。系统返回 `(None, current_head)` 并静默跳过更新。图谱保持旧状态，用户毫不知情。

**位置**：
- `terrain/foundation/services/git_service.py:52-78`
- `terrain/entrypoints/mcp/server.py:177-182`

**修复方案**：
```python
# server.py — 检测到commit不存在时，触发full rebuild而非跳过
if changed_files is None:
    logger.warning(
        "last_indexed_commit {} not in git history — triggering full rebuild",
        (last_commit or "")[:8],
    )
    # 清除meta中的last_indexed_commit，触发下次full rebuild
    existing_meta.pop("last_indexed_commit", None)
    meta_file.write_text(json.dumps(existing_meta), encoding="utf-8")
    # 返回需要full rebuild的信号
    return "full_rebuild_needed"
```

**验证**：
```bash
# 测试用例：在已索引仓库上执行 git rebase + force push，然后触发incremental sync
# 期望：系统检测到commit丢失，触发full rebuild或明确通知用户
```

---

### 1.2 文件重命名导致调用关系断裂

**问题**：`git diff --name-only` 把重命名报告为"删除旧文件+新增新文件"。系统删除旧文件的节点，但指向旧模块的 CALLS 边不会被更新到新模块名。

**位置**：
- `terrain/foundation/services/git_service.py:53-74`（使用 `--name-only` 而非 `--name-status`）
- `terrain/domains/core/graph/incremental_updater.py:142-152`

**修复方案**：
```python
# git_service.py — 改用 --name-status -M 检测重命名
def get_changed_files(self, repo_path, last_commit):
    result = subprocess.run(
        ["git", "diff", "--name-status", "-M", last_commit, "HEAD"],
        capture_output=True, text=True, cwd=repo_path,
    )
    changes = []
    renames = {}  # old_path -> new_path
    for line in result.stdout.strip().split("\n"):
        parts = line.split("\t")
        status = parts[0]
        if status.startswith("R"):  # Rename
            renames[parts[1]] = parts[2]
            changes.append(parts[1])  # 旧路径（需删除）
            changes.append(parts[2])  # 新路径（需重建）
        else:
            changes.append(parts[-1])
    return changes, current_head, renames

# incremental_updater.py — 处理重命名：重定向调用关系
```

**验证**：
```bash
# 测试：git mv src/foo.py src/bar.py && commit，然后增量更新
# 期望：bar.py的函数正确索引，所有原来调用foo.py函数的CALLS边指向bar.py
```

---

### 1.3 超过50个文件变更时静默跳过

**问题**：`INCREMENTAL_FILE_LIMIT = 50`，超过此数量时直接跳过增量更新，不触发full rebuild，不更新meta.json，图谱保持旧状态。

**位置**：`terrain/entrypoints/mcp/server.py:187-192`

**修复方案**：
```python
if len(changed_files) > INCREMENTAL_FILE_LIMIT:
    logger.info(
        "Too many changed files ({} > {}), triggering full rebuild",
        len(changed_files), INCREMENTAL_FILE_LIMIT,
    )
    # 选项A：直接触发full rebuild
    # 选项B：清除last_indexed_commit，让下次tool调用时触发
    existing_meta.pop("last_indexed_commit", None)
    meta_file.write_text(json.dumps(existing_meta), encoding="utf-8")
    return "full_rebuild_needed"
```

**验证**：
```bash
# 测试：一次性修改60个文件并commit，触发增量同步
# 期望：系统触发full rebuild或明确通知用户需要重建
```

---

### 1.4 删除成功但插入失败时无法回滚

**问题**：增量更新先删除旧节点（flush_all提交），再重新解析和插入。如果插入步骤crash（解析器出错、OOM、磁盘满），已删除的节点永久丢失。

**位置**：`terrain/domains/core/graph/incremental_updater.py:96-182`

**修复方案**：
```python
# 方案A（推荐）：先插入新数据，再删除旧数据
# 这样即使插入失败，旧数据仍然存在（最坏情况是有重复，但MERGE会处理）

# 方案B：备份+恢复
def run_incremental_update(ingestor, ...):
    # 1. 导出即将删除的节点到内存备份
    backup = _backup_nodes_for_files(ingestor, all_rel_paths)
    try:
        # 2. 删除旧节点
        _delete_nodes_for_files(ingestor, all_rel_paths)
        ingestor.flush_all()
        # 3. 重新解析和插入
        graph_updater.process_files_subset(existing_files)
        ingestor.flush_all()
    except Exception:
        # 4. 恢复备份
        _restore_nodes(ingestor, backup)
        ingestor.flush_all()
        raise

# 方案C（最简单）：失败时清除meta，强制下次full rebuild
def run_incremental_update(ingestor, ...):
    try:
        _delete_nodes_for_files(ingestor, all_rel_paths)
        ingestor.flush_all()
        graph_updater.process_files_subset(existing_files)
        ingestor.flush_all()
    except Exception as e:
        logger.error("Incremental update failed, clearing index state: {}", e)
        # 清除meta中的commit记录，下次强制full rebuild
        _clear_last_indexed_commit(meta_path)
        raise
```

**验证**：
```bash
# 测试：mock解析器在特定文件上抛出异常，验证回滚行为
# 期望：图谱要么完整更新，要么恢复到更新前状态（或标记为需要full rebuild）
```

---

## 二、大代码库韧性（3个CRITICAL + 2个HIGH）

### 2.1 Kuzu flush_nodes 逐条插入（N+1问题）

**问题**：`flush_nodes()` 对每个节点执行单独的 MERGE 查询。10万函数 = 10万次数据库查询。这是索引速度的最大瓶颈。

**位置**：`terrain/foundation/services/kuzu_service.py:389-454`

**修复方案**：
```python
# 使用Kuzu的COPY FROM（批量导入）或参数化批量MERGE
def flush_nodes(self) -> None:
    for label, nodes in by_label.items():
        self._ensure_schema(label)
        if not nodes:
            continue
        # 批量MERGE：用UNWIND将列表展开为多行
        cypher = f"""
        UNWIND $batch AS props
        MERGE (n:{label} {{qualified_name: props.qualified_name}})
        SET n += props
        """
        # 分批执行，每批1000个
        for i in range(0, len(nodes), 1000):
            batch = nodes[i:i+1000]
            self._execute_with_retry(cypher, {"batch": batch})
```

**验证**：对比修复前后索引10万函数代码库的耗时和内存峰值。

---

### 2.2 AST缓存完整拷贝到列表

**问题**：`_process_function_calls()` 用 `list(self.ast_cache.items())` 把全部AST树拷贝到一个列表。10万文件 = 500MB-1GB单次分配。

**位置**：`terrain/domains/core/graph/graph_updater.py:483-496`

**修复方案**：
```python
# 直接迭代cache，不做拷贝。如果需要两次遍历，分开迭代。
def _process_function_calls(self) -> None:
    # Pass 1: 处理调用关系
    for file_path, (root_node, language) in self.ast_cache.items():
        self.factory.call_processor.process_calls_in_file(...)
    
    # Pass 2: 处理函数指针（仅C/C++）
    for file_path, (root_node, language) in self.ast_cache.items():
        if language in (cs.SupportedLanguage.C, cs.SupportedLanguage.CPP):
            ...
```

**验证**：在10万文件的代码库上，监控 `_process_function_calls()` 前后的内存变化。

---

### 2.3 嵌入向量全部驻留内存

**问题**：`MemoryVectorStore._records` 把所有嵌入向量保存在内存中。10万函数 × 2560维 × 4字节 = ~1GB常驻内存。搜索时对每个向量计算余弦相似度，O(n)。

**位置**：`terrain/domains/core/embedding/vector_store.py:161-331`

**修复方案（分阶段）**：
```
阶段1（短期）：加内存警告
- 当records数量>50000时，日志警告"大型向量库，建议使用外部向量数据库"

阶段2（中期）：分片 + mmap
- 将向量存储为numpy memmap文件，只在搜索时加载
- 使用faiss或annoy做近似最近邻，避免暴力搜索

阶段3（长期）：支持外部向量数据库
- 可选接入Qdrant/Milvus，大代码库自动切换
```

**验证**：对比修复前后10万函数代码库的常驻内存。

---

### 2.4 嵌入批处理累积不释放

**问题**：`records_to_store` 列表在整个嵌入过程中持续增长，直到所有函数处理完毕才写入。10万函数的嵌入结果全部积压在内存中。

**位置**：
- `terrain/domains/core/graph/graph_updater.py:498-589`
- `terrain/entrypoints/mcp/pipeline.py:1229-1270`

**修复方案**：
```python
# 每个batch处理完后立即写入vector_store，然后清空列表
for i in range(0, len(texts_to_embed), batch_size):
    batch_texts = texts_to_embed[i:i+batch_size]
    batch_info = node_info[i:i+batch_size]
    embeddings = embedder.embed_batch(batch_texts)
    records = [VectorRecord(...) for ...]
    vector_store.store_embeddings_batch(records)  # 立即写入
    # records自动释放（局部变量）
```

**验证**：监控嵌入过程中的内存曲线，应为锯齿形（周期性释放）而非单调递增。

---

### 2.5 AST缓存驱逐策略不足

**问题**：`BoundedASTCache` 内存超限时只驱逐10%，导致大代码库上频繁"解析→驱逐→重新解析"的thrashing。`sys.getsizeof()` 只测量Python对象头，不含tree-sitter AST的实际内存。

**位置**：`terrain/domains/core/graph/graph_updater.py:165-217`

**修复方案**：
```python
# 1. 驱逐比例从10%提高到25%
entries_to_remove = max(1, len(self.cache) // 4)

# 2. 使用粗略估算替代sys.getsizeof
# tree-sitter AST大约是源代码大小的10-20倍
def _estimate_ast_memory(self, root_node, source_len):
    return source_len * 15  # 粗略估算

# 3. 对于超大文件（>1MB源代码），不缓存AST
```

---

## 三、并发安全（3个HIGH）

### 3.1 KuzuIngestor引用计数非线程安全

**问题**：`_ref_count` 的递增/递减没有加锁。MCP server并发调用多个tool时，可能导致数据库连接提前关闭或永不关闭。

**位置**：`terrain/foundation/services/kuzu_service.py:104-105, 131-146`

**修复方案**：
```python
import threading

class KuzuIngestor:
    def __init__(self, db_path, ...):
        self._lock = threading.RLock()
        self._ref_count = 0
        ...
    
    def __enter__(self):
        with self._lock:
            self._ref_count += 1
            if self._ref_count == 1:
                self._db = kuzu.Database(str(self._db_path))
                self._conn = kuzu.Connection(self._db)
        return self
    
    def __exit__(self, *args):
        with self._lock:
            self._ref_count -= 1
            if self._ref_count == 0:
                self._conn.close()
                self._db.close()
```

**验证**：
```python
# 测试：10个线程同时 with ingestor 并执行查询
# 期望：无crash、无连接泄漏、无死锁
```

---

### 3.2 MCPToolsRegistry 共享状态无保护

**问题**：`_active_repo_path`、`_ingestor` 等实例变量在并发tool调用中被同时读写。一个tool在切换仓库，另一个tool在查询，结果不可预测。

**位置**：`terrain/entrypoints/mcp/tools.py:270-275, 305-352`

**修复方案**：
```python
class MCPToolsRegistry:
    def __init__(self, ...):
        self._state_lock = threading.RLock()
        ...
    
    def _load_services(self, artifact_dir):
        with self._state_lock:
            # 原有逻辑
            self._active_artifact_dir = artifact_dir
            self._ingestor = KuzuIngestor(...)
            ...
    
    def _set_active(self, artifact_dir):
        with self._state_lock:
            (self._workspace / "active.txt").write_text(...)
```

---

### 3.3 MCP link_repository 在Windows上因symlink崩溃

**问题**：MCP的 `_handle_link_repository()` 直接调用 `dst.symlink_to(src)`，Windows非开发者模式下必然失败。CLI中有fallback到copy的逻辑，但MCP中没有。

**位置**：
- `terrain/entrypoints/mcp/tools.py:1122`（无fallback）
- `terrain/entrypoints/cli/cli.py:1369`（有fallback）

**修复方案**：
```python
# tools.py — 复制CLI的fallback逻辑
try:
    dst.symlink_to(src)
except OSError:
    if src.is_dir():
        shutil.copytree(str(src), str(dst))
    else:
        shutil.copy2(str(src), str(dst))
```

---

## 四、跨平台路径（2个MEDIUM）

### 4.1 示例代码中硬编码 /tmp

**位置**：
- `terrain/examples/test_cli_demo.py:24`
- `terrain/examples/example_configuration.py:163`

**修复**：改用 `tempfile.gettempdir()`。

### 4.2 generate_wiki 硬编码 /usr/local/bin/mmdc

**位置**：`terrain/examples/generate_wiki.py:170`

**修复**：改用 `shutil.which("mmdc")` 并在找不到时明确报错。

---

## 实施顺序

按 "影响 × 修复速度" 排序，推荐每天修一个：

| 天数 | 修什么 | 为什么先修这个 |
|------|--------|--------------|
| Day 1 | 1.3 超50文件静默跳过 | 3行代码修复，影响大，最快见效 |
| Day 2 | 1.1 force-push后静默跳过 | 5行代码修复，常见场景 |
| Day 3 | 3.3 Windows symlink崩溃 | 5行代码，直接复制CLI逻辑 |
| Day 4 | 4.1+4.2 硬编码路径 | 简单替换，顺手清理 |
| Day 5 | 2.2 AST缓存拷贝 | 删一行代码，省1GB内存 |
| Day 6 | 2.4 嵌入批处理累积 | 中等改动，大代码库必修 |
| Day 7 | 1.4 增量更新无回滚 | 中等改动，选方案C最简单 |
| Day 8 | 3.1 Kuzu连接线程安全 | 加锁逻辑，需要仔细测试 |
| Day 9 | 3.2 Registry共享状态 | 同上 |
| Day 10 | 1.2 文件重命名检测 | 需改git diff调用方式 |
| Day 11 | 2.1 Kuzu N+1查询 | 最复杂但收益最大 |
| Day 12 | 2.5 AST缓存驱逐 | 调参+估算逻辑 |
| Day 13 | 2.3 向量内存警告 | 阶段1，先加警告 |

**每个修复必须附带**：
1. 一个复现问题的测试（先写测试，再改代码）
2. 一条changelog条目
3. `dep_check.py` 零违规
