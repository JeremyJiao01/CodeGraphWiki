"""Regression tests for C function ingestion error resilience.

Covers:
- 7be31d6: A single bad function in a C file must not skip the entire file's
  functions. typedef/macro failures are isolated from function ingestion.
- process_file catches top-level exceptions and returns None gracefully.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from code_graph_builder.foundation.parsers.definition_processor import DefinitionProcessor
from code_graph_builder.foundation.types import constants as cs


def _make_processor():
    """Create a DefinitionProcessor with all dependencies mocked."""
    processor = DefinitionProcessor.__new__(DefinitionProcessor)
    processor.repo_path = Path("/fake/repo")
    processor.project_name = "test_project"
    processor.module_qn_to_file_path = {}
    processor.ingestor = MagicMock()
    processor.import_processor = MagicMock()
    return processor


def _make_mock_file(file_path_str: str = "/fake/repo/test.c"):
    """Create a mock Path that has read_bytes returning valid C source."""
    mock_file = MagicMock(spec=Path)
    mock_file.read_bytes.return_value = b"int main() { return 0; }"
    mock_file.relative_to.return_value = Path("test.c")
    mock_file.name = "test.c"
    mock_file.suffix = ".c"
    mock_file.__str__ = lambda self: file_path_str
    mock_file.__fspath__ = lambda self: file_path_str
    return mock_file


class TestCIngestionIsolation:
    """Individual function/typedef/macro failures must not block
    the rest of the file's ingestion."""

    @patch("code_graph_builder.foundation.parsers.definition_processor.normalize_to_utf8_bytes",
           return_value=b"int main() { return 0; }")
    def test_typedef_failure_does_not_block_functions(self, mock_normalize):
        """If _ingest_c_typedefs raises, functions are still ingested."""
        processor = _make_processor()
        mock_file = _make_mock_file()

        mock_root = MagicMock()
        mock_root.has_error = False
        mock_root.children = []

        mock_tree = MagicMock()
        mock_tree.root_node = mock_root

        mock_parser = MagicMock()
        mock_parser.parse.return_value = mock_tree

        queries = {cs.SupportedLanguage.C: {
            "parser": mock_parser,
            "functions": MagicMock(),
            "config": {},
        }}

        with patch.object(processor, "_create_module_node"), \
             patch.object(processor, "_create_module_relationships"), \
             patch.object(processor, "_ingest_functions") as mock_funcs, \
             patch.object(processor, "_ingest_classes"), \
             patch.object(processor, "_ingest_c_typedefs", side_effect=Exception("GBK decode error")), \
             patch.object(processor, "_ingest_c_macros"):

            result = processor.process_file(mock_file, cs.SupportedLanguage.C, queries, {})

            mock_funcs.assert_called_once()
            assert result is not None

    @patch("code_graph_builder.foundation.parsers.definition_processor.normalize_to_utf8_bytes",
           return_value=b"int main() { return 0; }")
    def test_macro_failure_does_not_block_functions(self, mock_normalize):
        """If _ingest_c_macros raises, the overall result is still returned."""
        processor = _make_processor()
        mock_file = _make_mock_file()

        mock_root = MagicMock()
        mock_root.has_error = False
        mock_root.children = []

        mock_tree = MagicMock()
        mock_tree.root_node = mock_root

        mock_parser = MagicMock()
        mock_parser.parse.return_value = mock_tree

        queries = {cs.SupportedLanguage.C: {
            "parser": mock_parser,
            "functions": MagicMock(),
            "config": {},
        }}

        with patch.object(processor, "_create_module_node"), \
             patch.object(processor, "_create_module_relationships"), \
             patch.object(processor, "_ingest_functions"), \
             patch.object(processor, "_ingest_classes"), \
             patch.object(processor, "_ingest_c_typedefs"), \
             patch.object(processor, "_ingest_c_macros", side_effect=RuntimeError("bad macro")):

            result = processor.process_file(mock_file, cs.SupportedLanguage.C, queries, {})

            assert result is not None

    def test_process_file_returns_none_on_total_failure(self):
        """If the entire process_file fails (e.g. can't read file), return None."""
        processor = _make_processor()

        mock_file = _make_mock_file()
        mock_file.read_bytes.side_effect = OSError("file not found")

        queries = {cs.SupportedLanguage.C: {"parser": MagicMock()}}

        result = processor.process_file(mock_file, cs.SupportedLanguage.C, queries, {})

        assert result is None
