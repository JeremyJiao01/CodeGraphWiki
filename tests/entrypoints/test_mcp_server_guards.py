"""Regression tests for MCP server safety guards.

Covers:
- bdc3d54: _SKIP_SYNC_TOOLS — write-heavy tools skip incremental sync
  to avoid Kuzu lock contention on Windows
- 2aa931b: stderr logging removed to prevent Windows pipe deadlock
- d9362b2: PYTHONUNBUFFERED / write_through for MCP stdio transport
"""

from __future__ import annotations

import pytest


class TestSkipSyncTools:
    """Write-heavy tools must skip incremental sync to prevent Kuzu lock
    contention on Windows when the sync hasn't released its DB handle."""

    def test_skip_sync_tools_defined(self):
        """The _SKIP_SYNC_TOOLS constant must exist and contain the
        correct set of write-heavy tool names."""
        # Read the server module source to extract the constant
        # (it's defined inside a function, so we verify via source inspection)
        import inspect
        from terrain.entrypoints.mcp import server

        source = inspect.getsource(server)
        assert "_SKIP_SYNC_TOOLS" in source
        assert '"initialize_repository"' in source
        assert '"build_graph"' in source
        assert '"rebuild_embeddings"' in source
        assert '"reload_config"' in source

    def test_incremental_sync_has_timeout(self):
        """_maybe_incremental_sync is wrapped in asyncio.wait_for with a
        timeout to prevent blocking forever on git calls."""
        import inspect
        from terrain.entrypoints.mcp import server

        source = inspect.getsource(server)
        assert "wait_for" in source
        assert "timeout=30" in source or "timeout = 30" in source


class TestWindowsIOSafety:
    """On Windows, MCP stdio transport requires unbuffered I/O and
    no stderr logging to prevent pipe deadlocks."""

    def test_server_removes_default_logger(self):
        """Server startup must call logger.remove() to strip stderr sink."""
        import inspect
        from terrain.entrypoints.mcp import server

        source = inspect.getsource(server)
        assert "logger.remove()" in source

    def test_npm_launcher_sets_unbuffered(self):
        """The npm launcher must set PYTHONUNBUFFERED=1."""
        from pathlib import Path
        npm_cli = Path(__file__).resolve().parents[2] / "npm-package" / "bin" / "cli.mjs"
        if npm_cli.exists():
            content = npm_cli.read_text()
            assert "PYTHONUNBUFFERED" in content
