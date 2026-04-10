# Repo-Local `.terrain/` Artifact Directory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Support a repo-local `.terrain/` directory as the preferred artifact source, so teams can share indexed databases via git without extra configuration.

**Architecture:** Add a priority-based artifact resolution layer: when `repo_path` is known, check `{repo_path}/.terrain/graph.db` first; if it exists, use `.terrain/` as the artifact directory, otherwise fall back to the workspace `{name}_{hash}/` directory. For `terrain index`, add a `_select_menu()` prompt letting users choose output destination.

**Tech Stack:** Python 3.11+, pathlib, existing CLI UI primitives (`_select_menu`, `_T_DOT`, `_T_SIDE`, etc.)

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `terrain/entrypoints/mcp/tools.py` | Modify | `_try_auto_load()` adds `.terrain/` priority check |
| `terrain/entrypoints/cli/cli.py` | Modify | `_load_repos()` adds `.terrain/` resolution; `cmd_index()` adds output destination prompt |
| `terrain/entrypoints/mcp/pipeline.py` | Modify | `save_meta()` unchanged, but `cmd_index` will pass `.terrain/` path as `artifact_dir` |
| `tests/entrypoints/test_repo_local_cgb.py` | Create | All tests for `.terrain/` discovery, priority, and fallback |

---

### Task 1: Add `.terrain/` priority resolution helper

**Files:**
- Create: `tests/entrypoints/test_repo_local_cgb.py`
- Modify: `terrain/entrypoints/mcp/tools.py:185-197`

This task adds a shared helper function `_resolve_artifact_dir()` and the tests for it.

- [ ] **Step 1: Write failing tests for `.terrain/` resolution logic**

Create `tests/entrypoints/test_repo_local_cgb.py`:

```python
"""Tests for repo-local .terrain/ artifact directory resolution."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def _make_artifact_dir(path: Path, repo_path: str = "/fake/repo") -> None:
    """Create a minimal artifact dir with meta.json and graph.db."""
    path.mkdir(parents=True, exist_ok=True)
    (path / "graph.db").write_bytes(b"fake")
    (path / "meta.json").write_text(
        json.dumps({"repo_path": repo_path, "repo_name": "repo", "steps": {"graph": True}}),
        encoding="utf-8",
    )


class TestResolveArtifactDir:
    """_resolve_artifact_dir prefers {repo_path}/.terrain/ over workspace artifact dir."""

    def test_prefers_local_cgb_when_exists(self, tmp_path: Path):
        """When .terrain/graph.db exists under repo_path, return .terrain/ dir."""
        from terrain.entrypoints.mcp.tools import _resolve_artifact_dir

        repo = tmp_path / "myrepo"
        repo.mkdir()
        local_cgb = repo / ".cgb"
        _make_artifact_dir(local_cgb, repo_path=repo.as_posix())

        ws_artifact = tmp_path / "workspace" / "myrepo_abc123"
        _make_artifact_dir(ws_artifact, repo_path=repo.as_posix())

        result = _resolve_artifact_dir(ws_artifact)
        assert result == local_cgb

    def test_falls_back_to_workspace_when_no_local_cgb(self, tmp_path: Path):
        """When .terrain/ does not exist, return the original workspace artifact dir."""
        from terrain.entrypoints.mcp.tools import _resolve_artifact_dir

        repo = tmp_path / "myrepo"
        repo.mkdir()

        ws_artifact = tmp_path / "workspace" / "myrepo_abc123"
        _make_artifact_dir(ws_artifact, repo_path=repo.as_posix())

        result = _resolve_artifact_dir(ws_artifact)
        assert result == ws_artifact

    def test_falls_back_when_local_cgb_has_no_graph_db(self, tmp_path: Path):
        """When .terrain/ exists but has no graph.db, return workspace dir."""
        from terrain.entrypoints.mcp.tools import _resolve_artifact_dir

        repo = tmp_path / "myrepo"
        local_cgb = repo / ".cgb"
        local_cgb.mkdir(parents=True)
        (local_cgb / "meta.json").write_text("{}", encoding="utf-8")
        # No graph.db

        ws_artifact = tmp_path / "workspace" / "myrepo_abc123"
        _make_artifact_dir(ws_artifact, repo_path=repo.as_posix())

        result = _resolve_artifact_dir(ws_artifact)
        assert result == ws_artifact

    def test_falls_back_when_repo_path_missing_from_meta(self, tmp_path: Path):
        """When meta.json has no repo_path, return workspace dir as-is."""
        from terrain.entrypoints.mcp.tools import _resolve_artifact_dir

        ws_artifact = tmp_path / "workspace" / "myrepo_abc123"
        ws_artifact.mkdir(parents=True)
        (ws_artifact / "graph.db").write_bytes(b"fake")
        (ws_artifact / "meta.json").write_text(
            json.dumps({"repo_name": "repo"}), encoding="utf-8"
        )

        result = _resolve_artifact_dir(ws_artifact)
        assert result == ws_artifact

    def test_falls_back_when_repo_path_does_not_exist(self, tmp_path: Path):
        """When repo_path points to a non-existent directory, return workspace dir."""
        from terrain.entrypoints.mcp.tools import _resolve_artifact_dir

        ws_artifact = tmp_path / "workspace" / "myrepo_abc123"
        _make_artifact_dir(ws_artifact, repo_path="/nonexistent/path")

        result = _resolve_artifact_dir(ws_artifact)
        assert result == ws_artifact
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/entrypoints/test_repo_local_cgb.py -v`
Expected: FAIL — `_resolve_artifact_dir` does not exist yet.

