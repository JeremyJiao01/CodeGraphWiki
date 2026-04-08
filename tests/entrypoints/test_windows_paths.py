"""Regression tests for Windows path handling.

Covers:
- 0960c46: artifact_dir_for uses POSIX path for hashing (cross-platform consistency)
- 75c3d7c: _parse_repo_path handles Windows paths from File Explorer address bar
"""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath, PureWindowsPath
from unittest.mock import patch

import pytest

from code_graph_builder.entrypoints.mcp.pipeline import artifact_dir_for


# ---------------------------------------------------------------------------
# artifact_dir_for: cross-platform hash consistency (fix 0960c46)
# ---------------------------------------------------------------------------

class TestArtifactDirFor:
    """artifact_dir_for must produce the same directory name regardless of
    whether the input path uses forward or back slashes."""

    def test_posix_and_windows_paths_produce_same_hash(self, tmp_path: Path):
        """A POSIX path and its Windows equivalent must hash identically."""
        posix = PurePosixPath("C:/Users/john/project")
        win = PureWindowsPath(r"C:\Users\john\project")

        dir_posix = artifact_dir_for(tmp_path, posix)
        dir_win = artifact_dir_for(tmp_path, win)

        assert dir_posix == dir_win

    def test_native_path_matches_posix(self, tmp_path: Path):
        """A native Path (Unix) must produce the same hash as PurePosixPath."""
        native = PurePosixPath("/home/user/repo")
        result = artifact_dir_for(tmp_path, native)

        expected_hash = hashlib.md5("/home/user/repo".encode()).hexdigest()[:8]
        assert result == tmp_path / f"repo_{expected_hash}"

    def test_drive_root_fallback_name(self, tmp_path: Path):
        """When repo_path.name is empty (drive root), use anchor as name."""
        root = PureWindowsPath("C:\\")
        result = artifact_dir_for(tmp_path, root)

        # C:\ -> anchor "C:\", name "" -> fallback "C"
        assert result.parent == tmp_path
        name = result.name
        assert name.startswith("C_")  # "C" from anchor with backslash/colon stripped

    def test_unix_root_fallback(self, tmp_path: Path):
        """Unix root '/' has empty name — should fall back to 'root'."""
        root = PurePosixPath("/")
        result = artifact_dir_for(tmp_path, root)
        assert "root_" in result.name

    def test_hash_deterministic(self, tmp_path: Path):
        """Same path always produces the same directory."""
        p = PurePosixPath("/some/repo")
        assert artifact_dir_for(tmp_path, p) == artifact_dir_for(tmp_path, p)


# ---------------------------------------------------------------------------
# _parse_repo_path: Windows path detection on non-Windows (fix 75c3d7c)
# ---------------------------------------------------------------------------

class TestParseRepoPath:
    """_parse_repo_path detects Windows absolute paths and returns
    PureWindowsPath + is_remote=True on non-Windows platforms."""

    @pytest.fixture(autouse=True)
    def _import_func(self):
        from code_graph_builder.entrypoints.cli.cli import _parse_repo_path
        self._parse = _parse_repo_path

    @patch("code_graph_builder.entrypoints.cli.cli.platform")
    def test_windows_path_on_macos(self, mock_platform):
        """A Windows path on macOS returns (PureWindowsPath, True)."""
        mock_platform.system.return_value = "Darwin"
        path, is_remote = self._parse(r"C:\Users\john\project")

        assert is_remote is True
        assert isinstance(path, PureWindowsPath)
        assert path.name == "project"

    @patch("code_graph_builder.entrypoints.cli.cli.platform")
    def test_windows_path_forward_slash_on_linux(self, mock_platform):
        """Windows path with forward slashes is also detected."""
        mock_platform.system.return_value = "Linux"
        path, is_remote = self._parse("D:/work/myrepo")

        assert is_remote is True
        assert isinstance(path, PureWindowsPath)
        assert path.name == "myrepo"

    @patch("code_graph_builder.entrypoints.cli.cli.platform")
    def test_quoted_windows_path(self, mock_platform):
        """Surrounding quotes are stripped before parsing."""
        mock_platform.system.return_value = "Darwin"
        path, _ = self._parse('"C:\\Users\\john\\project"')

        assert isinstance(path, PureWindowsPath)
        assert path.name == "project"

    @patch("code_graph_builder.entrypoints.cli.cli.platform")
    def test_native_unix_path(self, mock_platform):
        """A native Unix path on macOS returns (Path, False)."""
        mock_platform.system.return_value = "Darwin"
        path, is_remote = self._parse("/tmp/test_repo")

        assert is_remote is False
        assert isinstance(path, Path)

    @patch("code_graph_builder.entrypoints.cli.cli.platform")
    def test_whitespace_stripped(self, mock_platform):
        """Leading/trailing whitespace is removed."""
        mock_platform.system.return_value = "Darwin"
        path, is_remote = self._parse("  C:\\Users\\test  ")

        assert is_remote is True
        assert isinstance(path, PureWindowsPath)

    @patch("code_graph_builder.entrypoints.cli.cli.platform")
    def test_windows_path_on_windows(self, mock_platform):
        """On actual Windows, a Windows path returns (Path, False)."""
        mock_platform.system.return_value = "Windows"
        path, is_remote = self._parse(r"C:\Users\john\project")

        assert is_remote is False
        # On real Windows this would be a resolved Path; here it's a Path object
        assert isinstance(path, Path)
