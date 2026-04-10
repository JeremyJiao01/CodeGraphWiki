"""Regression tests for pickle backward compatibility.

Covers:
- c677270: _CompatUnpickler remaps old module paths after harness refactor
"""

from __future__ import annotations

import io
import pickle

import pytest

from terrain.entrypoints.mcp.tools import _CompatUnpickler


class TestCompatUnpickler:
    """_CompatUnpickler must redirect old module paths to new ones so that
    vectors.pkl files created by pre-0.30 versions can still be loaded."""

    def test_renames_table_not_empty(self):
        """Sanity: the renames table has entries."""
        assert len(_CompatUnpickler._RENAMES) >= 6

    def test_old_embeddings_path_redirected(self):
        """Old 'terrain.embeddings.vector_store' -> new path."""
        unpickler = _CompatUnpickler(io.BytesIO(b""))
        new_mod, new_name = "terrain.domains.core.embedding.vector_store", "MemoryVectorStore"

        # find_class should resolve without error
        cls = unpickler.find_class(
            "terrain.embeddings.vector_store", "MemoryVectorStore"
        )
        from terrain.domains.core.embedding.vector_store import MemoryVectorStore
        assert cls is MemoryVectorStore

    def test_old_embedding_without_s_redirected(self):
        """Even older path without 's' is also redirected."""
        unpickler = _CompatUnpickler(io.BytesIO(b""))
        cls = unpickler.find_class(
            "terrain.embedding.vector_store", "MemoryVectorStore"
        )
        from terrain.domains.core.embedding.vector_store import MemoryVectorStore
        assert cls is MemoryVectorStore

    def test_old_vector_record_redirected(self):
        """VectorRecord from old path resolves correctly."""
        unpickler = _CompatUnpickler(io.BytesIO(b""))
        cls = unpickler.find_class(
            "terrain.embeddings.vector_store", "VectorRecord"
        )
        from terrain.domains.core.embedding.vector_store import VectorRecord
        assert cls is VectorRecord

    def test_old_semantic_search_redirected(self):
        """Old tools.semantic_search path resolves to domains.core.search."""
        unpickler = _CompatUnpickler(io.BytesIO(b""))
        cls = unpickler.find_class(
            "terrain.tools.semantic_search", "SemanticSearchService"
        )
        from terrain.domains.core.search.semantic_search import SemanticSearchService
        assert cls is SemanticSearchService

    def test_unknown_module_passes_through(self):
        """Modules not in _RENAMES are handled normally by pickle."""
        unpickler = _CompatUnpickler(io.BytesIO(b""))
        cls = unpickler.find_class("builtins", "list")
        assert cls is list

    def test_round_trip_with_compat_unpickler(self):
        """Pickle round-trip: serialize with new path, load with _CompatUnpickler."""
        from terrain.domains.core.embedding.vector_store import VectorRecord

        record = VectorRecord(
            node_id="test_id",
            qualified_name="test.func",
            embedding=[0.1, 0.2, 0.3],
            metadata={"lang": "python"},
        )

        buf = io.BytesIO()
        pickle.dump(record, buf)
        buf.seek(0)

        loaded = _CompatUnpickler(buf).load()
        assert loaded.node_id == "test_id"
        assert loaded.qualified_name == "test.func"
        assert loaded.embedding == [0.1, 0.2, 0.3]
