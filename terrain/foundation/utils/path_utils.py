"""Path utilities for code graph builder.

The canonical implementation lives in terrain.foundation.types.path_utils (L0).
This module re-exports it for backward compatibility.
"""

from terrain.foundation.types.path_utils import should_skip_path

__all__ = ["should_skip_path"]