- [ ] **Step 3: Implement `_resolve_artifact_dir()` in tools.py**

Add the following function in `terrain/entrypoints/mcp/tools.py` right before `class MCPToolsRegistry` (around line 170):

```python
def _resolve_artifact_dir(ws_artifact_dir: Path) -> Path:
    """Return the best artifact directory: prefer {repo_path}/.terrain/ over workspace.

    Reads meta.json from *ws_artifact_dir* to discover ``repo_path``, then
    checks whether ``{repo_path}/.terrain/graph.db`` exists.  If it does, return
    the ``.terrain/`` path; otherwise return *ws_artifact_dir* unchanged.
    """
    meta_file = ws_artifact_dir / "meta.json"
    if not meta_file.exists():
        return ws_artifact_dir
    try:
        meta = json.loads(meta_file.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError):
        return ws_artifact_dir

    repo_path_str = meta.get("repo_path")
    if not repo_path_str:
        return ws_artifact_dir

    repo_path = Path(repo_path_str)
    if not repo_path.is_dir():
        return ws_artifact_dir

    local_cgb = repo_path / ".cgb"
    if (local_cgb / "graph.db").exists():
        return local_cgb

    return ws_artifact_dir
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/entrypoints/test_repo_local_cgb.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/entrypoints/test_repo_local_cgb.py terrain/entrypoints/mcp/tools.py
git commit -m "feat: add _resolve_artifact_dir helper for .terrain/ priority resolution"
```

---

### Task 2: Wire `.terrain/` resolution into MCP `_try_auto_load()`

**Files:**
- Modify: `terrain/entrypoints/mcp/tools.py:185-197`
- Modify: `tests/entrypoints/test_repo_local_cgb.py`

- [ ] **Step 1: Write failing test for MCP auto-load with `.terrain/`**

Append to `tests/entrypoints/test_repo_local_cgb.py`:

