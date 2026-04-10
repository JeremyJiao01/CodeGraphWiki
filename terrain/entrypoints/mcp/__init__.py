"""MCP server for Terrain.

Exposes graph query, semantic search, and code retrieval tools
via the Model Context Protocol (MCP) stdio transport.

Usage:
    TERRAIN_WORKSPACE=~/.terrain python3 -m terrain.mcp.server
"""

from __future__ import annotations


def main() -> None:
    import asyncio

    from .server import main as _main

    asyncio.run(_main())


__all__ = ["main"]
