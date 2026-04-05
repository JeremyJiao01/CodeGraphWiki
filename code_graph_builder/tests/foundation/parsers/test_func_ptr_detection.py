"""Tests for C/C++ function pointer detection."""
from __future__ import annotations

from unittest.mock import MagicMock

from code_graph_builder.foundation.parsers.call_resolver import CallResolver


def _make_resolver() -> CallResolver:
    registry = MagicMock()
    registry.__contains__ = MagicMock(return_value=False)
    import_processor = MagicMock()
    import_processor.get_import_mapping.return_value = {}
    return CallResolver(function_registry=registry, import_processor=import_processor)


def test_register_and_resolve_func_ptr():
    resolver = _make_resolver()
    resolver.register_func_ptr("on_error", "project.pkg.handle_error")
    assert resolver.resolve_func_ptr_call("on_error") == "project.pkg.handle_error"


def test_resolve_func_ptr_call_unknown():
    resolver = _make_resolver()
    assert resolver.resolve_func_ptr_call("unknown_field") is None


def test_resolve_call_fallback_to_func_ptr():
    """When normal resolution fails, obj.field should resolve via func_ptr_map."""
    registry = MagicMock()
    registry.__contains__ = MagicMock(return_value=False)
    registry._entries = {}
    import_processor = MagicMock()
    import_processor.get_import_mapping.return_value = {}

    resolver = CallResolver(function_registry=registry, import_processor=import_processor)
    resolver.register_func_ptr("callback", "project.src.process_data")

    result = resolver.resolve_call("config.callback", "project.src.main")
    assert result == "project.src.process_data"