```python
from unittest.mock import patch, MagicMock


class TestMCPAutoLoadWithLocalCgb:
    """MCPToolsRegistry._try_auto_load() should prefer .terrain/ when available."""

    def test_auto_load_uses_local_cgb(self, tmp_path: Path):
        """When active repo has .terrain/, _try_auto_load passes .terrain/ to _load_services."""
        from terrain.entrypoints.mcp.tools import MCPToolsRegistry

        ws = tmp_path / "workspace"
        ws.mkdir()

        # Set up workspace artifact dir with meta pointing to repo
        repo = tmp_path / "myrepo"
        repo.mkdir()
        ws_artifact = ws / "myrepo_abc123"
        _make_artifact_dir(ws_artifact, repo_path=repo.as_posix())

        # Set up .terrain/ in repo
        local_cgb = repo / ".cgb"
        _make_artifact_dir(local_cgb, repo_path=repo.as_posix())

        # Write active.txt
        (ws / "active.txt").write_text("myrepo_abc123", encoding="utf-8")

        # Patch _load_services to capture which artifact_dir it receives
        with patch.object(MCPToolsRegistry, "_load_services") as mock_load:
            registry = MCPToolsRegistry(workspace=ws)
            mock_load.assert_called_once_with(local_cgb)

    def test_auto_load_falls_back_to_workspace(self, tmp_path: Path):
        """When no .terrain/, _try_auto_load passes workspace artifact dir."""
        from terrain.entrypoints.mcp.tools import MCPToolsRegistry

        ws = tmp_path / "workspace"
        ws.mkdir()

        repo = tmp_path / "myrepo"
        repo.mkdir()
        ws_artifact = ws / "myrepo_abc123"
        _make_artifact_dir(ws_artifact, repo_path=repo.as_posix())

        (ws / "active.txt").write_text("myrepo_abc123", encoding="utf-8")

        with patch.object(MCPToolsRegistry, "_load_services") as mock_load:
            registry = MCPToolsRegistry(workspace=ws)
            mock_load.assert_called_once_with(ws_artifact)
```

- [ ] **Step 2: Run tests to verify new tests fail**

Run: `python -m pytest tests/entrypoints/test_repo_local_cgb.py::TestMCPAutoLoadWithLocalCgb -v`
Expected: `test_auto_load_uses_local_cgb` FAILS (still passes workspace dir).

- [ ] **Step 3: Update `_try_auto_load()` to use `_resolve_artifact_dir()`**

In `terrain/entrypoints/mcp/tools.py`, modify `_try_auto_load()` (lines 185-197):

Replace:
```python
    def _try_auto_load(self) -> None:
        """Try to load the last active repo from workspace."""
        active_file = self._workspace / "active.txt"
        if not active_file.exists():
            return
        artifact_dir_name = active_file.read_text(encoding="utf-8", errors="replace").strip()
        artifact_dir = self._workspace / artifact_dir_name
        if artifact_dir.exists():
            try:
                self._load_services(artifact_dir)
                logger.info(f"Auto-loaded repo from: {artifact_dir}")
            except Exception as exc:
                logger.warning(f"Graph/LLM services unavailable: {exc}")
```

With:
```python
    def _try_auto_load(self) -> None:
        """Try to load the last active repo from workspace."""
        active_file = self._workspace / "active.txt"
        if not active_file.exists():
            return
        artifact_dir_name = active_file.read_text(encoding="utf-8", errors="replace").strip()
        artifact_dir = self._workspace / artifact_dir_name
        if artifact_dir.exists():
            artifact_dir = _resolve_artifact_dir(artifact_dir)
            try:
                self._load_services(artifact_dir)
                logger.info(f"Auto-loaded repo from: {artifact_dir}")
            except Exception as exc:
                logger.warning(f"Graph/LLM services unavailable: {exc}")
```

The only change is adding `artifact_dir = _resolve_artifact_dir(artifact_dir)` before `_load_services`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/entrypoints/test_repo_local_cgb.py -v`
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add terrain/entrypoints/mcp/tools.py tests/entrypoints/test_repo_local_cgb.py
git commit -m "feat: MCP _try_auto_load prefers repo-local .terrain/ over workspace"
```

---

### Task 3: Wire `.terrain/` resolution into CLI path resolution

**Files:**
- Modify: `terrain/entrypoints/cli/cli.py:385-410`
- Modify: `tests/entrypoints/test_repo_local_cgb.py`

- [ ] **Step 1: Write failing test for CLI `_load_repos()` with `.terrain/`**

Append to `tests/entrypoints/test_repo_local_cgb.py`:

