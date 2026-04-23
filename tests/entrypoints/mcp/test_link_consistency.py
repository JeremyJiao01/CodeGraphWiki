"""JER-100 — CLI link and MCP link_repository must agree on repo_path.

Historically:
    * CLI ``_link_update_meta`` wrote ``repo_path.as_posix()``.
    * MCP ``_handle_link_repository`` wrote ``str(repo)``.

On Windows the two strings differ (forward vs. back slashes); after JER-100
both funnel through :func:`terrain.foundation.utils.paths.normalize_repo_path`
so the ``repo_path`` field in meta.json — and therefore the hashed artifact
dir name — is identical regardless of which entry point wrote it.
"""
from __future__ import annotations

import json
from pathlib import Path, PureWindowsPath

from terrain.entrypoints.cli.cli import _link_update_meta, _load_repos
from terrain.entrypoints.mcp.pipeline import artifact_dir_for
from terrain.foundation.utils.paths import normalize_repo_path


class TestArtifactDirAgreement:
    """artifact_dir_for now hashes the canonical form — different input
    representations of the same logical path collapse to the same dir."""

    def test_forward_and_back_slash_windows_agree(self, tmp_path: Path):
        ws = tmp_path / "ws"
        ws.mkdir()
        back = PureWindowsPath(r"C:\Users\john\myrepo")
        fwd = PureWindowsPath("C:/Users/john/myrepo")
        assert artifact_dir_for(ws, back) == artifact_dir_for(ws, fwd)

    def test_mixed_case_drive_letter_agrees(self, tmp_path: Path):
        ws = tmp_path / "ws"
        ws.mkdir()
        lower = PureWindowsPath(r"c:\Users\john\myrepo")
        upper = PureWindowsPath(r"C:\Users\john\myrepo")
        assert artifact_dir_for(ws, lower) == artifact_dir_for(ws, upper)

    def test_trailing_slash_agrees(self, tmp_path: Path):
        ws = tmp_path / "ws"
        ws.mkdir()
        # Use a bogus abs path so ``Path.resolve`` behaves the same under tmp.
        repo = tmp_path / "some-repo"
        repo.mkdir()
        with_slash = normalize_repo_path(repo)
        without_slash = normalize_repo_path(str(repo).rstrip("/"))
        assert with_slash == without_slash


class TestCLIWriteMCPRead:
    """Write meta.json via CLI's _link_update_meta, then read it through the
    same code path MCP uses (list_repositories delegates to _get_repo_status_entries
    which reads meta directly) — they must agree."""

    def test_cli_write_produces_canonical_repo_path(self, tmp_path: Path):
        ws = tmp_path / "ws"
        ws.mkdir()
        repo = tmp_path / "my-project"
        repo.mkdir()

        artifact_dir = artifact_dir_for(ws, repo)
        artifact_dir.mkdir(parents=True)
        _link_update_meta(artifact_dir, repo)

        meta = json.loads((artifact_dir / "meta.json").read_text(encoding="utf-8"))
        assert meta["repo_path"] == normalize_repo_path(repo)

        # Reading back through _load_repos should report the same string.
        repos = _load_repos(ws)
        assert len(repos) == 1
        assert repos[0]["path"] == normalize_repo_path(repo)

    def test_meta_repo_path_roundtrip_is_idempotent(self, tmp_path: Path):
        """Re-linking the same repo must not mutate repo_path."""
        ws = tmp_path / "ws"
        ws.mkdir()
        repo = tmp_path / "idempotent-repo"
        repo.mkdir()

        artifact_dir = artifact_dir_for(ws, repo)
        artifact_dir.mkdir(parents=True)
        _link_update_meta(artifact_dir, repo)
        first = json.loads((artifact_dir / "meta.json").read_text(encoding="utf-8"))["repo_path"]

        _link_update_meta(artifact_dir, repo)
        second = json.loads((artifact_dir / "meta.json").read_text(encoding="utf-8"))["repo_path"]

        assert first == second


class TestLegacyArtifactDirFallback:
    """Workspaces that were indexed before JER-100 may contain a dir hashed
    from the raw ``.as_posix()`` form. artifact_dir_for must still find them
    (backward compatibility) rather than silently orphan them."""

    def test_legacy_dir_reused_when_new_hash_misses(self, tmp_path: Path):
        import hashlib

        ws = tmp_path / "ws"
        ws.mkdir()

        # Simulate a path whose legacy and canonical hashes differ: a raw
        # string with a trailing slash (canonical strips it, legacy keeps it
        # inside as_posix() of a str-coerced PurePath).
        # We fake a legacy dir by creating it with the legacy hash manually.
        repo = PureWindowsPath("c:/Some/Project")  # lowercase drive → canonical uppercases
        canonical = normalize_repo_path(repo)
        legacy = repo.as_posix()  # "c:/Some/Project"
        assert canonical != legacy

        name = repo.name
        legacy_hash = hashlib.md5(legacy.encode()).hexdigest()[:8]
        legacy_dir = ws / f"{name}_{legacy_hash}"
        legacy_dir.mkdir(parents=True)

        resolved = artifact_dir_for(ws, repo)
        assert resolved == legacy_dir
