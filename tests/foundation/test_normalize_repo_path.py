"""Tests for terrain.foundation.utils.paths.normalize_repo_path.

JER-100 — unify repo_path normalization across CLI / MCP / artifact hash so
the same logical repository produces the same canonical string regardless of
entry point (CLI `repo_path.as_posix()` vs MCP `str(repo)`).

Requirements:
    * POSIX-style forward slashes on output.
    * Windows drive letter uppercased.
    * Trailing '/' stripped, except roots ("/" or "C:/").
    * Idempotent — normalize(normalize(x)) == normalize(x).
    * UNC and WSL paths preserved.
    * Chinese / non-ASCII characters preserved verbatim.
"""
from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

from terrain.foundation.utils.paths import normalize_repo_path


class TestDriveLetterCase:
    def test_lower_drive_letter_uppercased(self):
        assert normalize_repo_path(PureWindowsPath(r"c:\Users\john")) == "C:/Users/john"

    def test_upper_drive_letter_preserved(self):
        assert normalize_repo_path(PureWindowsPath(r"C:\Users\john")) == "C:/Users/john"

    def test_lower_drive_letter_on_purepath_posix_form(self):
        # PurePosixPath preserves the odd "c:/..." shape some tools emit.
        assert normalize_repo_path(PurePosixPath("c:/Users/john")) == "C:/Users/john"


class TestTrailingSlash:
    def test_strip_trailing_slash(self):
        assert normalize_repo_path(PurePosixPath("/tmp/foo/")) == "/tmp/foo"

    def test_strip_multiple_trailing_slashes(self):
        # PurePath collapses internal slashes but preserves input shape enough
        # for us to verify trailing-slash handling without touching the real FS
        # (where /tmp -> /private/tmp on macOS etc.).
        assert normalize_repo_path(PurePosixPath("/tmp/foo")) == "/tmp/foo"
        assert normalize_repo_path("/no-such-root-12345/foo///") == "/no-such-root-12345/foo"

    def test_preserve_unix_root(self):
        assert normalize_repo_path(PurePosixPath("/")) == "/"

    def test_preserve_drive_root(self):
        assert normalize_repo_path(PureWindowsPath("C:\\")) == "C:/"

    def test_preserve_lower_drive_root(self):
        assert normalize_repo_path(PureWindowsPath("c:\\")) == "C:/"


class TestCrossFormAgreement:
    def test_posix_and_windows_paths_agree(self):
        a = normalize_repo_path(PurePosixPath("C:/Users/john/project"))
        b = normalize_repo_path(PureWindowsPath(r"C:\Users\john\project"))
        assert a == b == "C:/Users/john/project"

    def test_str_windows_backslash_matches_path(self):
        a = normalize_repo_path(r"C:\Users\john\project")
        b = normalize_repo_path(PureWindowsPath(r"C:\Users\john\project"))
        assert a == b == "C:/Users/john/project"


class TestUNCAndWSL:
    def test_unc_path_preserved(self):
        # \\server\share\dir -> //server/share/dir
        result = normalize_repo_path(r"\\server\share\project")
        assert result == "//server/share/project"

    def test_wsl_path_preserved(self):
        # \\wsl$\Ubuntu\home\user\repo
        result = normalize_repo_path(r"\\wsl$\Ubuntu\home\user\repo")
        assert result == "//wsl$/Ubuntu/home/user/repo"


class TestChinesePath:
    def test_chinese_unix_path_preserved(self):
        assert normalize_repo_path(PurePosixPath("/tmp/测试项目/子模块")) == "/tmp/测试项目/子模块"

    def test_chinese_windows_path(self):
        assert normalize_repo_path(PureWindowsPath(r"C:\代码\测试项目")) == "C:/代码/测试项目"


class TestIdempotence:
    @pytest.mark.parametrize("raw", [
        "/tmp/foo",
        "/tmp/foo/",
        r"C:\Users\john",
        r"c:\Users\john\\",
        "/tmp/测试项目/子模块",
        r"\\server\share\dir",
        r"\\wsl$\Ubuntu\home\user",
        "/",
        "C:/",
    ])
    def test_normalize_is_idempotent(self, raw):
        once = normalize_repo_path(raw)
        twice = normalize_repo_path(once)
        assert once == twice


class TestNativeResolve:
    """When passed a concrete Path, resolve to absolute canonical form.

    Note: PurePath inputs are NOT resolved — only concrete Path inputs.
    This lets tests / callers using PurePath simulate cross-platform paths.
    """

    def test_concrete_path_is_resolved_to_absolute(self, tmp_path: Path):
        sub = tmp_path / "sub"
        sub.mkdir()
        result = normalize_repo_path(sub)
        assert result == sub.resolve().as_posix()

    def test_concrete_path_nonexistent_still_works(self, tmp_path: Path):
        # Path.resolve(strict=False) handles nonexistent paths.
        target = tmp_path / "does-not-exist"
        result = normalize_repo_path(target)
        assert result == target.resolve().as_posix()

    def test_purepath_not_resolved(self):
        # PurePath has no filesystem binding; leave as-is (just POSIX + drive case).
        p = PurePosixPath("/not-a-real-path-12345")
        assert normalize_repo_path(p) == "/not-a-real-path-12345"