```python
class TestCLILoadReposWithLocalCgb:
    """CLI _load_repos() should resolve .terrain/ for repos that have it."""

    def test_load_repos_resolves_local_cgb(self, tmp_path: Path):
        """When a repo has .terrain/, _load_repos returns .terrain/ as artifact_dir."""
        from terrain.entrypoints.cli.cli import _load_repos

        ws = tmp_path / "workspace"
        ws.mkdir()

        repo = tmp_path / "myrepo"
        repo.mkdir()
        ws_artifact = ws / "myrepo_abc123"
        _make_artifact_dir(ws_artifact, repo_path=repo.as_posix())

        local_cgb = repo / ".cgb"
        _make_artifact_dir(local_cgb, repo_path=repo.as_posix())

        (ws / "active.txt").write_text("myrepo_abc123", encoding="utf-8")

        repos = _load_repos(ws)
        assert len(repos) == 1
        assert repos[0]["artifact_dir"] == local_cgb

    def test_load_repos_keeps_workspace_when_no_local_cgb(self, tmp_path: Path):
        """When no .terrain/, _load_repos returns workspace artifact_dir."""
        from terrain.entrypoints.cli.cli import _load_repos

        ws = tmp_path / "workspace"
        ws.mkdir()

        repo = tmp_path / "myrepo"
        repo.mkdir()
        ws_artifact = ws / "myrepo_abc123"
        _make_artifact_dir(ws_artifact, repo_path=repo.as_posix())

        (ws / "active.txt").write_text("myrepo_abc123", encoding="utf-8")

        repos = _load_repos(ws)
        assert len(repos) == 1
        assert repos[0]["artifact_dir"] == ws_artifact
```

- [ ] **Step 2: Run tests to verify new tests fail**

Run: `python -m pytest tests/entrypoints/test_repo_local_cgb.py::TestCLILoadReposWithLocalCgb -v`
Expected: `test_load_repos_resolves_local_cgb` FAILS.

- [ ] **Step 3: Update `_load_repos()` to use `_resolve_artifact_dir()`**

In `terrain/entrypoints/cli/cli.py`, first add the import near the top of the file (with other local imports):

```python
from terrain.entrypoints.mcp.tools import _resolve_artifact_dir
```

Then modify `_load_repos()` (lines 385-410). Replace:

```python
def _load_repos(ws: Path) -> list[dict]:
    """Return all indexed repos, sorted by name, with 'active' flag set."""
    active_file = ws / "active.txt"
    active_name = active_file.read_text(encoding="utf-8").strip() if active_file.exists() else ""

    repos: list[dict] = []
    if not ws.exists():
        return repos
    for child in sorted(ws.iterdir()):
        if not child.is_dir():
            continue
        meta_file = child / "meta.json"
        if not meta_file.exists():
            continue
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        repos.append({
            "artifact_dir": child,
            "name": meta.get("repo_name", child.name),
            "path": meta.get("repo_path", "unknown"),
            "indexed_at": meta.get("indexed_at", "unknown"),
            "active": child.name == active_name,
        })
    return repos
```

With:

```python
def _load_repos(ws: Path) -> list[dict]:
    """Return all indexed repos, sorted by name, with 'active' flag set."""
    active_file = ws / "active.txt"
    active_name = active_file.read_text(encoding="utf-8").strip() if active_file.exists() else ""

    repos: list[dict] = []
    if not ws.exists():
        return repos
    for child in sorted(ws.iterdir()):
        if not child.is_dir():
            continue
        meta_file = child / "meta.json"
        if not meta_file.exists():
            continue
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        resolved = _resolve_artifact_dir(child)
        repos.append({
            "artifact_dir": resolved,
            "name": meta.get("repo_name", child.name),
            "path": meta.get("repo_path", "unknown"),
            "indexed_at": meta.get("indexed_at", "unknown"),
            "active": child.name == active_name,
        })
    return repos
```

The only change is adding `resolved = _resolve_artifact_dir(child)` and using `resolved` as `artifact_dir`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/entrypoints/test_repo_local_cgb.py -v`
Expected: All 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add terrain/entrypoints/cli/cli.py tests/entrypoints/test_repo_local_cgb.py
git commit -m "feat: CLI _load_repos prefers repo-local .terrain/ over workspace"
```

---

### Task 4: Add output destination prompt to `terrain index`

