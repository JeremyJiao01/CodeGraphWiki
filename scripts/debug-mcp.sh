#!/usr/bin/env bash
# =============================================================================
# MCP Inspector Debug Script
#
# Usage:
#   ./scripts/debug-mcp.sh              # Start MCP Inspector with debug logging
#   ./scripts/debug-mcp.sh --tail       # Just tail the debug log (.txt)
#   ./scripts/debug-mcp.sh --raw-test   # Raw stdin/stdout test (no Inspector)
# =============================================================================

set -euo pipefail

CGB_WORKSPACE="${CGB_WORKSPACE:-$HOME/.code-graph-builder}"
DEBUG_LOG="$CGB_WORKSPACE/debug.log"
DEBUG_TXT="$CGB_WORKSPACE/debug.txt"

# Ensure workspace exists
mkdir -p "$CGB_WORKSPACE"

# --- Mode: tail the debug log ---
if [[ "${1:-}" == "--tail" ]]; then
    echo "📄 Tailing $DEBUG_TXT (Ctrl+C to stop)"
    echo "   Start MCP Inspector in another terminal with: ./scripts/debug-mcp.sh"
    echo "---"
    tail -f "$DEBUG_TXT" 2>/dev/null || echo "Log file not found yet. Start the server first."
    exit 0
fi

# --- Mode: raw stdin/stdout test (bypass MCP Inspector) ---
if [[ "${1:-}" == "--raw-test" ]]; then
    echo "🔬 Raw JSON-RPC test — sending initialize request..."
    echo "   Debug log: $DEBUG_LOG"
    echo "   Debug txt: $DEBUG_TXT"
    echo ""
    echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"debug-test","version":"0.1"}}}' \
        | CGB_DEBUG=1 CGB_WORKSPACE="$CGB_WORKSPACE" timeout 15 python3 -m code_graph_builder.entrypoints.mcp.server 2>/dev/null \
        || echo ""
    echo ""
    echo "--- Debug txt tail ---"
    tail -20 "$DEBUG_TXT" 2>/dev/null || echo "(no debug txt)"
    exit 0
fi

# --- Mode: MCP Inspector ---
echo "🔍 MCP Debug with MCP Inspector"
echo "==============================="
echo ""
echo "  Debug log : $DEBUG_LOG"
echo "  Debug txt : $DEBUG_TXT"
echo "  Workspace : $CGB_WORKSPACE"
echo ""
echo "💡 Tip: Open another terminal and run:"
echo "   ./scripts/debug-mcp.sh --tail"
echo ""
echo "Starting MCP Inspector..."
echo ""

# Clear the old logs for a clean session
: > "$DEBUG_LOG"
: > "$DEBUG_TXT"

# Launch MCP Inspector connected to local Python source
export CGB_DEBUG=1
export CGB_WORKSPACE

npx @modelcontextprotocol/inspector \
    python3 -m code_graph_builder.entrypoints.mcp.server
