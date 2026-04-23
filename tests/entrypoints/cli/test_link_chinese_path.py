"""JER-100 — terrain link with Chinese paths.

Covers the end-to-end CLI → meta.json → MCP-style readback scenario for a
repository under ``/tmp/测试项目/子模块``. Before the fix, meta.json contained
``repo_path`` as written by CLI (``as_posix()``), while MCP wrote ``str(repo)``
— on Windows this divergence caused duplicate artifact dirs; on any OS the
concern is that UTF-8 bytes on disk must round-trip through meta.json using
``errors='strict'``.
"""
from __future__ import annotations

import json
from pathlib import Path

from terrain.entrypoints.cli.cli import (
    _get_repo_status_entries,
    _link_update_meta,
    _load_repos,
)
from terrain.entrypoints.mcp.pipeline import artifact_dir_for
from terrain.foundation.utils.paths import normalize_repo_path


def test_chinese_path_link_and_readback(tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()

    repo = tmp_path / "测试项目" / "子模块"
    repo.mkdir(parents=True)

    # Simulate `terrain link`
    artifact_dir = artifact_dir_for(ws, repo)
    artifact_dir.mkdir(parents=True)
    _link_update_meta(artifact_dir, repo)

    # meta.json bytes must be strict-UTF-8 decodable (JER-93 guard — no
    # mojibake introduced).
    raw_bytes = (artifact_dir / "meta.json").read_bytes()
    decoded = raw_bytes.decode("utf-8", errors="strict")  # must not raise
    meta = json.loads(decoded)

    expected = normalize_repo_path(repo)
    assert meta["repo_path"] == expected
    assert "测试项目" in meta["repo_path"]
    assert "子模块" in meta["repo_path"]

    # terrain status / terrain list readback.
    repos = _load_repos(ws)
    assert len(repos) == 1
    assert repos[0]["path"] == expected
    assert repos[0]["name"] == "子模块"

    entries = _get_repo_status_entries(ws)
    assert len(entries) == 1
    assert entries[0]["name"] == "子模块"
    # Entry path must also be the canonical form, pre-converted through Path().
    assert Path(entries[0]["path"]) == Path(expected)


def test_chinese_path_artifact_dir_stable(tmp_path: Path):
    """The hashed artifact dir name is deterministic and includes the Chinese
    name verbatim (no mojibake)."""
    ws = tmp_path / "ws"
    ws.mkdir()
    repo = tmp_path / "测试项目"
    repo.mkdir()

    a = artifact_dir_for(ws, repo)
    b = artifact_dir_for(ws, repo)
    assert a == b
    assert "测试项目" in a.name


def test_chinese_path_mcp_list_repositories_consistent(tmp_path: Path):
    """list_repositories (read path) surfaces the same canonical repo_path
    that CLI link wrote — no string-form drift."""
    ws = tmp_path / "ws"
    ws.mkdir()
    repo = tmp_path / "测试项目" / "子模块"
    repo.mkdir(parents=True)

    artifact_dir = artifact_dir_for(ws, repo)
    artifact_dir.mkdir(parents=True)
    # Fake a minimal graph.db so list_repositories treats this as a "real" repo.
    (artifact_dir / "graph.db").write_bytes(b"")
    _link_update_meta(artifact_dir, repo)

    meta = json.loads((artifact_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["repo_path"] == normalize_repo_path(repo)

    # MCP list_repositories reads meta.json field by field — verify the raw
    # value (pre-Path conversion) matches normalize_repo_path(repo).
    assert meta["repo_path"] == normalize_repo_path(repo)