**Files:**
- Modify: `terrain/entrypoints/cli/cli.py:1442-1575` (`cmd_index`)
- Modify: `tests/entrypoints/test_repo_local_cgb.py`

- [ ] **Step 1: Write failing tests for output destination selection**

Append to `tests/entrypoints/test_repo_local_cgb.py`:

```python
class TestIndexOutputDestination:
    """terrain index should support --output local/workspace flags."""

    def test_output_local_sets_artifact_dir_to_cgb(self, tmp_path: Path):
        """--output local should direct artifacts to {repo}/.terrain/."""
        from terrain.entrypoints.cli.cli import _resolve_index_artifact_dir
        from terrain.entrypoints.mcp.pipeline import artifact_dir_for

        repo = tmp_path / "myrepo"
        repo.mkdir()
        ws = tmp_path / "workspace"
        ws.mkdir()

        result = _resolve_index_artifact_dir(repo, ws, output="local")
        assert result == repo / ".cgb"

    def test_output_workspace_sets_artifact_dir_to_workspace(self, tmp_path: Path):
        """--output workspace should use the normal workspace artifact dir."""
        from terrain.entrypoints.cli.cli import _resolve_index_artifact_dir
        from terrain.entrypoints.mcp.pipeline import artifact_dir_for

        repo = tmp_path / "myrepo"
        repo.mkdir()
        ws = tmp_path / "workspace"
        ws.mkdir()

        result = _resolve_index_artifact_dir(repo, ws, output="workspace")
        expected = artifact_dir_for(ws, repo)
        assert result == expected

    def test_output_none_defaults_to_local(self, tmp_path: Path):
        """When output is None (interactive would show menu), default to local
        in non-interactive context."""
        from terrain.entrypoints.cli.cli import _resolve_index_artifact_dir

        repo = tmp_path / "myrepo"
        repo.mkdir()
        ws = tmp_path / "workspace"
        ws.mkdir()

        # When stdin is not a tty, should default to local
        result = _resolve_index_artifact_dir(repo, ws, output=None, interactive=False)
        assert result == repo / ".cgb"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/entrypoints/test_repo_local_cgb.py::TestIndexOutputDestination -v`
Expected: FAIL — `_resolve_index_artifact_dir` does not exist.

- [ ] **Step 3: Implement `_resolve_index_artifact_dir()` and integrate into `cmd_index()`**

Add the following function in `terrain/entrypoints/cli/cli.py`, before `cmd_index()` (around line 1440):

```python
def _resolve_index_artifact_dir(
    repo_path: Path, ws: Path, output: str | None = None, interactive: bool = True,
) -> Path:
    """Resolve the artifact directory for `terrain index` output.

    Args:
        repo_path: The repository being indexed.
        ws: Workspace root directory.
        output: "local" for .terrain/, "workspace" for workspace, None for interactive.
        interactive: If True and output is None, show menu. Otherwise default to local.

    Returns:
        The artifact directory path.
    """
    from terrain.entrypoints.mcp.pipeline import artifact_dir_for

    if output == "local":
        return repo_path / ".cgb"
    if output == "workspace":
        return artifact_dir_for(ws, repo_path)

    # output is None — interactive or default
    if not interactive:
        return repo_path / ".cgb"

    ws_dir = artifact_dir_for(ws, repo_path)
    options = [
        f".terrain/  (repo-local, shareable via git)",
        f"{ws_dir}  (workspace)",
    ]
    print()
    print(f"  {_T_DOT} {_c('1', 'Output destination')}")
    print(f"  {_T_SIDE}  Use ↑↓ to navigate, Enter to confirm")
    print(f"  {_T_SIDE}")
    choice = _select_menu(options, prefix=f"  {_T_SIDE}  ")
    if choice is None or choice == 0:
        return repo_path / ".cgb"
    return ws_dir
```

Then modify `cmd_index()` to use it. In `cmd_index()`, replace lines 1494-1498:

```python
    artifact_dir = artifact_dir_for(ws, repo_path)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    db_path = artifact_dir / "graph.db"
    vectors_path = artifact_dir / "vectors.pkl"
    wiki_dir = artifact_dir / "wiki"
```

