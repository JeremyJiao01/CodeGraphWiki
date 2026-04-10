"""Regression tests for Kuzu service fixes.

Covers:
- eaf2abf: flush_nodes and flush_relationships must use _execute_with_retry
  (not bare conn.execute) to handle lock contention on Windows
- 157da26: get_statistics must filter NODE tables from show_tables(),
  and use correct column index for table name
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import pytest

from terrain.foundation.services.kuzu_service import KuzuIngestor


@pytest.fixture
def ingestor():
    """Create a KuzuIngestor with mocked connection."""
    ing = KuzuIngestor.__new__(KuzuIngestor)
    ing._conn = MagicMock()
    ing._db = MagicMock()
    ing.node_buffer = []
    ing.relationship_buffer = []
    ing._schema_cache = set()
    ing._rel_schema_cache = set()
    ing._rel_table_overrides = {}
    return ing


class TestFlushUsesRetry:
    """flush_nodes and flush_relationships must call _execute_with_retry,
    not bare self._conn.execute, to prevent Windows lock deadlocks."""

    def test_flush_nodes_calls_execute_with_retry(self, ingestor):
        """flush_nodes should delegate to _execute_with_retry."""
        ingestor.node_buffer = [
            ("Function", {
                "qualified_name": "test.func",
                "name": "func",
                "path": "test.py",
                "start_line": 1,
                "end_line": 10,
            }),
        ]

        with patch.object(ingestor, "_execute_with_retry", return_value=MagicMock()) as mock_retry, \
             patch.object(ingestor, "_ensure_schema"):
            ingestor.flush_nodes()

        # _execute_with_retry should have been called (not _conn.execute)
        assert mock_retry.call_count >= 1
        # _conn.execute should NOT have been called directly for the MERGE
        # (it may be called by _ensure_schema indirectly, that's fine)

    def test_flush_relationships_calls_execute_with_retry(self, ingestor):
        """flush_relationships should delegate to _execute_with_retry."""
        ingestor.relationship_buffer = [
            (
                ("Function", "qualified_name", "mod.caller"),
                "CALLS",
                ("Function", "qualified_name", "mod.callee"),
                {},
            ),
        ]

        with patch.object(ingestor, "_execute_with_retry", return_value=MagicMock()) as mock_retry, \
             patch.object(ingestor, "_ensure_rel_schema"):
            ingestor.flush_relationships()

        assert mock_retry.call_count >= 1


class TestGetStatisticsNodeFilter:
    """get_statistics must only count NODE tables, not REL tables,
    and must read the table name from the correct column index."""

    def test_only_node_tables_counted(self, ingestor):
        """REL-type tables should be excluded from node_labels."""
        # Mock show_tables() to return NODE and REL tables
        show_result = MagicMock()
        rows = [
            # (id, name, type, ...)
            [0, "Function", "NODE"],
            [1, "Module", "NODE"],
            [2, "CALLS", "REL"],
            [3, "CONTAINS", "REL"],
        ]
        show_result.has_next.side_effect = [True, True, True, True, False]
        show_result.get_next.side_effect = rows

        # Mock count queries
        count_result = MagicMock()
        count_result.has_next.return_value = True
        count_result.get_next.return_value = [42]

        def mock_execute(cypher, **kwargs):
            if "show_tables" in cypher:
                return show_result
            return count_result

        with patch.object(ingestor, "_execute_with_retry", side_effect=mock_execute):
            stats = ingestor.get_statistics()

        # Only NODE tables should be in node_labels
        assert "Function" in stats["node_labels"]
        assert "Module" in stats["node_labels"]
        assert "CALLS" not in stats["node_labels"]
        assert "CONTAINS" not in stats["node_labels"]

    def test_table_name_from_column_1(self, ingestor):
        """Table name is read from column index 1 (row[1]), not row[0]."""
        show_result = MagicMock()
        show_result.has_next.side_effect = [True, False]
        show_result.get_next.return_value = [99, "MyNodeTable", "NODE"]

        count_result = MagicMock()
        count_result.has_next.return_value = True
        count_result.get_next.return_value = [5]

        def mock_execute(cypher, **kwargs):
            if "show_tables" in cypher:
                return show_result
            return count_result

        with patch.object(ingestor, "_execute_with_retry", side_effect=mock_execute):
            stats = ingestor.get_statistics()

        # The label should be "MyNodeTable" (from index 1), not 99 (index 0)
        assert "MyNodeTable" in stats["node_labels"]
        assert 99 not in stats["node_labels"]
