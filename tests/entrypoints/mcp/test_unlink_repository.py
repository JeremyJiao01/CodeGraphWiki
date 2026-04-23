"""JER-102 — MCP ``unlink_repository`` and ``linked_source`` exposure.

The MCP surface mirrors the CLI:

* ``list_repositories`` and ``get_repository_info`` expose a
  ``linked_source`` field when the active (or listed) artifact is a
  linked child (schema v2 ``source_artifact``).
* ``unlink_repository`` is the symmetric teardown for ``link_repository``
  — it must refuse to tear down the authoritative source.
"""
from __future__ import annotations

import asyncio
import json
import platform
from pathlib import Path

import pytest

from terrain.entrypoints.link_ops import register_link
from terrain.entrypoints.mcp.tools import MCPToolsRegistry
from terrain.foundation.utils.paths import normalize_repo_path


def _make_source_dir(ws: Path, artifact_name: str, repo: Path) -> Path:
    d = ws / artifact_name
    d.mkdir(parents=True)
    (d / "graph.db").write_text("source-graph", encoding="utf-8")
    (d / "api_docs").mkdir()
    (d / "api_docs" / "index.md").write_text("source-api", encoding="utf-8")
    (d / "meta.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "repo_path": normalize_repo_path(repo),
                "repo_name": repo.name,
                "indexed_at": "2026-04-23T00:00:00",
                "steps": {"graph": True, "api_docs": True,
                          "embeddings": False, "wiki": False},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return d


def _link_into(ws: Path, source_dir: Path, target_name: str, repo: Path) -> Path:
    target = ws / target_name
    target.mkdir(parents=True)
    for name in ("graph.db", "api_docs"):
        src = source_dir / name
        dst = target / name
        if not src.exists():
            continue
        if platform.system() == "Windows":
            import shutil
            if src.is_dir():
                shutil.copytree(str(src), str(dst))
            else:
                shutil.copy2(str(src), str(dst))
        else:
            dst.symlink_to(src)
    register_link(ws, source_dir=source_dir, target_dir=target,
                  repo_path=repo)
    return target


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestListRepositoriesLinkedSource:
    def test_child_row_has_linked_source_field(self, tmp_path: Path):
        ws = tmp_path / "ws"
        ws.mkdir()
        src_repo = tmp_path / "origin"
        src_repo.mkdir()
        child_repo = tmp_path / "clone_a"
        child_repo.mkdir()
        source_dir = _make_source_dir(ws, "origin_aaaa1111", src_repo)
        child = _link_into(ws, source_dir, "origin_bbbb2222", child_repo)

        registry = MCPToolsRegistry(ws)
        try:
            result = _run(registry._handle_list_repositories())
        finally:
            registry.close()

        by_dir = {r["artifact_dir"]: r for r in result["repositories"]}
        assert by_dir[child.name]["linked_source"] == src_repo.name
        assert by_dir[source_dir.name].get("linked_source") in (None, "")
        assert by_dir[source_dir.name]["shared_count"] == 1


class TestGetRepositoryInfoLinkedSource:
    def test_active_child_exposes_linked_source(self, tmp_path: Path):
        ws = tmp_path / "ws"
        ws.mkdir()
        src_repo = tmp_path / "origin"
        src_repo.mkdir()
        child_repo = tmp_path / "clone_a"
        child_repo.mkdir()
        source_dir = _make_source_dir(ws, "origin_aaaa1111", src_repo)
        child = _link_into(ws, source_dir, "origin_bbbb2222", child_repo)

        # Activate the child so get_repository_info targets it.
        (ws / "active.txt").write_text(child.name, encoding="utf-8")

        registry = MCPToolsRegistry(ws)
        try:
            # _handle_get_repository_info requires _active_artifact_dir; the
            # auto-load in __init__ may skip side-effects that need graph.db
            # — but the linked_source field is sourced from meta.json, not
            # from the graph. Patch the minimal state manually if needed.
            if registry._active_artifact_dir is None:
                registry._active_artifact_dir = child
                registry._active_repo_path = child_repo
            result = _run(registry._handle_get_repository_info())
        finally:
            registry.close()

        assert result.get("linked_source") == src_repo.name
        assert result.get("source_artifact") == source_dir.name


class TestUnlinkRepositoryHandler:
    def test_unlink_repository_removes_child(self, tmp_path: Path):
        ws = tmp_path / "ws"
        ws.mkdir()
        src_repo = tmp_path / "origin"
        src_repo.mkdir()
        child_repo = tmp_path / "clone_a"
        child_repo.mkdir()
        source_dir = _make_source_dir(ws, "origin_aaaa1111", src_repo)
        child = _link_into(ws, source_dir, "origin_bbbb2222", child_repo)

        registry = MCPToolsRegistry(ws)
        try:
            result = _run(registry._handle_unlink_repository(target=str(child_repo)))
        finally:
            registry.close()

        assert result["status"] == "success"
        assert result["artifact_dir"] == child.name
        assert not child.exists()
        # Authoritative source + its data files untouched.
        assert source_dir.exists()
        assert (source_dir / "graph.db").read_text(encoding="utf-8") == "source-graph"

    def test_unlink_repository_refuses_source(self, tmp_path: Path):
        ws = tmp_path / "ws"
        ws.mkdir()
        src_repo = tmp_path / "origin"
        src_repo.mkdir()
        child_repo = tmp_path / "clone_a"
        child_repo.mkdir()
        source_dir = _make_source_dir(ws, "origin_aaaa1111", src_repo)
        _link_into(ws, source_dir, "origin_bbbb2222", child_repo)

        registry = MCPToolsRegistry(ws)
        try:
            from terrain.entrypoints.mcp.tools import ToolError
            with pytest.raises(ToolError):
                _run(registry._handle_unlink_repository(target=source_dir.name))
        finally:
            registry.close()

    def test_unlink_repository_clears_active_when_removing_active(self, tmp_path: Path):
        ws = tmp_path / "ws"
        ws.mkdir()
        src_repo = tmp_path / "origin"
        src_repo.mkdir()
        child_repo = tmp_path / "clone_a"
        child_repo.mkdir()
        source_dir = _make_source_dir(ws, "origin_aaaa1111", src_repo)
        child = _link_into(ws, source_dir, "origin_bbbb2222", child_repo)
        (ws / "active.txt").write_text(child.name, encoding="utf-8")

        registry = MCPToolsRegistry(ws)
        try:
            result = _run(registry._handle_unlink_repository(target=child.name))
        finally:
            registry.close()

        assert result["cleared_active"] is True
        active = ws / "active.txt"
        if active.exists():
            assert active.read_text(encoding="utf-8").strip() == ""


class TestUnlinkRepositoryToolRegistered:
    def test_unlink_repository_dispatched(self, tmp_path: Path):
        """unlink_repository mirrors link_repository: hidden from
        ``tools()`` but dispatchable via ``get_handler`` — CLI drives it."""
        ws = tmp_path / "ws"
        ws.mkdir()
        registry = MCPToolsRegistry(ws)
        try:
            assert registry.get_handler("unlink_repository") is not None
        finally:
            registry.close()
