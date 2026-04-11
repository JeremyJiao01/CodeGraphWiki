"""Encoding utilities for reading source files with automatic fallback.

The canonical implementation lives in terrain.foundation.types.encoding (L0).
This module re-exports everything for backward compatibility.
"""

from terrain.foundation.types.encoding import (
    normalize_to_utf8_bytes,
    read_source_file,
    read_source_lines,
    smart_decode,
)

__all__ = [
    "normalize_to_utf8_bytes",
    "read_source_file",
    "read_source_lines",
    "smart_decode",
]
