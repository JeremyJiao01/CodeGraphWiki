"""Tests for repo-local .cgb/ artifact directory resolution."""
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
    """_resolve_artifact_dir prefers {repo_path}/.cgb/ over workspace artifact dir."""

    def test_prefers_local_cgb_when_exists(self, tmp_path: Path):
        from code_graph_builder.entrypoints.mcp.tools import _resolve_artifact_dir

        repo = tmp_path / "myrepo"
        repo.mkdir()
        local_cgb = repo / ".cgb"
        _make_artifact_dir(local_cgb, repo_path=repo.as_posix())

        ws_artifact = tmp_path / "workspace" / "myrepo_abc123"
        _make_artifact_dir(ws_artifact, repo_path=repo.as_posix())

        result = _resolve_artifact_dir(ws_artifact)
        assert result == local_cgb

    def test_falls_back_to_workspace_when_no_local_cgb(self, tmp_path: Path):
        from code_graph_builder.entrypoints.mcp.tools import _resolve_artifact_dir

        repo = tmp_path / "myrepo"
        repo.mkdir()

        ws_artifact = tmp_path / "workspace" / "myrepo_abc123"
        _make_artifact_dir(ws_artifact, repo_path=repo.as_posix())

        result = _resolve_artifact_dir(ws_artifact)
        assert result == ws_artifact

    def test_falls_back_when_local_cgb_has_no_graph_db(self, tmp_path: Path):
        from code_graph_builder.entrypoints.mcp.tools import _resolve_artifact_dir

        repo = tmp_path / "myrepo"
        local_cgb = repo / ".cgb"
        local_cgb.mkdir(parents=True)
        (local_cgb / "meta.json").write_text("{}", encoding="utf-8")

        ws_artifact = tmp_path / "workspace" / "myrepo_abc123"
        _make_artifact_dir(ws_artifact, repo_path=repo.as_posix())

        result = _resolve_artifact_dir(ws_artifact)
        assert result == ws_artifact

    def test_falls_back_when_repo_path_missing_from_meta(self, tmp_path: Path):
        from code_graph_builder.entrypoints.mcp.tools import _resolve_artifact_dir

        ws_artifact = tmp_path / "workspace" / "myrepo_abc123"
        ws_artifact.mkdir(parents=True)
        (ws_artifact / "graph.db").write_bytes(b"fake")
        (ws_artifact / "meta.json").write_text(
            json.dumps({"repo_name": "repo"}), encoding="utf-8"
        )

        result = _resolve_artifact_dir(ws_artifact)
        assert result == ws_artifact

    def test_falls_back_when_repo_path_does_not_exist(self, tmp_path: Path):
        from code_graph_builder.entrypoints.mcp.tools import _resolve_artifact_dir

        ws_artifact = tmp_path / "workspace" / "myrepo_abc123"
        _make_artifact_dir(ws_artifact, repo_path="/nonexistent/path")

        result = _resolve_artifact_dir(ws_artifact)
        assert result == ws_artifact
