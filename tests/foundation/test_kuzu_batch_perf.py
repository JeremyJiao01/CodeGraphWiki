"""Tests for Kuzu batch insert via UNWIND parameterized queries.

Covers:
- flush_nodes must use UNWIND $batch instead of per-node string-concatenated MERGE
- flush_relationships must use UNWIND $batch instead of per-relationship MERGE
- _value_to_cypher is no longer called in the write path
- Special characters (quotes, newlines, backslashes) handled correctly via parameterization
- Empty buffers are no-ops
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from terrain.foundation.services.kuzu_service import KuzuIngestor


@pytest.fixture
def db_path(tmp_path):
    """Provide a temporary database path."""
    return tmp_path / "test_batch.db"


@pytest.fixture
def ingestor(db_path):
    """Create a real KuzuIngestor connected to a temp database."""
    ing = KuzuIngestor(db_path, batch_size=1000)
    with ing:
        yield ing


class TestBatchNodeInsert:
    """flush_nodes must use UNWIND parameterized queries, not per-node MERGE."""

    def test_batch_insert_multiple_nodes(self, ingestor):
        """Inserting multiple nodes should produce correct data in DB."""
        for i in range(50):
            ingestor.ensure_node_batch("Function", {
                "qualified_name": f"mod.func_{i}",
                "name": f"func_{i}",
                "path": f"/src/file_{i % 10}.py",
                "start_line": i * 10,
                "end_line": i * 10 + 5,
                "docstring": f"Docstring for func {i}",
                "return_type": "int",
                "signature": f"def func_{i}(x: int) -> int",
                "visibility": "public",
                "parameters": ["x: int"],
                "kind": "function",
            })
        ingestor.flush_nodes()

        rows = ingestor.query("MATCH (f:Function) RETURN count(f) AS cnt")
        assert rows[0]["cnt"] == 50

    def test_batch_insert_special_characters(self, ingestor):
        """Nodes with quotes, newlines, backslashes, tabs must insert correctly."""
        ingestor.ensure_node_batch("Function", {
            "qualified_name": "mod.func_special",
            "name": "func_special",
            "path": "C:\\Users\\test\\src\\file.py",
            "start_line": 1,
            "end_line": 10,
            "docstring": "Line1\nLine2\twith\ttabs\nand 'quotes' and \"double\"",
            "return_type": "str",
            "signature": "def func_special(s: str = 'default') -> str",
            "visibility": "public",
            "parameters": ["s: str = 'default'"],
            "kind": "function",
        })
        ingestor.flush_nodes()

        rows = ingestor.query(
            "MATCH (f:Function {qualified_name: $qn}) RETURN f.docstring AS doc, f.path AS path",
            {"qn": "mod.func_special"},
        )
        assert len(rows) == 1
        assert "Line1\nLine2" in rows[0]["doc"]
        assert "quotes" in rows[0]["doc"]
        assert "Users" in rows[0]["path"]

    def test_batch_merge_updates_existing(self, ingestor):
        """MERGE should update existing nodes, not create duplicates."""
        # Insert first version
        ingestor.ensure_node_batch("Function", {
            "qualified_name": "mod.func_update",
            "name": "func_v1",
            "path": "/src/old.py",
            "start_line": 1,
            "end_line": 5,
        })
        ingestor.flush_nodes()

        # Insert second version with same qualified_name
        ingestor.ensure_node_batch("Function", {
            "qualified_name": "mod.func_update",
            "name": "func_v2",
            "path": "/src/new.py",
            "start_line": 10,
            "end_line": 20,
        })
        ingestor.flush_nodes()

        rows = ingestor.query(
            "MATCH (f:Function {qualified_name: $qn}) RETURN f.name AS name, f.path AS path",
            {"qn": "mod.func_update"},
        )
        assert len(rows) == 1, "MERGE should not create duplicates"
        assert rows[0]["name"] == "func_v2"
        assert rows[0]["path"] == "/src/new.py"

    def test_batch_insert_empty_buffer_is_noop(self, ingestor):
        """Flushing an empty buffer should not error."""
        ingestor.flush_nodes()  # Should not raise

    def test_batch_insert_multiple_labels(self, ingestor):
        """Nodes of different labels should be batched separately and inserted correctly."""
        ingestor.ensure_node_batch("Function", {
            "qualified_name": "mod.func_a",
            "name": "func_a",
            "path": "/src/a.py",
            "start_line": 1,
            "end_line": 5,
        })
        ingestor.ensure_node_batch("Module", {
            "qualified_name": "mod",
            "name": "mod",
            "path": "/src/",
            "start_line": 0,
            "end_line": 100,
        })
        ingestor.flush_nodes()

        func_rows = ingestor.query("MATCH (f:Function) RETURN count(f) AS cnt")
        mod_rows = ingestor.query("MATCH (m:Module) RETURN count(m) AS cnt")
        assert func_rows[0]["cnt"] == 1
        assert mod_rows[0]["cnt"] == 1

    def test_no_value_to_cypher_in_write_path(self, ingestor):
        """_value_to_cypher should NOT be called during flush_nodes.
        The write path must use parameterized queries exclusively."""
        from unittest.mock import patch

        ingestor.ensure_node_batch("Function", {
            "qualified_name": "mod.func_check",
            "name": "func_check",
            "path": "/src/check.py",
            "start_line": 1,
            "end_line": 5,
        })

        with patch.object(ingestor, "_value_to_cypher", wraps=ingestor._value_to_cypher) as spy:
            ingestor.flush_nodes()
            assert spy.call_count == 0, (
                f"_value_to_cypher was called {spy.call_count} times during flush_nodes — "
                "write path should use parameterized queries, not string concatenation"
            )


class TestBatchRelationshipInsert:
    """flush_relationships must use UNWIND parameterized queries."""

    def test_batch_insert_relationships(self, ingestor):
        """Inserting relationships via UNWIND should produce correct edges."""
        # First create nodes
        for i in range(10):
            ingestor.ensure_node_batch("Function", {
                "qualified_name": f"mod.func_{i}",
                "name": f"func_{i}",
                "path": "/src/test.py",
                "start_line": i,
                "end_line": i + 1,
            })
        ingestor.flush_nodes()

        # Create call relationships: func_0 -> func_1, func_1 -> func_2, ...
        for i in range(9):
            ingestor.ensure_relationship_batch(
                ("Function", "qualified_name", f"mod.func_{i}"),
                "CALLS",
                ("Function", "qualified_name", f"mod.func_{i+1}"),
            )
        ingestor.flush_relationships()

        rows = ingestor.query("MATCH ()-[r:CALLS]->() RETURN count(r) AS cnt")
        assert rows[0]["cnt"] == 9

    def test_batch_relationship_deduplication(self, ingestor):
        """Duplicate relationships in the same buffer should be deduplicated."""
        # Create two nodes
        for name in ["caller", "callee"]:
            ingestor.ensure_node_batch("Function", {
                "qualified_name": f"mod.{name}",
                "name": name,
                "path": "/src/test.py",
                "start_line": 1,
                "end_line": 5,
            })
        ingestor.flush_nodes()

        # Add same relationship twice
        for _ in range(2):
            ingestor.ensure_relationship_batch(
                ("Function", "qualified_name", "mod.caller"),
                "CALLS",
                ("Function", "qualified_name", "mod.callee"),
            )
        ingestor.flush_relationships()

        rows = ingestor.query("MATCH ()-[r:CALLS]->() RETURN count(r) AS cnt")
        assert rows[0]["cnt"] == 1, "Duplicate relationships should be deduplicated"

    def test_no_value_to_cypher_in_relationship_write(self, ingestor):
        """_value_to_cypher should NOT be called during flush_relationships."""
        from unittest.mock import patch

        # Create nodes first
        for name in ["src", "dst"]:
            ingestor.ensure_node_batch("Function", {
                "qualified_name": f"mod.{name}",
                "name": name,
                "path": "/src/test.py",
                "start_line": 1,
                "end_line": 5,
            })
        ingestor.flush_nodes()

        ingestor.ensure_relationship_batch(
            ("Function", "qualified_name", "mod.src"),
            "CALLS",
            ("Function", "qualified_name", "mod.dst"),
        )

        with patch.object(ingestor, "_value_to_cypher", wraps=ingestor._value_to_cypher) as spy:
            ingestor.flush_relationships()
            assert spy.call_count == 0, (
                f"_value_to_cypher was called {spy.call_count} times during flush_relationships — "
                "write path should use parameterized queries, not string concatenation"
            )

    def test_batch_relationship_empty_buffer_is_noop(self, ingestor):
        """Flushing an empty relationship buffer should not error."""
        ingestor.flush_relationships()  # Should not raise
