"""Canonical repository path normalization.

JER-100 — CLI and MCP entrypoints historically disagreed about the exact
string form of ``repo_path``:

    * CLI `_link_update_meta` used ``repo_path.as_posix()``.
    * MCP `_handle_link_repository` used ``str(repo)``.

On Windows those two produce different strings for the same directory, which
then hashes (via :func:`terrain.entrypoints.mcp.pipeline.artifact_dir_for`)
into two **different** artifact dir names — orphan "ghost" artifacts, cross-
entrypoint meta reads failing, ``terrain status`` / MCP path checks going
sideways.

``normalize_repo_path`` is the single canonical form used for:
    * writing ``repo_path`` into ``meta.json``
    * hashing into the artifact dir name
    * comparing paths across CLI and MCP

Rules:
    * Output uses forward slashes.
    * Windows drive letters are uppercased (``c:/..." -> "C:/...``).
    * Trailing ``/`` is stripped, except roots (``"/"`` or ``"C:/"``).
    * Native concrete :class:`~pathlib.Path` inputs are resolved to absolute.
    * Abstract :class:`~pathlib.PurePath` inputs are NOT resolved (so tests
      can simulate cross-platform paths without touching the filesystem).
    * UNC (``\\\\server\\share``) and WSL (``\\\\wsl$\\...``) paths are
      preserved as ``//server/share`` / ``//wsl$/...``.
    * Idempotent: ``normalize_repo_path(normalize_repo_path(x)) == normalize_repo_path(x)``.
"""
from __future__ import annotations

from pathlib import Path, PurePath, PureWindowsPath


def _looks_windows(s: str) -> bool:
    """True if *s* looks like a Windows path (drive letter or UNC prefix)."""
    if len(s) >= 3 and s[0].isalpha() and s[1] == ":" and s[2] in ("/", "\\"):
        return True
    if s.startswith("\\\\") or s.startswith("//"):
        return True
    return False


def normalize_repo_path(p: str | Path | PurePath) -> str:
    """Return the canonical POSIX-style string for a repo path.

    See module docstring for the full rules.
    """
    # 1. Convert to a POSIX-style string.
    if isinstance(p, PureWindowsPath):
        s = p.as_posix()
    elif isinstance(p, Path):
        # Concrete filesystem Path — resolve to absolute canonical form.
        try:
            s = p.resolve().as_posix()
        except (OSError, RuntimeError):
            s = p.as_posix()
    elif isinstance(p, PurePath):
        # Abstract PurePath (e.g. PurePosixPath) — no filesystem resolution.
        s = p.as_posix()
    else:
        raw = str(p)
        if _looks_windows(raw):
            s = raw.replace("\\", "/")
        else:
            try:
                s = Path(raw).resolve().as_posix()
            except (OSError, RuntimeError):
                s = raw.replace("\\", "/")

    # 2. Uppercase drive letter.
    if len(s) >= 2 and s[0].isalpha() and s[1] == ":":
        s = s[0].upper() + s[1:]

    # 3. Strip trailing slashes (but keep root forms intact).
    if len(s) > 1 and s.endswith("/"):
        is_drive_root = len(s) >= 3 and s[1] == ":" and s.rstrip("/") == s[:2]
        is_unc_root = s.startswith("//") and s.count("/") <= 3  # //server/share
        if not is_drive_root and not is_unc_root:
            s = s.rstrip("/") or "/"
        elif is_drive_root:
            s = s[:2] + "/"

    return s


__all__ = ["normalize_repo_path"]