With:

```python
    output_flag = getattr(args, "output", None)
    artifact_dir = _resolve_index_artifact_dir(
        repo_path, ws, output=output_flag, interactive=sys.stdin.isatty(),
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    db_path = artifact_dir / "graph.db"
    vectors_path = artifact_dir / "vectors.pkl"
    wiki_dir = artifact_dir / "wiki"
```

Also, after the `save_meta` call and `active.txt` write (around line 1528-1530), add workspace meta stub when using local output. Replace:

```python
        save_meta(artifact_dir, repo_path, 0, last_indexed_commit=_head, repo_name=custom_name)
        ws_root = _get_workspace_root()
        (ws_root / "active.txt").write_text(artifact_dir.name, encoding="utf-8")
```

With:

```python
        save_meta(artifact_dir, repo_path, 0, last_indexed_commit=_head, repo_name=custom_name)
        ws_root = _get_workspace_root()
        # When outputting to .terrain/, also maintain a workspace stub for discovery
        if artifact_dir == repo_path / ".cgb":
            from terrain.entrypoints.mcp.pipeline import artifact_dir_for
            ws_stub = artifact_dir_for(ws_root, repo_path)
            ws_stub.mkdir(parents=True, exist_ok=True)
            save_meta(ws_stub, repo_path, 0, last_indexed_commit=_head, repo_name=custom_name)
            (ws_root / "active.txt").write_text(ws_stub.name, encoding="utf-8")
        else:
            (ws_root / "active.txt").write_text(artifact_dir.name, encoding="utf-8")
```

Apply the same pattern to the final `save_meta` call (around line 1561-1562). Replace:

```python
        save_meta(artifact_dir, repo_path, page_count, last_indexed_commit=_head, repo_name=custom_name)
```

With:

```python
        save_meta(artifact_dir, repo_path, page_count, last_indexed_commit=_head, repo_name=custom_name)
        # Update workspace stub too when using .terrain/
        if artifact_dir == repo_path / ".cgb":
            from terrain.entrypoints.mcp.pipeline import artifact_dir_for
            ws_stub = artifact_dir_for(ws_root, repo_path)
            save_meta(ws_stub, repo_path, page_count, last_indexed_commit=_head, repo_name=custom_name)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/entrypoints/test_repo_local_cgb.py -v`
Expected: All 12 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add terrain/entrypoints/cli/cli.py tests/entrypoints/test_repo_local_cgb.py
git commit -m "feat: terrain index supports output to .terrain/ or workspace via menu/flag"
```

---

### Task 5: Add `--output` CLI argument to `terrain index`

**Files:**
- Modify: `terrain/entrypoints/cli/cli.py` (argparse section)

- [ ] **Step 1: Find the argparse section for `terrain index`**

Search for `index_parser` or `add_parser("index"` in `cli.py`.

- [ ] **Step 2: Add `--output` argument**

In the argparse setup for the `index` subcommand, add:

```python
index_parser.add_argument(
    "--output", choices=["local", "workspace"], default=None,
    help="Output destination: 'local' for .terrain/ in repo, 'workspace' for ~/.terrain-ai/",
)
```

- [ ] **Step 3: Verify by running help**

Run: `python -m terrain.entrypoints.cli.cli index --help`
Expected: `--output {local,workspace}` appears in the help output.

- [ ] **Step 4: Commit**

```bash
git add terrain/entrypoints/cli/cli.py
git commit -m "feat: add --output flag to terrain index for destination selection"
```

---

### Task 6: Run full test suite and verify

**Files:** None (verification only)

- [ ] **Step 1: Run the new tests**

Run: `python -m pytest tests/entrypoints/test_repo_local_cgb.py -v`
Expected: All tests PASS.

- [ ] **Step 2: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: No regressions.

- [ ] **Step 3: Run dependency check**

Run: `python tools/dep_check.py`
Expected: No layer violations.

- [ ] **Step 4: Commit any fixes if needed, then final commit**

```bash
git add -A
git commit -m "test: verify repo-local .terrain/ feature passes full suite"
```
